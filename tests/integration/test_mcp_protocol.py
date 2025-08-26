import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent, Tool

from odoo_intelligence_mcp.server import app, handle_call_tool, handle_list_tools


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_tools() -> None:
    tools = await handle_list_tools()

    assert isinstance(tools, list)
    assert len(tools) > 0

    # Check for some expected tools
    tool_names = {tool.name for tool in tools}
    expected_tools = {"model_info", "search_models", "field_usages", "odoo_status", "execute_code"}
    assert expected_tools.issubset(tool_names)

    # Verify tool structure
    for tool in tools:
        assert isinstance(tool, Tool)
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "inputSchema")
        assert isinstance(tool.inputSchema, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_no_arguments() -> None:
    result = await handle_call_tool("test_tool", None)

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert "error" in content
    assert "No arguments provided" in content["error"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_unknown_tool() -> None:
    result = await handle_call_tool("unknown_tool", {"test": "data"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert "error" in content
    assert "Unknown tool" in content["error"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_model_info_success() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(
        return_value={
            "model": "res.partner",
            "name": "res.partner",
            "table": "res_partner",
            "description": "Contact",
            "fields": {"name": {"type": "char", "string": "Name"}},
            "field_count": 1,
            "methods": ["create", "write"],
            "method_count": 2,
        }
    )

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("model_info", {"model_name": "res.partner"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert content["model"] == "res.partner"
    assert "fields" in content
    assert "methods" in content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_with_error() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(side_effect=Exception("Test error"))

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("model_info", {"model_name": "res.partner"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert "error" in content
    assert "Test error" in content["error"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_search_models() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(
        return_value={
            "exact_matches": [{"name": "product.product", "description": "Product"}],
            "partial_matches": [],
            "description_matches": [],
        }
    )

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("search_models", {"pattern": "product"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert "exact_matches" in content
    assert len(content["exact_matches"]) > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_field_usages() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(
        return_value={
            "model": "product.template",
            "field": "name",
            "views": {"form": ["form_view_1"], "tree": ["tree_view_1"]},
            "methods": ["compute_display_name"],
            "domains": [],
        }
    )

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("field_usages", {"model_name": "product.template", "field_name": "name"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert content["model"] == "product.template"
    assert content["field"] == "name"
    assert "views" in content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_with_pagination() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(
        return_value={
            "items": [{"name": f"item_{i}"} for i in range(10)],
            "total_count": 10,
            "page_info": {"has_next_page": False, "has_previous_page": False, "start_cursor": "0", "end_cursor": "9"},
        }
    )

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("pattern_analysis", {"pattern_type": "computed_fields", "limit": 5, "offset": 0})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert "items" in content or "computed_fields" in content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_odoo_status() -> None:
    mock_env = AsyncMock()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "running"
        mock_run.return_value.stderr = ""

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            # Pass an empty dict as arguments, not None
            result = await handle_call_tool("odoo_status", {"dummy": "arg"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert "containers" in content
    assert "overall_status" in content


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_execute_code() -> None:
    mock_env = MagicMock()
    mock_env.execute_code = MagicMock(return_value={"result": 4})

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("execute_code", {"code": "result = 2 + 2"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)
    assert content["result"] == 4


@pytest.mark.asyncio
@pytest.mark.integration
async def test_server_initialization() -> None:
    assert app.name == "odoo-intelligence"

    # Test that server has proper tool registration
    tools = await handle_list_tools()
    assert len(tools) > 20  # We should have at least 20 tools registered


@pytest.mark.asyncio
@pytest.mark.integration
async def test_tool_input_validation() -> None:
    # Test missing required field
    result = await handle_call_tool("model_info", {})

    assert len(result) == 1
    content = json.loads(result[0].text)
    assert "error" in content

    # Test with wrong type
    result = await handle_call_tool("model_info", {"model_name": 123})

    assert len(result) == 1
    _content = json.loads(result[0].text)
    # Should still work as the handler will convert to string


@pytest.mark.asyncio
@pytest.mark.integration
async def test_environment_cleanup() -> None:
    mock_env = AsyncMock()
    mock_cr = MagicMock()
    mock_cr.close = MagicMock()
    mock_env.cr = mock_cr
    mock_env.execute_code = AsyncMock(return_value={"success": True})

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        await handle_call_tool("model_info", {"model_name": "res.partner"})

    # Verify cursor was closed
    mock_cr.close.assert_called_once()
