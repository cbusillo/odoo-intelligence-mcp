import json
import re
import subprocess
import textwrap
from typing import Any

from ...core.env import load_env_config


async def odoo_update_module(modules: str, force_install: bool = False) -> dict[str, Any]:
    try:
        config = load_env_config()
        container_name = config.script_runner_container
        database = config.db_name

        # Sanitize module names to prevent command injection
        # Only allow alphanumeric, underscore, dash, and dot
        safe_pattern = re.compile(r"^[a-zA-Z0-9_\-.]+$")
        raw_modules = modules.split(",")
        safe_modules = []

        for module in raw_modules:
            module = module.strip()
            if not safe_pattern.match(module):
                return {
                    "success": False,
                    "error": f"Invalid module name: {module}. Only alphanumeric, underscore, dash, and dot are allowed.",
                    "modules": modules,
                }
            safe_modules.append(module)

        modules_str = ",".join(safe_modules)

        # Check if container exists first
        check_cmd = ["docker", "inspect", container_name, "--format", "{{.State.Status}}"]
        check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)

        if check_result.returncode != 0:
            # Container doesn't exist or Docker error
            if "no such container" in check_result.stderr.lower() or "no such object" in check_result.stderr.lower():
                return {
                    "success": False,
                    "error": f"Container '{container_name}' not found",
                    "modules": modules,
                    "hint": "Use the 'odoo_restart' tool to restart services, or run 'docker compose up -d script-runner' to start the script-runner service",
                }
            else:
                return {
                    "success": False,
                    "error": f"Docker error: {check_result.stderr}",
                    "modules": modules,
                }

        # Check container status
        status = check_result.stdout.strip()
        if status != "running":
            return {
                "success": False,
                "error": f"Container '{container_name}' is {status}, not running",
                "modules": modules,
                "hint": "Use the 'odoo_restart' tool to restart the container",
            }

        check_code = textwrap.dedent(
            f"""
            import json
            import odoo.modules.module as module

            modules = {safe_modules!r}
            found = env['ir.module.module'].search([('name', 'in', modules)]).mapped('name')
            missing = sorted(set(modules) - set(found))
            if missing:
                missing = [name for name in missing if not module.get_module_path(name)]
            print(json.dumps({{"missing": missing}}))
            """
        )

        check_cmd = [
            "docker",
            "exec",
            "-i",
            container_name,
            "/odoo/odoo-bin",
            "shell",
            "--database",
            database,
            "--db_host",
            config.db_host,
            "--db_port",
            config.db_port,
            "--no-http",
        ]

        check_result = subprocess.run(check_cmd, input=check_code, capture_output=True, text=True, timeout=60)
        if check_result.returncode != 0:
            return {
                "success": False,
                "error": f"Module existence check failed: {check_result.stderr}",
                "modules": modules,
            }

        check_lines = check_result.stdout.strip().split("\n")
        if check_lines:
            try:
                check_payload = json.loads(check_lines[-1])
            except json.JSONDecodeError:
                check_payload = {}
        else:
            check_payload = {}
        missing = check_payload.get("missing", []) if isinstance(check_payload, dict) else []
        if missing:
            return {
                "success": False,
                "error": f"Modules not found: {', '.join(missing)}",
                "modules": modules,
            }

        # Build the odoo-bin command
        if force_install:
            odoo_cmd = f"/odoo/odoo-bin -d {database} --no-http --stop-after-init -i {modules_str}"
        else:
            odoo_cmd = f"/odoo/odoo-bin -d {database} --no-http --stop-after-init -u {modules_str}"

        # Execute the command in the container
        exec_cmd = ["docker", "exec", container_name, "sh", "-c", odoo_cmd]

        exec_result = subprocess.run(exec_cmd, capture_output=True, text=True, timeout=300)  # 5 minute timeout

        # Parse output for success/failure
        success = exec_result.returncode == 0
        stdout = exec_result.stdout
        stderr = exec_result.stderr

        # Check for common error patterns
        if "error" in stdout.lower() or "error" in stderr.lower():
            success = False
        if "module not found" in stdout.lower() or "module not found" in stderr.lower():
            success = False

        operation = "installed" if force_install else "updated"

        return {
            "success": success,
            "modules": modules_str,
            "operation": operation,
            "message": f"Successfully {operation} modules: {modules_str}" if success else f"Failed to {operation[:-1]} modules",
            "exit_code": exec_result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "command": " ".join(exec_cmd),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Module update timed out after 5 minutes",
            "modules": modules,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "modules": modules,
        }


async def odoo_install_module(modules: str) -> dict[str, Any]:
    # Reuse the update function with force_install=True
    return await odoo_update_module(modules, force_install=True)
