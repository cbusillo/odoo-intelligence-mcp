from typing import Any
from unittest.mock import MagicMock

from odoo_intelligence_mcp.core.env import EnvConfig, load_env_config


def create_successful_container_mock() -> MagicMock:
    """Create a mock container with successful status."""
    mock_container = MagicMock()
    mock_container.status = "running"
    return mock_container


def create_docker_manager_with_get_container(mock_manager_class: MagicMock) -> MagicMock:
    """Create DockerClientManager mock with get_container method."""
    mock_container = create_successful_container_mock()

    mock_instance = MagicMock()
    mock_instance.get_container.return_value = mock_container

    # Make handle_container_operation use the same container
    def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
        inner_result = func(mock_container)
        return {"success": True, "operation": operation, "container": container_name, "data": inner_result}

    mock_instance.handle_container_operation.side_effect = mock_handle_operation

    mock_manager_class.return_value = mock_instance
    return mock_instance


def get_test_config() -> EnvConfig:
    """Get test configuration from environment - single source of truth."""
    return load_env_config()


def get_expected_container_names() -> dict[str, str | None]:
    """Get expected container names from environment configuration."""
    config = get_test_config()
    return {
        "web": config.web_container,
        "script_runner": config.script_runner_container,
        "database": getattr(config, "database_container", None),
        "container_name": config.container_name,
        "container_prefix": config.container_prefix,
    }
