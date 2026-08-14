import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
import odoo_intelligence_mcp.tools.analysis.pattern_analysis_fs as pattern_analysis_fs

from tests.fixtures.fs_index import create_mock_build_ast_index


@pytest.mark.asyncio
async def test_analyze_patterns_fs_rejects_invalid_pattern_type() -> None:
    result = await pattern_analysis_fs.analyze_patterns_fs("invalid")

    assert result["success"] is False
    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["valid_pattern_types"] == pattern_analysis_fs.VALID_PATTERN_TYPES
    assert result["example"] == {"pattern_type": "computed_fields"}


@pytest.mark.asyncio
async def test_analyze_patterns_fs_returns_all_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pattern_analysis_fs, "build_ast_index", create_mock_build_ast_index())

    result = await pattern_analysis_fs.analyze_patterns_fs("all", PaginationParams(page_size=10))

    assert result["mode_used"] == "fs"
    assert result["data_quality"] == "approximate"
    assert result["computed_fields"]["pagination"]["total_count"] == 4
    assert any(item["field"] == "amount_total" for item in result["computed_fields"]["items"])
    assert result["related_fields"]["pagination"]["total_count"] == 2
    assert any(item["field"] == "manager_id" for item in result["related_fields"]["items"])
    assert result["api_decorators"]["pagination"]["total_count"] == 7
    assert any(item["method"] == "_onchange_state" for item in result["api_decorators"]["items"])
    assert result["custom_methods"]["pagination"]["total_count"] == 9
    assert any(item["method"] == "action_close" for item in result["custom_methods"]["items"])
    assert result["state_machines"]["pagination"]["total_count"] == 3
    assert any(item["model"] == "sale.order" for item in result["state_machines"]["items"])


@pytest.mark.asyncio
async def test_analyze_patterns_fs_paginates_single_category(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pattern_analysis_fs, "build_ast_index", create_mock_build_ast_index())

    result = await pattern_analysis_fs.analyze_patterns_fs("computed_fields", PaginationParams(page_size=2))

    computed_fields = result["computed_fields"]
    assert computed_fields["pagination"]["total_count"] == 4
    assert len(computed_fields["items"]) == 2
    assert computed_fields["pagination"]["has_next_page"] is True


@pytest.mark.asyncio
async def test_analyze_patterns_fs_returns_empty_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_models = {
        "empty.model": {
            "class": "EmptyModel",
            "module": "test",
            "file": "/odoo/addons/test/models/empty_model.py",
            "description": "Empty model",
            "fields": {"name": {"type": "char", "string": "Name", "store": True}},
            "decorators": {},
            "methods": ["create"],
            "inherits": [],
            "delegates": {},
        }
    }
    monkeypatch.setattr(pattern_analysis_fs, "build_ast_index", create_mock_build_ast_index(empty_models, include_defaults=False))

    result = await pattern_analysis_fs.analyze_patterns_fs("computed_fields")

    assert result["computed_fields"]["pagination"]["total_count"] == 0
    assert result["computed_fields"]["items"] == []
