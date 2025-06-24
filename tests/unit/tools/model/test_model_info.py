from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.model_info import get_model_info


@pytest.mark.asyncio
async def test_get_model_info_basic(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "description" in result
    assert "fields" in result
    assert "methods" in result


@pytest.mark.asyncio
async def test_get_model_info_with_fields(mock_odoo_env: MagicMock) -> None:
    model_name = "product.template"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "model" in result
    assert "fields" in result
    assert isinstance(result["fields"], dict)

    for field_info in result["fields"].values():
        assert "type" in field_info
        assert "string" in field_info


@pytest.mark.asyncio
async def test_get_model_info_with_methods(mock_odoo_env: MagicMock) -> None:
    model_name = "sale.order"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "model" in result
    assert "methods" in result
    assert isinstance(result["methods"], list)


@pytest.mark.asyncio
async def test_get_model_info_with_inheritance(mock_odoo_env: MagicMock) -> None:
    model_name = "account.move"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "model" in result
    assert "inheritance" in result
    assert "parent_models" in result


@pytest.mark.asyncio
async def test_get_model_info_invalid_model(mock_odoo_env: MagicMock) -> None:
    model_name = "nonexistent.model"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_model_info_decorators(mock_odoo_env: MagicMock) -> None:
    model_name = "res.partner"

    result = await get_model_info(mock_odoo_env, model_name)

    assert "model" in result
    assert "decorators" in result
