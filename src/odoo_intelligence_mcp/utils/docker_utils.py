from typing import Any

import docker
from docker.errors import APIError, NotFound
from docker.models.containers import Container


class DockerClientManager:
    def __init__(self) -> None:
        self.client = docker.from_env()

    def get_container(self, container_name: str) -> Container | dict[str, Any]:
        try:
            return self.client.containers.get(container_name)
        except NotFound:
            return DockerClientManager._create_error_response(f"Container '{container_name}' not found", "NotFound", container_name)
        except APIError as e:
            return DockerClientManager._create_error_response(f"Docker API error: {e}", "APIError", container_name)
        except Exception as e:
            return DockerClientManager._create_error_response(str(e), type(e).__name__, container_name)

    def handle_container_operation(self, container_name: str, operation_name: str, operation_func: Any) -> dict[str, Any]:
        container_result = self.get_container(container_name)
        if isinstance(container_result, dict):
            return container_result

        try:
            result = operation_func(container_result)
            return DockerClientManager._create_success_response(operation_name, container_name, result)
        except APIError as e:
            return DockerClientManager._create_error_response(
                f"Docker API error during {operation_name}: {e}", "APIError", container_name
            )
        except Exception as e:
            return DockerClientManager._create_error_response(
                f"Error during {operation_name}: {e!s}", type(e).__name__, container_name
            )

    @staticmethod
    def _create_error_response(error_message: str, error_type: str, container: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": error_message,
            "error_type": error_type,
            "container": container,
        }

    @staticmethod
    def _create_success_response(operation: str, container: str, data: Any = None) -> dict[str, Any]:
        response = {
            "success": True,
            "operation": operation,
            "container": container,
        }
        if data is not None:
            response["data"] = data
        return response
