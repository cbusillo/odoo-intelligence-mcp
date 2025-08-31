from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.field.field_dependencies import get_field_dependencies


@pytest.mark.asyncio
async def test_field_dependencies_basic(mock_odoo_env: MagicMock) -> None:
    model_name = "product.template"
    field_name = "name"

    result = await get_field_dependencies(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "field" in result
    assert result["field"] == field_name


@pytest.mark.asyncio
async def test_field_dependencies_with_dependents(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order"
    field_name = "partner_id"

    result = await get_field_dependencies(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert "field" in result
    assert "dependent_fields" in result
    assert isinstance(result["dependent_fields"], dict)  # Paginated structure
    assert "items" in result["dependent_fields"]


@pytest.mark.asyncio
async def test_field_dependencies_with_chain(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order.line"
    field_name = "product_id"

    result = await get_field_dependencies(mock_odoo_env, model_name, field_name)

    assert "model" in result
    assert "field" in result
    assert "dependency_chain" in result
    assert isinstance(result["dependency_chain"], dict)  # Paginated structure
    assert "items" in result["dependency_chain"]


@pytest.mark.asyncio
async def test_field_dependencies_invalid_model(mock_odoo_env: MagicMock) -> None:
    model_name = "invalid.model"
    field_name = "name"

    result = await get_field_dependencies(mock_odoo_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_field_dependencies_invalid_field(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"
    field_name = "nonexistent_field"

    result = await get_field_dependencies(mock_odoo_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_field_dependencies_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    model_name = "account.move"
    field_name = "state"
    pagination = PaginationParams(page_size=5)

    result = await get_field_dependencies(mock_odoo_env, model_name, field_name, pagination)

    assert "model" in result
    assert "field" in result
    if "dependent_fields" in result and isinstance(result["dependent_fields"], dict):
        assert "pagination" in result["dependent_fields"]
