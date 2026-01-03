from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.container_status import odoo_status
from tests.fixtures import get_expected_container_names


def _managed_container_names(containers: dict[str, Any]) -> list[str]:
    order = ("web", "script_runner", "database")
    names: list[str] = []
    for key in order:
        value = containers.get(key)
        if value and value not in names:
            names.append(value)
    return names


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_status_all_running() -> None:
    with patch("subprocess.run") as mock_run:
        # Mock docker version succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 20.10.0", stderr="")

        with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
            # Mock containers
            containers = get_expected_container_names()
            container_names = _managed_container_names(containers)

            mock_instance = MagicMock()

            # Mock get_container to return running containers
            # noinspection PyUnusedLocal
            def mock_get_container(container_name: str, auto_start: bool = False) -> dict[str, Any]:
                if container_name in container_names:
                    return {
                        "success": True,
                        "container": container_name,
                        "state": {
                            "Status": "running",
                            "Id": "abc123456789",
                            "Created": "2024-01-01T00:00:00",
                            "Config": {"Image": f"{container_name}:latest"},
                        },
                    }
                return {"success": False, "error": "Not found"}

            mock_instance.get_container.side_effect = mock_get_container
            mock_manager.return_value = mock_instance

            result = await odoo_status()

            assert result["success"] is True
            assert result["data"]["overall_status"] == "healthy"
            expected_total = len(container_names)
            assert result["data"]["total_containers"] == expected_total
            assert result["data"]["running_containers"] == expected_total
            assert all(c["running"] for c in result["data"]["containers"].values())


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_status_with_verbose() -> None:
    with patch("subprocess.run") as mock_run:
        # Mock docker version succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 20.10.0", stderr="")

        with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
            # Mock container with verbose info
            container_state = {
                "Status": "running",
                "Id": "abc123456789def",
                "State": {"Status": "running", "StartedAt": "2024-01-01T00:00:00"},
                "Created": "2024-01-01T00:00:00",
                "Config": {"Image": "odoo:16.0"},
            }

            mock_instance = MagicMock()
            mock_instance.get_container.return_value = {"success": True, "container": "test-container", "state": container_state}
            mock_manager.return_value = mock_instance

            result = await odoo_status(verbose=True)

        assert result["success"] is True
        # Check verbose fields are present
        container_info = next(iter(result["data"]["containers"].values()))
        assert "state" in container_info
        assert "id" in container_info
        assert "image" in container_info
        assert "created" in container_info


@pytest.mark.asyncio
async def test_odoo_status_some_stopped() -> None:
    with patch("subprocess.run") as mock_run:
        # Mock docker version succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 20.10.0", stderr="")

        with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
            # Mock containers with different states
            containers = get_expected_container_names()
            managed_names = _managed_container_names(containers)

            # noinspection PyUnusedLocal
            def mock_get_container(container_name: str, auto_start: bool = False) -> dict[str, Any]:
                if container_name == containers["web"]:
                    return {
                        "success": True,
                        "container": container_name,
                        "state": {"Status": "exited", "Id": "abc123", "Created": "", "Config": {}},
                    }
                if container_name == containers["script_runner"]:
                    return {
                        "success": True,
                        "container": container_name,
                        "state": {"Status": "running", "Id": "def456", "Created": "", "Config": {}},
                    }
                if containers.get("database") and container_name == containers["database"]:
                    return {
                        "success": True,
                        "container": container_name,
                        "state": {"Status": "running", "Id": "ghi789", "Created": "", "Config": {}},
                    }
                return {"success": False}

            mock_instance = MagicMock()
            mock_instance.get_container.side_effect = mock_get_container
            mock_manager.return_value = mock_instance

            result = await odoo_status()

            assert result["success"] is True
            assert result["success"] is True
            assert result["data"]["overall_status"] == "unhealthy"
            expected_running = len(managed_names) - 1
            assert result["data"]["running_containers"] == expected_running
            containers = get_expected_container_names()
            assert not result["data"]["containers"][containers["web"]]["running"]
            assert result["data"]["containers"][containers["script_runner"]]["running"]
            if containers.get("database"):
                assert result["data"]["containers"][containers["database"]]["running"]


@pytest.mark.asyncio
async def test_odoo_status_container_not_found() -> None:
    with patch("subprocess.run") as mock_run:
        # Mock docker version succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 20.10.0", stderr="")

        with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
            mock_instance = MagicMock()
            mock_instance.get_container.return_value = {"success": False, "error": "Container not found"}
            mock_manager.return_value = mock_instance

            result = await odoo_status()

        assert result["success"] is True
        assert result["data"]["overall_status"] == "unhealthy"
        assert result["data"]["running_containers"] == 0
        # All containers should show as not found
        for container_info in result["data"]["containers"].values():
            assert container_info["status"] == "not_found"
            assert not container_info["running"]


@pytest.mark.asyncio
async def test_odoo_status_docker_not_running() -> None:
    with patch("subprocess.run") as mock_run:
        # Mock docker version command failing
        mock_run.side_effect = FileNotFoundError("docker command not found")

        result = await odoo_status()

        assert result["success"] is False
        assert "Docker daemon is not available" in result["error"]
        assert result["error_type"] == "DockerConnectionError"


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_status_verbose_image_error_handling() -> None:
    """Test the fix for verbose mode image lookup error"""
    with patch("subprocess.run") as mock_run:
        # Mock docker version succeeds
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker version 20.10.0", stderr="")

        with patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_manager:
            mock_instance = MagicMock()
            # Mock get_container to return success with state info
            mock_instance.get_container.return_value = {
                "success": True,
                "container": "test-container",
                "state": {
                    "Status": "running",
                    "Id": "abc123456789",
                    "Created": "2024-01-01T00:00:00",
                    "Config": {"Image": "odoo-fallback-image"},
                },
            }
            mock_manager.return_value = mock_instance

            result = await odoo_status(verbose=True)

        assert result["success"] is True
        # Should fall back to Config.Image
        container_info = next(iter(result["data"]["containers"].values()))
        assert container_info["image"] == "odoo-fallback-image"
