from typing import Any

from ...core.env import load_env_config
from ...utils.docker_utils import DockerClientManager
from ...utils.response_utils import ResponseBuilder


async def odoo_status(verbose: bool = False) -> dict[str, Any]:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        containers = [
            config.web_container,
            config.script_runner_container,
        ]
        database_container = getattr(config, "database_container", None)
        if database_container:
            containers.append(database_container)
        status = {}

        # Test Docker connection first by trying to run docker version
        import subprocess

        try:
            result = subprocess.run(["docker", "version"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return ResponseBuilder.error(
                    "Docker daemon is not available. Please ensure Docker is running.",
                    "DockerConnectionError",
                    details=result.stderr,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return ResponseBuilder.error(
                "Docker daemon is not available. Please ensure Docker is running.", "DockerConnectionError", details=str(e)
            )

        for container_name in containers:
            # Auto-start containers that should be running
            container_result = docker_manager.get_container(container_name, auto_start=True)

            if not container_result.get("success"):
                status[container_name] = {"status": "not_found", "running": False}
                continue

            state = container_result.get("state", {})
            state_data = state if isinstance(state, dict) else {}
            container_status = state_data.get("Status", "unknown")

            container_info = {
                "status": container_status,
                "running": container_status == "running",
            }

            resolved_name = container_result.get("container")
            if resolved_name and resolved_name != container_name:
                container_info["resolved_container"] = resolved_name

            if verbose:
                config_data = state_data.get("Config")
                image_name = "unknown"
                if isinstance(config_data, dict):
                    image_name = config_data.get("Image", "unknown")
                verbose_info = {
                    "state": state_data,
                    "id": state_data.get("Id", "unknown")[:12] if state_data.get("Id") else "unknown",
                    "created": state_data.get("Created", "unknown"),
                    "image": image_name,
                }

                container_info.update(verbose_info)

            status[container_name] = container_info

        all_running = all(c.get("running", False) for c in status.values())

        return ResponseBuilder.success(
            overall_status="healthy" if all_running else "unhealthy",
            containers=status,
            total_containers=len(containers),
            running_containers=sum(1 for c in status.values() if c.get("running", False)),
        )

    except Exception as e:
        return ResponseBuilder.from_exception(e)
