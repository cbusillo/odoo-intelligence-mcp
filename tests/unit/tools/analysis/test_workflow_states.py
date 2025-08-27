import pytest

from odoo_intelligence_mcp.tools.analysis.workflow_states import analyze_workflow_states
from tests.mock_types import MockOdooEnvironment


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
async def test_analyze_workflow_states_with_state_fields(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "purchase.order"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "model" in result
    assert "state_fields" in result
    assert isinstance(result["state_fields"], dict)


@pytest.mark.asyncio
async def test_analyze_workflow_states_state_transitions(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "account.move"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "state_transitions" in result
    assert isinstance(result["state_transitions"], dict)  # Paginated structure
    assert "items" in result["state_transitions"]


@pytest.mark.asyncio
async def test_analyze_workflow_states_button_actions(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "mrp.production"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "button_actions" in result
    assert isinstance(result["button_actions"], dict)  # Paginated structure
    assert "items" in result["button_actions"]


@pytest.mark.asyncio
async def test_analyze_workflow_states_automated_transitions(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "stock.picking"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "automated_transitions" in result
    assert isinstance(result["automated_transitions"], dict)  # Paginated structure
    assert "items" in result["automated_transitions"]


@pytest.mark.asyncio
async def test_analyze_workflow_states_invalid_model(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "nonexistent.model"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_analyze_workflow_states_no_states(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "product.template"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "model" in result
    assert "state_fields" in result
    # Product.template usually doesn't have workflow states


@pytest.mark.asyncio
async def test_analyze_workflow_states_complex_workflow(mock_odoo_env: MockOdooEnvironment) -> None:
    model_name = "project.task"

    result = await analyze_workflow_states(mock_odoo_env, model_name)

    assert "model" in result
    assert "state_fields" in result
    assert "state_transitions" in result
    assert "state_dependencies" in result


@pytest.mark.asyncio
async def test_analyze_workflow_states_with_pagination(mock_odoo_env: MockOdooEnvironment) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    model_name = "sale.order"
    pagination = PaginationParams(page=1, page_size=5)

    result = await analyze_workflow_states(mock_odoo_env, model_name, pagination)

    assert "model" in result
    assert "state_transitions" in result
    if isinstance(result["state_transitions"], dict):
        assert "pagination" in result["state_transitions"]
