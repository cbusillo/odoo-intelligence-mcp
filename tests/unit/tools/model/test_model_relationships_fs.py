import pytest

import odoo_intelligence_mcp.tools.model.model_relationships_fs as model_relationships_fs
from odoo_intelligence_mcp.core.utils import PaginationParams
from tests.fixtures.fs_index import create_mock_get_models_index


@pytest.mark.asyncio
async def test_get_model_relationships_fs_returns_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_relationships_fs, "get_models_index", create_mock_get_models_index())

    result = await model_relationships_fs.get_model_relationships_fs("sale.order", PaginationParams(page_size=2))

    assert result["model"] == "sale.order"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["relationship_summary"] == {
        "many2one_count": 1,
        "one2many_count": 1,
        "many2many_count": 1,
        "reverse_many2one_count": 0,
        "reverse_one2many_count": 0,
        "reverse_many2many_count": 0,
    }
    assert result["relationships"]["pagination"]["total_count"] == 3
    assert len(result["relationships"]["items"]) == 2
    assert any(item["relationship_type"] == "many2one" for item in result["relationships"]["items"])


@pytest.mark.asyncio
async def test_get_model_relationships_fs_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_relationships_fs, "get_models_index", create_mock_get_models_index())

    result = await model_relationships_fs.get_model_relationships_fs("missing.model")

    assert result["error"] == "Model missing.model not found (fs)"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
