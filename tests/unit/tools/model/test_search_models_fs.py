import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
import odoo_intelligence_mcp.tools.model.search_models_fs as search_models_fs
from tests.fixtures.fs_index import create_mock_build_ast_index


@pytest.mark.asyncio
async def test_search_models_fs_returns_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_models_fs, "build_ast_index", create_mock_build_ast_index())

    result = await search_models_fs.search_models_fs("res.partner")

    assert result["pattern"] == "res.partner"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["matches"]["pagination"]["total_count"] == 1
    assert result["matches"]["items"][0]["match_type"] == "exact"
    assert result["matches"]["items"][0]["priority"] == 1


@pytest.mark.asyncio
async def test_search_models_fs_returns_partial_and_description_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_models_fs, "build_ast_index", create_mock_build_ast_index())

    result = await search_models_fs.search_models_fs("sale", PaginationParams(page_size=1))

    assert result["matches"]["pagination"]["total_count"] == 2
    assert len(result["matches"]["items"]) == 1
    assert result["matches"]["items"][0]["match_type"] == "partial"


@pytest.mark.asyncio
async def test_search_models_fs_returns_description_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_models_fs, "build_ast_index", create_mock_build_ast_index())

    result = await search_models_fs.search_models_fs("support")

    assert result["matches"]["pagination"]["total_count"] == 1
    assert result["matches"]["items"][0]["match_type"] == "description"
    assert result["matches"]["items"][0]["name"] == "helpdesk.ticket"


@pytest.mark.asyncio
async def test_search_models_fs_returns_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_models_fs, "build_ast_index", create_mock_build_ast_index())

    result = await search_models_fs.search_models_fs("nomatch")

    assert result["matches"]["items"] == []
    assert result["matches"]["pagination"]["total_count"] == 0
