"""Tests for read_odoo_file function."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.code.read_odoo_file import read_odoo_file


@pytest.mark.asyncio
async def test_read_full_file_from_host() -> None:
    """Test reading entire file from host mapping."""
    test_content = """line 1
line 2
line 3
line 4
line 5"""

    mock_path = Path("/volumes/addons/test_module/models/test.py")

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_map.return_value = mock_path

        result = await read_odoo_file("/volumes/addons/test_module/models/test.py")

        assert result["success"] is True
        assert result["via"] == "host"
        assert "   1: line 1" in result["content"]
        assert "   5: line 5" in result["content"]
        assert result["total_lines"] == 5


@pytest.mark.asyncio
async def test_read_with_line_range() -> None:
    """Test reading specific line range."""
    test_content = "\n".join(f"line {i}" for i in range(1, 101))

    mock_path = Path("/volumes/addons/test_module/models/test.py")

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_map.return_value = mock_path

        result = await read_odoo_file("/volumes/addons/test_module/models/test.py", start_line=10, end_line=15)

        assert result["success"] is True
        assert result["lines"] == "10-15"
        assert "  10: line 10" in result["content"]
        assert "  15: line 15" in result["content"]
        assert "  16: line 16" not in result["content"]


@pytest.mark.asyncio
async def test_read_with_pattern_search() -> None:
    """Test searching for pattern with context."""
    test_content = """def first_function():
    pass

def test_pattern():
    # This is the pattern
    return True

def another_function():
    pass"""

    mock_path = Path("/volumes/addons/test_module/models/test.py")

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_map.return_value = mock_path

        result = await read_odoo_file("/volumes/addons/test_module/models/test.py", pattern="test_pattern", context_lines=2)

        assert result["success"] is True
        assert result["pattern"] == "test_pattern"
        assert len(result["matches"]) == 1
        assert result["matches"][0]["line"] == 4
        assert "def test_pattern():" in result["matches"][0]["match"]


@pytest.mark.asyncio
async def test_read_from_docker_fallback() -> None:
    """Test falling back to docker when host mapping fails."""
    test_content = "docker content"

    mock_container = MagicMock()
    mock_exec_result = MagicMock()
    mock_exec_result.exit_code = 0
    mock_exec_result.output = (test_content.encode(), b"")
    mock_container.exec_run.return_value = mock_exec_result

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host", return_value=None),
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker_class,
    ):
        mock_docker = MagicMock()
        mock_docker.get_container.return_value = mock_container
        mock_docker_class.return_value = mock_docker

        result = await read_odoo_file("/odoo/addons/sale/models/sale.py")

        assert result["success"] is True
        assert result["via"] == "docker"
        assert "docker content" in result["content"]
        mock_container.exec_run.assert_called()


@pytest.mark.asyncio
async def test_read_relative_path_search() -> None:
    """Test searching for file in addon paths."""
    test_content = "found content"

    mock_path = Path("/volumes/addons/sale/models/sale.py")

    with (
        patch("odoo_intelligence_mcp.tools.addon.get_addon_paths.get_addon_paths_from_container") as mock_get_paths,
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_get_paths.return_value = ["/odoo/addons", "/volumes/addons", "/volumes/enterprise"]
        mock_map.return_value = mock_path

        result = await read_odoo_file("sale/models/sale.py")

        assert result["success"] is True
        assert "found content" in result["content"]


@pytest.mark.asyncio
async def test_file_not_found() -> None:
    """Test file not found error."""
    with (
        patch("odoo_intelligence_mcp.tools.addon.get_addon_paths.get_addon_paths_from_container") as mock_get_paths,
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host", return_value=None),
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker_class,
    ):
        mock_get_paths.return_value = ["/odoo/addons", "/volumes/addons"]
        mock_docker = MagicMock()
        mock_container = MagicMock()
        mock_docker.get_container.return_value = mock_container

        # Make all exec_run calls fail
        test_result = MagicMock()
        test_result.exit_code = 1
        mock_container.exec_run.return_value = test_result

        mock_docker_class.return_value = mock_docker

        result = await read_odoo_file("nonexistent/file.py")

        assert result["success"] is False
        assert "File not found" in result["error"]
        assert "searched_paths" in result


@pytest.mark.asyncio
async def test_invalid_pattern() -> None:
    """Test invalid regex pattern."""
    test_content = "some content"

    mock_path = Path("/volumes/addons/test_module/models/test.py")

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_map.return_value = mock_path

        result = await read_odoo_file("/volumes/addons/test_module/models/test.py", pattern="[invalid(regex")

        assert result["success"] is False
        assert "Invalid regex pattern" in result["error"]


@pytest.mark.asyncio
async def test_large_file_no_line_numbers() -> None:
    """Test that large files (>500 lines) don't get line numbers."""
    test_content = "\n".join(f"line {i}" for i in range(1, 1001))

    mock_path = Path("/volumes/addons/test_module/models/test.py")

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_map.return_value = mock_path

        result = await read_odoo_file("/volumes/addons/test_module/models/test.py")

        assert result["success"] is True
        assert result["total_lines"] == 1000
        # Should not have line numbers for large files
        assert "   1:" not in result["content"]
        assert "line 1" in result["content"]


@pytest.mark.asyncio
async def test_docker_container_error() -> None:
    """Test handling docker container errors."""
    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host", return_value=None),
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker_class,
    ):
        mock_docker = MagicMock()
        mock_docker.get_container.return_value = {"error": "Container not found", "success": False}
        mock_docker_class.return_value = mock_docker

        result = await read_odoo_file("/odoo/addons/sale/models/sale.py")

        assert result["success"] is False
        assert "Container error" in result["error"]


@pytest.mark.asyncio
async def test_out_of_range_line_numbers() -> None:
    """Test handling out of range line numbers."""
    test_content = "line 1\nline 2\nline 3"

    mock_path = Path("/volumes/addons/test_module/models/test.py")

    with (
        patch("odoo_intelligence_mcp.tools.code.read_odoo_file.map_container_path_to_host") as mock_map,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value=test_content),
    ):
        mock_map.return_value = mock_path

        result = await read_odoo_file("/volumes/addons/test_module/models/test.py", start_line=10, end_line=15)

        assert result["success"] is False
        assert "out of range" in result["error"]
