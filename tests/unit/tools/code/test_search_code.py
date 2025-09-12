"""Simple test for search_code function (FS-first)."""

from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.tools.code.search_code import search_code


@pytest.mark.asyncio
async def test_search_code_basic() -> None:
    """Test basic search functionality."""
    pattern = "test_pattern"

    # Mock Docker exec to return a JSON list of matches
    mock_stdout = (
        "[\n"
        "  {\n"
        "    \"file\": \"/odoo/addons/test_module/models/test_model.py\",\n"
        "    \"line\": 5,\n"
        "    \"match\": \"    def test_pattern_method(self):\"\n"
        "  }\n"
        "]\n"
    )

    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": mock_stdout, "stderr": "", "exit_code": 0}

        result = await search_code(pattern)

        # Check result structure
        assert result.get("success") is True
        assert result.get("mode_used") == "fs"
        assert result.get("data_quality") == "approximate"
        assert "results" in result and "items" in result["results"]
        assert "pagination" in result["results"]

        # Should find the pattern in the file
        if result["results"]["items"]:
            item = result["results"]["items"][0]
            assert item["file"].endswith("test_model.py")
            assert item["line"] == 5
            assert pattern in item["match"]


@pytest.mark.asyncio
async def test_search_code_no_matches() -> None:
    """Test search with no matches."""
    pattern = "nonexistent_pattern_xyz123"

    # Mock empty results from container
    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": "[]", "stderr": "", "exit_code": 0}

        result = await search_code(pattern)

        assert result.get("success") is True
        assert result["results"]["pagination"]["total_count"] == 0
        assert result["results"]["items"] == []


@pytest.mark.asyncio
async def test_search_code_invalid_regex() -> None:
    """Test search with invalid regex pattern."""
    invalid_pattern = "[invalid(regex"

    result = await search_code(invalid_pattern)

    assert "error" in result
    assert "Invalid regex pattern" in result["error"]
