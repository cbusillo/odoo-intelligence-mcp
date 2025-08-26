import pytest

from odoo_intelligence_mcp.tools.model.inheritance_chain import analyze_inheritance_chain
from tests.mock_types import MockOdooEnvironment


@pytest.mark.asyncio
async def test_get_inheritance_chain_basic(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"

    result = await analyze_inheritance_chain(mock_odoo_env, model_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "mro" in result
    assert "inherits" in result
    assert "inherited_fields" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_get_inheritance_chain_with_inherits(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.product"

    result = await analyze_inheritance_chain(mock_odoo_env, model_name)

    assert "model" in result
    assert "inherits" in result
    assert "inherits_from" in result


@pytest.mark.asyncio
async def test_get_inheritance_chain_abstract_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "mail.thread"

    result = await analyze_inheritance_chain(mock_odoo_env, model_name)

    assert "model" in result
    assert "mro" in result
    assert "inherited_methods" in result


@pytest.mark.asyncio
async def test_get_inheritance_chain_complex_hierarchy(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"

    result = await analyze_inheritance_chain(mock_odoo_env, model_name)

    assert "model" in result
    assert "mro" in result
    assert "inherited_fields" in result
    assert "overridden_methods" in result


@pytest.mark.asyncio
async def test_get_inheritance_chain_invalid_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "invalid.model"

    result = await analyze_inheritance_chain(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_inheritance_chain_field_sources(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "res.partner"

    result = await analyze_inheritance_chain(mock_odoo_env, model_name)

    assert "model" in result
    assert "mro" in result
    assert "inherited_fields" in result
    assert "inherited_methods" in result
