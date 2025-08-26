from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.model import search_decorators


@pytest.mark.asyncio
async def test_search_decorators_depends(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    decorator_type = "depends"

    result = await search_decorators(mock_odoo_env, decorator_type, PaginationParams())

    assert "decorator" in result
    assert result["decorator"] == decorator_type
    assert "methods" in result
    assert isinstance(result["methods"], dict)
    assert "items" in result["methods"]


@pytest.mark.asyncio
async def test_search_decorators_constrains(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    decorator_type = "constrains"

    result = await search_decorators(mock_odoo_env, decorator_type, PaginationParams())

    assert "decorator" in result
    assert result["decorator"] == decorator_type
    assert "methods" in result


@pytest.mark.asyncio
async def test_search_decorators_onchange(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    decorator_type = "onchange"

    result = await search_decorators(mock_odoo_env, decorator_type, PaginationParams())

    assert "decorator" in result
    assert result["decorator"] == decorator_type
    assert "methods" in result


@pytest.mark.asyncio
async def test_search_decorators_model_create_multi(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    decorator_type = "model_create_multi"

    result = await search_decorators(mock_odoo_env, decorator_type, PaginationParams())

    assert "decorator" in result
    assert result["decorator"] == decorator_type
    assert "methods" in result


@pytest.mark.asyncio
async def test_search_decorators_invalid(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams
    
    decorator_type = "invalid_decorator"

    result = await search_decorators(mock_odoo_env, decorator_type, PaginationParams())

    assert "error" in result or "methods" in result
    if "methods" in result and isinstance(result["methods"], dict):
        assert result["methods"]["items"] == []


@pytest.mark.asyncio
async def test_search_decorators_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    decorator_type = "depends"
    pagination = PaginationParams(page=1, page_size=10)

    result = await search_decorators(mock_odoo_env, decorator_type, pagination)

    assert "decorator" in result
    assert "methods" in result
    if isinstance(result["methods"], dict):
        assert "pagination" in result["methods"]