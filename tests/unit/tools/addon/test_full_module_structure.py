from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.addon.module_structure import get_module_structure


@pytest.mark.asyncio
async def test_get_module_structure_complete() -> None:
    # Mock a complete module structure
    mock_files = {
        "models": ["product.py", "category.py", "__init__.py"],
        "views": ["product_views.xml", "menu.xml"],
        "data": ["data.xml", "demo.xml"],
        "security": ["ir.model.access.csv", "security.xml"],
        "controllers": ["main.py", "__init__.py"],
        "wizard": ["import_wizard.py"],
        "report": ["product_report.xml"],
        "static/src/js": ["widget.js", "utils.js"],
        "static/src/css": ["style.css"],
        "static/src/xml": ["templates.xml"],
        "i18n": ["es.po", "fr.po"],
    }

    def mock_rglob(pattern: str) -> list[Path]:
        if pattern == "*.py":
            result = []
            for dir_name, files in mock_files.items():
                if not dir_name.startswith("static"):
                    result.extend([Path(f"/addons/test_module/{dir_name}/{f}") for f in files if f.endswith(".py")])
            return result
        elif pattern == "*.xml":
            result = []
            for dir_name, files in mock_files.items():
                if not dir_name.startswith("static"):
                    result.extend([Path(f"/addons/test_module/{dir_name}/{f}") for f in files if f.endswith(".xml")])
            return result
        return []

    def mock_iterdir() -> list[Path]:
        return [Path(f"/addons/test_module/{d}") for d in mock_files if "/" not in d]

    with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.rglob", side_effect=mock_rglob):
            with patch("pathlib.Path.iterdir", side_effect=mock_iterdir):
                with patch("pathlib.Path.name", new_callable=lambda: property(lambda self: self.parts[-1])):
                    result = await get_module_structure("test_module")

    assert result["success"] is True
    assert result["module"] == "test_module"
    assert len(result["structure"]["models"]) == 2  # Excluding __init__.py
    assert len(result["structure"]["views"]) == 2
    assert len(result["structure"]["controllers"]) == 1
    assert result["has_models"] is True
    assert result["has_views"] is True
    assert result["has_controllers"] is True


@pytest.mark.asyncio
async def test_get_module_structure_not_found() -> None:
    with patch("pathlib.Path.exists", return_value=False):
        result = await get_module_structure("nonexistent_module")

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_get_module_structure_empty_module() -> None:
    with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.rglob", return_value=[]):
            with patch("pathlib.Path.iterdir", return_value=[]):
                result = await get_module_structure("empty_module")

    assert result["success"] is True
    assert result["has_models"] is False
    assert result["has_views"] is False
    assert result["has_controllers"] is False
    assert all(len(v) == 0 for v in result["structure"].values() if isinstance(v, list))


@pytest.mark.asyncio
async def test_get_module_structure_models_only() -> None:
    mock_model_files = [
        Path("/addons/simple_module/models/simple_model.py"),
        Path("/addons/simple_module/models/__init__.py"),
    ]

    with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_rglob.side_effect = lambda p: mock_model_files if p == "*.py" else []
            with patch("pathlib.Path.iterdir", return_value=[Path("/addons/simple_module/models")]):
                result = await get_module_structure("simple_module")

    assert result["success"] is True
    assert result["has_models"] is True
    assert result["has_views"] is False
    assert len(result["structure"]["models"]) == 1
    assert "simple_model.py" in result["structure"]["models"]


@pytest.mark.asyncio
async def test_get_module_structure_with_static_assets() -> None:
    def mock_rglob(pattern: str) -> list[Path]:
        if pattern == "static/src/**/*.js":
            return [Path("/addons/ui_module/static/src/js/widget.js")]
        elif pattern == "static/src/**/*.css":
            return [Path("/addons/ui_module/static/src/css/style.css")]
        elif pattern == "static/src/**/*.xml":
            return [Path("/addons/ui_module/static/src/xml/templates.xml")]
        return []

    with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.rglob", side_effect=mock_rglob):
            with patch("pathlib.Path.iterdir", return_value=[]):
                result = await get_module_structure("ui_module")

    assert result["success"] is True
    assert len(result["structure"]["static"]["js"]) == 1
    assert len(result["structure"]["static"]["css"]) == 1
    assert len(result["structure"]["static"]["xml"]) == 1
    assert result["has_static"] is True


@pytest.mark.asyncio
async def test_get_module_structure_with_tests() -> None:
    mock_test_files = [
        Path("/addons/tested_module/tests/test_models.py"),
        Path("/addons/tested_module/tests/test_controllers.py"),
        Path("/addons/tested_module/tests/__init__.py"),
    ]

    def mock_iterdir() -> list[Path]:
        tests_dir = MagicMock()
        tests_dir.name = "tests"
        tests_dir.is_dir.return_value = True
        tests_dir.rglob.return_value = mock_test_files
        return [tests_dir]

    with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
        with patch("pathlib.Path.rglob", return_value=[]):
            with patch("pathlib.Path.iterdir", side_effect=mock_iterdir):
                result = await get_module_structure("tested_module")

    assert result["success"] is True
    assert len(result["structure"]["tests"]) == 2  # Excluding __init__.py
    assert result["has_tests"] is True


@pytest.mark.asyncio
async def test_get_module_structure_error_handling() -> None:
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.is_dir", side_effect=PermissionError("Access denied")):
            result = await get_module_structure("protected_module")

    assert result["success"] is False
    assert "error" in result
