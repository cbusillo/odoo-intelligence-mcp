from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.container_status import odoo_status
from ....helpers.docker_test_helpers import get_expected_container_names


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_status_all_running() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
        # Mock containers
        containers = get_expected_container_names()
        container_names = [containers["web"], containers["shell"], containers["script_runner"]]
        mock_containers = {}
        for name in container_names:
            container = MagicMock()
            container.status = "running"
            container.short_id = "abc123"
            container.attrs = {"State": {"Status": "running"}, "Created": "2024-01-01T00:00:00", "Config": {"Image": name}}
            container.image.tags = [f"{name}:latest"]
            mock_containers[name] = container

        mock_instance = MagicMock()
        mock_instance.client.ping.return_value = None  # Docker is available
        mock_instance.get_container.side_effect = lambda container_name: mock_containers.get(container_name)
        mock_manager.return_value = mock_instance

        result = await odoo_status()

        assert result["success"] is True
        assert result["overall_status"] == "healthy"
        assert result["total_containers"] == 3
        assert result["running_containers"] == 3
        assert all(c["running"] for c in result["containers"].values())


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_status_with_verbose() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
        # Mock container with verbose info
        container = MagicMock()
        container.status = "running"
        container.short_id = "abc123"
        container.attrs = {
            "State": {"Status": "running", "StartedAt": "2024-01-01T00:00:00"},
            "Created": "2024-01-01T00:00:00",
            "Config": {"Image": "odoo-test"},
        }
        container.image.tags = ["odoo:16.0"]

        # noinspection DuplicatedCode
        mock_instance = MagicMock()
        mock_instance.client.ping.return_value = None
        mock_instance.get_container.return_value = container
        mock_manager.return_value = mock_instance

        result = await odoo_status(verbose=True)

        assert result["success"] is True
        # Check verbose fields are present
        container_info = next(iter(result["containers"].values()))
        assert "state" in container_info
        assert "id" in container_info
        assert "image" in container_info
        assert "created" in container_info


@pytest.mark.asyncio
async def test_odoo_status_some_stopped() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
        # Mock containers with different states
        containers = get_expected_container_names()
        mock_containers = {
            containers["web"]: MagicMock(status="exited", short_id="abc123", attrs={"State": {}, "Created": "", "Config": {}}),
            containers["shell"]: MagicMock(status="running", short_id="def456", attrs={"State": {}, "Created": "", "Config": {}}),
            containers["script_runner"]: MagicMock(
                status="running", short_id="ghi789", attrs={"State": {}, "Created": "", "Config": {}}
            ),
        }

        for container in mock_containers.values():
            container.image.tags = []

        mock_instance = MagicMock()
        mock_instance.client.ping.return_value = None
        mock_instance.get_container.side_effect = lambda container_name: mock_containers.get(container_name)
        mock_manager.return_value = mock_instance

        result = await odoo_status()

        assert result["success"] is True
        assert result["overall_status"] == "unhealthy"
        assert result["running_containers"] == 2
        containers = get_expected_container_names()
        assert not result["containers"][containers["web"]]["running"]
        assert result["containers"][containers["shell"]]["running"]


@pytest.mark.asyncio
async def test_odoo_status_container_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()
        mock_instance.client.ping.return_value = None
        mock_instance.get_container.return_value = {"error": "Container not found"}
        mock_manager.return_value = mock_instance

        result = await odoo_status()

        assert result["success"] is True
        assert result["overall_status"] == "unhealthy"
        assert result["running_containers"] == 0
        # All containers should show as not found
        for container_info in result["containers"].values():
            assert container_info["status"] == "not_found"
            assert not container_info["running"]


@pytest.mark.asyncio
async def test_odoo_status_docker_not_running() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
        mock_instance = MagicMock()
        mock_instance.client.ping.side_effect = Exception("Cannot connect to Docker daemon")
        mock_manager.return_value = mock_instance

        result = await odoo_status()

        assert result["success"] is False
        assert "Docker daemon is not available" in result["error"]
        assert result["error_type"] == "DockerConnectionError"


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_status_verbose_image_error_handling() -> None:
    """Test the fix for verbose mode image lookup error"""
    with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
        # Mock container where image.tags access fails
        container = MagicMock()
        container.status = "running"
        container.short_id = "abc123"
        container.attrs = {
            "State": {"Status": "running"},
            "Created": "2024-01-01T00:00:00",
            "Config": {"Image": "odoo-fallback-image"},
        }
        # Simulate the error that was occurring
        container.image.tags = []  # Empty tags list

        # noinspection DuplicatedCode
        mock_instance = MagicMock()
        mock_instance.client.ping.return_value = None
        mock_instance.get_container.return_value = container
        mock_manager.return_value = mock_instance

        result = await odoo_status(verbose=True)

        assert result["success"] is True
        # Should fall back to Config.Image
        container_info = next(iter(result["containers"].values()))
        assert container_info["image"] == "odoo-fallback-image"
