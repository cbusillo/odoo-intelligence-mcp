import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.model.search_models import search_models


class TestSearchModelsIntegration:
    @pytest.fixture
    async def odoo_env(self) -> HostOdooEnvironment:
        manager = HostOdooEnvironmentManager()
        return await manager.get_environment()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_product_pattern(self, odoo_env: HostOdooEnvironment) -> None:
        result = await search_models(odoo_env, "product")

        assert "error" not in result
        assert "exact_matches" in result
        assert "partial_matches" in result
        assert "description_matches" in result
        assert "total_models" in result
        assert result["total_models"] > 0

        # Check that product models are found
        all_matches = result["exact_matches"] + result["partial_matches"] + result["description_matches"]
        product_model_names = [m["name"] for m in all_matches]

        # Common product models should be found
        assert any("product.template" in name for name in product_model_names)
        assert any("product.product" in name for name in product_model_names)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_exact_match(self, odoo_env: HostOdooEnvironment) -> None:
        result = await search_models(odoo_env, "res.partner")

        assert "error" not in result
        assert len(result["exact_matches"]) == 1
        assert result["exact_matches"][0]["name"] == "res.partner"
        assert result["exact_matches"][0]["description"] == "Contact"
        assert result["exact_matches"][0]["table"] == "res_partner"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_case_insensitive(self, odoo_env: HostOdooEnvironment) -> None:
        result_lower = await search_models(odoo_env, "partner")
        result_upper = await search_models(odoo_env, "PARTNER")

        # Should find same models regardless of case
        lower_names = {m["name"] for m in result_lower["partial_matches"]}
        upper_names = {m["name"] for m in result_upper["partial_matches"]}

        assert lower_names == upper_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_motor_models(self, odoo_env: HostOdooEnvironment) -> None:
        result = await search_models(odoo_env, "motor")

        assert "error" not in result

        # Check if motor models exist
        all_matches = result["exact_matches"] + result["partial_matches"] + result["description_matches"]

        if all_matches:
            motor_models = [m for m in all_matches if "motor" in m["name"]]
            assert len(motor_models) > 0

            # Verify motor model properties
            for model in motor_models:
                assert "name" in model
                assert "description" in model
                assert "table" in model
                assert "transient" in model
                assert "abstract" in model

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_no_results(self, odoo_env: HostOdooEnvironment) -> None:
        result = await search_models(odoo_env, "xyz123nonexistent")

        assert "error" not in result
        assert len(result["exact_matches"]) == 0
        assert len(result["partial_matches"]) == 0
        assert len(result["description_matches"]) == 0
        assert result["total_models"] > 0  # Should still count all models

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_transient_models(self, odoo_env: HostOdooEnvironment) -> None:
        # Search for wizard models which are typically transient
        result = await search_models(odoo_env, "wizard")

        assert "error" not in result

        # Check if any transient models are found
        all_matches = result["exact_matches"] + result["partial_matches"] + result["description_matches"]

        transient_models = [m for m in all_matches if m.get("transient")]
        if transient_models:
            assert all(m["transient"] is True for m in transient_models)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_models_description_search(self, odoo_env: HostOdooEnvironment) -> None:
        # Search for "user" which should match in descriptions
        result = await search_models(odoo_env, "user")

        assert "error" not in result

        # Should find res.users in exact or partial matches
        all_name_matches = result["exact_matches"] + result["partial_matches"]
        user_model_names = [m["name"] for m in all_name_matches]
        assert "res.users" in user_model_names

        # Should also find models with "user" in description
        if result["description_matches"]:
            for match in result["description_matches"]:
                assert "user" in match["description"].lower()
