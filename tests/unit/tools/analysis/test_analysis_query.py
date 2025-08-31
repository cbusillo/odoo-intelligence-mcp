import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.analysis.pattern_analysis import analyze_patterns
from odoo_intelligence_mcp.tools.analysis.performance_analysis import analyze_performance
from odoo_intelligence_mcp.tools.analysis.workflow_states import analyze_workflow_states
from tests.fixtures.types import MockOdooEnvironment


@pytest.mark.asyncio
async def test_analyze_patterns_computed_fields(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "computed_fields"
    result = await analyze_patterns(mock_odoo_env, pattern_type)
    
    assert "computed_fields" in result
    assert isinstance(result["computed_fields"], dict)
    assert "items" in result["computed_fields"]


@pytest.mark.asyncio
async def test_analyze_patterns_related_fields(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "related_fields"
    result = await analyze_patterns(mock_odoo_env, pattern_type)
    
    assert "related_fields" in result
    assert isinstance(result["related_fields"], dict)
    assert "items" in result["related_fields"]


@pytest.mark.asyncio
async def test_analyze_patterns_api_decorators(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "api_decorators"
    result = await analyze_patterns(mock_odoo_env, pattern_type)
    
    assert "api_decorators" in result
    assert isinstance(result["api_decorators"], dict)
    assert "items" in result["api_decorators"]


@pytest.mark.asyncio
async def test_analyze_patterns_all(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "all"
    result = await analyze_patterns(mock_odoo_env, pattern_type)
    
    assert "computed_fields" in result
    assert "related_fields" in result
    assert "api_decorators" in result


@pytest.mark.asyncio
async def test_analyze_performance_basic(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"
    result = await analyze_performance(mock_odoo_env, model_name)
    
    assert "model" in result
    assert result["model"] == model_name
    assert "performance_issues" in result
    assert isinstance(result["performance_issues"], dict)


@pytest.mark.asyncio
async def test_analyze_performance_with_pagination(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"
    pagination = PaginationParams(page_size=5)
    result = await analyze_performance(mock_odoo_env, model_name, pagination)
    
    assert "model" in result
    assert result["model"] == model_name
    assert "performance_issues" in result
    assert isinstance(result["performance_issues"], dict)


@pytest.mark.asyncio
async def test_analyze_workflow_states_basic(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"
    result = await analyze_workflow_states(mock_odoo_env, model_name)
    
    assert "model" in result
    assert result["model"] == model_name
    assert "state_fields" in result
    assert "state_transitions" in result
    assert "button_actions" in result
    assert "automated_transitions" in result


@pytest.mark.asyncio
async def test_analyze_workflow_states_with_pagination(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "sale.order"
    pagination = PaginationParams(page_size=10)
    result = await analyze_workflow_states(mock_odoo_env, model_name, pagination)
    
    assert "model" in result
    assert result["model"] == model_name
    assert "state_fields" in result


@pytest.mark.asyncio
async def test_analyze_workflow_states_nonexistent_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "nonexistent.model"
    result = await analyze_workflow_states(mock_odoo_env, model_name)
    
    assert "error" in result
    assert "Model nonexistent.model not found" in result["error"]