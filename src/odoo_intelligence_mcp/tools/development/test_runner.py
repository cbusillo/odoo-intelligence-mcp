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
    max_output_lines: int = 1000,
) -> dict[str, Any]:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        container_name = config.script_runner_container

        # Check if container exists and is running
        container_result = docker_manager.get_container(container_name)
        if not container_result.get("success", False):
            # Add helpful hint to the error response
            if "not found" in str(container_result.get("error", "")).lower():
                container_result["hint"] = (
                    "Use the 'odoo_restart' tool to restart services, "
                    "or run 'docker compose up -d script-runner' to start the script-runner service"
                )
            return container_result

        # Build test target specification
        test_target = module
        if test_class and test_method:
            test_target = f"{module}.{test_class}.{test_method}"
        elif test_class:
            test_target = f"{module}.{test_class}"

        # Use a random port to avoid conflicts
        # Odoo typically uses 8069-8072, so we'll use a higher range
        http_port = random.randint(9000, 9999)  # noqa: S311 - Not used for security purposes

        # Build command to run tests
        database = config.db_name
        addons_path = config.addons_path

        # Use different approach based on module status
        # For existing modules, skip install/update to avoid conflicts
        cmd = [
            "/odoo/odoo-bin",
            f"--database={database}",
            f"--addons-path={addons_path}",
            f"--http-port={http_port}",  # Use random port to avoid conflicts
            "--stop-after-init",
            "--test-enable",
            "--without-demo=all",  # Avoid demo data conflicts
        ]

        # Add module with appropriate operation
        cmd.extend(["-u", module])

        # Add test tags if specified
        if test_tags:
            cmd.extend(["--test-tags", test_tags])

        # Execute command in container
        exec_result = docker_manager.exec_run(container_name, cmd)

        if not exec_result.get("success", False):
            return exec_result

        exit_code = exec_result.get("exit_code", 1)
        stdout = exec_result.get("stdout", "")
        stderr = exec_result.get("stderr", "")

        # Output is already strings from exec_run
        stdout_str = stdout if stdout else ""
        stderr_str = stderr if stderr else ""

        # Combine output
        output = stdout_str + "\n" + stderr_str

        # Filter out verbose Odoo initialization messages to reduce token count
        output = _filter_output(output, max_output_lines)

        # Extract test results from output
        test_results, test_status = _parse_test_results(output)

        # Extract individual test failures if any
        failures = _extract_test_failures(output)

        # Check if module was installed successfully
        module_installed = "Module" not in output or "not found" not in output

        # Handle pagination for output
        if pagination is None:
            pagination = PaginationParams(page_size=20)  # Limit default page size
        # Split output into lines for pagination
        output_lines = output.splitlines()
        # Create items for pagination - group lines into chunks
        chunk_size = 25  # Reduced lines per item to control token usage
        output_items = []
        for i in range(0, len(output_lines), chunk_size):
            chunk_lines = output_lines[i : i + chunk_size]
            output_items.append(
                {"line_start": i + 1, "line_end": min(i + chunk_size, len(output_lines)), "content": "\n".join(chunk_lines)}
            )

        paginated_output = paginate_dict_list(output_items, pagination, ["content"])

        result_dict = {
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

        # Add error field when tests fail for consistency with other tools
        if exit_code != 0:
            # Check for specific database errors
            if "unique constraint" in output.lower() or "constraint violation" in output.lower():
                result_dict["error"] = (
                    "Database constraint violation detected. Try using '--test-tags' to run specific tests or clean test data."
                )
                result_dict["error_type"] = "DatabaseConstraintError"
                result_dict["recommendation"] = "Consider running tests with specific tags or on a clean test database"
            elif "lock timeout" in output.lower() or "could not obtain lock" in output.lower():
                result_dict["error"] = "Database lock timeout. The database may be in use by another Odoo instance."
                result_dict["error_type"] = "DatabaseLockError"
                result_dict["recommendation"] = "Stop other Odoo instances or wait for current operations to complete"
            elif "ERROR" in output or "CRITICAL" in output:
                result_dict["error"] = f"Test execution failed with return code {exit_code}. Check output_chunks for details."
                result_dict["error_type"] = "TestExecutionError"
            else:
                result_dict["error"] = f"Tests failed with return code {exit_code}"
                result_dict["error_type"] = "TestExecutionError"

        return result_dict

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


def _filter_output(output: str, max_lines: int = 1000) -> str:
    lines = output.splitlines()
    filtered_lines = []
    important_patterns = [
        r"^(FAIL|ERROR|OK):",
        r"^Ran \d+ tests?",
        r"^={70,}",  # Test separators
        r"^-{70,}",  # Test separators
        r"test_\w+",  # Test names
        r"AssertionError",
        r"Traceback",
        r"^  File",  # Stack traces
        r"FAILED \(",
        r"WARNING:",
        r"ERROR:",
        r"CRITICAL:",
    ]

    skip_patterns = [
        r"^INFO:odoo\.",  # Verbose Odoo logs
        r"^DEBUG:",
        r"loading module",
        r"module .+ loaded",
        r"registry loaded",
        r"^loading translation",
    ]

    skip_mode = False
    kept_lines = 0

    for line in lines:
        if kept_lines >= max_lines:
            filtered_lines.append(f"... Output truncated at {max_lines} lines ...")
            break

        # Check if line should be kept
        should_keep = False
        should_skip = False

        for pattern in important_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                should_keep = True
                skip_mode = False
                break

        if not should_keep:
            for pattern in skip_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    should_skip = True
                    skip_mode = True
                    break

        # Keep line if important or if we're in context of important info
        if should_keep or (not should_skip and not skip_mode and line.strip()):
            filtered_lines.append(line)
            kept_lines += 1
        elif not skip_mode and "test" in line.lower():
            # Keep lines mentioning tests even if not matching patterns
            filtered_lines.append(line)
            kept_lines += 1

    return "\\n".join(filtered_lines)


def _parse_test_results(output: str) -> tuple[dict[str, int], str]:
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

    return test_results, test_status


def _extract_test_failures(output: str) -> list[dict[str, str]]:
    failures = []
    failure_pattern = r"FAIL: (test_\w+) \(([^)]+)\)"
    for match in re.finditer(failure_pattern, output):
        failures.append(
            {
                "test_method": match.group(1),
                "test_class": match.group(2),
            }
        )
    return failures
