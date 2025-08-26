from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.find_method import find_method_implementations


@pytest.mark.asyncio
async def test_find_method_basic(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    method_name = "create"

    result = await find_method_implementations(mock_odoo_env, method_name, PaginationParams())

    assert "method_name" in result
    assert result["method_name"] == method_name
    assert "models" in result
    assert isinstance(result["models"], dict)
    assert "items" in result["models"]


@pytest.mark.asyncio
async def test_find_method_with_results(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    method_name = "compute_amount"

    result = await find_method_implementations(mock_odoo_env, method_name, PaginationParams())

    assert "method_name" in result
    assert result["method_name"] == method_name
    assert "models" in result
    assert isinstance(result["models"], dict)


@pytest.mark.asyncio
async def test_find_method_not_found(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    method_name = "nonexistent_method"

    result = await find_method_implementations(mock_odoo_env, method_name, PaginationParams())

    assert "method_name" in result
    assert result["method_name"] == method_name
    assert "models" in result
    if isinstance(result["models"], dict):
        assert result["models"]["items"] == []


@pytest.mark.asyncio
async def test_find_method_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    method_name = "write"
    pagination = PaginationParams(page=1, page_size=5)

    result = await find_method_implementations(mock_odoo_env, method_name, pagination)

    assert "method_name" in result
    assert "models" in result
    if isinstance(result["models"], dict):
        assert "pagination" in result["models"]
