from unittest.mock import MagicMock, patch

import pytest
from docker.errors import APIError, DockerException, NotFound

from odoo_intelligence_mcp.utils.docker_utils import DockerClientManager


def test_docker_client_manager_init_success() -> None:
    """Test successful DockerClientManager initialization."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        assert manager.client == mock_client
        mock_docker.assert_called_once()


def test_docker_client_manager_init_failure() -> None:
    """Test DockerClientManager initialization when Docker is not available."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_docker.side_effect = DockerException("Docker not available")

        with pytest.raises(DockerException):
            DockerClientManager()


def test_get_container_success() -> None:
    """Test successful container retrieval."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        result = manager.get_container("test-container")

        assert result == mock_container
        mock_client.containers.get.assert_called_with("test-container")


def test_get_container_not_found() -> None:
    """Test container not found error."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        result = manager.get_container("missing-container")

        assert isinstance(result, dict)
        assert result["success"] is False
        assert "Container 'missing-container' not found" in result["error"]
        assert result["error_type"] == "NotFound"


def test_get_container_api_error() -> None:
    """Test Docker API error handling."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = APIError("API error")
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        result = manager.get_container("test-container")

        assert isinstance(result, dict)
        assert "API error" in result["error"]


def test_handle_container_operation_success() -> None:
    """Test successful container operation."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        # noinspection PyUnusedLocal
        def operation(container: object) -> dict[str, str]:
            return {"result": "success"}

        result = manager.handle_container_operation("test-container", "test_op", operation)

        assert result["success"] is True
        assert result["operation"] == "test_op"
        assert result["data"]["result"] == "success"


def test_handle_container_operation_failure() -> None:
    """Test container operation with exception."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        # noinspection PyUnusedLocal
        def operation(container: object) -> None:
            raise ValueError("Operation failed")

        result = manager.handle_container_operation("test-container", "test_op", operation)

        assert result["success"] is False
        assert result["error"] == "Error during test_op: Operation failed"
        assert result["error_type"] == "ValueError"


def test_handle_container_operation_container_error() -> None:
    """Test container operation when container retrieval fails."""
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client

        manager = DockerClientManager()

        with patch.object(manager, "get_container") as mock_get:
            mock_get.return_value = {
                "success": False,
                "error": "Container not found",
                "error_type": "NotFound",
                "container": "missing-container",
            }

            # noinspection PyUnusedLocal
            def operation(container: object) -> dict[str, str]:
                return {"result": "success"}

            result = manager.handle_container_operation("missing-container", "test_op", operation)

            assert result["success"] is False
            assert result["error"] == "Container not found"
            assert result["error_type"] == "NotFound"
            assert result["container"] == "missing-container"
