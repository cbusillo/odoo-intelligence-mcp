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
    assert "partial_matches" in result


@pytest.mark.asyncio
async def test_search_models_partial_match(mock_odoo_env: MagicMock) -> None:
    pattern = "sale"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "partial_matches" in result
    assert isinstance(result["partial_matches"], list)


@pytest.mark.asyncio
async def test_search_models_description_match(mock_odoo_env: MagicMock) -> None:
    pattern = "partner"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "description_matches" in result


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


@pytest.mark.asyncio
async def test_search_models_wildcard_pattern(mock_odoo_env: MagicMock) -> None:
    pattern = "product"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "partial_matches" in result

    matches = result["partial_matches"]
    product_models = [m for m in matches if "product" in m["model"]]
    assert len(product_models) > 0


@pytest.mark.asyncio
async def test_search_models_with_pagination(mock_odoo_env: MagicMock) -> None:
    pattern = "account"

    result = await search_models(mock_odoo_env, pattern)

    assert "pattern" in result
    assert "total_matches" in result
    assert "search_summary" in result
