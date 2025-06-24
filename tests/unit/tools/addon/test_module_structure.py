from unittest.mock import mock_open, patch

import pytest

from odoo_intelligence_mcp.tools.addon.module_structure import get_module_structure
from tests.test_utils import create_exists_side_effect_for_module_structure


@pytest.mark.asyncio
async def test_module_structure_not_found() -> None:
    module_name = "nonexistent_module"

    with patch("pathlib.Path.exists", return_value=False):
        result = await get_module_structure(module_name)
        assert "error" in result
        assert f"Module {module_name} not found in any addon path" in result["error"]


@pytest.mark.asyncio
async def test_module_structure_basic() -> None:
    module_name = "simple_module"

    mock_manifest_content = """{
    'name': 'Simple Module',
    'version': '1.0.0',
    'depends': ['base'],
}"""

    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.rglob", return_value=[]),
        patch("builtins.open", mock_open(read_data=mock_manifest_content)),
    ):
        # Mock exists: False for bare module name, True for other paths except static
        mock_exists.side_effect = create_exists_side_effect_for_module_structure(module_name, has_static=False)

        result = await get_module_structure(module_name)

        assert "path" in result
        assert "manifest" in result
        assert result["manifest"]["name"] == "Simple Module"
        assert len(result["models"]) == 0
        assert len(result["views"]) == 0
        assert len(result["controllers"]) == 0
        assert len(result["static"]["js"]) == 0


@pytest.mark.asyncio
async def test_module_structure_manifest_error() -> None:
    """Test handling of manifest parse errors."""
    module_name = "broken_module"

    # Invalid manifest
    broken_manifest = """{ 'name': 'Broken', invalid syntax }"""

    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.rglob", return_value=[]),
        patch("builtins.open", mock_open(read_data=broken_manifest)),
    ):
        mock_exists.side_effect = create_exists_side_effect_for_module_structure(module_name, has_static=False)

        result = await get_module_structure(module_name)

        # Should still return basic structure even with manifest error
        assert "path" in result
        assert "manifest" in result
        # Manifest should be empty due to parse error handling we added
        assert result["manifest"] == {}
