from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.container_restart import odoo_restart
from ....helpers.docker_test_helpers import (
    create_mock_handle_operation_success,
    get_expected_container_names,
)


def create_mock_docker_manager(
    handle_operation_func: Callable[[str, str, Any], dict[str, Any]] | None = None,
) -> tuple[MagicMock, MagicMock]:
    mock_manager = MagicMock()
    mock_instance = MagicMock()

    if handle_operation_func:
        mock_instance.handle_container_operation.side_effect = handle_operation_func

    mock_manager.return_value = mock_instance
    return mock_manager, mock_instance


@pytest.mark.asyncio
async def test_odoo_restart_default_services() -> None:
    containers = get_expected_container_names()
    expected_services = [containers["web"], containers["shell"], containers["script_runner"]]

    mock_handle_operation = create_mock_handle_operation_success()
    mock_manager, _ = create_mock_docker_manager(mock_handle_operation)

    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager", mock_manager):
        result = await odoo_restart()

        assert result["success"] is True
        assert result["services"] == expected_services
        assert len(result["results"]) == 3
        assert all(r["success"] for r in result["results"].values())


@pytest.mark.asyncio
async def test_odoo_restart_specific_services() -> None:
    containers = get_expected_container_names()
    expected_services = [containers["web"]]

    mock_handle_operation = create_mock_handle_operation_success()
    mock_manager, _ = create_mock_docker_manager(mock_handle_operation)

    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager", mock_manager):
        result = await odoo_restart(services="web-1")

        assert result["success"] is True
        assert result["services"] == expected_services
        assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_odoo_restart_container_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        mock_instance.handle_container_operation.return_value = {
            "success": False,
            "error": "Container not found",
            "error_type": "NotFound",
            "container": f"{get_expected_container_names()['web'].split('-')[0]}-fake-service",
        }
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="fake-service")

        assert result["success"] is False
        assert "failed to restart" in result["error"]
        containers = get_expected_container_names()
        expected_fake_service = f"{containers['web'].split('-')[0]}-fake-service"
        assert result["services"] == [expected_fake_service]


@pytest.mark.asyncio
async def test_odoo_restart_partial_success() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        def mock_handle_operation(container_name: str, _operation: str, func: Any) -> dict[str, Any]:
            if "web-1" in container_name:
                mock_container = MagicMock()
                mock_container.status = "running"
                func(mock_container)
                return {"success": True, "operation": _operation, "container": container_name, "data": {"status": "running"}}
            else:
                return {"success": False, "error": "Container not found", "container": container_name}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="web-1,fake-service")

        assert result["success"] is False  # Overall false due to partial failure
        assert len(result["results"]) == 2
        containers = get_expected_container_names()
        expected_fake_service = f"{containers['web'].split('-')[0]}-fake-service"
        assert result["results"][containers["web"]]["success"] is True
        assert result["results"][expected_fake_service]["success"] is False


@pytest.mark.asyncio
async def test_odoo_restart_exception_handling() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        def mock_handle_operation(container_name: str, _operation: str, func: Any) -> dict[str, Any]:
            # Simulate exception in restart
            mock_container = MagicMock()
            mock_container.restart.side_effect = Exception("Docker API error")
            try:
                func(mock_container)
                return {"success": True, "operation": _operation, "container": container_name, "data": {"status": "running"}}
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

        def mock_handle_operation(container_name: str, _operation: str, _func: Any) -> dict[str, Any]:
            called_services.append(container_name)
            return {"success": True, "operation": _operation, "container": container_name, "data": {"status": "running"}}

        mock_instance.handle_container_operation.side_effect = mock_handle_operation
        mock_manager.return_value = mock_instance

        # Test with extra spaces and mixed formats
        result = await odoo_restart(services=" web-1 , shell-1 ")

        containers = get_expected_container_names()
        expected_services = [containers["web"], containers["shell"]]
        assert result["services"] == expected_services
        assert containers["web"] in called_services
        assert containers["shell"] in called_services
