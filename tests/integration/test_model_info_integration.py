import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.model.model_info import get_model_info


class TestModelInfoIntegration:
    @pytest.fixture
    async def odoo_env(self) -> HostOdooEnvironment:
        manager = HostOdooEnvironmentManager()
        return await manager.get_environment()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_res_partner(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_info(odoo_env, "res.partner")

        assert "error" not in result
        assert result["name"] == "res.partner"
        assert result["table"] == "res_partner"
        assert result["description"] == "Contact"
        assert result["field_count"] > 0
        assert result["method_count"] > 0

        # Check some common fields exist
        assert "name" in result["fields"]
        assert "email" in result["fields"]
        assert "phone" in result["fields"]

        # Check field properties
        name_field = result["fields"]["name"]
        assert name_field["type"] == "char"
        assert name_field["string"] == "Name"
        assert "store" in name_field

        # Check some common methods exist
        assert "create" in result["methods"]
        assert "write" in result["methods"]
        assert "search" in result["methods"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_product_template(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_info(odoo_env, "product.template")

        assert "error" not in result
        assert result["name"] == "product.template"
        assert result["table"] == "product_template"
        assert result["description"] == "Product"

        # Check relational fields
        if "categ_id" in result["fields"]:
            categ_field = result["fields"]["categ_id"]
            assert categ_field["type"] == "many2one"
            assert categ_field["relation"] == "product.category"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_motor_product_template(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_info(odoo_env, "motor.product.template")

        assert "error" not in result
        assert result["name"] == "motor.product.template"
        assert result["description"] == "Motor Product Template"
        assert result["field_count"] > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_nonexistent_model(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_model_info(odoo_env, "nonexistent.model")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_model_info_selection_fields(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a model that has selection fields
        result = await get_model_info(odoo_env, "res.partner")

        # Find a selection field (e.g., type)
        if "type" in result["fields"]:
            type_field = result["fields"]["type"]
            if type_field["type"] == "selection":
                assert "selection" in type_field
                # Should be either a list or "Dynamic selection"
                assert isinstance(type_field["selection"], (list, str))
