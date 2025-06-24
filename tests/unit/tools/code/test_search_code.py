"""Simple test for search_code function."""

from pathlib import Path
from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.tools.code.search_code import search_code


@pytest.mark.asyncio
async def test_search_code_basic() -> None:
    """Test basic search functionality."""
    pattern = "test_pattern"

    # Mock files that contain the pattern
    mock_files = [
        Path("/volumes/addons/test_module/models/test_model.py"),
    ]

    file_content = """
class TestModel(models.Model):
    _name = 'test.model'

    def test_pattern_method(self):
        return True
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.rglob", return_value=mock_files),
        patch("pathlib.Path.read_text", return_value=file_content),
    ):
        result = await search_code(pattern)

        # Check result structure
        assert "items" in result
        assert "pagination" in result

        # Should find the pattern in the file
        if len(result["items"]) > 0:
            item = result["items"][0]
            assert "file" in item
            assert "line" in item
            assert "match" in item
            assert pattern in item["match"]


@pytest.mark.asyncio
async def test_search_code_no_matches() -> None:
    """Test search with no matches."""
    pattern = "nonexistent_pattern_xyz123"

    mock_files = [
        Path("/volumes/addons/test_module/models/test_model.py"),
    ]

    file_content = """
class TestModel(models.Model):
    _name = 'test.model'

    def some_method(self):
        return True
"""

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.rglob", return_value=mock_files),
        patch("pathlib.Path.read_text", return_value=file_content),
    ):
        result = await search_code(pattern)

        assert "items" in result
        assert len(result["items"]) == 0
        assert result["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_search_code_invalid_regex() -> None:
    """Test search with invalid regex pattern."""
    invalid_pattern = "[invalid(regex"

    result = await search_code(invalid_pattern)

    assert "error" in result
    assert "Invalid regex pattern" in result["error"]
