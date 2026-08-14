import pytest

import odoo_intelligence_mcp.tools.field.search_field_type_fs as search_field_type_fs
from odoo_intelligence_mcp.core.utils import PaginationParams
from tests.fixtures.fs_index import create_mock_get_models_index


@pytest.mark.asyncio
async def test_search_field_type_fs_returns_relational_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_field_type_fs, "get_models_index", create_mock_get_models_index())

    result = await search_field_type_fs.search_field_type_fs("many2one", PaginationParams(page_size=1))

    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["results"]["pagination"]["total_count"] == 6
    assert len(result["results"]["items"]) == 1
    first_model = result["results"]["items"][0]
    assert "comodel_name" in first_model["fields"][0]


@pytest.mark.asyncio
async def test_search_field_type_fs_rejects_invalid_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_field_type_fs, "get_models_index", create_mock_get_models_index())

    result = await search_field_type_fs.search_field_type_fs("invalid")

    assert result["success"] is False
    assert result["valid_types"] == search_field_type_fs.VALID_FIELD_TYPES
    assert result["example"] == {"field_type": "char"}


@pytest.mark.asyncio
async def test_search_field_type_fs_returns_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_field_type_fs, "get_models_index", create_mock_get_models_index())

    result = await search_field_type_fs.search_field_type_fs("binary")

    assert result["results"]["items"] == []
    assert result["results"]["pagination"]["total_count"] == 0
