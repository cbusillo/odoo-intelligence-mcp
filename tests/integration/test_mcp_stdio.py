import json
from unittest.mock import AsyncMock, patch

import pytest

from odoo_intelligence_mcp.server import run_server


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_initialize_request() -> None:
    # Mock the app.run method directly instead of trying to simulate the protocol
    with patch("odoo_intelligence_mcp.server.app.run") as mock_run:
        # Make the mock return immediately
        mock_run.return_value = None

        # Call run_server which will set up the app and call app.run
        with patch("odoo_intelligence_mcp.server.stdio_server") as mock_stdio:
            mock_read = AsyncMock()
            mock_write = AsyncMock()
            mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)

            await run_server()

            # Verify app.run was called with correct initialization options
            mock_run.assert_called_once()
            init_options = mock_run.call_args[0][2]
            assert init_options.server_name == "odoo-intelligence"
            assert init_options.server_version == "0.1.0"
            assert hasattr(init_options.capabilities, "tools")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_list_tools_request() -> None:
    # Import the handle_list_tools function
    from odoo_intelligence_mcp.server import handle_list_tools

    # Get the tools list
    tools = await handle_list_tools()

    # Verify we have tools
    assert len(tools) > 0
    assert all(hasattr(tool, "name") for tool in tools)
    assert all(hasattr(tool, "description") for tool in tools)

    # Check specific tools exist
    tool_names = [tool.name for tool in tools]
    assert "model_info" in tool_names
    assert "search_models" in tool_names
    assert "execute_code" in tool_names
    assert "odoo_shell" in tool_names
    assert "odoo_update_module" in tool_names

    # Verify all tools have proper schemas
    assert all(hasattr(tool, "inputSchema") for tool in tools)

    # Check we have at least 25 tools
    assert len(tools) >= 25


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_call_tool_request() -> None:
    from odoo_intelligence_mcp.server import handle_call_tool

    # Mock the environment
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(
        return_value={
            "model": "res.partner",
            "name": "res.partner",
            "description": "Contact",
            "table": "res_partner",
            "rec_name": "name",
            "order": "id",
            "fields": {"name": {"type": "char", "string": "Name", "required": True}, "email": {"type": "char", "string": "Email"}},
            "methods": ["create", "write", "read"],
            "field_count": 2,
            "method_count": 3,
        }
    )

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        # Test calling the model_info tool
        result = await handle_call_tool("model_info", {"model_name": "res.partner"})

        # Verify result structure
        assert result is not None
        assert len(result) > 0
        assert result[0].type == "text"

        # Parse the JSON response
        content = json.loads(result[0].text)
        assert content["model"] == "res.partner"
        assert "fields" in content
        assert "methods" in content
        assert content["field_count"] == 2
        assert content["method_count"] == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_error_handling() -> None:
    from odoo_intelligence_mcp.server import handle_call_tool

    # Test with missing required argument
    result = await handle_call_tool("model_info", {})

    # Should return an error response
    assert result is not None
    assert len(result) > 0
    assert result[0].type == "text"

    # Parse the error response
    content = json.loads(result[0].text)
    assert "error" in content
    assert content["success"] is False

    # Test with invalid tool name
    result = await handle_call_tool("invalid_tool", {"some": "params"})
    assert result is not None
    assert len(result) > 0
    content = json.loads(result[0].text)
    assert "error" in content
    assert "Unknown tool" in content["error"]

    # Test with invalid model name
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(side_effect=Exception("Model not found"))

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("model_info", {"model_name": "invalid.model"})

        assert result is not None
        assert len(result) > 0
        content = json.loads(result[0].text)
        assert "error" in content or content.get("success") is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_server_function() -> None:
    with patch("odoo_intelligence_mcp.server.stdio_server") as mock_stdio:
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)

        with patch("odoo_intelligence_mcp.server.app.run") as mock_run:
            mock_run.return_value = None

            await run_server()

            mock_stdio.assert_called_once()
            mock_run.assert_called_once()

            # Check initialization options
            init_options = mock_run.call_args[0][2]
            assert init_options.server_name == "odoo-intelligence"
            assert init_options.server_version == "0.1.0"
            assert hasattr(init_options.capabilities, "tools")
