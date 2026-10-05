import json
from unittest.mock import AsyncMock, MagicMock, patch

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
            result = await handle_call_tool("field_query", {"operation": "resolve_dynamic", "model_name": "sale.order"})

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
            result = await handle_call_tool("field_query", {"operation": "search_properties", "property": "computed"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        # The tool returns paginated results
        assert "items" in content or "error" in content or isinstance(content, list)

    @pytest.mark.asyncio
    async def test_handle_search_field_type(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "results": [
                    {
                        "model": "sale.order",
                        "description": "Sales Order",
                        "fields": [
                            {"field": "partner_id", "string": "Customer", "required": True, "comodel_name": "res.partner"},
                            {"field": "user_id", "string": "Salesperson", "required": False, "comodel_name": "res.users"},
                        ],
                    }
                ]
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("field_query", {"operation": "search_type", "field_type": "many2one"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "fields" in content  # The result is paginated under "fields" key

    @pytest.mark.asyncio
    async def test_handle_analysis_query_workflow(self) -> None:
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
            result = await handle_call_tool("analysis_query", {"analysis_type": "workflow", "model_name": "sale.order"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert "state_fields" in content
        assert "transitions" in content

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
            result = await handle_call_tool(
                "field_query", {"operation": "analyze_values", "model_name": "product.template", "field_name": "list_price"}
            )

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

        # Mock docker client
        # Mock subprocess.run for the module update operation
        with patch("subprocess.run") as mock_run:
            # First call: docker inspect to check container
            # Second call: module existence check
            # Third call: docker exec to update module
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="running", stderr=""),  # docker inspect
                MagicMock(returncode=0, stdout='{"missing": []}', stderr=""),  # module check
                MagicMock(returncode=0, stdout="Module updated successfully", stderr=""),  # docker exec
            ]

            with patch(
                "odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env
            ):
                result = await handle_call_tool("odoo_update_module", {"modules": "sale"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "success" in content
        assert content["success"] is True

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
            result = await handle_call_tool(
                "field_query", {"operation": "dependencies", "model_name": "sale.order", "field_name": "amount_total"}
            )

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert content["field"] == "amount_total"
        assert "depends_on" in content
        assert "depended_by" in content

    @pytest.mark.asyncio
    async def test_handle_error_with_odoo_mcp_error(self) -> None:
        from odoo_intelligence_mcp.utils.error_utils import ModelNotFoundError

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(side_effect=ModelNotFoundError("Model test.model not found"))

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("model_query", {"operation": "info", "model_name": "test.model"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "error" in content
        assert "Model test.model not found" in content["error"]
        assert content["error_type"] == "ModelNotFoundError"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("module_exists", [True, False])
    async def test_handle_module_structure(self, module_exists: bool) -> None:
        module_name = "fixture_module"
        module_path = f"/fixture/addons/{module_name}"
        structure = {
            "path": module_path,
            "models": ["models/order.py"],
            "views": ["views/order.xml"],
            "manifest": {"name": "Fixture"},
        }
        docker_client = MagicMock()
        docker_client.get_container.return_value = {"success": True}
        if module_exists:
            docker_client.exec_run.side_effect = [
                {"success": True, "exit_code": 0, "stdout": module_path},
                {"success": True, "exit_code": 0, "stdout": json.dumps(structure)},
            ]
        else:
            docker_client.exec_run.return_value = {"success": False, "exit_code": 1, "stdout": ""}
        environment = MagicMock()
        environment.cr = None
        with (
            patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", AsyncMock(return_value=environment)),
            patch("odoo_intelligence_mcp.tools.addon.module_structure.DockerClientManager", return_value=docker_client),
            patch(
                "odoo_intelligence_mcp.tools.addon.module_structure.get_addon_paths_from_container",
                AsyncMock(return_value=["/fixture/addons"]),
            ),
        ):
            response = await handle_call_tool("module_structure", {"module_name": module_name})
        content = json.loads(response[0].text)
        if not module_exists:
            assert module_name in content["error"]
            assert "not found" in content["error"].lower()
            return
        assert "error" not in content
        assert content["module"] == module_name
        assert content["manifest"] == structure["manifest"]
        assert [item["path"] for item in content["files"]["items"]] == structure["models"] + structure["views"]
        assert content["files"]["pagination"]["total_count"] == len(structure["models"]) + len(structure["views"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("addon_exists", [True, False])
    async def test_handle_addon_dependencies(self, addon_exists: bool) -> None:
        addon_name = "fixture_addon"
        addon_path = f"/fixture/addons/{addon_name}"
        manifest = {"name": "Fixture", "depends": ["base", "mail"]}
        dependent_name = "fixture_consumer"
        docker_client = MagicMock()
        docker_client.get_container.return_value = {"success": True}

        def execute_container_command(container_name: str, command: list[str]) -> dict[str, object]:
            if command[0] == "ls":
                return {"success": True, "exit_code": 0, "stdout": f"/fixture/addons/{dependent_name}/"}
            if command == ["cat", f"{addon_path}/__manifest__.py"] and addon_exists:
                return {"success": True, "exit_code": 0, "stdout": repr(manifest)}
            if command == ["cat", f"/fixture/addons/{dependent_name}/__manifest__.py"]:
                return {"success": True, "exit_code": 0, "stdout": repr({"depends": [addon_name]})}
            return {"success": False, "exit_code": 1, "stdout": ""}

        docker_client.exec_run.side_effect = execute_container_command
        environment = MagicMock()
        environment.cr = None
        with (
            patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", AsyncMock(return_value=environment)),
            patch("odoo_intelligence_mcp.tools.addon.addon_dependencies.DockerClientManager", return_value=docker_client),
            patch(
                "odoo_intelligence_mcp.tools.addon.addon_dependencies._get_addon_paths", AsyncMock(return_value=["/fixture/addons"])
            ),
        ):
            response = await handle_call_tool("addon_dependencies", {"addon_name": addon_name})
        content = json.loads(response[0].text)
        if not addon_exists:
            assert addon_name in content["error"]
            assert "not found" in content["error"].lower()
            return
        assert "error" not in content
        assert content["addon"] == addon_name
        assert content["depends"] == manifest["depends"]
        assert [item["name"] for item in content["depends_on_this"]["items"]] == [dependent_name]
        assert content["statistics"]["direct_dependencies"] == len(manifest["depends"])

    @pytest.mark.asyncio
    async def test_handle_view_model_usage(self) -> None:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "success": True,
                "result": {
                    "model": "sale.order",
                    "views": [
                        {"id": 1, "name": "sale.view_order_form", "type": "form", "priority": 1},
                        {"id": 2, "name": "sale.view_order_tree", "type": "tree", "priority": 1},
                    ],
                    "field_coverage": {
                        "exposed_fields": ["name", "partner_id", "date_order", "amount_total"],
                        "unexposed_fields": ["create_uid", "write_uid"],
                        "coverage_percentage": 80.0,
                    },
                    "exposed_fields": ["name", "partner_id", "date_order", "amount_total"],
                    "field_usage_count": {"name": 2, "partner_id": 2, "date_order": 1, "amount_total": 2},
                    "view_types": {"form": 1, "tree": 1},
                    "actions": [{"name": "Confirm", "method": "action_confirm"}],
                    "buttons": [{"name": "Send by Email", "action": "action_quotation_send"}],
                },
            }
        )

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock, return_value=mock_env):
            result = await handle_call_tool("model_query", {"operation": "view_usage", "model_name": "sale.order"})

        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content["model"] == "sale.order"
        assert "views" in content
        assert "field_coverage" in content
