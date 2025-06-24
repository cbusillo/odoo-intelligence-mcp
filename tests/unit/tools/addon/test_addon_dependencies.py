"""Simple tests for addon dependencies analysis."""

from unittest.mock import mock_open, patch

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
    }
}"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[]),
        patch("builtins.open", mock_open(read_data=mock_manifest_content)),
    ):
        result = await get_addon_dependencies(addon_name)

    assert result["addon"] == addon_name
    assert "path" in result
    assert "base" in result["depends"]
    assert "sale" in result["depends"]

    assert result["external_dependencies"]["python"] == ["requests"]
    assert result["external_dependencies"]["bin"] == ["wkhtmltopdf"]

    assert len(result["depends_on_this"]) == 0
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
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[]),
        patch("builtins.open", mock_open(read_data=mock_manifest_content)),
    ):
        result = await get_addon_dependencies(addon_name)

    assert result["addon"] == addon_name
    assert result["auto_install"] is False
    assert len(result["depends"]) == 1
    assert "base" in result["depends"]
    assert len(result["depends_on_this"]) == 0  # No other addons depend on this
    assert result["statistics"]["direct_dependencies"] == 1
    assert result["statistics"]["addons_depending_on_this"] == 0
