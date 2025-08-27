from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.view_model_usage import get_view_model_usage


@pytest.mark.asyncio
async def test_view_model_usage_basic(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    model_name = "sale.order"

    result = await get_view_model_usage(mock_odoo_env, model_name, PaginationParams())

    assert "model" in result
    assert result["model"] == model_name
    assert "views" in result
    assert isinstance(result["views"], dict)
    assert "items" in result["views"]


@pytest.mark.asyncio
async def test_view_model_usage_with_views(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    model_name = "product.template"

    result = await get_view_model_usage(mock_odoo_env, model_name, PaginationParams())

    assert "model" in result
    assert result["model"] == model_name
    assert "views" in result
    assert isinstance(result["views"], dict)


@pytest.mark.asyncio
async def test_view_model_usage_invalid_model(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    model_name = "invalid.model"

    result = await get_view_model_usage(mock_odoo_env, model_name, PaginationParams())

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_view_model_usage_coverage(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    model_name = "res.partner"

    result = await get_view_model_usage(mock_odoo_env, model_name, PaginationParams())

    assert "model" in result
    assert "field_coverage" in result
    if isinstance(result["field_coverage"], dict):
        assert "total_fields" in result["field_coverage"]
        assert "exposed_fields" in result["field_coverage"]


@pytest.mark.skip(reason="Test needs refactoring for pagination")
@pytest.mark.asyncio
async def test_view_model_usage_buttons(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    model_name = "account.move"

    result = await get_view_model_usage(mock_odoo_env, model_name, PaginationParams())

    assert "model" in result
    assert "buttons" in result
    assert isinstance(result["buttons"], dict)


@pytest.mark.asyncio
async def test_view_model_usage_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    model_name = "sale.order.line"
    pagination = PaginationParams(page=1, page_size=10)

    result = await get_view_model_usage(mock_odoo_env, model_name, pagination)

    assert "model" in result
    assert "views" in result
    if isinstance(result["views"], dict):
        assert "pagination" in result["views"]