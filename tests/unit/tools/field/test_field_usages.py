import pytest

from odoo_intelligence_mcp.tools.field.field_usages import get_field_usages
from tests.mock_types import MockOdooEnvironment


@pytest.mark.asyncio
async def test_analyze_field_usage_basic(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"
    field_name = "name"

    result = await get_field_usages(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "field" in result
    assert result["field"] == field_name
    assert "usages" in result


@pytest.mark.asyncio
async def test_analyze_field_usage_many2one(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order.line"
    field_name = "product_id"

    result = await get_field_usages(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert "field" in result
    assert "usages" in result
    assert "field_type" in result


@pytest.mark.asyncio
async def test_analyze_field_usage_computed(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"
    field_name = "amount_total"

    result = await get_field_usages(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert "field" in result
    assert "usages" in result


@pytest.mark.asyncio
async def test_analyze_field_usage_invalid_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "invalid.model"
    field_name = "name"

    result = await get_field_usages(mock_odoo_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_analyze_field_usage_invalid_field(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"
    field_name = "nonexistent_field"

    result = await get_field_usages(mock_odoo_env, model_name, field_name)

    assert "error" in result
    assert "field" in result["error"].lower()


@pytest.mark.asyncio
async def test_analyze_field_usage_view_coverage(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "res.partner"
    field_name = "email"

    result = await get_field_usages(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert "field" in result
    assert "usages" in result
    assert "view_usage" in result
