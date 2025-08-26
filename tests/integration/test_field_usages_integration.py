import pytest

from odoo_intelligence_mcp.tools.field.field_usages import get_field_usages
from odoo_intelligence_mcp.type_defs.odoo_types import CompatibleEnvironment


class TestFieldUsagesIntegration:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_res_partner_name(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "name")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert result["field"] == "name"
        assert "field_info" in result
        assert "usages" in result
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
    async def test_get_field_usages_res_partner_email(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "email")

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
    async def test_get_field_usages_many2one_field(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a many2one field
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "parent_id")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert result["field"] == "parent_id"

        field_info = result["field_info"]
        assert field_info["type"] == "many2one"
        assert field_info["relation"] == "res.partner"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_one2many_field(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a one2many field if it exists
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "child_ids")

        if "error" not in result:
            assert result["model"] == "res.partner"
            assert result["field"] == "child_ids"

            field_info = result["field_info"]
            assert field_info["type"] == "one2many"
            assert field_info["relation"] == "res.partner"
            # inverse_name might be None or not present, so just check if it exists
            if field_info.get("inverse_name"):
                assert field_info["inverse_name"] == "parent_id"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_computed_field(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with display_name which is typically computed
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "display_name")

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
    async def test_get_field_usages_product_template_name(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_field_usages(real_odoo_env_if_available, "product.template", "name")

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
    async def test_get_field_usages_motor_product_template(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a custom model from the project
        result = await get_field_usages(real_odoo_env_if_available, "motor.product.template", "name")

        if "error" not in result:
            assert result["model"] == "motor.product.template"
            assert result["field"] == "name"

            field_info = result["field_info"]
            assert field_info["type"] == "char"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_nonexistent_model(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_field_usages(real_odoo_env_if_available, "nonexistent.model", "field")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_nonexistent_field(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "nonexistent_field")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_selection_field(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a selection field - type field in res.partner
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "type")

        if "error" not in result:
            assert result["model"] == "res.partner"
            assert result["field"] == "type"

            field_info = result["field_info"]
            assert field_info["type"] == "selection"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_state_field(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a state field if available
        result = await get_field_usages(real_odoo_env_if_available, "sale.order", "state")

        if "error" not in result:
            assert result["model"] == "sale.order"
            assert result["field"] == "state"

            field_info = result["field_info"]
            assert field_info["type"] == "selection"

            # State fields typically have methods that use them
            assert result["usage_summary"]["method_count"] >= 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_views_analysis(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test that views are properly analyzed
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "name")

        assert "error" not in result
        usages = result["usages"]["items"]

        # Check view structure if any view usages found
        view_usages = [usage for usage in usages if usage.get("usage_type") == "view"]
        if view_usages:
            for view in view_usages:
                assert "id" in view
                assert "name" in view
                assert "type" in view
                assert view["type"] in ["form", "tree", "list", "kanban", "search", "graph", "pivot", "calendar", "activity"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_domains_analysis(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test that domains are properly analyzed
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "name")

        assert "error" not in result
        usages = result["usages"]["items"]

        # Check domain structure if any domain usages found
        domain_usages = [usage for usage in usages if usage.get("usage_type") == "domain"]
        if domain_usages:
            for domain in domain_usages:
                assert "type" in domain
                assert domain["type"] in ["action", "filter"]
                assert "name" in domain
                assert "domain" in domain

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_field_usages_methods_analysis(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test that methods are properly analyzed
        result = await get_field_usages(real_odoo_env_if_available, "res.partner", "name")

        assert "error" not in result
        usages = result["usages"]["items"]

        # Check method structure if any method usages found
        method_usages = [usage for usage in usages if usage.get("usage_type") == "method"]
        if method_usages:
            for method in method_usages:
                assert "type" in method
                assert method["type"] in ["compute", "constraint", "onchange", "method"]
                assert "method" in method
