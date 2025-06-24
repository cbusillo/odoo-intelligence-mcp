from typing import Any

from ...utils.docker_utils import DockerClientManager
from ...utils.response_utils import ResponseBuilder


async def odoo_restart(services: str = "web-1,shell-1,script-runner-1") -> dict[str, Any]:
    try:
        docker_manager = DockerClientManager()
        service_list = [f"odoo-opw-{s.strip()}" for s in services.split(",")]
        results = {}

        for service_name in service_list:

            def restart_container(container_obj: Any) -> dict[str, Any]:
                container_obj.restart(timeout=60)
                return {"status": container_obj.status}

            result = docker_manager.handle_container_operation(service_name, "restart", restart_container)
            results[service_name] = result

        all_success = all(r.get("success", False) for r in results.values())

        return (
            ResponseBuilder.success(
                services=service_list,
                results=results,
                message="All services restarted successfully" if all_success else "Some services failed to restart",
            )
            if all_success
            else ResponseBuilder.error(
                "Some services failed to restart",
                services=service_list,
                results=results,
            )
        )

    except Exception as e:
        return ResponseBuilder.from_exception(e, services=services)
