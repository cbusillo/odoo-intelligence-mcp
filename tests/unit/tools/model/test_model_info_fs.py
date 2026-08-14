import pytest

import odoo_intelligence_mcp.tools.model.model_info_fs as model_info_fs
from odoo_intelligence_mcp.core.utils import PaginationParams
from tests.fixtures.fs_index import create_mock_get_models_index


@pytest.mark.asyncio
async def test_get_model_info_fs_paginates_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_info_fs, model_info_fs.get_models_index.__name__, create_mock_get_models_index())

    result = await model_info_fs.get_model_info_fs("res.partner", PaginationParams(page_size=3))

    assert result["name"] == "res.partner"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["total_field_count"] == 7
    assert result["displayed_field_count"] == 3
    assert result["pagination"] == {
        "page": 1,
        "page_size": 3,
        "total_count": 7,
        "has_next": True,
        "has_previous": False,
    }
    assert result["fields"]["child_ids"]["relation"] == "res.partner"
    assert result["fields"]["display_name"]["store"] is False
    assert result["fields"]["manager_id"]["relation"] == "res.users"
    assert result["methods_sample"] == ["create", "write", "unlink", "search", "read", "exists", "custom_sync", "custom_validate"]


@pytest.mark.asyncio
async def test_get_model_info_fs_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_info_fs, model_info_fs.get_models_index.__name__, create_mock_get_models_index())

    result = await model_info_fs.get_model_info_fs("missing.model")

    assert result["error"] == "Model missing.model not found (fs)"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
