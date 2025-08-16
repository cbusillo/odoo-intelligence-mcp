from typing import Any

from ...core.env import load_env_config
from ...utils.docker_utils import DockerClientManager
from ...utils.response_utils import ResponseBuilder


async def odoo_status(verbose: bool = False) -> dict[str, Any]:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        containers = [
            config["web_container"],
            config["shell_container"],
            config["script_runner_container"],
        ]
        status = {}

        # Test Docker connection first
        try:
            docker_manager.client.ping()
        except Exception as e:
            return ResponseBuilder.error(
                "Docker daemon is not available. Please ensure Docker is running.", "DockerConnectionError", details=str(e)
            )

        for container_name in containers:
            container_result = docker_manager.get_container(container_name)

            if isinstance(container_result, dict):
                status[container_name] = {"status": "not_found", "running": False}
            else:
                container = container_result
                container_info = {
                    "status": container.status,
                    "running": container.status == "running",
                }

                if verbose:
                    verbose_info = {
                        "state": container.attrs["State"],
                        "id": container.short_id,
                        "created": container.attrs["Created"],
                    }

                    try:
                        if container.image.tags:
                            verbose_info["image"] = container.image.tags[0]
                        else:
                            verbose_info["image"] = container.attrs.get("Config", {}).get("Image", "unknown")
                    except Exception:
                        verbose_info["image"] = container.attrs.get("Config", {}).get("Image", "unknown")

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
