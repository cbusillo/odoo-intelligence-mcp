from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.field.resolve_dynamic_fields import resolve_dynamic_fields


@pytest.mark.asyncio
async def test_resolve_dynamic_fields_basic(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order.line"

    result = await resolve_dynamic_fields(mock_odoo_env, model_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "computed_fields" in result
    assert "related_fields" in result


@pytest.mark.asyncio
async def test_resolve_dynamic_fields_with_computed(mock_odoo_env: MagicMock) -> None:
    model_name = "account.move.line"

    result = await resolve_dynamic_fields(mock_odoo_env, model_name)

    assert "model" in result
    assert "computed_fields" in result
    assert isinstance(result["computed_fields"], dict)  # Paginated structure
    assert "items" in result["computed_fields"]


@pytest.mark.asyncio
async def test_resolve_dynamic_fields_with_related(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order"

    result = await resolve_dynamic_fields(mock_odoo_env, model_name)

    assert "model" in result
    assert "related_fields" in result
    assert isinstance(result["related_fields"], dict)  # Paginated structure
    assert "items" in result["related_fields"]


@pytest.mark.asyncio
async def test_resolve_dynamic_fields_invalid_model(mock_odoo_env: MagicMock) -> None:
    model_name = "invalid.model"

    result = await resolve_dynamic_fields(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_resolve_dynamic_fields_with_dependencies(mock_odoo_env: MagicMock) -> None:
    model_name = "product.template"

    result = await resolve_dynamic_fields(mock_odoo_env, model_name)

    assert "model" in result
    assert "dependency_graph" in result
    assert isinstance(result["dependency_graph"], dict)  # Paginated structure


@pytest.mark.asyncio
async def test_resolve_dynamic_fields_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    model_name = "account.move"
    pagination = PaginationParams(page=1, page_size=5)

    result = await resolve_dynamic_fields(mock_odoo_env, model_name, pagination)

    assert "model" in result
    if "computed_fields" in result and isinstance(result["computed_fields"], dict):
        assert "pagination" in result["computed_fields"]