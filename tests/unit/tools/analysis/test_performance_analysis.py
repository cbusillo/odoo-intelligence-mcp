import pytest

from odoo_intelligence_mcp.tools.analysis.performance_analysis import analyze_performance
from tests.mock_types import MockOdooEnvironment


@pytest.mark.asyncio
async def test_analyze_performance_basic(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"

    result = await analyze_performance(mock_odoo_env, model_name)

    assert "model" in result
    assert result["model"] == model_name
    assert "performance_issues" in result
    assert isinstance(result["performance_issues"], dict)  # Paginated structure


@pytest.mark.asyncio
async def test_analyze_performance_n_plus_one_detection(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order.line"

    result = await analyze_performance(mock_odoo_env, model_name)

    assert "model" in result
    assert "performance_issues" in result
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)


@pytest.mark.asyncio
async def test_analyze_performance_missing_indexes(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"

    result = await analyze_performance(mock_odoo_env, model_name)

    assert "model" in result
    assert "performance_issues" in result


@pytest.mark.asyncio
async def test_analyze_performance_invalid_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "nonexistent.model"

    result = await analyze_performance(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_analyze_performance_complex_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "account.move"

    result = await analyze_performance(mock_odoo_env, model_name)

    assert "model" in result
    assert "performance_issues" in result
    assert "field_analysis" in result
