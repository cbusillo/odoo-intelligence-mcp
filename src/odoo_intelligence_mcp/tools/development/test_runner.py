import random
import re
from typing import Any

from ...core.env import load_env_config
from ...core.utils import PaginationParams, paginate_dict_list
from ...utils.docker_utils import DockerClientManager


async def run_tests(
    module: str,
    test_class: str | None = None,
    test_method: str | None = None,
    test_tags: str | None = None,
    pagination: PaginationParams | None = None,
) -> dict[str, Any]:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        container_name = config["script_runner_container"]

        # Get container
        container_result = docker_manager.get_container(container_name)
        if isinstance(container_result, dict):
            # Add helpful hint to the error response
            if "not found" in str(container_result.get("error", "")).lower():
                container_result["hint"] = (
                    "Use the 'odoo_restart' tool to restart services, or run 'docker compose up -d script-runner' to start the script-runner service"
                )
            return container_result

        container = container_result

        # Build test target specification
        test_target = module
        if test_class and test_method:
            test_target = f"{module}.{test_class}.{test_method}"
        elif test_class:
            test_target = f"{module}.{test_class}"

        # Use a random port to avoid conflicts
        # Odoo typically uses 8069-8072, so we'll use a higher range
        http_port = random.randint(9000, 9999)

        # Build command to run tests
        database = config["database"]
        cmd = [
            "/odoo/odoo-bin",
            f"--database={database}",
            "--addons-path=/volumes/addons,/odoo/addons,/volumes/enterprise",
            f"--http-port={http_port}",  # Use random port to avoid conflicts
            "--stop-after-init",
            "--test-enable",
            "-i",
            module,
        ]

        # Add test tags if specified
        if test_tags:
            cmd.extend(["--test-tags", test_tags])

        # Execute command in container
        exec_result = container.exec_run(
            cmd,
            stdout=True,
            stderr=True,
            demux=True,
        )

        exit_code = exec_result.exit_code
        stdout, stderr = exec_result.output

        # Decode output
        stdout_str = stdout.decode("utf-8") if stdout else ""
        stderr_str = stderr.decode("utf-8") if stderr else ""

        # Combine output
        output = stdout_str + "\n" + stderr_str

        # Extract test results from output
        test_results = {
            "tests_run": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
        }

        # Look for test summary patterns
        ran_pattern = r"Ran (\d+) tests? in"
        ran_match = re.search(ran_pattern, output)
        if ran_match:
            test_results["tests_run"] = int(ran_match.group(1))

        # Look for OK or FAILED patterns
        if "OK" in output and "FAILED" not in output:
            test_results["passed"] = test_results["tests_run"]
            test_status = "passed"
        else:
            # Parse failure details
            failed_pattern = r"FAILED \((?:failures=(\d+))?(?:,\s*)?(?:errors=(\d+))?(?:,\s*)?(?:skipped=(\d+))?\)"
            failed_match = re.search(failed_pattern, output)
            if failed_match:
                test_results["failed"] = int(failed_match.group(1) or 0)
                test_results["errors"] = int(failed_match.group(2) or 0)
                test_results["skipped"] = int(failed_match.group(3) or 0)
                test_results["passed"] = test_results["tests_run"] - test_results["failed"] - test_results["errors"]
                test_status = "failed"
            else:
                test_status = "unknown"

        # Extract individual test failures if any
        failures = []
        failure_pattern = r"FAIL: (test_\w+) \(([^)]+)\)"
        for match in re.finditer(failure_pattern, output):
            failures.append(
                {
                    "test_method": match.group(1),
                    "test_class": match.group(2),
                }
            )

        # Check if module was installed successfully
        module_installed = "Module" not in output or "not found" not in output

        # Handle pagination for output
        if pagination is None:
            pagination = PaginationParams()
        # Split output into lines for pagination
        output_lines = output.splitlines()
        # Create items for pagination - group lines into chunks
        chunk_size = 50  # Lines per item
        output_items = []
        for i in range(0, len(output_lines), chunk_size):
            chunk_lines = output_lines[i : i + chunk_size]
            output_items.append(
                {"line_start": i + 1, "line_end": min(i + chunk_size, len(output_lines)), "content": "\n".join(chunk_lines)}
            )

        paginated_output = paginate_dict_list(output_items, pagination, ["content"])

        return {
            "success": exit_code == 0,
            "module": module,
            "test_class": test_class,
            "test_method": test_method,
            "test_tags": test_tags,
            "test_target": test_target,
            "command": " ".join(cmd),
            "status": test_status,
            "module_installed": module_installed,
            "test_results": test_results,
            "failures": failures,
            "output_lines": len(output_lines),
            "output_chunks": paginated_output.to_dict(),
            "return_code": exit_code,
            "container": container_name,
        }

    except Exception as e:
        if "timeout" in str(e).lower():
            return {
                "success": False,
                "error": "Test execution timed out",
                "error_type": "TimeoutError",
                "module": module,
                "test_class": test_class,
                "test_method": test_method,
                "recommendation": "Try running a smaller subset of tests or increase timeout",
            }
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "module": module,
            "test_class": test_class,
            "test_method": test_method,
        }
