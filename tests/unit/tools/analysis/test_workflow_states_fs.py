import pytest

import odoo_intelligence_mcp.tools.analysis.workflow_states_fs as workflow_states_fs
from tests.fixtures.fs_index import create_mock_get_models_index


@pytest.mark.asyncio
async def test_analyze_workflow_states_fs_returns_state_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow_states_fs, "get_models_index", create_mock_get_models_index())

    result = await workflow_states_fs.analyze_workflow_states_fs("sale.order")

    assert result["model"] == "sale.order"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["state_fields"]["state"]["selection"][0][0] == "draft"
    assert result["summary"]["has_workflow"] is True
    assert result["summary"]["state_field_count"] == 1
    assert result["button_actions"]["pagination"]["total_count"] == 1
    assert result["button_actions"]["items"][0]["method"] == "_onchange_partner_id"
    assert result["automated_transitions"]["pagination"]["total_count"] == 1
    assert result["automated_transitions"]["items"][0]["method"] == "_compute_amount_total"


@pytest.mark.asyncio
async def test_analyze_workflow_states_fs_handles_models_without_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow_states_fs, "get_models_index", create_mock_get_models_index())

    result = await workflow_states_fs.analyze_workflow_states_fs("product.template")

    assert result["state_fields"] == {}
    assert result["summary"]["has_workflow"] is False
    assert result["summary"]["state_field_count"] == 0
    assert result["button_actions"] == []
    assert result["automated_transitions"] == []


@pytest.mark.asyncio
async def test_analyze_workflow_states_fs_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workflow_states_fs, "get_models_index", create_mock_get_models_index())

    result = await workflow_states_fs.analyze_workflow_states_fs("missing.model")

    assert result["error"] == "Model missing.model not found (fs)"
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
