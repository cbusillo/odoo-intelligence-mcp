from typing import Any

import docker
from docker.errors import APIError, NotFound


async def odoo_update_module(modules: str, force_install: bool = False) -> dict[str, Any]:
    try:
        client = docker.from_env()
        container_name = "odoo-opw-script-runner-1"
        module_list = [m.strip() for m in modules.split(",")]

        # Build command
        cmd = [
            "/odoo/odoo-bin",
            "--database=opw",
            "--addons-path=/volumes/addons,/odoo/addons,/volumes/enterprise",
            "--stop-after-init",
        ]

        if force_install:
            cmd.extend(["-i", ",".join(module_list)])
        else:
            cmd.extend(["-u", ",".join(module_list)])

        # Execute command in container
        try:
            container = client.containers.get(container_name)
            exec_result = container.exec_run(cmd, demux=True)

            stdout = exec_result.output[0].decode("utf-8") if exec_result.output[0] else ""
            stderr = exec_result.output[1].decode("utf-8") if exec_result.output[1] else ""

            return {
                "success": exec_result.exit_code == 0,
                "modules": module_list,
                "operation": "install" if force_install else "update",
                "exit_code": exec_result.exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "command": " ".join(cmd),
            }

        except NotFound:
            return {
                "success": False, 
                "error": f"Container '{container_name}' not found", 
                "modules": modules,
                "hint": "Use the 'odoo_restart' tool to restart services, or run 'docker compose up -d script-runner' to start the script-runner service"
            }
        except APIError as e:
            return {"success": False, "error": f"Docker API error: {e}", "modules": modules}

    except Exception as e:
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "modules": modules}


async def odoo_install_module(modules: str) -> dict[str, Any]:
    # Reuse the update function with force_install=True
    return await odoo_update_module(modules, force_install=True)
