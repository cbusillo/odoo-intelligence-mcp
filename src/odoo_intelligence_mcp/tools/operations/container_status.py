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
            config.shell_container,
            config.script_runner_container,
        ]
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
            else:
                # Get the container state from the result
                state = container_result.get("state", {})
                container_status = state.get("Status", "unknown")

                container_info = {
                    "status": container_status,
                    "running": container_status == "running",
                }

                if verbose:
                    verbose_info = {
                        "state": state,
                        "id": state.get("Id", "unknown")[:12] if state.get("Id") else "unknown",
                        "created": state.get("Created", "unknown"),
                    }

                    # Try to get image info
                    verbose_info["image"] = state.get("Config", {}).get("Image", "unknown") if isinstance(state, dict) else "unknown"

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
