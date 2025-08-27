from unittest.mock import MagicMock, patch
import pytest

from odoo_intelligence_mcp.tools.filesystem.find_files import find_files
from odoo_intelligence_mcp.core.utils import PaginationParams


@pytest.mark.asyncio
async def test_find_files_basic_pattern() -> None:
    with patch("odoo_intelligence_mcp.tools.filesystem.find_files.DockerClientManager") as mock_docker:
        with patch("odoo_intelligence_mcp.tools.filesystem.find_files.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons", "/volumes/addons"]
            
            mock_instance = mock_docker.return_value
            mock_container = MagicMock()
            mock_instance.get_container.return_value = mock_container
            
            # Mock find command output
            mock_exec_result = MagicMock()
            mock_exec_result.exit_code = 0
            mock_exec_result.output = b"/odoo/addons/sale/models/sale.py\n/odoo/addons/sale/models/sale_order.py"
            mock_container.exec_run.return_value = mock_exec_result
            
            result = await find_files("*.py")
            
            assert "results" in result
            assert "pagination" in result["results"]
            # Each file appears twice (once per addon path)
            assert len(result["results"]["items"]) == 4
            assert result["results"]["items"][0]["path"] == "/odoo/addons/sale/models/sale.py"
            assert result["results"]["items"][0]["module"] == "sale"
            assert result["results"]["items"][0]["filename"] == "sale.py"
            

@pytest.mark.asyncio
async def test_find_files_with_file_type() -> None:
    with patch("odoo_intelligence_mcp.tools.filesystem.find_files.DockerClientManager") as mock_docker:
        with patch("odoo_intelligence_mcp.tools.filesystem.find_files.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]
            
            mock_instance = mock_docker.return_value
            mock_container = MagicMock()
            mock_instance.get_container.return_value = mock_container
            
            mock_exec_result = MagicMock()
            mock_exec_result.exit_code = 0
            mock_exec_result.output = b"/odoo/addons/sale/views/sale_view.xml"
            mock_container.exec_run.return_value = mock_exec_result
            
            result = await find_files("sale_view", file_type="xml")
            
            assert "results" in result
            # Check that file_type was added to pattern
            mock_container.exec_run.assert_called_with(["find", "/odoo/addons", "-type", "f", "-name", "*sale_view*.xml"])
            

@pytest.mark.asyncio
async def test_find_files_no_matches() -> None:
    with patch("odoo_intelligence_mcp.tools.filesystem.find_files.DockerClientManager") as mock_docker:
        with patch("odoo_intelligence_mcp.tools.filesystem.find_files.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]
            
            mock_instance = mock_docker.return_value
            mock_container = MagicMock()
            mock_instance.get_container.return_value = mock_container
            
            mock_exec_result = MagicMock()
            mock_exec_result.exit_code = 0
            mock_exec_result.output = b""
            mock_container.exec_run.return_value = mock_exec_result
            
            result = await find_files("nonexistent.py")
            
            assert "results" in result
            assert len(result["results"]["items"]) == 0
            assert result["results"]["pagination"]["total_count"] == 0


@pytest.mark.asyncio  
async def test_find_files_container_error() -> None:
    with patch("odoo_intelligence_mcp.tools.filesystem.find_files.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_instance.get_container.return_value = {"error": "Container not found"}
        
        result = await find_files("*.py")
        
        assert result["success"] is False
        assert "Container error" in result["error"]


@pytest.mark.asyncio
async def test_find_files_with_pagination() -> None:
    with patch("odoo_intelligence_mcp.tools.filesystem.find_files.DockerClientManager") as mock_docker:
        with patch("odoo_intelligence_mcp.tools.filesystem.find_files.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons"]
            
            mock_instance = mock_docker.return_value
            mock_container = MagicMock()
            mock_instance.get_container.return_value = mock_container
            
            # Create many file results
            files = [f"/odoo/addons/module{i}/file{i}.py" for i in range(20)]
            mock_exec_result = MagicMock()
            mock_exec_result.exit_code = 0
            mock_exec_result.output = "\n".join(files).encode()
            mock_container.exec_run.return_value = mock_exec_result
            
            pagination = PaginationParams(page=1, page_size=5)
            result = await find_files("*.py", pagination=pagination)
            
            assert "results" in result
            assert len(result["results"]["items"]) == 5  # Limited by page_size
            assert result["results"]["pagination"]["total_count"] == 20
            assert result["results"]["pagination"]["page"] == 1
            assert result["results"]["pagination"]["page_size"] == 5
            assert result["results"]["pagination"]["has_next_page"] is True