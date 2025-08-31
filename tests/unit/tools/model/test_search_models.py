from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.search_models import search_models


@pytest.mark.asyncio
async def test_search_models_exact_match(mock_odoo_env: MagicMock) -> None:
    pattern = "res.partner"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert result["pattern"] == pattern
    assert "exact_matches" in result
    assert "total_models" in result
    assert len(result["exact_matches"]) > 0


@pytest.mark.asyncio
async def test_search_models_partial_match(mock_odoo_env: MagicMock) -> None:
    pattern = "sale"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "partial_matches" in result
    assert isinstance(result["partial_matches"], list)
    assert len(result["partial_matches"]) > 0


@pytest.mark.asyncio
async def test_search_models_description_match(mock_odoo_env: MagicMock) -> None:
    pattern = "partner"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "description_matches" in result
    assert len(result["description_matches"]) > 0


@pytest.mark.asyncio
async def test_search_models_no_matches(mock_odoo_env: MagicMock) -> None:
    # noinspection SpellCheckingInspection
    pattern = "xyznomatch"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "exact_matches" in result
    assert "partial_matches" in result
    assert "description_matches" in result
    assert len(result["exact_matches"]) == 0
    assert len(result["partial_matches"]) == 0
    assert len(result["description_matches"]) == 0


@pytest.mark.asyncio
async def test_search_models_wildcard_pattern(mock_odoo_env: MagicMock) -> None:
    pattern = "product"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "partial_matches" in result

    matches = result.get("partial_matches", [])
    assert isinstance(matches, list)
    assert len(matches) > 0


@pytest.mark.asyncio
async def test_search_models_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    pattern = "account"
    pagination = PaginationParams(page_size=10)

    result = await search_models(mock_odoo_env, pattern, pagination)

    assert "pattern" in result
    assert "total_models" in result
    assert "matches" in result
    assert isinstance(result["matches"], dict)  # Paginated structure
    assert "items" in result["matches"]
    assert "pagination" in result["matches"]
