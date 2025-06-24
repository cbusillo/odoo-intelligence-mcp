from unittest.mock import AsyncMock, MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.view_model_usage import get_view_model_usage


class TestViewModelUsageCoroutineFix:
    """
    Test suite demonstrating coroutine issues in view_model_usage and defining expected behavior.

    The main issues are:
    1. search() returns a coroutine that isn't awaited before iteration
    2. Accessing view attributes on coroutine objects
    3. Iterating over coroutine results
    """

    @pytest.mark.asyncio
    async def test_view_model_usage_handles_view_search(self, mock_odoo_env: MagicMock) -> None:
        """Test that view_model_usage properly handles search() returning coroutines."""
        model_name = "sale.order"

        # Mock the model
        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Order Reference", type="char"),
            "partner_id": MagicMock(string="Customer", type="many2one"),
            "date_order": MagicMock(string="Order Date", type="datetime"),
            "amount_total": MagicMock(string="Total", type="monetary"),
            "state": MagicMock(string="Status", type="selection"),
        }

        # Mock views
        mock_views = [
            MagicMock(
                name="sale.order.form",
                type="form",
                xml_id="sale.view_order_form",
                arch='<form><field name="name"/><field name="partner_id"/></form>',
            ),
            MagicMock(
                name="sale.order.tree",
                type="tree",
                xml_id="sale.view_order_tree",
                arch='<tree><field name="name"/><field name="amount_total"/></tree>',
            ),
        ]

        # Mock the view model with async search
        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=mock_views)

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        # Execute the function
        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should handle async search and iterate over views
        assert result["model"] == model_name
        assert len(result["views"]) == 2
        assert result["views"][0]["name"] == "sale.order.form"
        assert result["views"][1]["name"] == "sale.order.tree"
        assert "name" in result["exposed_fields"]
        assert "partner_id" in result["exposed_fields"]
        assert "amount_total" in result["exposed_fields"]

    @pytest.mark.asyncio
    async def test_view_model_usage_handles_empty_search_results(self, mock_odoo_env: MagicMock) -> None:
        """Test view_model_usage when search returns empty results via coroutine."""
        model_name = "custom.model"

        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Name", type="char"),
            "active": MagicMock(string="Active", type="boolean"),
        }

        # Mock empty search result
        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=[])

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should handle empty results gracefully
        assert result["model"] == model_name
        assert len(result["views"]) == 0
        assert len(result["exposed_fields"]) == 0
        assert result["field_coverage"]["total_fields"] == 2
        assert result["field_coverage"]["exposed_fields"] == 0
        assert result["field_coverage"]["coverage_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_view_model_usage_complex_view_parsing(self, mock_odoo_env: MagicMock) -> None:
        """Test complex view parsing with nested structures and multiple field references."""
        model_name = "project.task"

        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Task Name", type="char"),
            "project_id": MagicMock(string="Project", type="many2one"),
            "user_id": MagicMock(string="Assigned to", type="many2one"),
            "stage_id": MagicMock(string="Stage", type="many2one"),
            "priority": MagicMock(string="Priority", type="selection"),
            "description": MagicMock(string="Description", type="html"),
            "tag_ids": MagicMock(string="Tags", type="many2many"),
            "subtask_count": MagicMock(string="Subtasks", type="integer"),
        }

        # Complex form view
        complex_arch = """
        <form string="Task">
            <header>
                <field name="stage_id" widget="statusbar"/>
                <button name="action_assign" string="Assign" type="object"/>
            </header>
            <sheet>
                <div class="oe_title">
                    <field name="name" placeholder="Task Title"/>
                </div>
                <group>
                    <group>
                        <field name="project_id"/>
                        <field name="user_id" widget="many2one_avatar_user"/>
                        <field name="priority" widget="priority"/>
                    </group>
                    <group>
                        <field name="tag_ids" widget="many2many_tags"/>
                        <field name="subtask_count" invisible="1"/>
                    </group>
                </group>
                <notebook>
                    <page string="Description">
                        <field name="description" widget="html"/>
                    </page>
                </notebook>
            </sheet>
            <div class="oe_chatter">
                <field name="message_follower_ids"/>
            </div>
        </form>
        """

        mock_views = [
            MagicMock(name="project.task.form", type="form", xml_id="project.view_task_form", arch=complex_arch),
            MagicMock(
                name="project.task.kanban",
                type="kanban",
                xml_id="project.view_task_kanban",
                arch="""
                <kanban default_group_by="stage_id">
                    <field name="name"/>
                    <field name="user_id"/>
                    <field name="priority"/>
                    <field name="project_id"/>
                    <templates>
                        <t t-name="kanban-box">
                            <div>
                                <field name="name"/>
                            </div>
                        </t>
                    </templates>
                </kanban>
                """,
            ),
        ]

        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=mock_views)

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should parse all fields and buttons correctly
        assert len(result["views"]) == 2

        # Check form view
        form_view = next(v for v in result["views"] if v["type"] == "form")
        assert form_view["name"] == "project.task.form"
        form_fields = [f["name"] for f in form_view["fields_used"]]
        assert "name" in form_fields
        assert "stage_id" in form_fields
        assert "user_id" in form_fields
        assert "description" in form_fields
        assert "subtask_count" in form_fields  # Even invisible fields

        # Check buttons
        assert len(form_view["buttons"]) > 0
        button_names = [b["name"] for b in form_view["buttons"] if "name" in b]
        assert "action_assign" in button_names

        # Check field coverage
        assert result["field_coverage"]["total_fields"] == 8
        assert result["field_coverage"]["exposed_fields"] >= 7  # All except message_follower_ids

    @pytest.mark.asyncio
    async def test_view_model_usage_multiple_view_types(self, mock_odoo_env: MagicMock) -> None:
        """Test handling of multiple view types including form, tree, search, kanban, graph."""
        model_name = "account.move"

        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Number", type="char"),
            "partner_id": MagicMock(string="Partner", type="many2one"),
            "date": MagicMock(string="Date", type="date"),
            "amount_total": MagicMock(string="Total", type="monetary"),
            "state": MagicMock(string="Status", type="selection"),
            "move_type": MagicMock(string="Type", type="selection"),
        }

        mock_views = [
            MagicMock(
                name="account.move.form",
                type="form",
                xml_id="account.view_move_form",
                arch='<form><field name="name"/><field name="partner_id"/><field name="date"/></form>',
            ),
            MagicMock(
                name="account.move.tree",
                type="tree",
                xml_id="account.view_move_tree",
                arch='<tree><field name="name"/><field name="date"/><field name="amount_total"/></tree>',
            ),
            MagicMock(
                name="account.move.search",
                type="search",
                xml_id="account.view_move_search",
                arch="""
                <search>
                    <field name="name"/>
                    <field name="partner_id"/>
                    <filter name="draft" domain="[('state','=','draft')]"/>
                    <filter name="posted" domain="[('state','=','posted')]"/>
                    <group expand="0" string="Group By">
                        <filter name="by_partner" context="{'group_by':'partner_id'}"/>
                    </group>
                </search>
                """,
            ),
            MagicMock(
                name="account.move.kanban",
                type="kanban",
                xml_id="account.view_move_kanban",
                arch='<kanban><field name="name"/><field name="state"/></kanban>',
            ),
            MagicMock(
                name="account.move.graph",
                type="graph",
                xml_id="account.view_move_graph",
                arch='<graph><field name="date" type="row"/><field name="amount_total" type="measure"/></graph>',
            ),
        ]

        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=mock_views)

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should handle all view types
        assert len(result["views"]) == 5
        assert len(result["view_types"]) == 5
        assert "form" in result["view_types"]
        assert "tree" in result["view_types"]
        assert "search" in result["view_types"]
        assert "kanban" in result["view_types"]
        assert "graph" in result["view_types"]

        # Check field usage count
        assert result["field_usage_count"]["name"] >= 4  # Used in form, tree, search, kanban
        assert result["field_usage_count"]["date"] >= 2  # Used in form, tree, graph
        assert result["field_usage_count"]["amount_total"] >= 2  # Used in tree, graph

    @pytest.mark.asyncio
    async def test_view_model_usage_with_inheritance(self, mock_odoo_env: MagicMock) -> None:
        """Test view model usage with inherited views."""
        model_name = "res.partner"

        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Name", type="char"),
            "email": MagicMock(string="Email", type="char"),
            "phone": MagicMock(string="Phone", type="char"),
            "is_company": MagicMock(string="Is Company", type="boolean"),
            "customer_rank": MagicMock(string="Customer Rank", type="integer"),
            "supplier_rank": MagicMock(string="Supplier Rank", type="integer"),
        }

        # Base view and inherited view
        mock_views = [
            MagicMock(
                name="res.partner.form",
                type="form",
                xml_id="base.view_partner_form",
                arch='<form><field name="name"/><field name="email"/></form>',
            ),
            MagicMock(
                name="res.partner.form.inherit.sale",
                type="form",
                xml_id="sale.view_partner_form_inherit",
                arch="""
                <xpath expr="//field[@name='email']" position="after">
                    <field name="customer_rank"/>
                </xpath>
                """,
            ),
            MagicMock(
                name="res.partner.form.inherit.purchase",
                type="form",
                xml_id="purchase.view_partner_form_inherit",
                arch="""
                <xpath expr="//form" position="inside">
                    <group>
                        <field name="supplier_rank"/>
                    </group>
                </xpath>
                """,
            ),
        ]

        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=mock_views)

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should detect fields from all views including inherited
        assert "name" in result["exposed_fields"]
        assert "email" in result["exposed_fields"]
        assert "customer_rank" in result["exposed_fields"]
        assert "supplier_rank" in result["exposed_fields"]

        # Check unexposed fields
        unexposed = result["field_coverage"]["unexposed_fields"]
        assert "phone" in unexposed
        assert "is_company" in unexposed

    @pytest.mark.asyncio
    async def test_view_model_usage_error_recovery(self, mock_odoo_env: MagicMock) -> None:
        """Test that view_model_usage handles errors gracefully during async operations."""
        model_name = "test.model"

        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Name", type="char"),
        }

        # Mock view with invalid arch that might cause parsing issues
        mock_views = [
            MagicMock(
                name="test.view",
                type="form",
                xml_id="test.view_form",
                arch="<form><field name='name'/><invalid_tag/></form>",  # Invalid but parseable
            ),
            MagicMock(
                name="test.view2",
                type="tree",
                xml_id="test.view_tree",
                arch=None,  # No arch
            ),
        ]

        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=mock_views)

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should handle views with issues gracefully
        assert result["model"] == model_name
        assert len(result["views"]) == 2
        # Should still extract field from first view
        assert "name" in result["exposed_fields"]

    @pytest.mark.asyncio
    async def test_view_model_usage_with_computed_fields(self, mock_odoo_env: MagicMock) -> None:
        """Test view model usage with computed and related fields."""
        model_name = "product.template"

        mock_model = MagicMock()
        mock_model._name = model_name
        mock_model._fields = {
            "name": MagicMock(string="Name", type="char"),
            "list_price": MagicMock(string="Sale Price", type="float"),
            "standard_price": MagicMock(string="Cost", type="float"),
            "margin": MagicMock(string="Margin", type="float", compute="_compute_margin"),
            "display_name": MagicMock(string="Display Name", type="char", compute="_compute_display_name"),
            "partner_ref": MagicMock(string="Partner Ref", type="char", related="seller_ids.partner_id.ref"),
        }

        mock_views = [
            MagicMock(
                name="product.template.form",
                type="form",
                xml_id="product.view_template_form",
                arch="""
                <form>
                    <field name="name"/>
                    <field name="list_price"/>
                    <field name="standard_price"/>
                    <field name="margin" readonly="1"/>
                    <field name="display_name" invisible="1"/>
                </form>
                """,
            ),
        ]

        mock_view_model = MagicMock()
        mock_view_model.search = AsyncMock(return_value=mock_views)

        mock_odoo_env.env = {
            model_name: mock_model,
            "ir.ui.view": mock_view_model,
        }

        result = await get_view_model_usage(mock_odoo_env, model_name)

        # Expected behavior: Should detect all fields including computed/invisible
        assert "margin" in result["exposed_fields"]
        assert "display_name" in result["exposed_fields"]
        assert "partner_ref" not in result["exposed_fields"]  # Not in any view

        # Verify field info includes compute info
        form_view = result["views"][0]
        margin_field = next((f for f in form_view["fields_used"] if f["name"] == "margin"), None)
        assert margin_field is not None
        assert margin_field["type"] == "float"
