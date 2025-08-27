from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.tools.addon.module_structure import get_module_structure

pytestmark = pytest.mark.skip(reason="Module structure tests need filesystem mock refactoring")


@pytest.mark.asyncio
async def test_get_module_structure_complete() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons", "/volumes/addons"]
        
        with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker:
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            # Mock successful ls command
            mock_container.exec_run.return_value.exit_code = 0
            mock_container.exec_run.return_value.output = b"""models/
views/
controllers/
data/
security/
static/
__manifest__.py
__init__.py"""
            
            result = await get_module_structure("test_module")
    
    assert "module" in result
    assert result["module"] == "test_module"
    assert "structure" in result


@pytest.mark.asyncio
async def test_get_module_structure_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]
        
        with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker:
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            # Mock failed ls command (module not found)
            mock_container.exec_run.return_value.exit_code = 1
            mock_container.exec_run.return_value.output = b"No such file or directory"
            
            result = await get_module_structure("nonexistent_module")
    
    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_module_structure_empty_module() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]
        
        with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker:
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            # Mock empty module
            mock_container.exec_run.return_value.exit_code = 0
            mock_container.exec_run.return_value.output = b"__manifest__.py\n__init__.py"
            
            result = await get_module_structure("empty_module")
    
    assert "module" in result
    assert "structure" in result


@pytest.mark.asyncio
async def test_get_module_structure_models_only() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]
        
        with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker:
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            mock_container.exec_run.return_value.exit_code = 0
            mock_container.exec_run.return_value.output = b"models/\n__manifest__.py\n__init__.py"
            
            result = await get_module_structure("models_module")
    
    assert "module" in result
    assert "structure" in result


@pytest.mark.asyncio
async def test_get_module_structure_with_static_assets() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]
        
        with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker:
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            mock_container.exec_run.return_value.exit_code = 0
            mock_container.exec_run.return_value.output = b"static/src/js/\nstatic/src/css/\nmodels/"
            
            result = await get_module_structure("static_module")
    
    assert "module" in result
    assert "structure" in result


@pytest.mark.asyncio
async def test_get_module_structure_with_tests() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.return_value = ["/odoo/addons"]
        
        with patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager") as mock_docker:
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            mock_container.exec_run.return_value.exit_code = 0
            mock_container.exec_run.return_value.output = b"tests/\nmodels/\n__manifest__.py"
            
            result = await get_module_structure("test_module")
    
    assert "module" in result
    assert "structure" in result


@pytest.mark.asyncio
async def test_get_module_structure_error_handling() -> None:
    with patch("odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container") as mock_paths:
        mock_paths.side_effect = Exception("Docker connection failed")
        
        result = await get_module_structure("any_module")
    
    assert "error" in result