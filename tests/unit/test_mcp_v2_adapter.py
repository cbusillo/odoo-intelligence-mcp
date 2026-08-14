from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent

from odoo_intelligence_mcp.server import app, handle_call_tool_request, handle_list_tools_request


@pytest.fixture
def request_context() -> object:
    return MagicMock()


@pytest.mark.asyncio
async def test_list_tools_request_returns_v2_result(request_context: object) -> None:
    result = await handle_list_tools_request(request_context, None)

    assert isinstance(result, ListToolsResult)
    assert len(result.tools) >= 15
    assert all(tool.model_dump()["input_schema"]["type"] == "object" for tool in result.tools)
    assert "inputSchema" in result.model_dump(by_alias=True)["tools"][0]


@pytest.mark.asyncio
async def test_call_tool_request_dispatches_valid_arguments(request_context: object) -> None:
    content = [TextContent(type="text", text='{"success": true}')]
    request_parameters = CallToolRequestParams(name="odoo_status", arguments={"verbose": True})

    with patch("odoo_intelligence_mcp.server.handle_call_tool", new_callable=AsyncMock, return_value=content) as handle_call_tool:
        result = await handle_call_tool_request(request_context, request_parameters)

    assert isinstance(result, CallToolResult)
    assert result.content == content
    assert result.is_error is False
    assert result.model_dump(by_alias=True)["isError"] is False
    handle_call_tool.assert_awaited_once_with("odoo_status", {"verbose": True})


@pytest.mark.asyncio
async def test_call_tool_request_rejects_invalid_arguments(request_context: object) -> None:
    request_parameters = CallToolRequestParams(
        name="permission_checker",
        arguments={"user": "admin", "model": "res.partner", "operation": "delete"},
    )

    with patch("odoo_intelligence_mcp.server.handle_call_tool", new_callable=AsyncMock) as handle_call_tool:
        result = await handle_call_tool_request(request_context, request_parameters)

    assert isinstance(result, CallToolResult)
    assert result.is_error is True
    assert result.model_dump(by_alias=True)["isError"] is True
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text.startswith("Input validation error:")
    handle_call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_tool_request_converts_adapter_failures(request_context: object) -> None:
    request_parameters = CallToolRequestParams(name="odoo_status", arguments={"verbose": False})

    with patch("odoo_intelligence_mcp.server.handle_list_tools", new_callable=AsyncMock, side_effect=RuntimeError("schema failure")):
        result = await handle_call_tool_request(request_context, request_parameters)

    assert result.is_error is True
    assert result.model_dump(by_alias=True)["isError"] is True
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text == "schema failure"


def test_server_initialization_uses_registered_tool_handlers() -> None:
    initialization_options = app.create_initialization_options()

    assert initialization_options.server_name == "odoo-intelligence"
    assert initialization_options.server_version == "0.1.0"
    assert initialization_options.capabilities.tools is not None
