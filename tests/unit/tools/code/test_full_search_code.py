from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.code.search_code import search_code


@pytest.mark.asyncio
async def test_search_code_basic_pattern() -> None:
    # Mock environment with search results
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(
        return_value=[
            {
                "file": "/addons/test_module/models/test_model.py",
                "line": 5,
                "match": "    def test_method(self):",
                "context": "    def test_method(self):",
            }
        ]
    )

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

        result = await search_code("test_method")

    assert "items" in result
    assert "pagination" in result
    assert len(result["items"]) == 1
    assert result["items"][0]["line"] == 5
    assert "test_method" in result["items"][0]["match"]


@pytest.mark.asyncio
async def test_search_code_xml_files() -> None:
    # Mock environment with XML search results
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(
        return_value=[
            {
                "file": "/addons/module/views/view.xml",
                "line": 5,
                "match": '        <field name="model">test.model</field>',
                "context": '        <field name="model">test.model</field>',
            }
        ]
    )

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

        result = await search_code("test\\.model", "xml")

    assert "items" in result
    assert "pagination" in result


@pytest.mark.asyncio
async def test_search_code_with_pagination() -> None:
    # Create many mock results
    mock_results = []
    for i in range(30):
        mock_results.append(
            {
                "file": f"/addons/module/models/model_{i}.py",
                "line": 10,
                "match": "def test_method(self):",
                "context": "def test_method(self):",
            }
        )

    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(return_value=mock_results)

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

        pagination = PaginationParams(limit=10, offset=0)
        result = await search_code("test_method", pagination=pagination)

    assert "items" in result
    assert "pagination" in result
    assert result["pagination"]["page_size"] == 10


@pytest.mark.asyncio
async def test_search_code_no_matches() -> None:
    # Mock environment with no results
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(return_value=[])

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

        result = await search_code("nonexistent_pattern")

    assert "items" in result
    assert len(result["items"]) == 0
    assert result["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_search_code_invalid_regex() -> None:
    # Invalid regex should be caught before execution
    result = await search_code("[invalid(regex")

    assert "error" in result
    assert "Invalid regex pattern" in result["error"]


@pytest.mark.asyncio
async def test_search_code_file_read_error() -> None:
    # Mock environment that returns an error
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(return_value={"error": "Failed to read file", "error_type": "IOError"})

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

        result = await search_code("test_pattern")

    assert "error" in result
    assert "Failed to read file" in result["error"]


@pytest.mark.asyncio
async def test_search_code_javascript_files() -> None:
    # Mock environment with JS search results
    mock_env = MagicMock()
    mock_env.execute_code = AsyncMock(
        return_value=[
            {
                "file": "/addons/module/static/src/js/widget.js",
                "line": 15,
                "match": "    testFunction: function() {",
                "context": "    testFunction: function() {",
            }
        ]
    )

    with patch("odoo_intelligence_mcp.core.env.HostOdooEnvironmentManager") as mock_manager:
        mock_manager.return_value.get_environment = AsyncMock(return_value=mock_env)

        result = await search_code("testFunction", "js")

    assert "items" in result
    assert len(result["items"]) == 1
    assert result["items"][0]["file"].endswith(".js")
    assert "testFunction" in result["items"][0]["match"]
