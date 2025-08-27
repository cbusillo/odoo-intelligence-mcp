"""Tests for read_odoo_file function."""

from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.code.read_odoo_file import read_odoo_file


@pytest.mark.asyncio
async def test_read_full_file_from_docker() -> None:
    """Test reading entire file from Docker container."""
    test_content = """line 1
line 2
line 3
line 4
line 5"""
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        # Mock successful cat command (with demux=True returns tuple)
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/odoo/addons/sale/models/sale.py")
        
        assert result["success"] is True
        assert "   1: line 1" in result["content"]
        assert "   5: line 5" in result["content"]
        assert result["total_lines"] == 5


@pytest.mark.asyncio
async def test_read_with_line_range() -> None:
    """Test reading specific line range."""
    test_content = "\n".join(f"line {i}" for i in range(1, 101))
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/odoo/addons/test.py", start_line=10, end_line=20)
        
        assert result["success"] is True
        assert "  10: line 10" in result["content"]
        assert "  20: line 20" in result["content"]
        assert "line 9" not in result["content"]
        assert "line 21" not in result["content"]


@pytest.mark.asyncio
async def test_read_with_pattern_search() -> None:
    """Test pattern search with context."""
    test_content = """class TestModel(models.Model):
    _name = 'test.model'
    
    def compute_total(self):
        total = 0
        for line in self.lines:
            total += line.amount
        return total"""
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/odoo/addons/test.py", pattern="total")
        
        assert result["success"] is True
        assert "matches" in result
        assert len(result["matches"]) > 0
        assert result["pattern"] == "total"


@pytest.mark.asyncio
async def test_read_file_not_found() -> None:
    """Test file not found error."""
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 1
        exec_result.output = (None, b"cat: /nonexistent.py: No such file or directory")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/nonexistent.py")
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_read_with_invalid_regex() -> None:
    """Test invalid regex pattern."""
    test_content = "test content"
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/test.py", pattern="[invalid(regex")
        
        assert result["success"] is False
        assert "invalid regex" in result["error"].lower()


@pytest.mark.asyncio
async def test_read_with_context_lines() -> None:
    """Test pattern search with custom context lines."""
    test_content = "\n".join(f"line {i}" for i in range(1, 21))
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/test.py", pattern="line 10", context_lines=2)
        
        assert result["success"] is True
        assert "matches" in result
        assert len(result["matches"]) > 0


@pytest.mark.asyncio
async def test_read_large_file_no_line_numbers() -> None:
    """Test that large files (>500 lines) are returned without line numbers."""
    # Create content with 600 lines
    test_content = "\n".join(f"line {i}" for i in range(1, 601))
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        result = await read_odoo_file("/test.py")
        
        assert result["success"] is True
        assert result["total_lines"] == 600
        # Large files return raw content without line numbers
        assert result["content"] == test_content
        assert "   1:" not in result["content"]  # No line numbers


@pytest.mark.asyncio
async def test_read_docker_connection_error() -> None:
    """Test Docker connection error handling."""
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_instance.get_container.return_value = {"error": "Docker connection failed"}
        
        result = await read_odoo_file("/test.py")
        
        assert result["success"] is False
        assert "error" in result
        assert "Container error" in result["error"]


@pytest.mark.asyncio
async def test_read_file_with_relative_path_search() -> None:
    """Test searching for files using relative paths in addon directories."""
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        with patch("odoo_intelligence_mcp.tools.addon.get_addon_paths.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons", "/volumes/addons"]
            
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            # First exec_run (absolute path check) fails
            first_exec = MagicMock()
            first_exec.exit_code = 1
            first_exec.output = (b"", b"not found")
            
            # Second exec_run (test -f for first addon path) succeeds
            test_exec = MagicMock()
            test_exec.exit_code = 0
            
            # Third exec_run (cat file) succeeds
            cat_exec = MagicMock()
            cat_exec.exit_code = 0
            cat_exec.output = (b"# Product module code\nclass Product:\n    pass", b"")
            
            mock_container.exec_run.side_effect = [first_exec, test_exec, cat_exec]
            
            result = await read_odoo_file("product/models/product.py")
            
            assert result["success"] is True
            assert "Product module code" in result["content"]
            # Path could be from either addon path
            assert result["path"] in [
                "/odoo/addons/product/models/product.py",
                "/volumes/addons/product/models/product.py"
            ]


@pytest.mark.asyncio
async def test_read_file_with_addon_prefix_path() -> None:
    """Test reading files with addons/ or enterprise/ prefix."""
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        with patch("odoo_intelligence_mcp.tools.addon.get_addon_paths.get_addon_paths_from_container") as mock_paths:
            mock_paths.return_value = ["/odoo/addons", "/volumes/enterprise"]
            
            mock_instance = mock_docker.return_value
            mock_container = mock_instance.get_container.return_value
            
            # First exec_run (absolute path) fails
            first_exec = MagicMock()
            first_exec.exit_code = 1
            first_exec.output = (b"", b"not found")
            
            # Second exec_run (test -f for mapped path) succeeds
            test_exec = MagicMock()
            test_exec.exit_code = 0
            
            # Third exec_run (cat file) succeeds
            cat_exec = MagicMock()
            cat_exec.exit_code = 0
            cat_exec.output = (b"# Enterprise module", b"")
            
            mock_container.exec_run.side_effect = [first_exec, test_exec, cat_exec]
            
            result = await read_odoo_file("enterprise/hr_payroll/models/hr_payslip.py")
            
            assert result["success"] is True
            assert "Enterprise module" in result["content"]


@pytest.mark.asyncio
async def test_read_with_out_of_range_start_line() -> None:
    """Test out of range start_line validation."""
    test_content = "\n".join(f"line {i}" for i in range(1, 11))  # 10 lines
    
    with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
        mock_instance = mock_docker.return_value
        mock_container = mock_instance.get_container.return_value
        
        exec_result = MagicMock()
        exec_result.exit_code = 0
        exec_result.output = (test_content.encode(), b"")  # (stdout, stderr)
        mock_container.exec_run.return_value = exec_result
        
        # Test with start_line > total lines
        result = await read_odoo_file("/test.py", start_line=20, end_line=25)
        
        assert result["success"] is False
        assert "out of range" in result["error"]
        assert "file has 10 lines" in result["error"]