from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.addon.addon_dependencies import get_addon_dependencies


@pytest.mark.asyncio
async def test_get_addon_dependencies_success() -> None:
    mock_manifest = {
        "name": "Product Connect",
        "version": "18.0.1.0.0",
        "depends": ["product", "stock", "sale"],
        "auto_install": False,
        "category": "Sales",
        "description": "Connect products to external systems",
    }

    mock_dependent_addons = ["motor_management", "shopify_sync"]

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.open", MagicMock()):
            with patch("ast.literal_eval", return_value=mock_manifest):
                with patch("pathlib.Path.rglob") as mock_rglob:
                    # Mock finding dependent addons
                    mock_files = [
                        MagicMock(parent=Path("/addons/motor_management")),
                        MagicMock(parent=Path("/addons/shopify_sync")),
                    ]
                    for f in mock_files:
                        f.read_text.return_value = "{'depends': ['product_connect']}"
                    mock_rglob.return_value = mock_files

                    result = await get_addon_dependencies("product_connect")

    assert result["success"] is True
    assert result["addon"] == "product_connect"
    assert result["manifest"]["name"] == "Product Connect"
    assert result["manifest"]["depends"] == ["product", "stock", "sale"]
    assert len(result["dependent_addons"]) == 2
    assert "motor_management" in result["dependent_addons"]


@pytest.mark.asyncio
async def test_get_addon_dependencies_not_found() -> None:
    with patch("pathlib.Path.exists", return_value=False):
        result = await get_addon_dependencies("nonexistent_addon")

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_get_addon_dependencies_invalid_manifest() -> None:
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.open", MagicMock()):
            with patch("ast.literal_eval", side_effect=SyntaxError("Invalid syntax")):
                result = await get_addon_dependencies("broken_addon")

    assert result["success"] is False
    assert "parse manifest" in result["error"]


@pytest.mark.asyncio
async def test_get_addon_dependencies_empty_depends() -> None:
    mock_manifest = {
        "name": "Simple Addon",
        "version": "18.0.1.0.0",
        "depends": [],
        "auto_install": False,
    }

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.open", MagicMock()):
            with patch("ast.literal_eval", return_value=mock_manifest):
                with patch("pathlib.Path.rglob", return_value=[]):
                    result = await get_addon_dependencies("simple_addon")

    assert result["success"] is True
    assert result["manifest"]["depends"] == []
    assert result["dependent_addons"] == []


@pytest.mark.asyncio
async def test_get_addon_dependencies_auto_install() -> None:
    mock_manifest = {
        "name": "Auto Install Addon",
        "version": "18.0.1.0.0",
        "depends": ["base"],
        "auto_install": True,
    }

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.open", MagicMock()):
            with patch("ast.literal_eval", return_value=mock_manifest):
                with patch("pathlib.Path.rglob", return_value=[]):
                    result = await get_addon_dependencies("auto_addon")

    assert result["success"] is True
    assert result["manifest"]["auto_install"] is True


@pytest.mark.asyncio
async def test_get_addon_dependencies_circular_dependency() -> None:
    # Test handling of circular dependencies
    mock_manifest = {
        "name": "Addon A",
        "depends": ["addon_b"],
    }

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.open", MagicMock()):
            with patch("ast.literal_eval", return_value=mock_manifest):
                with patch("pathlib.Path.rglob") as mock_rglob:
                    # Mock addon_b depending on addon_a (circular)
                    mock_file = MagicMock(parent=Path("/addons/addon_b"))
                    mock_file.read_text.return_value = "{'depends': ['addon_a']}"
                    mock_rglob.return_value = [mock_file]

                    result = await get_addon_dependencies("addon_a")

    assert result["success"] is True
    assert "addon_b" in result["dependent_addons"]
