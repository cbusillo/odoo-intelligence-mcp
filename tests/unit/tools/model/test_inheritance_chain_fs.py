import pytest

import odoo_intelligence_mcp.tools.model.inheritance_chain_fs as inheritance_chain_fs
from odoo_intelligence_mcp.core.utils import PaginationParams
from tests.fixtures.fs_index import create_mock_get_models_index


@pytest.mark.asyncio
async def test_analyze_inheritance_chain_fs_returns_inheritance_details(monkeypatch: pytest.MonkeyPatch) -> None:
    models = {
        "res.partner.ext": {
            "class": "ResPartnerExt",
            "module": "custom",
            "file": "/odoo/addons/custom/models/res_partner_ext.py",
            "description": "Extended partner",
            "fields": {"name": {"type": "char", "string": "Name"}, "parent_id": {"type": "many2one", "string": "Parent"}},
            "decorators": {},
            "methods": ["create", "write", "custom_sync"],
            "inherits": ["res.partner"],
            "delegates": {"partner_id": "res.partner"},
        },
        "res.partner.ext.consumer.a": {
            "class": "ResPartnerExtConsumerA",
            "module": "custom",
            "file": "/odoo/addons/custom/models/res_partner_ext_consumer_a.py",
            "description": "Consumer A",
            "fields": {},
            "decorators": {},
            "methods": ["create"],
            "inherits": ["res.partner.ext"],
            "delegates": {},
        },
        "res.partner.ext.consumer.b": {
            "class": "ResPartnerExtConsumerB",
            "module": "custom",
            "file": "/odoo/addons/custom/models/res_partner_ext_consumer_b.py",
            "description": "Consumer B",
            "fields": {},
            "decorators": {},
            "methods": ["create"],
            "inherits": ["res.partner.ext"],
            "delegates": {},
        },
        "res.partner.ext.consumer.c": {
            "class": "ResPartnerExtConsumerC",
            "module": "custom",
            "file": "/odoo/addons/custom/models/res_partner_ext_consumer_c.py",
            "description": "Consumer C",
            "fields": {},
            "decorators": {},
            "methods": ["create"],
            "inherits": ["res.partner.ext"],
            "delegates": {},
        },
    }
    monkeypatch.setattr(inheritance_chain_fs, inheritance_chain_fs.get_models_index.__name__, create_mock_get_models_index(models))

    result = await inheritance_chain_fs.analyze_inheritance_chain_fs("res.partner.ext", PaginationParams(page_size=2))

    assert result["model"] == "res.partner.ext"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["summary"]["total_inherited_fields"] == 2
    assert result["summary"]["total_models_inheriting"] == 3
    assert result["summary"]["total_overridden_methods"] == 3
    assert result["summary"]["inheritance_depth"] == 1
    assert result["summary"]["uses_delegation"] is True
    assert result["summary"]["uses_prototype"] is True
    assert result["inherited_fields"]["name"]["from_model"] == "res.partner"
    assert result["inheriting_models"]["pagination"]["total_count"] == 3
    assert len(result["inheriting_models"]["items"]) == 2


@pytest.mark.asyncio
async def test_analyze_inheritance_chain_fs_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inheritance_chain_fs, inheritance_chain_fs.get_models_index.__name__, create_mock_get_models_index())

    result = await inheritance_chain_fs.analyze_inheritance_chain_fs("missing.model")

    assert result["error"] == "Model missing.model not found (fs)"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
