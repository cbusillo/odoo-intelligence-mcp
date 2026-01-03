from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.container_restart import odoo_restart
from tests.fixtures import get_expected_container_names


def create_mock_docker_manager(
    restart_func: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[MagicMock, MagicMock]:
    mock_manager = MagicMock()
    mock_instance = MagicMock()

    def mock_get_container(container_name: str, auto_start: bool = False) -> dict[str, Any]:
        return {"success": True, "container": container_name, "auto_start": auto_start}

    mock_instance.get_container.side_effect = mock_get_container
    if restart_func:
        mock_instance.restart_container.side_effect = restart_func

    mock_manager.return_value = mock_instance
    return mock_manager, mock_instance


def _default_service_names(containers: dict[str, Any]) -> list[str]:
    order = ("web", "script_runner", "database")
    names: list[str] = []
    for key in order:
        value = containers.get(key)
        if value and value not in names:
            names.append(value)
    return names


@pytest.mark.asyncio
async def test_odoo_restart_default_services() -> None:
    containers = get_expected_container_names()
    expected_services = _default_service_names(containers)

    def mock_restart(container_name: str) -> dict[str, Any]:
        return {"success": True, "operation": "restart", "container": container_name}

    mock_manager, _ = create_mock_docker_manager(mock_restart)

    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager", mock_manager):
        result = await odoo_restart()

        assert result["success"] is True
        assert result["data"]["services"] == expected_services
        assert len(result["data"]["results"]) == len(expected_services)
        assert all(r["success"] for r in result["data"]["results"].values())


@pytest.mark.asyncio
async def test_odoo_restart_specific_services() -> None:
    containers = get_expected_container_names()
    expected_services = [containers["web"]]

    def mock_restart(container_name: str) -> dict[str, Any]:
        return {"success": True, "operation": "restart", "container": container_name}

    mock_manager, _ = create_mock_docker_manager(mock_restart)

    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager", mock_manager):
        result = await odoo_restart(services="web-1")

        assert result["success"] is True
        assert result["data"]["services"] == expected_services
        assert len(result["data"]["results"]) == 1


@pytest.mark.asyncio
async def test_odoo_restart_container_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        mock_instance.restart_container.return_value = {
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

        def mock_restart(container_name: str) -> dict[str, Any]:
            if "web-1" in container_name:
                return {"success": True, "operation": "restart", "container": container_name}
            else:
                return {"success": False, "error": "Container not found", "container": container_name}

        mock_instance.restart_container.side_effect = mock_restart
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

        def mock_restart(container_name: str) -> dict[str, Any]:
            # Simulate exception in restart
            return {"success": False, "error": "Docker API error", "error_type": "Exception", "container": container_name}

        mock_instance.restart_container.side_effect = mock_restart
        mock_manager.return_value = mock_instance

        result = await odoo_restart(services="web-1")

        assert result["success"] is False
        assert "Docker API error" in str(result)


@pytest.mark.asyncio
async def test_odoo_restart_service_name_sanitization() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()

        called_services = []

        def mock_restart(container_name: str) -> dict[str, Any]:
            called_services.append(container_name)
            return {"success": True, "operation": "restart", "container": container_name}

        mock_instance.restart_container.side_effect = mock_restart
        mock_manager.return_value = mock_instance

        # Test with extra spaces and mixed formats
        result = await odoo_restart(services=" web-1 , script-runner-1 ")

        containers = get_expected_container_names()
        expected_services = [containers["web"], containers["script_runner"]]
        assert result["data"]["services"] == expected_services
        assert containers["web"] in called_services
        assert containers["script_runner"] in called_services
