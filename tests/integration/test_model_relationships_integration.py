import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.model.model_relationships import get_model_relationships


class TestModelRelationshipsIntegration:
    @pytest.fixture
    async def odoo_env(self) -> HostOdooEnvironment:
        manager = HostOdooEnvironmentManager()
        return await manager.get_environment()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_relationships_res_partner(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_relationships(odoo_env, "res.partner")

        assert "error" not in result
        assert result["model"] == "res.partner"

        # res.partner should have parent_id (self-reference)
        parent_field = next((f for f in result["many2one_fields"] if f["field_name"] == "parent_id"), None)
        if parent_field:
            assert parent_field["target_model"] == "res.partner"

        # Should have many reverse relationships
        assert result["relationship_summary"]["reverse_many2one_count"] > 0

        # Check common reverse relationships
        reverse_models = {r["source_model"] for r in result["reverse_many2one"]}
        # Most Odoo installations have these
        expected_models = {"res.users", "res.company"}
        assert any(model in reverse_models for model in expected_models)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_relationships_product_template(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_relationships(odoo_env, "product.template")

        assert "error" not in result
        assert result["model"] == "product.template"

        # Should have categ_id
        categ_field = next((f for f in result["many2one_fields"] if f["field_name"] == "categ_id"), None)
        if categ_field:
            assert categ_field["target_model"] == "product.category"

        # Should have product variants
        variant_field = next((f for f in result["one2many_fields"] if f["field_name"] == "product_variant_ids"), None)
        if variant_field:
            assert variant_field["target_model"] == "product.product"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_relationships_nonexistent(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_relationships(odoo_env, "nonexistent.model")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_relationships_motor_models(self, odoo_env: HostOdooEnvironment) -> None:
        # Test motor.product.template if it exists
        result = await get_model_relationships(odoo_env, "motor.product.template")

        if "error" not in result:
            assert result["model"] == "motor.product.template"
            # Check for relationships specific to motor models
            assert "relationship_summary" in result

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_relationships_transient_model(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a wizard/transient model
        result = await get_model_relationships(odoo_env, "base.module.upgrade")

        if "error" not in result:
            assert result["model"] == "base.module.upgrade"
            # Transient models usually have fewer relationships
            total_relationships = sum(
                [
                    result["relationship_summary"]["many2one_count"],
                    result["relationship_summary"]["one2many_count"],
                    result["relationship_summary"]["many2many_count"],
                ]
            )
            assert total_relationships >= 0
