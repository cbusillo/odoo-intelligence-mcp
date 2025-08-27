from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.addon.module_structure import get_module_structure


def create_mock_module_path(exists=True, has_manifest=True, models=None, views=None, static_js=None):
    """Helper to create a mock module path with files."""
    mock_module_path = MagicMock(spec=Path)
    mock_module_path.exists.return_value = exists
    mock_module_path.__str__ = lambda self: "/odoo/addons/test_module"

    # Mock manifest
    mock_manifest = MagicMock()
    mock_manifest.exists.return_value = has_manifest
    if has_manifest:
        mock_manifest.open.return_value.__enter__.return_value.read.return_value = "{'name': 'Test Module', 'version': '1.0'}"

    # Mock static path
    mock_static_path = MagicMock()
    mock_static_path.exists.return_value = bool(static_js)
    mock_static_path.rglob.return_value = static_js or []

    # Setup path operations
    def truediv(self, other):
        if other == "__manifest__.py":
            return mock_manifest
        elif other == "static":
            mock_static = MagicMock()
            mock_static.__truediv__ = lambda s, o: mock_static_path if o == "src" else MagicMock()
            return mock_static
        else:
            return mock_module_path

    mock_module_path.__truediv__ = truediv

    # Mock rglob for Python and XML files
    def rglob(pattern):
        if pattern == "*.py":
            return models or []
        elif pattern == "*.xml":
            return views or []
        return []

    mock_module_path.rglob = rglob

    return mock_module_path


@pytest.mark.asyncio
async def test_get_module_structure_complete() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons", "/volumes/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.Path") as mock_path_class:
            # Create mock files
            mock_model_file = MagicMock()
            mock_model_file.relative_to.return_value = Path("models/sale.py")
            mock_view_file = MagicMock()
            mock_view_file.relative_to.return_value = Path("views/sale_view.xml")

            mock_module_path = create_mock_module_path(models=[mock_model_file], views=[mock_view_file])
            mock_path_class.return_value = mock_module_path

            result = await get_module_structure("test_module")

    assert "module" in result
    assert result["module"] == "test_module"
    assert "files" in result
    assert "summary" in result
    assert result["summary"]["models_count"] == 1
    assert result["summary"]["views_count"] == 1


@pytest.mark.asyncio
async def test_get_module_structure_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.Path") as mock_path_class:
            mock_path = create_mock_module_path(exists=False)
            mock_path_class.return_value = mock_path

            # Also make the path check in loop fail
            mock_path_class.side_effect = lambda x: mock_path if isinstance(x, str) else MagicMock(exists=lambda: False)

            result = await get_module_structure("nonexistent_module")

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_module_structure_empty_module() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.Path") as mock_path_class:
            mock_module_path = create_mock_module_path(models=[], views=[])
            mock_path_class.return_value = mock_module_path

            result = await get_module_structure("empty_module")

    assert "module" in result
    assert "summary" in result
    assert result["summary"]["models_count"] == 0
    assert result["summary"]["views_count"] == 0


@pytest.mark.asyncio
async def test_get_module_structure_models_only() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.Path") as mock_path_class:
            # Create mock model files
            mock_model1 = MagicMock()
            mock_model1.relative_to.return_value = Path("models/model1.py")
            mock_model2 = MagicMock()
            mock_model2.relative_to.return_value = Path("models/model2.py")

            mock_module_path = create_mock_module_path(models=[mock_model1, mock_model2], views=[])
            mock_path_class.return_value = mock_module_path

            result = await get_module_structure("models_module")

    assert "module" in result
    assert "summary" in result
    assert result["summary"]["models_count"] == 2
    assert result["summary"]["views_count"] == 0


@pytest.mark.asyncio
async def test_get_module_structure_with_static_assets() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.Path") as mock_path_class:
            # Create mock static files
            mock_js = MagicMock()
            mock_js.relative_to.return_value = Path("widget.js")

            mock_module_path = create_mock_module_path(static_js=[mock_js])
            mock_path_class.return_value = mock_module_path

            result = await get_module_structure("static_module")

    assert "module" in result
    assert "summary" in result
    assert result["summary"]["static_js_count"] == 1


@pytest.mark.asyncio
async def test_get_module_structure_with_tests() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.Path") as mock_path_class:
            # Tests aren't categorized separately in the function, they're just python files
            mock_test = MagicMock()
            mock_test.relative_to.return_value = Path("tests/test_sale.py")

            mock_module_path = create_mock_module_path(models=[mock_test])
            mock_path_class.return_value = mock_module_path

            result = await get_module_structure("test_module")

    assert "module" in result
    assert "files" in result


@pytest.mark.asyncio
async def test_get_module_structure_error_handling() -> None:
    async def raise_error():
        raise Exception("Docker connection failed")

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.side_effect = raise_error

        result = await get_module_structure("any_module")

    assert "error" in result
    assert "Docker connection failed" in str(result["error"])
