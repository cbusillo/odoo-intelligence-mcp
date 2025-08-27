import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock


def create_mock_odoo_model(
    model_name: str,
    fields: dict[str, dict[str, Any]] | None = None,
    methods: list[str] | None = None,
    records: list[dict[str, Any]] | None = None,
) -> MagicMock:
    model = MagicMock()
    model._name = model_name
    model._table = model_name.replace(".", "_")
    model._description = f"{model_name.split('.')[-1].title()} Model"

    if fields:
        model._fields = {name: MagicMock(**field_attrs) for name, field_attrs in fields.items()}
        model.fields_get = MagicMock(return_value=fields)

    if methods:
        for method in methods:
            setattr(model, method, MagicMock())

    if records:
        model.search = MagicMock(
            return_value=MagicMock(
                __iter__=lambda self: iter(records),
                __len__=lambda self: len(records),
                ids=[r.get("id", i) for i, r in enumerate(records)],
            )
        )
        model.browse = MagicMock(side_effect=lambda ids: [MagicMock(**r) for r in records if r.get("id") in ids])

    return model


def create_odoo_response(
    success: bool = True, result: Any = None, error: str | None = None, error_type: str | None = None
) -> dict[str, Any]:
    if success:
        return {"success": True, "result": result} if result is not None else {"success": True}
    else:
        response = {"success": False, "error": error or "Unknown error"}
        if error_type:
            response["error_type"] = error_type
        return response


def assert_paginated_response(response: dict[str, Any]) -> None:
    assert "items" in response or any(k in response for k in ["exact_matches", "models", "results"])

    if "pagination" in response:
        pagination = response["pagination"]
        assert "page" in pagination
        assert "page_size" in pagination
        assert "total_count" in pagination
        assert "total_pages" in pagination
        assert "has_next_page" in pagination
        assert "has_previous_page" in pagination
        assert isinstance(pagination["page"], int)
        assert isinstance(pagination["page_size"], int)
        assert isinstance(pagination["total_count"], int)
        assert isinstance(pagination["has_next_page"], bool)


def assert_error_response(response: dict[str, Any], expected_error_type: str | None = None) -> None:
    assert "error" in response
    assert isinstance(response["error"], str)
    assert len(response["error"]) > 0

    if expected_error_type:
        assert "error_type" in response
        assert response["error_type"] == expected_error_type


def assert_tool_response_valid(response: Any) -> None:
    try:
        json.dumps(response, default=str)
    except (TypeError, ValueError) as e:
        raise AssertionError(f"Response is not JSON serializable: {e}")

    if isinstance(response, dict):
        if "error" in response:
            assert_error_response(response)
        elif "pagination" in response:
            assert_paginated_response(response)


def create_mock_docker_environment(
    container_running: bool = True, execute_success: bool = True, response_data: Any = None
) -> MagicMock:
    env = MagicMock()

    if container_running:
        env.execute_code = AsyncMock(return_value=response_data or {"success": execute_success})
    else:
        from odoo_intelligence_mcp.utils.error_utils import DockerConnectionError

        env.execute_code = AsyncMock(side_effect=DockerConnectionError("Container not running"))

    env.cr = MagicMock()
    env.cr.close = MagicMock()

    return env


def create_mock_subprocess_run(
    returncode: int = 0, stdout: str = "", stderr: str = "", side_effect: Exception | None = None
) -> MagicMock:
    mock_run = MagicMock()

    if side_effect:
        mock_run.side_effect = side_effect
    else:
        mock_run.return_value = MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)

    return mock_run


async def assert_handles_docker_failure(tool_function: Callable, *args: Any, **kwargs: Any) -> None:
    mock_env = create_mock_docker_environment(container_running=False)

    result = await tool_function(mock_env, *args, **kwargs)

    if isinstance(result, dict):
        assert "error" in result
        assert "docker" in result["error"].lower() or "container" in result["error"].lower()


def create_field_info(
    field_type: str = "char",
    required: bool = False,
    readonly: bool = False,
    store: bool = True,
    compute: str | None = None,
    related: str | None = None,
    **extra_attrs: Any,
) -> dict[str, Any]:
    field_info = {
        "type": field_type,
        "string": extra_attrs.pop("string", field_type.title()),
        "required": required,
        "readonly": readonly,
        "store": store,
    }

    if compute:
        field_info["compute"] = compute
    if related:
        field_info["related"] = related

    field_info.update(extra_attrs)
    return field_info


def assert_model_info_response(response: dict[str, Any], model_name: str) -> None:
    assert response.get("name") == model_name or response.get("model") == model_name
    assert "table" in response
    assert "description" in response
    assert "fields" in response
    assert isinstance(response["fields"], dict)
    assert "field_count" in response
    assert response["field_count"] == len(response["fields"])
    assert "methods" in response
    assert isinstance(response["methods"], list)
    assert "method_count" in response
    assert response["method_count"] == len(response["methods"])


def create_mock_registry(models: dict[str, MagicMock] | None = None) -> MagicMock:
    registry = MagicMock()
    registry.models = models or {}
    registry.__iter__ = lambda self: iter(self.models.keys())
    registry.__getitem__ = lambda self, key: self.models.get(key)
    registry.__contains__ = lambda self, key: key in self.models
    registry.keys = lambda self: self.models.keys()
    return registry
