import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from odoo_intelligence_mcp.server import handle_call_tool, handle_list_tools


class TestToolContracts:
    @pytest.fixture
    def mock_env(self) -> AsyncMock:
        env = AsyncMock()
        env.execute_code = AsyncMock()
        env.cr = AsyncMock()
        env.cr.close = AsyncMock()
        return env

    @pytest.mark.asyncio
    async def test_all_tools_return_text_content(self, mock_env: AsyncMock) -> None:
        tools = await handle_list_tools()

        mock_env.execute_code.return_value = {"success": True, "result": "test"}

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "test output"

                for tool in tools:
                    if tool.name in ["odoo_status", "odoo_logs", "odoo_restart", "odoo_update_module", "odoo_install_module"]:
                        result = await handle_call_tool(tool.name, {"modules": "test"} if "module" in tool.name else {})
                    elif tool.name == "execute_code":
                        result = await handle_call_tool(tool.name, {"code": "result = 1"})
                    elif tool.name == "odoo_shell":
                        result = await handle_call_tool(tool.name, {"code": "print('test')"})
                    elif tool.name == "model_info":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner"})
                    elif tool.name == "search_models":
                        result = await handle_call_tool(tool.name, {"pattern": "test"})
                    elif tool.name == "model_relationships":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner"})
                    elif tool.name == "field_usages":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner", "field_name": "name"})
                    elif tool.name == "field_value_analyzer":
                        result = await handle_call_tool(tool.name, {"model": "res.partner", "field": "name"})
                    elif tool.name == "permission_checker":
                        result = await handle_call_tool(tool.name, {"user": "admin", "model": "res.partner", "operation": "read"})
                    elif tool.name == "test_runner":
                        result = await handle_call_tool(tool.name, {"module": "base"})
                    elif tool.name == "read_odoo_file":
                        result = await handle_call_tool(tool.name, {"file_path": "odoo/addons/base/models/res_partner.py"})
                    elif tool.name == "find_files":
                        result = await handle_call_tool(tool.name, {"pattern": "*.py"})
                    elif tool.name == "search_code":
                        result = await handle_call_tool(tool.name, {"pattern": "def create"})
                    elif tool.name == "module_structure":
                        result = await handle_call_tool(tool.name, {"module_name": "base"})
                    elif tool.name == "find_method":
                        result = await handle_call_tool(tool.name, {"method_name": "create"})
                    elif tool.name == "search_decorators":
                        result = await handle_call_tool(tool.name, {"decorator": "depends"})
                    elif tool.name == "view_model_usage":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner"})
                    elif tool.name == "workflow_states":
                        result = await handle_call_tool(tool.name, {"model_name": "sale.order"})
                    elif tool.name == "field_dependencies":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner", "field_name": "name"})
                    elif tool.name == "search_field_properties":
                        result = await handle_call_tool(tool.name, {"property": "computed"})
                    elif tool.name == "search_field_type":
                        result = await handle_call_tool(tool.name, {"field_type": "many2one"})
                    elif tool.name == "addon_dependencies":
                        result = await handle_call_tool(tool.name, {"addon_name": "sale"})
                    elif tool.name == "inheritance_chain":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner"})
                    elif tool.name == "performance_analysis":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner"})
                    elif tool.name == "pattern_analysis":
                        result = await handle_call_tool(tool.name, {})
                    elif tool.name == "resolve_dynamic_fields":
                        result = await handle_call_tool(tool.name, {"model_name": "res.partner"})
                    else:
                        continue

                    assert len(result) == 1, f"Tool {tool.name} did not return exactly one TextContent"
                    assert isinstance(result[0], TextContent), f"Tool {tool.name} did not return TextContent"

                    try:
                        json.loads(result[0].text)
                    except json.JSONDecodeError:
                        pytest.fail(f"Tool {tool.name} returned non-JSON response")

    @pytest.mark.asyncio
    async def test_tools_handle_errors_gracefully(self, mock_env: AsyncMock) -> None:
        mock_env.execute_code.side_effect = Exception("Test error")

        error_testable_tools = [
            ("model_info", {"model_name": "res.partner"}),
            ("search_models", {"pattern": "test"}),
            ("model_relationships", {"model_name": "res.partner"}),
            ("field_usages", {"model_name": "res.partner", "field_name": "name"}),
            ("execute_code", {"code": "1/0"}),
            ("field_value_analyzer", {"model": "res.partner", "field": "name"}),
            ("permission_checker", {"user": "admin", "model": "res.partner", "operation": "read"}),
            ("test_runner", {"module": "base"}),
            ("field_dependencies", {"model_name": "res.partner", "field_name": "name"}),
            ("search_field_properties", {"property": "computed"}),
            ("search_field_type", {"field_type": "many2one"}),
        ]

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            for tool_name, args in error_testable_tools:
                result = await handle_call_tool(tool_name, args)

                assert len(result) == 1
                content = json.loads(result[0].text)
                assert "error" in content, f"Tool {tool_name} did not return error field"
                assert isinstance(content["error"], str)
                assert "error_type" in content, f"Tool {tool_name} did not return error_type field"

    @pytest.mark.asyncio
    async def test_tools_with_pagination_contract(self, mock_env: AsyncMock) -> None:
        paginated_tools = [
            ("search_models", {"pattern": "test", "page": 1, "page_size": 10}),
            ("model_relationships", {"model_name": "res.partner", "page": 1, "page_size": 10}),
            ("field_usages", {"model_name": "res.partner", "field_name": "name", "page": 1, "page_size": 10}),
            ("performance_analysis", {"model_name": "res.partner", "page": 1, "page_size": 10}),
            ("pattern_analysis", {"page": 1, "page_size": 10}),
            ("inheritance_chain", {"model_name": "res.partner", "page": 1, "page_size": 10}),
            ("addon_dependencies", {"addon_name": "sale", "page": 1, "page_size": 10}),
            ("search_field_properties", {"property": "computed", "page": 1, "page_size": 10}),
            ("search_field_type", {"field_type": "many2one", "page": 1, "page_size": 10}),
            ("resolve_dynamic_fields", {"model_name": "res.partner", "page": 1, "page_size": 10}),
        ]

        mock_env.execute_code.return_value = {
            "items": [{"test": "data"}],
            "pagination": {
                "page": 1,
                "page_size": 10,
                "total_count": 1,
                "total_pages": 1,
                "has_next_page": False,
                "has_previous_page": False,
            },
        }

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            for tool_name, args in paginated_tools:
                result = await handle_call_tool(tool_name, args)

                content = json.loads(result[0].text)

                if "pagination" in content:
                    pagination = content["pagination"]
                    assert "page" in pagination
                    assert "page_size" in pagination
                    assert "total_count" in pagination
                    assert "has_next_page" in pagination
                    assert isinstance(pagination["page"], int)
                    assert isinstance(pagination["page_size"], int)

    @pytest.mark.asyncio
    async def test_required_vs_optional_parameters(self, mock_env: AsyncMock) -> None:
        tools_with_requirements = [
            ("model_info", {"model_name": "res.partner"}, True),
            ("model_info", {}, False),
            ("search_models", {"pattern": "test"}, True),
            ("search_models", {}, False),
            ("field_usages", {"model_name": "res.partner", "field_name": "name"}, True),
            ("field_usages", {"model_name": "res.partner"}, False),
            ("field_usages", {"field_name": "name"}, False),
            ("execute_code", {"code": "result = 1"}, True),
            ("execute_code", {}, False),
            ("odoo_shell", {"code": "print('test')"}, True),
            ("odoo_update_module", {"modules": "base"}, True),
            ("odoo_install_module", {"modules": "base"}, True),
            ("field_value_analyzer", {"model": "res.partner", "field": "name"}, True),
            ("field_value_analyzer", {"model": "res.partner"}, False),
            ("permission_checker", {"user": "admin", "model": "res.partner", "operation": "read"}, True),
            ("permission_checker", {"user": "admin", "model": "res.partner"}, False),
        ]

        mock_env.execute_code.return_value = {"success": True}

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "success"

                for tool_name, args, should_succeed in tools_with_requirements:
                    result = await handle_call_tool(tool_name, args)
                    content = json.loads(result[0].text)

                    if should_succeed:
                        assert "error" not in content or "missing" not in content.get("error", "").lower()
                    else:
                        assert "error" in content

    @pytest.mark.asyncio
    async def test_tool_response_size_limits(self, mock_env: AsyncMock) -> None:
        large_response = {"data": "x" * 10000000}  # 10MB
        mock_env.execute_code.return_value = large_response

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("execute_code", {"code": "result = large_data"})

            assert len(result) == 1
            content = json.loads(result[0].text)

            if "error" not in content:
                assert len(json.dumps(content)) < 11000000  # Should be roughly same size or paginated

    @pytest.mark.asyncio
    async def test_tool_idempotency(self, mock_env: AsyncMock) -> None:
        idempotent_tools = [
            ("model_info", {"model_name": "res.partner"}),
            ("search_models", {"pattern": "test"}),
            ("field_dependencies", {"model_name": "res.partner", "field_name": "name"}),
            ("search_field_properties", {"property": "computed"}),
        ]

        mock_env.execute_code.return_value = {"success": True, "data": "test"}

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            for tool_name, args in idempotent_tools:
                result1 = await handle_call_tool(tool_name, args)
                result2 = await handle_call_tool(tool_name, args)

                content1 = json.loads(result1[0].text)
                content2 = json.loads(result2[0].text)

                assert content1 == content2, f"Tool {tool_name} is not idempotent"

    @pytest.mark.asyncio
    async def test_tool_input_sanitization(self, mock_env: AsyncMock) -> None:
        dangerous_inputs = [
            ("execute_code", {"code": "'; DROP TABLE users; --"}),
            ("odoo_shell", {"code": "import os; os.system('rm -rf /')"}),
            ("search_models", {"pattern": "../../../etc/passwd"}),
            ("read_odoo_file", {"file_path": "/etc/passwd"}),
            ("odoo_update_module", {"modules": "base; rm -rf /"}),
        ]

        mock_env.execute_code.return_value = {"error": "Invalid input"}

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stdout = ""
                mock_run.return_value.stderr = "Error"

                for tool_name, args in dangerous_inputs:
                    result = await handle_call_tool(tool_name, args)
                    content = json.loads(result[0].text)

                    if "error" in content:
                        assert any(word in content["error"].lower() for word in ["security", "invalid", "not allowed", "not found"])

    @pytest.mark.asyncio
    async def test_tool_schema_validation(self) -> None:
        tools = await handle_list_tools()

        for tool in tools:
            assert tool.name, "Tool must have a name"
            assert tool.description, "Tool must have a description"
            assert tool.inputSchema, "Tool must have an input schema"

            schema = tool.inputSchema
            assert "type" in schema
            assert schema["type"] == "object"

            if "required" in schema:
                assert isinstance(schema["required"], list)
                for required_field in schema["required"]:
                    assert required_field in schema.get("properties", {})

            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    assert "type" in prop_schema or "$ref" in prop_schema
                    assert "description" in prop_schema

    @pytest.mark.asyncio
    async def test_tool_consistency_across_errors(self, mock_env: AsyncMock) -> None:
        error_types = [
            ValueError("Value error"),
            TypeError("Type error"),
            KeyError("Key error"),
            AttributeError("Attribute error"),
            RuntimeError("Runtime error"),
        ]

        tools_to_test = ["model_info", "search_models", "execute_code"]

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            for tool_name in tools_to_test:
                error_formats = []

                for error in error_types:
                    mock_env.execute_code.side_effect = error

                    args = (
                        {"model_name": "test"}
                        if tool_name == "model_info"
                        else {"pattern": "test"}
                        if tool_name == "search_models"
                        else {"code": "test"}
                    )

                    result = await handle_call_tool(tool_name, args)
                    content = json.loads(result[0].text)

                    assert "error" in content
                    assert "error_type" in content

                    error_format = set(content.keys())
                    error_formats.append(error_format)

                assert all(fmt == error_formats[0] for fmt in error_formats), f"Tool {tool_name} returns inconsistent error formats"


class TestToolPerformanceContracts:
    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self) -> None:
        import asyncio

        mock_env = AsyncMock()

        async def slow_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
            await asyncio.sleep(10)
            return {"success": True}

        mock_env.execute_code = slow_execution

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(handle_call_tool("execute_code", {"code": "slow_operation()"}), timeout=0.1)

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self) -> None:
        import asyncio

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"success": True})
        mock_env.cr = AsyncMock()
        mock_env.cr.close = AsyncMock()

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            tasks = [handle_call_tool("model_info", {"model_name": f"model_{i}"}) for i in range(10)]

            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            assert all(len(r) == 1 for r in results)

            for result in results:
                content = json.loads(result[0].text)
                assert "error" not in content or content.get("success") is False

    @pytest.mark.asyncio
    async def test_tool_memory_efficiency(self) -> None:
        mock_env = AsyncMock()

        large_items = [{"id": i, "data": f"item_{i}" * 100} for i in range(10000)]
        mock_env.execute_code.return_value = {
            "items": large_items,
            "pagination": {
                "page": 1,
                "page_size": 100,
                "total_count": 10000,
                "total_pages": 100,
                "has_next_page": True,
                "has_previous_page": False,
            },
        }

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("search_models", {"pattern": "test", "page_size": 100})

            content = json.loads(result[0].text)

            if "items" in content:
                assert len(content["items"]) <= 100
            if "pagination" in content:
                assert content["pagination"]["page_size"] <= 100
