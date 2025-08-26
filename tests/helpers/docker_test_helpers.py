from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

from odoo_intelligence_mcp.core.env import load_env_config


def create_successful_container_mock() -> MagicMock:
    """Create a mock container with successful status."""
    mock_container = MagicMock()
    mock_container.status = "running"
    return mock_container


def create_mock_handle_operation_success() -> Callable[[str, str, Any], dict[str, Any]]:
    """Create a standard successful mock handle_operation function."""

    def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
        mock_container = create_successful_container_mock()
        func(mock_container)
        return {"success": True, "operation": operation, "container": container_name, "data": {"status": "running"}}

    return mock_handle_operation


def create_mock_handle_operation_with_result() -> Callable[[str, str, Any], dict[str, Any]]:
    """Create mock handle_operation that returns the inner function result."""

    def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
        mock_container = create_successful_container_mock()
        inner_result = func(mock_container)
        return {"success": True, "operation": operation, "container": container_name, "data": inner_result}

    return mock_handle_operation


def setup_docker_manager_mock(mock_manager_class: MagicMock, handle_operation_func: Callable | None = None) -> MagicMock:
    """Set up a complete DockerClientManager mock."""
    mock_instance = MagicMock()
    if handle_operation_func:
        mock_instance.handle_container_operation.side_effect = handle_operation_func
    else:
        mock_instance.handle_container_operation.side_effect = create_mock_handle_operation_success()

    mock_manager_class.return_value = mock_instance
    return mock_instance


def create_docker_manager_with_get_container(mock_manager_class: MagicMock) -> MagicMock:
    """Create DockerClientManager mock with get_container method."""
    mock_container = create_successful_container_mock()

    mock_instance = MagicMock()
    mock_instance.get_container.return_value = mock_container
    mock_instance.handle_container_operation.side_effect = create_mock_handle_operation_with_result()

    mock_manager_class.return_value = mock_instance
    return mock_instance


def get_test_config() -> dict[str, str]:
    """Get test configuration from environment - single source of truth."""
    return load_env_config()


def get_expected_container_names() -> dict[str, str]:
    """Get expected container names from environment configuration."""
    config = get_test_config()
    return {
        "web": config["web_container"],
        "shell": config["shell_container"],
        "script_runner": config["script_runner_container"],
        "container_name": config["container_name"],
    }


def get_expected_database_name() -> str:
    """Get expected database name from environment configuration."""
    return get_test_config()["database"]


def create_mock_handle_operation_with_error_handling() -> Callable[[str, str, Any], dict[str, Any]]:
    """Create mock handle_operation that handles UnicodeDecodeError."""

    def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
        mock_container = create_successful_container_mock()
        try:
            inner_result = func(mock_container)
            return {"success": True, "operation": operation, "container": container_name, "data": inner_result}
        except UnicodeDecodeError as e:
            return {"success": False, "error": str(e), "error_type": "UnicodeDecodeError", "container": container_name}

    return mock_handle_operation


async def run_mcp_server_test(app: Any, read_stream: Any, write_stream: Any, expected_responses: int = 2) -> list[bytes]:
    """Helper to run MCP server test with standard setup/teardown pattern."""
    import asyncio
    import contextlib

    server_task = asyncio.create_task(
        app.run(read_stream, write_stream, None)  # noinspection PyTypeChecker
    )

    await asyncio.sleep(0.2)

    server_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await server_task

    # Validate expected responses
    assert len(write_stream.written) >= expected_responses
    return write_stream.written
