import json
import subprocess
from typing import Any

from ..core.env import build_compose_up_command, load_env_config, resolve_existing_container_name, should_allow_autostart

COMPOSE_TIMEOUT = 600


class DockerClientManager:
    def __init__(self) -> None:
        pass

    def get_container(self, container_name: str, auto_start: bool = False) -> dict[str, Any]:
        try:
            # Check if container exists and get its status
            inspect_cmd = ["docker", "inspect", container_name, "--format", "{{json .}}"]
            result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                stderr_lower = result.stderr.lower()
                missing_container = "no such container" in stderr_lower or "no such object" in stderr_lower
                if missing_container:
                    config = load_env_config()
                    resolved_container = resolve_existing_container_name(config, container_name)
                    if resolved_container and resolved_container != container_name:
                        inspect_cmd = ["docker", "inspect", resolved_container, "--format", "{{json .}}"]
                        result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            container_info = json.loads(result.stdout)
                            return {
                                "success": True,
                                "container": resolved_container,
                                "state": container_info.get("State", {}),
                                "inspect": container_info,
                            }

                if auto_start:
                    success = self._auto_start_container(container_name)
                    if success:
                        result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            container_info = json.loads(result.stdout)
                            return {
                                "success": True,
                                "container": container_name,
                                "state": container_info.get("State", {}),
                                "inspect": container_info,
                            }

                if missing_container:
                    return self._create_error_response(f"Container '{container_name}' not found", "NotFound", container_name)
                return self._create_error_response(f"Docker error: {result.stderr}", "DockerError", container_name)

            # Container exists, parse the JSON output
            container_info = json.loads(result.stdout)
            return {
                "success": True,
                "container": container_name,
                "state": container_info.get("State", {}),
                "inspect": container_info,
            }

        except subprocess.TimeoutExpired:
            return self._create_error_response("Docker command timed out", "TimeoutError", container_name)
        except json.JSONDecodeError as e:
            return self._create_error_response(f"Failed to parse Docker output: {e}", "ParseError", container_name)
        except Exception as e:
            return self._create_error_response(str(e), type(e).__name__, container_name)

    def handle_container_operation(self, container_name: str, operation_name: str, operation_func: Any) -> dict[str, Any]:
        container_result = self.get_container(container_name)
        if not container_result.get("success", False):
            return container_result

        try:
            # For subprocess-based operations, pass container name instead of container object
            result = operation_func(container_name)
            return self._create_success_response(operation_name, container_name, result)
        except Exception as e:
            return self._create_error_response(f"Error during {operation_name}: {e!s}", type(e).__name__, container_name)

    def restart_container(self, container_name: str) -> dict[str, Any]:
        try:
            restart_cmd = ["docker", "restart", container_name]
            result = subprocess.run(restart_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return self._create_success_response("restart", container_name)
            stderr_lower = result.stderr.lower()
            if "no such container" in stderr_lower or "not found" in stderr_lower:
                started = self._auto_start_container(container_name)
                if started:
                    retry_result = subprocess.run(restart_cmd, capture_output=True, text=True, timeout=30)
                    if retry_result.returncode == 0:
                        return self._create_success_response("restart", container_name)
                    container_state = self.get_container(container_name)
                    if container_state.get("success"):
                        data = container_state.get("state", {})
                        return self._create_success_response("restart", container_name, data)
            return self._create_error_response(f"Failed to restart container: {result.stderr}", "RestartError", container_name)
        except subprocess.TimeoutExpired:
            return self._create_error_response("Container restart timed out", "TimeoutError", container_name)
        except Exception as e:
            return self._create_error_response(str(e), type(e).__name__, container_name)

    def get_container_logs(self, container_name: str, tail: int = 100) -> dict[str, Any]:
        try:
            logs_cmd = ["docker", "logs", container_name, "--tail", str(tail)]
            result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return self._create_success_response("logs", container_name, {"stdout": result.stdout, "stderr": result.stderr})
            else:
                return self._create_error_response(f"Failed to get logs: {result.stderr}", "LogsError", container_name)
        except subprocess.TimeoutExpired:
            return self._create_error_response("Getting logs timed out", "TimeoutError", container_name)
        except Exception as e:
            return self._create_error_response(str(e), type(e).__name__, container_name)

    @staticmethod
    def exec_run(container_name: str, cmd: list[str] | str, **kwargs: Any) -> dict[str, Any]:
        try:
            # Build docker exec command
            if isinstance(cmd, str):
                exec_cmd = ["docker", "exec", container_name, "sh", "-c", cmd]
            else:
                exec_cmd = ["docker", "exec", container_name] + cmd

            # Handle optional parameters
            timeout = kwargs.get("timeout", 30)

            result = subprocess.run(exec_cmd, capture_output=True, text=True, timeout=timeout)

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "output": result.stdout + result.stderr if result.returncode != 0 else result.stdout,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "exit_code": -1, "output": "Command timed out", "error": "TimeoutError"}
        except Exception as e:
            return {"success": False, "exit_code": -1, "output": str(e), "error": type(e).__name__}

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

    @staticmethod
    def _auto_start_container(container_name: str) -> bool:
        try:
            config = load_env_config()
            if not should_allow_autostart(config):
                return False
            # First try docker start (for existing stopped containers)
            start_result = subprocess.run(["docker", "start", container_name], capture_output=True, text=True, timeout=10)

            if start_result.returncode == 0:
                return True

            # If container doesn't exist, try docker compose
            if "no such container" in start_result.stderr.lower() or "not found" in start_result.stderr.lower():
                # Extract service name from container name (e.g., "odoo-web-1" -> "web")
                if "-" in container_name:
                    parts = container_name.split("-")
                    if len(parts) >= 3:  # e.g., ["odoo", "web", "1"]
                        service_name = parts[-2]  # Get "web" from "odoo-web-1"

                        # Try to find the compose file directory
                        config = load_env_config()
                        compose_cmd, project_dir = build_compose_up_command(config, [service_name])
                        if project_dir:
                            try:
                                compose_result = subprocess.run(
                                    compose_cmd,
                                    cwd=str(project_dir),
                                    capture_output=True,
                                    text=True,
                                    timeout=COMPOSE_TIMEOUT,
                                )
                                if compose_result.returncode == 0:
                                    return True
                            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                                return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False


# Compatibility exceptions for existing code that might catch these
class NotFound(Exception):
    pass


class APIError(Exception):
    pass
