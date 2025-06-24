from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.container_restart import odoo_restart


@pytest.mark.asyncio
async def test_odoo_restart_default_services() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        # Mock successful restart for all default services
        def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
            # Simulate calling the restart function
            mock_container = MagicMock()
            mock_container.status = "running"
            func(mock_container)
            return {"success": True, "operation": operation, "container": container_name, "data": {"status": "running"}}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_restart()

        assert result["success"] is True
        assert result["services"] == ["odoo-opw-web-1", "odoo-opw-shell-1", "odoo-opw-script-runner-1"]
        assert len(result["results"]) == 3
        assert all(r["success"] for r in result["results"].values())


@pytest.mark.asyncio
async def test_odoo_restart_specific_services() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
            mock_container = MagicMock()
            mock_container.status = "running"
            func(mock_container)
            return {"success": True, "operation": operation, "container": container_name, "data": {"status": "running"}}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="web-1")

        assert result["success"] is True
        assert result["services"] == ["odoo-opw-web-1"]
        assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_odoo_restart_container_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        mock_instance.handle_container_operation.return_value = {
            "success": False,
            "error": "Container not found",
            "error_type": "NotFound",
            "container": "odoo-opw-fake-service",
        }
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="fake-service")

        assert result["success"] is False
        assert "failed to restart" in result["error"]
        assert result["services"] == ["odoo-opw-fake-service"]


@pytest.mark.asyncio
async def test_odoo_restart_partial_success() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
            if "web-1" in container_name:
                mock_container = MagicMock()
                mock_container.status = "running"
                func(mock_container)
                return {"success": True, "operation": operation, "container": container_name, "data": {"status": "running"}}
            else:
                return {"success": False, "error": "Container not found", "container": container_name}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="web-1,fake-service")

        assert result["success"] is False  # Overall false due to partial failure
        assert len(result["results"]) == 2
        assert result["results"]["odoo-opw-web-1"]["success"] is True
        assert result["results"]["odoo-opw-fake-service"]["success"] is False


@pytest.mark.asyncio
async def test_odoo_restart_exception_handling() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
            # Simulate exception in restart
            mock_container = MagicMock()
            mock_container.restart.side_effect = Exception("Docker API error")
            try:
                func(mock_container)
            except Exception as e:
                return {"success": False, "error": str(e), "error_type": type(e).__name__, "container": container_name}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="web-1")

        assert result["success"] is False
        assert "Docker API error" in str(result)


@pytest.mark.asyncio
async def test_odoo_restart_service_name_sanitization() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        called_services = []

        def mock_handle_operation(container_name: str, operation: str, func: Any) -> dict[str, Any]:
            called_services.append(container_name)
            return {"success": True, "operation": operation, "container": container_name, "data": {"status": "running"}}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        # Test with extra spaces and mixed formats
        result = await odoo_restart(services=" web-1 , shell-1 ")

        assert result["services"] == ["odoo-opw-web-1", "odoo-opw-shell-1"]
        assert "odoo-opw-web-1" in called_services
        assert "odoo-opw-shell-1" in called_services
