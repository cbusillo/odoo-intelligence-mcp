from typing import Any

from ...core.env import load_env_config
from ...utils.docker_utils import DockerClientManager
from ...utils.response_utils import ResponseBuilder


async def odoo_restart(services: str | None = None) -> dict[str, Any]:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        container_prefix = config.container_prefix

        default_services = [
            config.web_container,
            config.shell_container,
            config.script_runner_container,
        ]
        database_container = getattr(config, "database_container", None)
        if database_container:
            default_services.append(database_container)

        if services is None or not services.strip():
            service_list = default_services
        else:
            service_list = []
            for s in services.split(","):
                service = s.strip()
                if not service:
                    continue
                if service.startswith(f"{container_prefix}-"):
                    service_list.append(service)
                else:
                    service_list.append(f"{container_prefix}-{service}")
            if not service_list:
                service_list = default_services
        results: dict[str, Any] = {}

        for service_name in service_list:
            result = docker_manager.restart_container(service_name)
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
