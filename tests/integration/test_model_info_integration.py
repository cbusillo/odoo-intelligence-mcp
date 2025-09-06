import pytest

from odoo_intelligence_mcp.tools.model.model_info import get_model_info
from odoo_intelligence_mcp.type_defs.odoo_types import CompatibleEnvironment


class TestModelInfoIntegration:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_res_partner(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_model_info(real_odoo_env_if_available, "res.partner")

        assert "error" not in result
        assert result["name"] == "res.partner"
        assert result["table"] == "res_partner"
        # Description can vary in customized Odoo installations
        assert "description" in result
        assert isinstance(result["description"], str)
        assert result["total_field_count"] > 0
        assert result["total_method_count"] > 0
        assert "pagination" in result
        assert result["displayed_field_count"] == len(result["fields"])

        # Check that we have paginated fields
        assert len(result["fields"]) <= result["pagination"]["page_size"]
        
        # Check that at least one field exists and has proper structure
        if result["fields"]:
            first_field_name = list(result["fields"].keys())[0]
            first_field = result["fields"][first_field_name]
            assert "type" in first_field
            assert "string" in first_field
            assert "required" in first_field
            assert "readonly" in first_field
            assert "store" in first_field

        # Check that we have a methods sample
        assert isinstance(result["methods_sample"], list)
        assert len(result["methods_sample"]) > 0
        assert len(result["methods_sample"]) <= 20  # Limited to 20 methods

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_product_template(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_model_info(real_odoo_env_if_available, "product.template")

        assert "error" not in result
        assert result["name"] == "product.template"
        assert result["table"] == "product_template"
        # Description can vary in customized Odoo installations
        assert "description" in result
        assert isinstance(result["description"], str)

        # Check relational fields
        if "categ_id" in result["fields"]:
            categ_field = result["fields"]["categ_id"]
            assert categ_field["type"] == "many2one"
            assert categ_field["relation"] == "product.category"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_motor_product_template(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_model_info(real_odoo_env_if_available, "motor.product.template")

        assert "error" not in result
        assert result["name"] == "motor.product.template"
        # Description can vary in customized Odoo installations
        assert "description" in result
        assert isinstance(result["description"], str)
        assert result["total_field_count"] > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_nonexistent_model(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await get_model_info(real_odoo_env_if_available, "nonexistent.model")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_selection_fields(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a model that has selection fields
        result = await get_model_info(real_odoo_env_if_available, "res.partner")

        # Find a selection field (e.g., type)
        if "type" in result["fields"]:
            type_field = result["fields"]["type"]
            if type_field["type"] == "selection":
                assert "selection" in type_field
                # Should be either a list or "Dynamic selection"
                assert isinstance(type_field["selection"], (list, str))
