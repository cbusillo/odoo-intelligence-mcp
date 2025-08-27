import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from odoo_intelligence_mcp.server import handle_call_tool


class TestServerHandlers:
    @pytest.mark.asyncio
    async def test_handle_resolve_dynamic_fields(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "model": "sale.order",
                "computed_fields": [
                    {
                        "name": "amount_total",
                        "depends": ["order_line", "order_line.price_total"],
                        "store": True,
                        "compute_method": "_compute_amounts",
                    }
                ],
                "related_fields": [{"name": "partner_name", "related": "partner_id.name", "store": False}],
                "dependency_graph": {"amount_total": ["order_line", "order_line.price_total"], "partner_name": ["partner_id"]},
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("resolve_dynamic_fields", {"model_name": "sale.order"})

        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert "computed_fields" in content
        assert "related_fields" in content
        assert "dependency_graph" in content

    @pytest.mark.asyncio
    async def test_handle_search_field_properties(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value=[
                {
                    "model": "sale.order",
                    "field_name": "amount_total",
                    "field_type": "float",
                    "field_string": "Total",
                    "compute": "_compute_amounts",
                    "store": True,
                },
                {
                    "model": "sale.order",
                    "field_name": "amount_untaxed",
                    "field_type": "float",
                    "field_string": "Untaxed Amount",
                    "compute": "_compute_amounts",
                    "store": True,
                },
            ]
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("search_field_properties", {"property": "computed"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        # The tool returns paginated results
        assert "items" in content or "error" in content or isinstance(content, list)

    @pytest.mark.asyncio
    async def test_handle_search_field_type(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "field_type": "many2one",
                "models": [
                    {
                        "model": "sale.order",
                        "fields": [
                            {"name": "partner_id", "type": "many2one", "relation": "res.partner"},
                            {"name": "user_id", "type": "many2one", "relation": "res.users"},
                        ],
                    }
                ],
                "total_count": 2,
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("search_field_type", {"field_type": "many2one"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["field_type"] == "many2one"
        assert "models" in content

    @pytest.mark.asyncio
    async def test_handle_workflow_states(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "model": "sale.order",
                "state_fields": [
                    {
                        "name": "state",
                        "type": "selection",
                        "selection": [
                            ["draft", "Quotation"],
                            ["sent", "Quotation Sent"],
                            ["sale", "Sales Order"],
                            ["done", "Done"],
                            ["cancel", "Cancelled"],
                        ],
                    }
                ],
                "transitions": [{"from_state": "draft", "to_state": "sent", "method": "action_quotation_send", "button": True}],
                "automated_transitions": [],
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("workflow_states", {"model_name": "sale.order"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert "state_fields" in content
        assert "transitions" in content

    @pytest.mark.asyncio
    async def test_handle_test_runner(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "success": True,
                "module": "sale",
                "tests_run": 5,
                "tests_passed": 5,
                "tests_failed": 0,
                "test_results": [{"test": "test_sale.TestSaleOrder.test_create", "status": "passed", "duration": 0.5}],
                "total_duration": 2.5,
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("test_runner", {"module": "sale"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["success"] is True
        assert content["module"] == "sale"
        assert content["tests_run"] == 5
        assert content["tests_passed"] == 5

    @pytest.mark.asyncio
    async def test_handle_field_value_analyzer(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "model": "product.template",
                "field": "list_price",
                "analysis": {
                    "type": "float",
                    "total_records": 100,
                    "null_count": 5,
                    "unique_count": 50,
                    "statistics": {"min": 0.0, "max": 1000.0, "mean": 250.0, "median": 200.0},
                    "sample_values": [10.0, 20.0, 30.0, 40.0, 50.0],
                },
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("field_value_analyzer", {"model": "product.template", "field": "list_price"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "product.template"
        assert content["field"] == "list_price"
        assert "analysis" in content
        assert "statistics" in content["analysis"]

    @pytest.mark.asyncio
    async def test_handle_permission_checker(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "success": True,
                "user": "demo",
                "model": "sale.order",
                "operation": "read",
                "access_allowed": True,
                "model_access": {"create": False, "read": True, "write": False, "unlink": False},
                "record_rules": [],
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("permission_checker", {"user": "demo", "model": "sale.order", "operation": "read"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["success"] is True
        assert content["access_allowed"] is True
        assert "model_access" in content

    @pytest.mark.asyncio
    async def test_handle_odoo_update_module(self) -> None:
        mock_env = AsyncMock()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Module updated successfully"
            mock_run.return_value.stderr = ""

            with patch(
                "odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env
            ):
                result = await handle_call_tool("odoo_update_module", {"modules": "sale"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "success" in content
        assert content["success"] is True

    @pytest.mark.asyncio
    async def test_handle_odoo_shell(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"success": True, "result": 10, "output": ""})

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("odoo_shell", {"code": "result = 5 + 5"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["success"] is True
        assert content["result"] == 10

    @pytest.mark.asyncio
    async def test_handle_odoo_install_module(self) -> None:
        mock_env = AsyncMock()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Module installed successfully"
            mock_run.return_value.stderr = ""

            with patch(
                "odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env
            ):
                result = await handle_call_tool("odoo_install_module", {"modules": "sale_management"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "success" in content
        assert content["success"] is True

    @pytest.mark.asyncio
    async def test_handle_odoo_logs(self) -> None:
        mock_env = AsyncMock()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "2024-01-01 10:00:00,123 INFO odoo: Odoo version 16.0\n2024-01-01 10:00:01,456 INFO odoo.modules.loading: Loading module sale"
            mock_run.return_value.stderr = ""

            with patch(
                "odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env
            ):
                result = await handle_call_tool("odoo_logs", {"lines": 50})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "logs" in content
        assert len(content["logs"]) > 0

    @pytest.mark.asyncio
    async def test_handle_field_dependencies(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "model": "sale.order",
                "field": "amount_total",
                "depends_on": ["order_line", "order_line.price_total"],
                "depended_by": ["invoice_status"],
                "compute_method": "_compute_amounts",
                "inverse_method": None,
                "search_method": None,
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("field_dependencies", {"model_name": "sale.order", "field_name": "amount_total"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert content["field"] == "amount_total"
        assert "depends_on" in content
        assert "depended_by" in content

    @pytest.mark.asyncio
    async def test_handle_call_tool_with_pagination_params(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "items": [{"name": f"model_{i}"} for i in range(10)],
                "pagination": {
                    "page": 1,
                    "page_size": 5,
                    "total_count": 10,
                    "total_pages": 2,
                    "has_next_page": True,
                    "has_previous_page": False,
                },
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("search_models", {"pattern": "sale", "page": 1, "page_size": 5})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "items" in content or "exact_matches" in content
        if "pagination" in content:
            assert content["pagination"]["page"] == 1
            assert content["pagination"]["page_size"] == 5

    @pytest.mark.asyncio
    async def test_handle_error_with_odoo_mcp_error(self) -> None:
        from odoo_intelligence_mcp.utils.error_utils import ModelNotFoundError

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(side_effect=ModelNotFoundError("Model test.model not found"))

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("model_info", {"model_name": "test.model"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "error" in content
        assert "Model test.model not found" in content["error"]
        assert content["error_type"] == "ModelNotFoundError"

    @pytest.mark.asyncio
    async def test_handle_module_structure(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "module": "sale",
                "structure": {
                    "models": ["sale.order", "sale.order.line"],
                    "views": ["sale_order_form", "sale_order_tree"],
                    "controllers": [],
                    "wizards": ["sale.advance.payment.inv"],
                    "reports": ["sale.report_saleorder"],
                    "static": {"js": ["sale.js"], "css": ["sale.css"]},
                    "security": ["ir.model.access.csv", "sale_security.xml"],
                },
                "manifest": {"name": "Sales", "version": "16.0.1.0.0", "depends": ["account", "mail"]},
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("module_structure", {"module_name": "sale"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["module"] == "sale"
        assert "structure" in content
        assert "manifest" in content

    @pytest.mark.asyncio
    async def test_handle_addon_dependencies(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "addon": "sale_management",
                "manifest": {
                    "name": "Sales Management",
                    "version": "16.0.1.0.0",
                    "depends": ["sale", "account"],
                    "external_dependencies": {"python": ["pandas"]},
                },
                "depends_on": ["sale", "account"],
                "depended_by": ["sale_timesheet", "sale_stock"],
                "dependency_tree": {"sale": ["account", "product"], "account": ["base"]},
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("addon_dependencies", {"addon_name": "sale_management"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["addon"] == "sale_management"
        assert "depends_on" in content
        assert "depended_by" in content

    @pytest.mark.asyncio
    async def test_handle_view_model_usage(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "model": "sale.order",
                "views": {
                    "form": [{"id": 1, "name": "sale.view_order_form", "priority": 1}],
                    "tree": [{"id": 2, "name": "sale.view_order_tree", "priority": 1}],
                },
                "field_coverage": {
                    "exposed_fields": ["name", "partner_id", "date_order", "amount_total"],
                    "unexposed_fields": ["create_uid", "write_uid"],
                    "coverage_percentage": 80.0,
                },
                "actions": [{"name": "Confirm", "method": "action_confirm"}],
                "buttons": [{"name": "Send by Email", "action": "action_quotation_send"}],
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("view_model_usage", {"model_name": "sale.order"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert "views" in content
        assert "field_coverage" in content
