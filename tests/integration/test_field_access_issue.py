import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.field.field_dependencies import get_field_dependencies
from odoo_intelligence_mcp.tools.field.field_value_analyzer import analyze_field_values


class TestFieldAccessIntegration:
    @pytest.fixture
    async def odoo_env(self) -> HostOdooEnvironment:
        manager = HostOdooEnvironmentManager()
        return await manager.get_environment()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_field_value_analyzer_standard_field_issue(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_field_values(odoo_env, "product.template", "name")

        assert "error" not in result, f"Expected no error, got: {result.get('error')}"
        assert result["model"] == "product.template"
        assert result["field"] == "name"
        assert "field_info" in result
        assert result["field_info"]["type"] == "char"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_field_dependencies_standard_field_issue(self, odoo_env: HostOdooEnvironment) -> None:
        result = await get_field_dependencies(odoo_env, "product.template", "name")

        assert "error" not in result, f"Expected no error, got: {result.get('error')}"
        assert result["model"] == "product.template"
        assert result["field"] == "name"
        assert result["type"] == "char"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_inherited_field_access(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_field_values(odoo_env, "product.template", "create_date")

        assert "error" not in result, f"Expected no error, got: {result.get('error')}"
        assert result["field_info"]["type"] == "datetime"
