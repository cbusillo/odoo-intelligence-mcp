from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.tools.addon.addon_dependencies import get_addon_dependencies


@pytest.mark.asyncio
async def test_get_addon_dependencies_success() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons", "/volumes/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._read_manifest_from_container") as mock_read:
            mock_read.return_value = {
                "name": "Product Connect",
                "version": "18.0.1.0.0",
                "depends": ["product", "stock", "sale"],
                "auto_install": False,
                "category": "Sales",
                "data": [],
                "external_dependencies": {},
                "application": False,
            }

            with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._find_dependent_addons") as mock_deps:
                mock_deps.return_value = [
                    {"name": "motor_management", "path": "/addons/motor_management"},
                    {"name": "shopify_sync", "path": "/addons/shopify_sync"},
                ]

                result = await get_addon_dependencies("product_connect")

    assert "addon" in result
    assert result["addon"] == "product_connect"
    assert "depends" in result
    assert result["depends"] == ["product", "stock", "sale"]
    assert "depends_on_this" in result
    assert isinstance(result["depends_on_this"], dict)


@pytest.mark.asyncio
async def test_get_addon_dependencies_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._read_manifest_from_container") as mock_read:
            mock_read.return_value = None

            result = await get_addon_dependencies("nonexistent_addon")

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_addon_dependencies_empty_depends() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._read_manifest_from_container") as mock_read:
            mock_read.return_value = {
                "name": "Simple Addon",
                "version": "18.0.1.0.0",
                "depends": [],
                "auto_install": False,
                "data": [],
                "external_dependencies": {},
                "application": False,
            }

            with patch("odoo_intelligence_mcp.tools.addon.addon_dependencies._find_dependent_addons") as mock_deps:
                mock_deps.return_value = []

                result = await get_addon_dependencies("simple_addon")

    assert "addon" in result
    assert result["depends"] == []
    assert "depends_on_this" in result
