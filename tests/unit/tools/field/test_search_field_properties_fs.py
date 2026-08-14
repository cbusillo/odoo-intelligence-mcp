import pytest

import odoo_intelligence_mcp.tools.field.search_field_properties_fs as search_field_properties_fs
from odoo_intelligence_mcp.core.utils import PaginationParams
from tests.fixtures.fs_index import create_mock_get_models_index


@pytest.mark.asyncio
async def test_search_field_properties_fs_returns_computed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_field_properties_fs, "get_models_index", create_mock_get_models_index())

    result = await search_field_properties_fs.search_field_properties_fs("computed", PaginationParams(page_size=2))

    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["results"]["pagination"]["total_count"] == 4
    assert len(result["results"]["items"]) == 2
    assert any(item["field_name"] == "amount_total" for item in result["results"]["items"])


@pytest.mark.asyncio
async def test_search_field_properties_fs_returns_related_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_field_properties_fs, "get_models_index", create_mock_get_models_index())

    result = await search_field_properties_fs.search_field_properties_fs("related")

    assert result["results"]["pagination"]["total_count"] == 2
    assert any(item["field_name"] == "description_sale" for item in result["results"]["items"])


@pytest.mark.asyncio
async def test_search_field_properties_fs_returns_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_field_properties_fs, "get_models_index", create_mock_get_models_index())

    result = await search_field_properties_fs.search_field_properties_fs("readonly")

    assert result["results"]["items"] == []
    assert result["results"]["pagination"]["total_count"] == 0
