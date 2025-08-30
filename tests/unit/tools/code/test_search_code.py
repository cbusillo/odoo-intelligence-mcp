"""Simple test for search_code function."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.code.search_code import search_code


@pytest.mark.asyncio
async def test_search_code_basic() -> None:
    """Test basic search functionality."""
    pattern = "test_pattern"

    # Mock the environment manager and execute_code
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(
        return_value=[
            {
                "file": "/odoo/addons/test_module/models/test_model.py",
                "line": 5,
                "match": "    def test_pattern_method(self):",
                "context": "    def test_pattern_method(self):",
            }
        ]
    )

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

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

    # Mock empty results
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(return_value=[])

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

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
