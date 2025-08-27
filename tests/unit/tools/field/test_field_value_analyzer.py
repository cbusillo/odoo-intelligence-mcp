from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.field.field_value_analyzer import analyze_field_values


@pytest.mark.asyncio
async def test_field_value_analyzer_basic(mock_odoo_env: MagicMock) -> None:
    model_name = "product.template"
    field_name = "name"

    result = await analyze_field_values(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "field" in result
    assert result["field"] == field_name
    assert "analysis" in result


@pytest.mark.asyncio
async def test_field_value_analyzer_with_domain(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order"
    field_name = "state"
    domain = [("state", "=", "draft")]

    result = await analyze_field_values(mock_odoo_env, model_name, field_name, domain)

    assert "model" in result
    assert "field" in result
    assert "analysis" in result


@pytest.mark.asyncio
async def test_field_value_analyzer_with_sample_size(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"
    field_name = "email"
    sample_size = 100

    result = await analyze_field_values(mock_odoo_env, model_name, field_name, sample_size=sample_size)

    assert "model" in result
    assert "field" in result
    assert "analysis" in result


@pytest.mark.asyncio
async def test_field_value_analyzer_invalid_model(mock_odoo_env: MagicMock) -> None:
    model_name = "invalid.model"
    field_name = "name"

    result = await analyze_field_values(mock_odoo_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_field_value_analyzer_invalid_field(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"
    field_name = "nonexistent_field"

    result = await analyze_field_values(mock_odoo_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_field_value_analyzer_empty_results(mock_odoo_env: MagicMock) -> None:
    model_name = "product.product"
    field_name = "barcode"
    domain = [("id", "=", 0)]  # Domain that returns no records

    result = await analyze_field_values(mock_odoo_env, model_name, field_name, domain)

    assert "model" in result
    assert "field" in result
    assert "analysis" in result
