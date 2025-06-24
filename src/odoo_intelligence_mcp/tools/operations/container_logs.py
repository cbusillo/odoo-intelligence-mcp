from typing import Any

from ...utils.docker_utils import DockerClientManager


async def odoo_logs(container: str = "odoo-opw-web-1", lines: int = 100) -> dict[str, Any]:
    docker_manager = DockerClientManager()

    def get_logs(container_obj: Any) -> dict[str, Any]:
        logs = container_obj.logs(tail=lines)
        log_text = logs.decode() if isinstance(logs, bytes) else logs

        return {
            "container": container,
            "lines_requested": lines,
            "logs": log_text,
            "status": container_obj.status,
        }

    return docker_manager.handle_container_operation(container, "get_logs", get_logs)
