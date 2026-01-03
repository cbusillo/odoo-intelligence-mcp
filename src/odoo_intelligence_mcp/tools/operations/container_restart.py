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
            config.script_runner_container,
        ]
        database_container = getattr(config, "database_container", None)
        if database_container:
            default_services.append(database_container)

        skipped_services: list[str] = []

        if services is None or not services.strip():
            service_list = []
            for service_name in default_services:
                container_result = docker_manager.get_container(service_name)
                if not container_result.get("success"):
                    skipped_services.append(service_name)
                    continue
                resolved_name = container_result.get("container")
                if resolved_name and resolved_name != service_name:
                    skipped_services.append(service_name)
                    continue
                service_list.append(service_name)
        else:
            service_list = []
            for s in services.split(","):
                service = s.strip()
                if not service:
                    continue
                if container_prefix and service.startswith(f"{container_prefix}-"):
                    service_list.append(service)
                elif container_prefix:
                    service_list.append(f"{container_prefix}-{service}")
                else:
                    service_list.append(service)
            if not service_list:
                service_list = default_services
        results: dict[str, Any] = {}
        if not service_list:
            return ResponseBuilder.error(
                "No matching services to restart",
                services=service_list,
                skipped_services=skipped_services,
            )

        for service_name in service_list:
            result = docker_manager.restart_container(service_name)
            results[service_name] = result

        all_success = all(r.get("success", False) for r in results.values())

        response: dict[str, Any]
        if all_success:
            response = ResponseBuilder.success(
                services=service_list,
                results=results,
                message="All services restarted successfully" if all_success else "Some services failed to restart",
            )
        else:
            response = ResponseBuilder.error(
                "Some services failed to restart",
                services=service_list,
                results=results,
            )

        if skipped_services:
            response["skipped_services"] = skipped_services
        return response

    except Exception as e:
        return ResponseBuilder.from_exception(e, services=services)
