from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.model_info import get_model_info


@pytest.mark.asyncio
async def test_get_model_info_basic(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "name" in result
    assert result["name"] == model_name
    assert result["model"] == model_name
    assert "table" in result
    assert result["table"] == "res_partner"
    assert "description" in result
    assert result["description"] == "Partner Model"
    assert "rec_name" in result
    assert result["rec_name"] == "name"
    assert "order" in result
    assert result["order"] == "id"
    assert "fields" in result
    assert isinstance(result["fields"], dict)
    assert "field_count" in result
    assert result["field_count"] == len(result["fields"])
    assert "methods" in result
    assert isinstance(result["methods"], list)
    assert "method_count" in result
    assert result["method_count"] == len(result["methods"])


@pytest.mark.asyncio
async def test_get_model_info_with_fields(mock_odoo_env: MagicMock) -> None:
    model_name = "product.template"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "fields" in result
    assert isinstance(result["fields"], dict)
    assert len(result["fields"]) > 0

    for field_name, field_info in result["fields"].items():
        assert isinstance(field_name, str)
        assert isinstance(field_info, dict)
        assert "type" in field_info
        assert field_info["type"] in [
            "char",
            "integer",
            "float",
            "boolean",
            "text",
            "many2one",
            "one2many",
            "many2many",
            "selection",
            "date",
            "datetime",
        ]
        assert "string" in field_info
        assert isinstance(field_info["string"], str)
        assert "required" in field_info
        assert isinstance(field_info["required"], bool)
        assert "readonly" in field_info
        assert isinstance(field_info["readonly"], bool)
        assert "store" in field_info
        assert isinstance(field_info["store"], bool)

        if field_info["type"] in ["many2one", "one2many", "many2many"]:
            assert "relation" in field_info
            assert isinstance(field_info["relation"], str)

        if field_info["type"] == "selection":
            assert "selection" in field_info


@pytest.mark.asyncio
async def test_get_model_info_with_methods(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "methods" in result
    assert isinstance(result["methods"], list)
    assert len(result["methods"]) > 0
    assert "method_count" in result
    assert result["method_count"] == len(result["methods"])

    expected_methods = ["create", "write", "unlink", "search", "read"]
    for method in expected_methods:
        assert method in result["methods"], f"Expected method '{method}' not found in methods"


@pytest.mark.asyncio
async def test_get_model_info_with_inheritance(mock_odoo_env: MagicMock) -> None:
    model_name = "account.move"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "name" in result
    assert result["name"] == model_name
    assert "fields" in result
    assert "methods" in result
    assert "_inherit" in result
    assert isinstance(result["_inherit"], list)
    assert len(result["_inherit"]) > 0
    assert "mail.thread" in result["_inherit"]
    assert "mail.activity.mixin" in result["_inherit"]


@pytest.mark.asyncio
async def test_get_model_info_invalid_model(mock_odoo_env: MagicMock) -> None:
    model_name = "nonexistent.model"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_model_info_decorators(mock_odoo_env: MagicMock) -> None:
    model_name = "product.template"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "decorators" in result
    assert isinstance(result["decorators"], dict)
    assert "api.depends" in result["decorators"]
    assert result["decorators"]["api.depends"] == 2
    assert "api.constrains" in result["decorators"]
    assert result["decorators"]["api.constrains"] == 1


@pytest.mark.asyncio
async def test_get_model_info_validates_model_name(mock_odoo_env: MagicMock) -> None:
    invalid_names = ["", "  ", "123invalid", "invalid-model", "model with spaces"]

    for invalid_name in invalid_names:
        result = await get_model_info(mock_odoo_env, invalid_name)
        assert "error" in result
        assert "Invalid" in result["error"] or "empty" in result["error"] or "format" in result["error"]
        assert "error_type" in result
        assert result["error_type"] == "InvalidArgumentError"


@pytest.mark.asyncio
async def test_get_model_info_empty_model_name(mock_odoo_env: MagicMock) -> None:
    result = await get_model_info(mock_odoo_env, "")
    assert "error" in result
    assert "non-empty string" in result["error"]
    assert result["error_type"] == "InvalidArgumentError"


@pytest.mark.asyncio
async def test_get_model_info_special_fields(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "fields" in result
    assert "id" in result["fields"]
    assert result["fields"]["id"]["type"] == "integer"
    assert result["fields"]["id"]["readonly"] is True
    assert "name" in result["fields"]
    assert result["fields"]["name"]["type"] == "char"
    assert result["fields"]["name"]["required"] is True
