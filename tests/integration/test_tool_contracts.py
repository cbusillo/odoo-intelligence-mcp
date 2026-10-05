import asyncio
import json
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

import pytest
from jsonschema import Draft202012Validator
from mcp.types import TextContent

from odoo_intelligence_mcp import server

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture
def tool_environment(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    environment = MagicMock()
    environment.execute_code = AsyncMock()
    environment.cr = MagicMock()
    monkeypatch.setattr(server.odoo_env_manager, "get_environment", AsyncMock(return_value=environment))
    return environment


async def test_advertised_tools_dispatch_and_return_json(tool_environment: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    tools = await server.handle_list_tools()
    assert tools
    for tool in tools:
        Draft202012Validator.check_schema(tool.model_dump()["input_schema"])
        assert callable(server.TOOL_HANDLERS[tool.name])
        payload = {"tool": tool.name, "records": [{"name": "fixture"}]}
        handler = AsyncMock(return_value=payload)
        monkeypatch.setitem(server.TOOL_HANDLERS, tool.name, handler)
        arguments = {"fixture_input": tool.name}

        response = await server.handle_call_tool(tool.name, arguments)

        assert len(response) == 1
        assert isinstance(response[0], TextContent)
        assert json.loads(response[0].text) == payload
        handler.assert_awaited_once_with(tool_environment, arguments)


async def test_known_handler_receives_empty_arguments(tool_environment: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"success": True}
    handler = AsyncMock(return_value=payload)
    monkeypatch.setitem(server.TOOL_HANDLERS, "argument_probe", handler)

    response = await server.handle_call_tool("argument_probe", None)

    assert json.loads(response[0].text) == payload
    handler.assert_awaited_once_with(tool_environment, {})


@pytest.mark.parametrize("failure_location", ["environment", "handler"])
async def test_dispatch_failures_preserve_error(failure_location: str, monkeypatch: pytest.MonkeyPatch) -> None:
    failure = ValueError("fixture failure")
    environment = MagicMock()
    environment.cr = None
    handler = AsyncMock(return_value={"success": True})
    environment_loader = AsyncMock(return_value=environment)
    if failure_location == "environment":
        environment_loader.side_effect = failure
    else:
        handler.side_effect = failure
    monkeypatch.setattr(server.odoo_env_manager, "get_environment", environment_loader)
    monkeypatch.setitem(server.TOOL_HANDLERS, "failure_probe", handler)

    response = await server.handle_call_tool("failure_probe", {})
    content = json.loads(response[0].text)

    assert content["error"] == str(failure)
    assert content["error_type"] == type(failure).__name__
    if failure_location == "environment":
        handler.assert_not_awaited()
    else:
        handler.assert_awaited_once_with(environment, {})


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("model_query", {"operation": "info", "model_name": "res.partner", "mode": "registry"}),
        ("model_query", {"operation": "search", "pattern": "fixture", "mode": "registry"}),
        ("model_query", {"operation": "relationships", "model_name": "res.partner", "mode": "registry"}),
        ("field_query", {"operation": "usages", "model_name": "res.partner", "field_name": "name", "mode": "registry"}),
        ("execute_code", {"code": "result = True"}),
        ("field_query", {"operation": "analyze_values", "model_name": "res.partner", "field_name": "name"}),
        ("permission_checker", {"user": "fixture", "model": "res.partner", "operation": "read"}),
        ("field_query", {"operation": "dependencies", "model_name": "res.partner", "field_name": "name", "mode": "registry"}),
        ("field_query", {"operation": "search_properties", "property": "computed", "mode": "registry"}),
        ("field_query", {"operation": "search_type", "field_type": "many2one", "mode": "registry"}),
    ],
)
async def test_registry_tools_preserve_execution_failure(
    tool_name: str, arguments: dict[str, object], tool_environment: MagicMock
) -> None:
    failure = ValueError("fixture execution failure")
    tool_environment.execute_code.side_effect = failure

    response = await server.handle_call_tool(tool_name, arguments)
    content = json.loads(response[0].text)

    assert str(failure) in content["error"]
    assert content["error_type"] == type(failure).__name__
    assert tool_environment.execute_code.await_count > 0


@pytest.mark.parametrize(
    ("arguments", "expected_names", "total_count"),
    [
        ({"page": 1, "page_size": 2}, ["fixture.alpha", "fixture.beta"], 4),
        ({"page": 2, "page_size": 2}, ["fixture.gamma", "fixture.zeta"], 4),
        ({"page": 1, "page_size": 1, "filter": "beta"}, ["fixture.beta"], 1),
        ({"limit": 2, "offset": 0}, ["fixture.alpha", "fixture.beta"], 4),
    ],
)
async def test_search_handler_selects_records(
    arguments: dict[str, object], expected_names: list[str], total_count: int, tool_environment: MagicMock
) -> None:
    records = [{"name": f"fixture.{name}", "description": name} for name in ["zeta", "gamma", "beta", "alpha"]]
    tool_environment.execute_code.return_value = {
        "exact_matches": [],
        "partial_matches": deepcopy(records),
        "description_matches": [],
        "pattern": "fixture",
        "total_models": len(records),
    }

    response = await server.handle_call_tool(
        "model_query", {"operation": "search", "pattern": "fixture", "mode": "registry", **arguments}
    )
    content = json.loads(response[0].text)

    assert "error" not in content
    assert [record["name"] for record in content["matches"]["items"]] == expected_names
    assert content["matches"]["pagination"]["total_count"] == total_count
    assert content["matches"]["pagination"]["page_size"] == arguments.get("page_size", arguments.get("limit"))
    assert content["matches"]["pagination"]["page"] == arguments.get("page", 1)
    assert tool_environment.execute_code.await_count > 0


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("model_query", {"operation": "info"}),
        ("model_query", {"operation": "search"}),
        ("field_query", {"operation": "usages", "model_name": "res.partner"}),
        ("execute_code", {}),
        ("permission_checker", {"user": "fixture", "model": "res.partner"}),
    ],
)
async def test_required_arguments_fail_before_execution(
    tool_name: str, arguments: dict[str, object], tool_environment: MagicMock
) -> None:
    response = await server.handle_call_tool(tool_name, arguments)
    content = json.loads(response[0].text)

    assert content["error"]
    tool_environment.execute_code.assert_not_awaited()


async def test_shared_runtime_tool_calls_do_not_overlap(tool_environment: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    first_started = asyncio.Event()
    first_finished = asyncio.Event()
    second_started = asyncio.Event()

    async def execute_tool(environment: object, arguments: dict[str, object]) -> dict[str, object]:
        if arguments["first"]:
            first_started.set()
            await first_finished.wait()
        else:
            second_started.set()
        return {"success": True}

    monkeypatch.setitem(server.TOOL_HANDLERS, "serialization_probe", execute_tool)
    first_request = asyncio.create_task(server.handle_call_tool("serialization_probe", {"first": True}))
    second_request = None
    try:
        await asyncio.wait_for(first_started.wait(), timeout=5)
        second_request = asyncio.create_task(server.handle_call_tool("serialization_probe", {"first": False}))
        await asyncio.sleep(0)
        assert not second_started.is_set()
    finally:
        first_finished.set()
        responses = await asyncio.gather(first_request, *([second_request] if second_request else []))
    assert second_started.is_set()
    assert all(json.loads(response[0].text) == {"success": True} for response in responses)


@pytest.mark.parametrize(
    "case",
    [
        (
            "model.search_models_fs",
            "build_ast_index",
            "model_query",
            {"operation": "search", "pattern": "fixture"},
            "matches",
            "name",
            "fixture.order",
        ),
        (
            "field.search_field_properties_fs",
            "get_models_index",
            "field_query",
            {"operation": "search_properties", "property": "computed"},
            "results",
            "field_name",
            "total",
        ),
        (
            "field.search_field_type_fs",
            "get_models_index",
            "field_query",
            {"operation": "search_type", "field_type": "float"},
            "results",
            "model",
            "fixture.order",
        ),
        (
            "analysis.pattern_analysis_fs",
            "build_ast_index",
            "analysis_query",
            {"analysis_type": "patterns", "pattern_type": "computed_fields"},
            "computed_fields",
            "field",
            "total",
        ),
    ],
)
async def test_filesystem_handlers_return_selected_data(
    case: tuple[str, str, str, dict[str, object], str, str, str],
    tool_environment: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path, loader_name, tool_name, arguments, collection_key, item_key, expected_value = case
    from importlib import import_module

    from tests.fixtures.fs_index import create_fs_ast_index

    models = {
        "fixture.order": {
            "description": "Fixture order",
            "module": "fixture",
            "file": "/fixture/order.py",
            "fields": {"total": {"type": "float", "compute": "compute_total", "store": True}},
            "methods": ["compute_total"],
            "inherits": [],
            "delegates": {},
            "decorators": {},
        }
    }
    index = create_fs_ast_index(models, include_defaults=False)
    loader_result = index if loader_name == "build_ast_index" else index["models"]
    module = import_module(f"odoo_intelligence_mcp.tools.{module_path}")
    monkeypatch.setattr(module, loader_name, AsyncMock(return_value=loader_result))

    response = await server.handle_call_tool(tool_name, {**arguments, "mode": "fs", "page_size": 1})
    content = json.loads(response[0].text)

    assert "error" not in content
    assert content["mode_used"] == "fs"
    assert content["data_quality"] == "approximate"
    assert content[collection_key]["pagination"]["total_count"] == len(models)
    assert [item[item_key] for item in content[collection_key]["items"]] == [expected_value]
    tool_environment.execute_code.assert_not_awaited()
