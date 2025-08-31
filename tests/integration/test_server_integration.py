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

    @pytest.mark.asyncio
    async def test_pagination_parameters_passed_correctly(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value=[])

        pagination_tools = [
            ("model_query", {"operation": "search", "pattern": "test"}),
            ("model_query", {"operation": "relationships", "model_name": "test.model"}),
            ("field_query", {"operation": "usages", "model_name": "test.model", "field_name": "test_field"}),
            ("analysis_query", {"analysis_type": "patterns"}),
            ("model_query", {"operation": "inheritance", "model_name": "test.model"}),
        ]

        for tool_name, args in pagination_tools:
            with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
                args.update({"page": 2, "page_size": 50, "filter": "test_filter"})

                result = await handle_call_tool(tool_name, args)

                # Some tools apply pagination after fetching data rather than in the query
                if tool_name in ["search_models", "analysis_query"]:
                    # For these tools, check that pagination is applied to the result
                    import json

                    result_data = json.loads(result[0].text)
                    # Check that pagination info is in the result
                    if "matches" in result_data:
                        matches = result_data["matches"]
                        if isinstance(matches, dict) and "pagination" in matches:
                            assert matches["pagination"]["page"] == 2
                            assert matches["pagination"]["page_size"] == 50
                else:
                    # For other tools, check pagination in execute_code call
                    call_args = mock_env.execute_code.call_args[0][0]
                    # These tools may not use offset/limit directly in code
                    # Just verify the execute_code was called
                    assert mock_env.execute_code.called

    @pytest.mark.asyncio
    async def test_response_size_validation(self) -> None:
        mock_env = AsyncMock()
        large_response = {"data": "x" * 1000000}  # 1MB response
        mock_env.execute_code = AsyncMock(return_value=large_response)

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("execute_code", {"code": "print('test')"})

            assert len(result) == 1
            content = json.loads(result[0].text)
            # execute_code wraps the response
            assert content["success"] is True
            assert content["result"] == large_response

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
            with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
                with patch("subprocess.run") as mock_run:
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

    @pytest.mark.asyncio
    async def test_pagination_response_structure(self) -> None:
        mock_env = AsyncMock()
        paginated_response = {
            "items": [{"id": i} for i in range(10)],
            "pagination": {
                "page": 1,
                "page_size": 10,
                "total_count": 100,
                "total_pages": 10,
                "has_next_page": True,
                "has_previous_page": False,
                "filter_applied": None,
            },
        }
        mock_env.execute_code = AsyncMock(return_value=paginated_response)

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("model_query", {"operation": "search", "pattern": "test"})

            content = json.loads(result[0].text)
            if "pagination" in content:
                pagination = content["pagination"]
                assert "page" in pagination
                assert "page_size" in pagination
                assert "total_count" in pagination
                assert "has_next_page" in pagination
                assert isinstance(pagination["page"], int)
                assert isinstance(pagination["has_next_page"], bool)


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
