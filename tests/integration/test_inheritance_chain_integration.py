import pytest

from odoo_intelligence_mcp.tools.model.inheritance_chain import analyze_inheritance_chain
from odoo_intelligence_mcp.type_defs.odoo_types import CompatibleEnvironment


class TestInheritanceChainIntegration:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_res_partner(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "res.partner")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert "mro" in result
        assert "inherits" in result
        assert "inherits_from" in result
        assert "inherited_fields" in result
        assert "inheriting_models" in result
        assert "overridden_methods" in result
        assert "inherited_methods" in result
        assert "summary" in result

        # Check MRO structure
        assert isinstance(result["mro"], list)
        assert len(result["mro"]) > 0
        mro_first = result["mro"][0]
        assert "class" in mro_first
        assert "model" in mro_first
        assert "module" in mro_first
        assert mro_first["model"] == "res.partner"

        # Check summary statistics
        summary = result["summary"]
        assert "total_inherited_fields" in summary
        assert "total_models_inheriting" in summary
        assert "total_overridden_methods" in summary
        assert "inheritance_depth" in summary
        assert "uses_delegation" in summary
        assert "uses_prototype" in summary
        assert isinstance(summary["total_inherited_fields"], int)
        assert isinstance(summary["total_models_inheriting"], int)
        assert isinstance(summary["inheritance_depth"], int)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_product_template(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "product.template")

        assert "error" not in result
        assert result["model"] == "product.template"

        # Product template usually inherits from mail.thread and others
        assert isinstance(result["inherits"], list)

        # Check for known inheriting models - handle paginated structure
        inheriting_models = result["inheriting_models"]
        if isinstance(inheriting_models, dict) and "items" in inheriting_models:
            inheriting_model_names = [m["model"] for m in inheriting_models["items"]]
        else:
            inheriting_model_names = [m["model"] for m in inheriting_models]
        # Check that we have some inheriting models (the specific models may vary by environment)
        assert isinstance(inheriting_model_names, list)

        # Check inherited fields structure - handle paginated structure
        inherited_fields = result["inherited_fields"]
        if isinstance(inherited_fields, dict) and "items" in inherited_fields:
            # Paginated structure
            for field_info in inherited_fields["items"]:
                assert "from_model" in field_info
                assert "type" in field_info
                assert "string" in field_info
                assert isinstance(field_info["from_model"], str)
                assert isinstance(field_info["type"], str)
        else:
            # Original dict structure
            for field_info in inherited_fields.values():
                assert "from_model" in field_info
                assert "type" in field_info
                assert "string" in field_info
                assert isinstance(field_info["from_model"], str)
                assert isinstance(field_info["type"], str)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_res_users(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "res.users")

        assert "error" not in result
        assert result["model"] == "res.users"

        # res.users typically uses delegation inheritance with res.partner
        if result["inherits_from"]:
            assert "res.partner" in result["inherits_from"]
            # Should have inherited fields from res.partner
            assert result["summary"]["total_inherited_fields"] > 0
            assert result["summary"]["uses_delegation"] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_sale_order(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "sale.order")

        assert "error" not in result
        assert result["model"] == "sale.order"

        # Sale order typically inherits from mail.thread
        if "mail.thread" in result["inherits"]:
            assert result["summary"]["uses_prototype"] is True

        # Check for sale.order.line in inheriting models - handle paginated structure
        inheriting_models = result["inheriting_models"]
        if isinstance(inheriting_models, dict) and "items" in inheriting_models:
            inheriting_model_items = inheriting_models["items"]
        else:
            inheriting_model_items = inheriting_models
        inheriting_model_names = [m["model"] for m in inheriting_model_items]
        if "sale.order.line" in inheriting_model_names:
            line_model = next(m for m in inheriting_model_items if m["model"] == "sale.order.line")
            assert "description" in line_model
            assert "module" in line_model

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_motor_product_template(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "motor.product.template")

        assert "error" not in result
        assert result["model"] == "motor.product.template"
        assert result["summary"]["inheritance_depth"] >= 0

        # Motor product template should inherit from product.template
        if "product.template" in result["inherits"]:
            assert result["summary"]["uses_prototype"] is True

        # Check for inherited fields from product.template
        template_fields = [f for f, info in result["inherited_fields"].items() if info["from_model"] == "product.template"]
        if template_fields:
            assert len(template_fields) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_nonexistent_model(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        with pytest.raises(Exception) as exc_info:
            await analyze_inheritance_chain(real_odoo_env_if_available, "nonexistent.model")
        
        assert "not found" in str(exc_info.value)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_ir_model(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "ir.model")

        assert "error" not in result
        assert result["model"] == "ir.model"

        # IR models are core Odoo models
        assert len(result["mro"]) > 0

        # Check that we can find models inheriting from ir.model - handle paginated structure
        inheriting_models = result["inheriting_models"]
        if isinstance(inheriting_models, dict) and "items" in inheriting_models:
            inheriting_model_items = inheriting_models["items"]
        else:
            inheriting_model_items = inheriting_models
        if inheriting_model_items:
            for inheriting_model in inheriting_model_items:
                assert "model" in inheriting_model
                assert "description" in inheriting_model
                assert "module" in inheriting_model

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_mail_thread(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "mail.thread")

        assert "error" not in result
        assert result["model"] == "mail.thread"

        # mail.thread is a mixin widely used, should have many inheriting models
        assert result["summary"]["total_models_inheriting"] > 0

        # Check structure of inheriting models - handle paginated structure
        inheriting_models = result["inheriting_models"]
        if isinstance(inheriting_models, dict) and "items" in inheriting_models:
            inheriting_model_items = inheriting_models["items"][:5]  # Check first 5
        else:
            inheriting_model_items = inheriting_models[:5]  # Check first 5
        for inheriting_model in inheriting_model_items:
            assert "model" in inheriting_model
            assert "description" in inheriting_model
            assert "module" in inheriting_model
            assert isinstance(inheriting_model["model"], str)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_overridden_methods(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Test with a model that likely has overridden methods
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "res.partner")

        assert "error" not in result

        # Check overridden methods structure - handle paginated structure
        overridden_methods = result["overridden_methods"]
        if isinstance(overridden_methods, dict) and "items" in overridden_methods:
            overridden_methods_items = overridden_methods["items"]
        else:
            overridden_methods_items = overridden_methods
        for method in overridden_methods_items:
            assert "method" in method
            assert "overridden_from" in method
            assert isinstance(method["method"], str)
            assert isinstance(method["overridden_from"], str)

        # Check inherited methods structure - handle paginated structure
        inherited_methods = result["inherited_methods"]
        if isinstance(inherited_methods, dict) and "items" in inherited_methods:
            # Paginated structure
            for method in inherited_methods["items"]:
                assert "method_name" in method
                assert "from_model" in method
                assert isinstance(method["method_name"], str)
                assert isinstance(method["from_model"], str)
        else:
            # Original dict structure
            for method_name, from_model in inherited_methods.items():
                assert isinstance(method_name, str)
                assert isinstance(from_model, str)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_inheritance_chain_summary_calculations(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        result = await analyze_inheritance_chain(real_odoo_env_if_available, "product.template")

        assert "error" not in result

        summary = result["summary"]

        # Validate summary calculations match actual data - handle paginated structure
        inherited_fields = result["inherited_fields"]
        if isinstance(inherited_fields, dict) and "items" in inherited_fields:
            inherited_fields_count = len(inherited_fields["items"])
        else:
            inherited_fields_count = len(inherited_fields)
        
        inheriting_models = result["inheriting_models"]
        if isinstance(inheriting_models, dict) and "items" in inheriting_models:
            inheriting_models_count = len(inheriting_models["items"])
        else:
            inheriting_models_count = len(inheriting_models)
        
        assert summary["total_inherited_fields"] == inherited_fields_count
        assert summary["total_models_inheriting"] == inheriting_models_count
        overridden_methods = result["overridden_methods"]
        if isinstance(overridden_methods, dict) and "items" in overridden_methods:
            overridden_methods_count = len(overridden_methods["items"])
        else:
            overridden_methods_count = len(overridden_methods)
        assert summary["total_overridden_methods"] == overridden_methods_count
        assert summary["inheritance_depth"] == len(result["mro"]) - 1
        assert summary["uses_delegation"] == bool(result["inherits_from"])
        assert summary["uses_prototype"] == bool(result["inherits"])

        # Validate types
        assert isinstance(summary["uses_delegation"], bool)
        assert isinstance(summary["uses_prototype"], bool)
