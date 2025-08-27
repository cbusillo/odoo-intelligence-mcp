from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.field.search_field_properties import search_field_properties


@pytest.mark.asyncio
async def test_search_field_properties_computed(mock_odoo_env: MagicMock) -> None:
    property_type = "computed"

    result = await search_field_properties(mock_odoo_env, property_type)

    assert "property" in result
    assert result["property"] == property_type
    assert "fields" in result
    assert isinstance(result["fields"], dict)  # Paginated structure
    assert "items" in result["fields"]


@pytest.mark.asyncio
async def test_search_field_properties_related(mock_odoo_env: MagicMock) -> None:
    property_type = "related"

    result = await search_field_properties(mock_odoo_env, property_type)

    assert "property" in result
    assert result["property"] == property_type
    assert "fields" in result
    assert isinstance(result["fields"], dict)  # Paginated structure


@pytest.mark.asyncio
async def test_search_field_properties_stored(mock_odoo_env: MagicMock) -> None:
    property_type = "stored"

    result = await search_field_properties(mock_odoo_env, property_type)

    assert "property" in result
    assert "fields" in result
    assert isinstance(result["fields"], dict)  # Paginated structure


@pytest.mark.asyncio
async def test_search_field_properties_required(mock_odoo_env: MagicMock) -> None:
    property_type = "required"

    result = await search_field_properties(mock_odoo_env, property_type)

    assert "property" in result
    assert "fields" in result


@pytest.mark.asyncio
async def test_search_field_properties_readonly(mock_odoo_env: MagicMock) -> None:
    property_type = "readonly"

    result = await search_field_properties(mock_odoo_env, property_type)

    assert "property" in result
    assert "fields" in result


@pytest.mark.asyncio
async def test_search_field_properties_invalid(mock_odoo_env: MagicMock) -> None:
    property_type = "invalid_property"

    result = await search_field_properties(mock_odoo_env, property_type)

    assert "error" in result
    assert "invalid" in result["error"].lower() or "unsupported" in result["error"].lower()


@pytest.mark.asyncio
async def test_search_field_properties_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    property_type = "computed"
    pagination = PaginationParams(page=1, page_size=10)

    result = await search_field_properties(mock_odoo_env, property_type, pagination)

    assert "property" in result
    assert "fields" in result
    if isinstance(result["fields"], dict):
        assert "pagination" in result["fields"]
