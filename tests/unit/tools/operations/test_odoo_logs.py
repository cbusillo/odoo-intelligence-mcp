from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.container_logs import odoo_logs


@pytest.mark.asyncio
async def test_odoo_logs_default() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_container = MagicMock()
        mock_container.logs.return_value = b"Log line 1\nLog line 2\nLog line 3"
        mock_container.status = "running"

        mock_instance = MagicMock()
        mock_instance.get_container.return_value = mock_container

        # Mock handle_container_operation to return the expected structure
        def mock_handle_operation(container_name, operation_name, operation_func):
            # Call the operation function to get the inner result
            inner_result = operation_func(mock_container)
            return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_logs()

        assert result["success"] is True
        assert result["container"] == "odoo-opw-web-1"  # Default container
        assert result["data"]["lines_requested"] == 100  # Default lines
        assert result["data"]["status"] == "running"
        assert "Log line 1" in result["data"]["logs"]
        assert "Log line 2" in result["data"]["logs"]
        assert "Log line 3" in result["data"]["logs"]

        # Check logs was called with correct parameters
        mock_container.logs.assert_called_once_with(tail=100)


@pytest.mark.asyncio
async def test_odoo_logs_custom_parameters() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_container = MagicMock()
        mock_container.logs.return_value = b"Custom log line"
        mock_container.status = "exited"

        mock_instance = MagicMock()
        mock_instance.get_container.return_value = mock_container

        def mock_handle_operation(container_name, operation_name, operation_func):
            inner_result = operation_func(mock_container)
            return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_logs(container="odoo-opw-shell-1", lines=50)

        assert result["success"] is True
        assert result["container"] == "odoo-opw-shell-1"
        assert result["data"]["lines_requested"] == 50
        assert result["data"]["status"] == "exited"
        mock_container.logs.assert_called_once_with(tail=50)


@pytest.mark.asyncio
async def test_odoo_logs_container_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        # Mock handle_container_operation to return error when container not found
        mock_instance.handle_container_operation.return_value = {
            "success": False,
            "error": "Container not found",
            "error_type": "ContainerNotFoundError",
            "container": "fake-container",
        }
        mock_manager.return_value = mock_instance

        result = await odoo_logs(container="fake-container")

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["container"] == "fake-container"


@pytest.mark.asyncio
async def test_odoo_logs_decode_error_handling() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_container = MagicMock()
        # Return bytes that can't be decoded as UTF-8
        mock_container.logs.return_value = b"\xff\xfe Invalid UTF-8"
        mock_container.status = "running"

        mock_instance = MagicMock()
        mock_instance.get_container.return_value = mock_container

        def mock_handle_operation(container_name, operation_name, operation_func):
            try:
                inner_result = operation_func(mock_container)
                return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}
            except UnicodeDecodeError as e:
                return {"success": False, "error": str(e), "error_type": "UnicodeDecodeError", "container": container_name}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_logs()

        # Should fail due to decode error
        assert result["success"] is False
        assert result["error_type"] == "UnicodeDecodeError"


@pytest.mark.asyncio
async def test_odoo_logs_empty_logs() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_container = MagicMock()
        mock_container.logs.return_value = b""
        mock_container.status = "running"

        mock_instance = MagicMock()
        mock_instance.get_container.return_value = mock_container

        def mock_handle_operation(container_name, operation_name, operation_func):
            inner_result = operation_func(mock_container)
            return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_logs()

        assert result["success"] is True
        assert result["data"]["logs"] == ""


@pytest.mark.asyncio
async def test_odoo_logs_multiline_with_timestamps() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_container = MagicMock()
        log_content = b"""2024-01-01 12:00:00,123 INFO odoo.modules.loading: Loading module 'sale'
2024-01-01 12:00:01,456 WARNING odoo.sql_db: Slow query detected
2024-01-01 12:00:02,789 ERROR odoo.http: Request failed"""
        mock_container.logs.return_value = log_content
        mock_container.status = "running"

        mock_instance = MagicMock()
        mock_instance.get_container.return_value = mock_container

        def mock_handle_operation(container_name, operation_name, operation_func):
            inner_result = operation_func(mock_container)
            return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_logs()

        assert result["success"] is True
        logs = result["data"]["logs"]
        assert "Loading module 'sale'" in logs
        assert "Slow query detected" in logs
        assert "Request failed" in logs


@pytest.mark.asyncio
async def test_odoo_logs_large_number_of_lines() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_logs.DockerClientManager") as mock_manager:
        mock_container = MagicMock()
        # Generate 1000 log lines
        log_lines = [f"Log line {i}".encode() for i in range(1000)]
        mock_container.logs.return_value = b"\n".join(log_lines)
        mock_container.status = "running"

        mock_instance = MagicMock()
        mock_instance.get_container.return_value = mock_container

        def mock_handle_operation(container_name, operation_name, operation_func):
            inner_result = operation_func(mock_container)
            return {"success": True, "operation": operation_name, "container": container_name, "data": inner_result}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_logs(lines=1000)

        assert result["success"] is True
        assert result["data"]["lines_requested"] == 1000
        assert len(result["data"]["logs"].split("\n")) == 1000
