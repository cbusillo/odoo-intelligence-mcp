from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.addon.module_structure import get_module_structure


@pytest.mark.asyncio
async def test_get_module_structure_complete() -> None:
    # Mock the check for module existence (first exec_run call)
    check_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "/odoo/addons/test_module\n",
        "stderr": ""
    }

    # Mock the analyze result (second exec_run call)
    analyze_result = {
        "success": True,
        "exit_code": 0,
        "stdout": """{"path": "/odoo/addons/test_module",
        "models": ["models/sale.py", "models/product.py"],
        "views": ["views/sale_view.xml", "views/product_view.xml"],
        "controllers": ["controllers/main.py"],
        "wizards": [],
        "reports": [],
        "static": {"js": ["js/widget.js"], "css": ["css/style.css"], "xml": []},
        "manifest": {"name": "Test Module", "version": "1.0", "depends": ["base", "sale"]}
    }""",
        "stderr": ""
    }

    def exec_run_side_effect(container_name: str, cmd: object) -> dict:
        if "for path in" in str(cmd):
            return check_result
        else:
            return analyze_result

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        # Mock get_container to return success
        mock_docker_instance.get_container.return_value = {"success": True}
        # Mock exec_run with our side effect
        mock_docker_instance.exec_run = MagicMock(side_effect=exec_run_side_effect)
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons", "/volumes/addons"]

            result = await get_module_structure("test_module")

    assert "module" in result
    assert result["module"] == "test_module"
    assert "files" in result
    assert "summary" in result
    assert result["summary"]["models_count"] == 2
    assert result["summary"]["views_count"] == 2
    assert result["summary"]["js_count"] == 1
    assert result["summary"]["css_count"] == 1


@pytest.mark.asyncio
async def test_get_module_structure_not_found() -> None:
    # Mock exec_run to return failure (module not found)
    check_result = {
        "success": False,
        "exit_code": 1,
        "stdout": "",
        "stderr": ""
    }

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        # Mock get_container to return success
        mock_docker_instance.get_container.return_value = {"success": True}
        # Mock exec_run to return the check_result
        mock_docker_instance.exec_run.return_value = check_result
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            result = await get_module_structure("nonexistent_module")

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_module_structure_empty_module() -> None:
    check_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "/odoo/addons/empty_module\n",
        "stderr": ""
    }

    analyze_result = {
        "success": True,
        "exit_code": 0,
        "stdout": """{"path": "/odoo/addons/empty_module",
        "models": [],
        "views": [],
        "controllers": [],
        "wizards": [],
        "reports": [],
        "static": {"js": [], "css": [], "xml": []},
        "manifest": {"name": "Empty Module", "version": "1.0"}
    }""",
        "stderr": ""
    }

    def exec_run_side_effect(container_name: str, cmd: object) -> dict:
        if "for path in" in str(cmd):
            return check_result
        else:
            return analyze_result

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        mock_docker_instance.get_container.return_value = {"success": True}
        mock_docker_instance.exec_run = MagicMock(side_effect=exec_run_side_effect)
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            result = await get_module_structure("empty_module")

    assert "module" in result
    assert result["module"] == "empty_module"
    assert result["summary"]["models_count"] == 0
    assert result["summary"]["views_count"] == 0


@pytest.mark.asyncio
async def test_get_module_structure_models_only() -> None:
    check_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "/odoo/addons/models_module\n",
        "stderr": ""
    }

    analyze_result = {
        "success": True,
        "exit_code": 0,
        "stdout": """{"path": "/odoo/addons/models_module",
        "models": ["models/model1.py", "models/model2.py", "models/model3.py"],
        "views": [],
        "controllers": [],
        "wizards": [],
        "reports": [],
        "static": {"js": [], "css": [], "xml": []},
        "manifest": {"name": "Models Module"}
    }""",
        "stderr": ""
    }

    def exec_run_side_effect(container_name: str, cmd: object) -> dict:
        if "for path in" in str(cmd):
            return check_result
        else:
            return analyze_result

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        mock_docker_instance.get_container.return_value = {"success": True}
        mock_docker_instance.exec_run = MagicMock(side_effect=exec_run_side_effect)
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            result = await get_module_structure("models_module")

    assert result["summary"]["models_count"] == 3
    assert result["summary"]["views_count"] == 0
    assert "items" in result["files"]


@pytest.mark.asyncio
async def test_get_module_structure_with_static_assets() -> None:
    check_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "/odoo/addons/static_module\n",
        "stderr": ""
    }

    analyze_result = {
        "success": True,
        "exit_code": 0,
        "stdout": """{"path": "/odoo/addons/static_module",
        "models": ["models/model.py"],
        "views": ["views/view.xml"],
        "controllers": [],
        "wizards": [],
        "reports": [],
        "static": {
            "js": ["js/widget.js", "js/app.js"],
            "css": ["css/style.css", "css/theme.css"],
            "xml": ["xml/template.xml"]
        },
        "manifest": {"name": "Static Module"}
    }""",
        "stderr": ""
    }

    def exec_run_side_effect(container_name: str, cmd: object) -> dict:
        if "for path in" in str(cmd):
            return check_result
        else:
            return analyze_result

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        mock_docker_instance.get_container.return_value = {"success": True}
        mock_docker_instance.exec_run = MagicMock(side_effect=exec_run_side_effect)
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            result = await get_module_structure("static_module")

    assert result["summary"]["js_count"] == 2
    assert result["summary"]["css_count"] == 2


@pytest.mark.asyncio
async def test_get_module_structure_with_tests() -> None:
    check_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "/odoo/addons/tested_module\n",
        "stderr": ""
    }

    analyze_result = {
        "success": True,
        "exit_code": 0,
        "stdout": """{"path": "/odoo/addons/tested_module",
        "models": ["models/model.py"],
        "views": ["views/view.xml"],
        "controllers": [],
        "wizards": [],
        "reports": [],
        "static": {"js": [], "css": [], "xml": []},
        "tests": ["tests/test_model.py", "tests/test_workflow.py"],
        "manifest": {"name": "Tested Module"}
    }""",
        "stderr": ""
    }

    def exec_run_side_effect(container_name: str, cmd: object) -> dict:
        if "for path in" in str(cmd):
            return check_result
        else:
            return analyze_result

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        mock_docker_instance.get_container.return_value = {"success": True}
        mock_docker_instance.exec_run = MagicMock(side_effect=exec_run_side_effect)
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            result = await get_module_structure("tested_module")

    assert "files" in result
    assert "items" in result["files"]


@pytest.mark.asyncio
async def test_get_module_structure_error_handling() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        mock_docker_instance.get_container.return_value = {"error": "Container not found"}
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            result = await get_module_structure("test_module")

    assert "error" in result
    assert "Container not found" in result["error"]


@pytest.mark.asyncio
async def test_get_module_structure_with_pagination() -> None:
    check_result = {
        "success": True,
        "exit_code": 0,
        "stdout": "/odoo/addons/large_module\n",
        "stderr": ""
    }

    files_list = [f'"models/model_{i}.py"' for i in range(20)]

    analyze_result = {
        "success": True,
        "exit_code": 0,
        "stdout": f"""{{
        "path": "/odoo/addons/large_module",
        "models": [{", ".join(files_list)}],
        "views": [],
        "controllers": [],
        "wizards": [],
        "reports": [],
        "static": {{"js": [], "css": [], "xml": []}},
        "manifest": {{"name": "Large Module"}}
    }}""",
        "stderr": ""
    }

    def exec_run_side_effect(container_name: str, cmd: object) -> dict:
        if "for path in" in str(cmd):
            return check_result
        else:
            return analyze_result

    with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker_manager:
        mock_docker_instance = MagicMock()
        mock_docker_instance.get_container.return_value = {"success": True}
        mock_docker_instance.exec_run = MagicMock(side_effect=exec_run_side_effect)
        mock_docker_manager.return_value = mock_docker_instance

        with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]

            from odoo_intelligence_mcp.core.utils import PaginationParams

            pagination = PaginationParams(page_size=10)
            result = await get_module_structure("large_module", pagination=pagination)

    assert "module" in result
    assert result["module"] == "large_module"
    assert "files" in result
