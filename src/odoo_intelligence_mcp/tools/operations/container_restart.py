
from ...core.env import load_env_config
from ...utils.docker_utils import DockerClientManager
from ...utils.response_utils import ResponseBuilder


async def odoo_restart(services: str = "web-1,shell-1,script-runner-1") -> dict:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        container_prefix = config.container_prefix
        
        # Handle both formats: "web-1" and "odoo-web-1"
        service_list = []
        for s in services.split(","):
            service = s.strip()
            if service.startswith(f"{container_prefix}-"):
                # Already has prefix, use as-is
                service_list.append(service)
            else:
                # Add prefix
                service_list.append(f"{container_prefix}-{service}")
        results = {}

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
