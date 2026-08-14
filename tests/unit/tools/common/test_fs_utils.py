from unittest.mock import AsyncMock

import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.common.fs_utils import ensure_pagination, fs_enrich, get_models_index, not_found, paginate_items


@pytest.mark.asyncio
async def test_get_models_index_returns_models(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_build_ast_index = AsyncMock(return_value={"models": {"res.partner": {"description": "Partner"}}})
    monkeypatch.setattr("odoo_intelligence_mcp.tools.common.fs_utils.build_ast_index", mock_build_ast_index)

    result = await get_models_index()

    assert result == {"res.partner": {"description": "Partner"}}


@pytest.mark.asyncio
async def test_get_models_index_handles_non_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_build_ast_index = AsyncMock(return_value=["unexpected"])
    monkeypatch.setattr("odoo_intelligence_mcp.tools.common.fs_utils.build_ast_index", mock_build_ast_index)

    result = await get_models_index()

    assert result == {}


def test_ensure_pagination_uses_default_page_size() -> None:
    pagination = ensure_pagination(None, default_page_size=25)

    assert pagination.page == 1
    assert pagination.page_size == 25


def test_ensure_pagination_returns_existing() -> None:
    pagination = PaginationParams(page=2, page_size=7)

    result = ensure_pagination(pagination, default_page_size=25)

    assert result is pagination


def test_not_found_marks_fs_mode() -> None:
    result = not_found("res.partner")

    assert result == {
        "error": "Model res.partner not found (fs)",
        "mode_used": "fs",
        "data_quality": "approximate",
    }


def test_fs_enrich_fills_defaults() -> None:
    payload = {"value": 1}

    result = fs_enrich(payload)

    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"


def test_fs_enrich_preserves_existing_values() -> None:
    payload = {"mode_used": "custom", "data_quality": "exact"}

    result = fs_enrich(payload)

    assert result == payload


def test_paginate_items_returns_paginated_dict() -> None:
    pagination = PaginationParams(page_size=1)

    result = paginate_items([{"name": "alpha"}, {"name": "beta"}], pagination, ["name"])

    assert result["items"][0]["name"] == "alpha"
    assert result["pagination"]["total_count"] == 2
