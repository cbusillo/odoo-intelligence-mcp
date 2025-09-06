"""Simple tests for addon dependencies analysis."""

from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.addon.addon_dependencies import get_addon_dependencies


@pytest.mark.asyncio
async def test_get_addon_dependencies_success() -> None:
    """Test successful addon dependencies analysis."""
    addon_name = "test_addon"

    mock_manifest_content = """{
    'name': 'Test Addon',
    'version': '1.0.0',
    'depends': ['base', 'sale'],
    'auto_install': False,
    'category': 'Sales',
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['requests'],
        'bin': ['wkhtmltopdf']
    },
    'data': [],
    'external_dependencies': {'python': ['requests'], 'bin': ['wkhtmltopdf']}
}"""

    # Mock Docker container operations instead of file system
    with (
        patch("odoo_intelligence_mcp.tools.addon.addon_dependencies.DockerClientManager") as mock_docker_manager_class,
        patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._get_addon_paths", return_value=["/opt/project/addons"]),
    ):
        # Set up Docker manager mock
        mock_docker_manager = MagicMock()
        mock_docker_manager_class.return_value = mock_docker_manager

        # Mock container
        mock_docker_manager.get_container.return_value = {"success": True}

        # Mock successful manifest read and empty dependent addons listing
        # noinspection PyUnusedLocal
        def mock_exec_run(container_name: str, cmd: list[str]) -> dict:
            if cmd == ["cat", "/opt/project/addons/test_addon/__manifest__.py"]:
                return {"success": True, "exit_code": 0, "stdout": mock_manifest_content, "stderr": ""}
            else:  # ls command for dependent addons
                return {"success": False, "exit_code": 1, "stdout": "", "stderr": ""}

        mock_docker_manager.exec_run.side_effect = mock_exec_run

        result = await get_addon_dependencies(addon_name)

    assert result["addon"] == addon_name
    assert "path" in result
    assert "base" in result["depends"]
    assert "sale" in result["depends"]

    assert result["external_dependencies"]["python"] == ["requests"]
    assert result["external_dependencies"]["bin"] == ["wkhtmltopdf"]

    assert len(result["depends_on_this"]["items"]) == 0
    assert result["auto_install"] is False

    assert result["statistics"]["direct_dependencies"] == 2
    assert result["statistics"]["has_external_dependencies"] is True


@pytest.mark.asyncio
async def test_get_addon_dependencies_not_found() -> None:
    """Test addon not found case."""
    addon_name = "missing_addon"

    with patch("pathlib.Path.exists", return_value=False):
        result = await get_addon_dependencies(addon_name)

    assert "error" in result
    assert f"Addon {addon_name} not found in any addon path" in result["error"]


@pytest.mark.asyncio
async def test_get_addon_dependencies_basic_only() -> None:
    """Test basic addon dependencies without the complex dependent logic."""
    addon_name = "simple_addon"

    mock_manifest_content = """{
    'name': 'Simple Addon',
    'version': '2.0.0',
    'depends': ['base'],
    'auto_install': False,
}"""

    with (
        patch("odoo_intelligence_mcp.tools.addon.addon_dependencies.DockerClientManager") as mock_docker_manager_class,
        patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._get_addon_paths", return_value=["/opt/project/addons"]),
    ):
        # Set up Docker manager mock
        mock_docker_manager = MagicMock()
        mock_docker_manager_class.return_value = mock_docker_manager

        # Mock container
        mock_docker_manager.get_container.return_value = {"success": True}

        # Mock successful manifest read and empty dependent addons listing
        # noinspection PyUnusedLocal
        def mock_exec_run(container_name: str, cmd: list[str]) -> dict:
            if cmd == ["cat", "/opt/project/addons/simple_addon/__manifest__.py"]:
                return {"success": True, "exit_code": 0, "stdout": mock_manifest_content, "stderr": ""}
            else:  # ls command for dependent addons
                return {"success": False, "exit_code": 1, "stdout": "", "stderr": ""}

        mock_docker_manager.exec_run.side_effect = mock_exec_run

        result = await get_addon_dependencies(addon_name)

    assert result["addon"] == addon_name
    assert result["auto_install"] is False
    assert len(result["depends"]) == 1
    assert "base" in result["depends"]
    assert len(result["depends_on_this"]["items"]) == 0  # No other addons depend on this
    assert result["statistics"]["direct_dependencies"] == 1
    assert result["statistics"]["addons_depending_on_this"] == 0
