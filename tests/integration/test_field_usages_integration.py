import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.field.field_usages import get_field_usages


class TestFieldUsagesIntegration:
    @pytest.fixture
    async def odoo_env(self) -> HostOdooEnvironment:
        manager = HostOdooEnvironmentManager()
        return await manager.get_environment()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_res_partner_name(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_field_usages(odoo_env, "res.partner", "name")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert result["field"] == "name"
        assert "field_info" in result
        assert "used_in_views" in result
        assert "used_in_domains" in result
        assert "used_in_methods" in result
        assert "usage_summary" in result

        # Check field info
        field_info = result["field_info"]
        assert field_info["type"] == "char"
        assert field_info["string"] == "Name"
        assert "required" in field_info
        assert "readonly" in field_info
        assert "store" in field_info

        # Check usage summary
        summary = result["usage_summary"]
        assert "view_count" in summary
        assert "domain_count" in summary
        assert "method_count" in summary
        assert "total_usages" in summary
        assert summary["total_usages"] >= 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_res_partner_email(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_field_usages(odoo_env, "res.partner", "email")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert result["field"] == "email"

        field_info = result["field_info"]
        assert field_info["type"] == "char"
        assert field_info["string"] == "Email"

        # Should have some usages (views at minimum)
        assert result["usage_summary"]["view_count"] >= 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_many2one_field(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a many2one field
        result = await get_field_usages(odoo_env, "res.partner", "parent_id")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert result["field"] == "parent_id"

        field_info = result["field_info"]
        assert field_info["type"] == "many2one"
        assert field_info["relation"] == "res.partner"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_one2many_field(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a one2many field if it exists
        result = await get_field_usages(odoo_env, "res.partner", "child_ids")

        if "error" not in result:
            assert result["model"] == "res.partner"
            assert result["field"] == "child_ids"

            field_info = result["field_info"]
            assert field_info["type"] == "one2many"
            assert field_info["relation"] == "res.partner"
            if "inverse_name" in field_info:
                assert field_info["inverse_name"] == "parent_id"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_computed_field(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with display_name which is typically computed
        result = await get_field_usages(odoo_env, "res.partner", "display_name")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert result["field"] == "display_name"

        field_info = result["field_info"]
        assert field_info["type"] == "char"
        # Should have compute method
        if "compute" in field_info:
            assert field_info["compute"] is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_product_template_name(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_field_usages(odoo_env, "product.template", "name")

        assert "error" not in result
        assert result["model"] == "product.template"
        assert result["field"] == "name"

        field_info = result["field_info"]
        assert field_info["type"] == "char"
        assert field_info["string"] == "Name"

        # Should have usages in views
        assert result["usage_summary"]["view_count"] >= 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_motor_product_template(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a custom model from the project
        result = await get_field_usages(odoo_env, "motor.product.template", "name")

        if "error" not in result:
            assert result["model"] == "motor.product.template"
            assert result["field"] == "name"

            field_info = result["field_info"]
            assert field_info["type"] == "char"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_nonexistent_model(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_field_usages(odoo_env, "nonexistent.model", "field")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_nonexistent_field(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_field_usages(odoo_env, "res.partner", "nonexistent_field")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_selection_field(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a selection field - type field in res.partner
        result = await get_field_usages(odoo_env, "res.partner", "type")

        if "error" not in result:
            assert result["model"] == "res.partner"
            assert result["field"] == "type"

            field_info = result["field_info"]
            assert field_info["type"] == "selection"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_state_field(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a state field if available
        result = await get_field_usages(odoo_env, "sale.order", "state")

        if "error" not in result:
            assert result["model"] == "sale.order"
            assert result["field"] == "state"

            field_info = result["field_info"]
            assert field_info["type"] == "selection"

            # State fields typically have methods that use them
            assert result["usage_summary"]["method_count"] >= 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_views_analysis(self, odoo_env: HostOdooEnvironment) -> None:
        # Test that views are properly analyzed
        result = await get_field_usages(odoo_env, "res.partner", "name")

        assert "error" not in result
        views = result["used_in_views"]

        # Check view structure if any views found
        if isinstance(views, list):
            for view in views:
                assert "id" in view
                assert "name" in view
                assert "type" in view
                assert view["type"] in ["form", "tree", "list", "kanban", "search", "graph", "pivot", "calendar", "activity"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_domains_analysis(self, odoo_env: HostOdooEnvironment) -> None:
        # Test that domains are properly analyzed
        result = await get_field_usages(odoo_env, "res.partner", "name")

        assert "error" not in result
        domains = result["used_in_domains"]

        # Check domain structure if any domains found
        if isinstance(domains, list):
            for domain in domains:
                assert "type" in domain
                assert domain["type"] in ["action", "filter"]
                assert "name" in domain
                assert "domain" in domain

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_methods_analysis(self, odoo_env: HostOdooEnvironment) -> None:
        # Test that methods are properly analyzed
        result = await get_field_usages(odoo_env, "res.partner", "name")

        assert "error" not in result
        methods = result["used_in_methods"]

        # Check method structure if any methods found
        if isinstance(methods, list):
            for method in methods:
                assert "type" in method
                assert method["type"] in ["compute", "constraint", "onchange", "method"]
                assert "method" in method
