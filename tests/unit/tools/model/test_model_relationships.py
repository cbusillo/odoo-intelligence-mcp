import pytest

from odoo_intelligence_mcp.tools.model.model_relationships import get_model_relationships
from tests.mock_types import MockOdooEnvironment


@pytest.mark.asyncio
async def test_get_model_relationships_basic(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "many2one" in result
    assert "one2many" in result
    assert "many2many" in result


@pytest.mark.asyncio
async def test_get_model_relationships_many2one(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order.line"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "model" in result
    assert "many2one" in result
    assert isinstance(result["many2one"], list)


@pytest.mark.asyncio
async def test_get_model_relationships_one2many(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "res.partner"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "model" in result
    assert "one2many" in result
    assert isinstance(result["one2many"], list)


@pytest.mark.asyncio
async def test_get_model_relationships_many2many(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "model" in result
    assert "many2many" in result
    assert isinstance(result["many2many"], list)


@pytest.mark.asyncio
async def test_get_model_relationships_reverse(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "model" in result
    assert "reverse_relationships" in result


@pytest.mark.asyncio
async def test_get_model_relationships_invalid_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "invalid.model"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_model_relationships_complex_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "account.move"

    result = await get_model_relationships(mock_odoo_env, model_name)

    assert "model" in result
    assert "relationship_summary" in result
