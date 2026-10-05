import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from odoo_intelligence_mcp.server import TOOL_HANDLERS, handle_call_tool
from odoo_intelligence_mcp.utils.error_utils import (
    CodeExecutionError,
    DockerConnectionError,
    FieldNotFoundError,
    InvalidArgumentError,
    ModelNotFoundError,
)


class TestServerIntegration:
    @pytest.fixture
    def mock_env_with_cleanup(self) -> AsyncMock:
        env = AsyncMock()
        env.cr = MagicMock()
        env.cr.close = MagicMock()
        return env

    @pytest.mark.asyncio
    async def test_all_handlers_defined(self) -> None:
        from odoo_intelligence_mcp.server import handle_list_tools

        tools = await handle_list_tools()
        tool_names = {tool.name for tool in tools}

        for tool_name in tool_names:
            assert tool_name in TOOL_HANDLERS, f"Tool {tool_name} has no handler defined"
            assert callable(TOOL_HANDLERS[tool_name]), f"Handler for {tool_name} is not callable"

    @pytest.mark.asyncio
    async def test_handler_error_types_properly_formatted(self, mock_env_with_cleanup: AsyncMock) -> None:
        test_errors = [
            (ModelNotFoundError("test.model"), "ModelNotFoundError"),
            (FieldNotFoundError("model", "field"), "FieldNotFoundError"),
            (InvalidArgumentError("bad_arg", "str", 123), "InvalidArgumentError"),
            (DockerConnectionError("test-container", "connection failed"), "DockerConnectionError"),
            (CodeExecutionError("bad code", "syntax error"), "CodeExecutionError"),
            (ValueError("generic error"), "ValueError"),
        ]

        for error, expected_type in test_errors:
            mock_env_with_cleanup.execute_code = AsyncMock(side_effect=error)

            with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env_with_cleanup):
                result = await handle_call_tool("model_query", {"operation": "info", "model_name": "test.model"})

                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                content = json.loads(result[0].text)
                assert "error" in content
                assert "error_type" in content
                assert content["error_type"] == expected_type

    @pytest.mark.asyncio
    async def test_cursor_cleanup_on_success(self, mock_env_with_cleanup: AsyncMock) -> None:
        mock_env_with_cleanup.execute_code = AsyncMock(return_value={"success": True})

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env_with_cleanup):
            await handle_call_tool("model_query", {"operation": "info", "model_name": "res.partner"})

        mock_env_with_cleanup.cr.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cursor_cleanup_on_failure(self, mock_env_with_cleanup: AsyncMock) -> None:
        mock_env_with_cleanup.execute_code = AsyncMock(side_effect=Exception("Test error"))

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env_with_cleanup):
            await handle_call_tool("model_query", {"operation": "info", "model_name": "res.partner"})

        mock_env_with_cleanup.cr.close.assert_called_once()

    # noinspection PyUnusedLocal

    @pytest.mark.asyncio
    async def test_execution_response_preserves_payload(self) -> None:
        mock_env = AsyncMock()
        execution_payload = {"data": "fixture text", "records": [{"name": "fixture"}]}
        mock_env.execute_code = AsyncMock(return_value=execution_payload)

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("execute_code", {"code": "print('test')"})

            assert len(result) == 1
            content = json.loads(result[0].text)
            # execute_code wraps the response
            assert content["success"] is True
            assert content["result"] == execution_payload

    @pytest.mark.asyncio
    async def test_concurrent_handler_execution(self) -> None:
        import asyncio

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"success": True})
        mock_env.cr = MagicMock()
        mock_env.cr.close = MagicMock()

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            tasks = [handle_call_tool("model_query", {"operation": "info", "model_name": f"model_{i}"}) for i in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(len(r) == 1 for r in results)
            assert mock_env.cr.close.call_count == 5

    @pytest.mark.asyncio
    async def test_invalid_tool_name_handling(self) -> None:
        result = await handle_call_tool("nonexistent_tool", {"test": "data"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "error" in content
        assert "Unknown tool" in content["error"]

    @pytest.mark.asyncio
    async def test_missing_required_arguments(self) -> None:
        mock_env = AsyncMock()

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("model_query", {"operation": "info"})

            assert len(result) == 1
            content = json.loads(result[0].text)
            assert "error" in content

    @pytest.mark.asyncio
    async def test_optional_argument_defaults(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"success": True})

        tools_with_optionals = [
            ("odoo_status", {}),
            ("odoo_restart", {}),
            ("field_query", {"operation": "analyze_values", "model_name": "test", "field_name": "name"}),
        ]

        for tool_name, required_args in tools_with_optionals:
            with (
                patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env),
                patch("subprocess.run") as mock_run,
            ):
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "success"

                result = await handle_call_tool(tool_name, required_args)
                assert len(result) == 1
                content = json.loads(result[0].text)
                assert "error" not in content or content.get("success") is False


class TestToolResponseContracts:
    @pytest.mark.asyncio
    async def test_all_responses_json_serializable(self) -> None:
        mock_env = AsyncMock()
        test_responses = [
            {"simple": "dict"},
            {"nested": {"data": ["list", "of", "items"]}},
            {"numbers": [1, 2.5, -3]},
            {"booleans": [True, False, None]},
        ]

        for response in test_responses:
            # execute_code wraps the response with success and result
            wrapped_response = {"success": True, "result": response}
            mock_env.execute_code = AsyncMock(return_value=wrapped_response)

            with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
                result = await handle_call_tool("execute_code", {"code": "test"})

                assert len(result) == 1
                assert isinstance(result[0], TextContent)
                parsed = json.loads(result[0].text)
                assert parsed == wrapped_response

    @pytest.mark.asyncio
    async def test_error_response_structure(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(side_effect=ValueError("Test error"))

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("model_query", {"operation": "info", "model_name": "test"})

            content = json.loads(result[0].text)
            assert "error" in content
            assert isinstance(content["error"], str)
            assert "error_type" in content
            assert isinstance(content["error_type"], str)


class TestResourceManagement:
    @pytest.mark.asyncio
    async def test_no_resource_leak_on_exception(self) -> None:
        mock_env = AsyncMock()
        mock_env.cr = MagicMock()
        mock_env.cr.close = MagicMock()

        exceptions_to_test = [
            KeyError("missing key"),
            AttributeError("missing attr"),
            TypeError("type error"),
            json.JSONDecodeError("json error", "", 0),
        ]

        for exc in exceptions_to_test:
            mock_env.execute_code = AsyncMock(side_effect=exc)
            mock_env.cr.close.reset_mock()

            with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
                result = await handle_call_tool("model_query", {"operation": "info", "model_name": "test"})

                assert mock_env.cr.close.called
                content = json.loads(result[0].text)
                assert "error" in content

    @pytest.mark.asyncio
    async def test_environment_manager_singleton(self) -> None:
        from odoo_intelligence_mcp.server import odoo_env_manager

        assert odoo_env_manager is not None
        with patch.object(odoo_env_manager, "get_environment") as mock_get:
            mock_get.return_value = AsyncMock()

            await handle_call_tool("model_query", {"operation": "info", "model_name": "test1"})
            await handle_call_tool("model_query", {"operation": "info", "model_name": "test2"})

            assert mock_get.call_count == 2
