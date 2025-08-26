import pytest

from odoo_intelligence_mcp.tools.analysis.pattern_analysis import analyze_patterns
from tests.mock_types import MockOdooEnvironment


@pytest.mark.asyncio
async def test_analyze_computed_fields(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "computed_fields"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "computed_fields" in result
    assert isinstance(result["computed_fields"], dict)  # Paginated structure
    assert "items" in result["computed_fields"]


@pytest.mark.asyncio
async def test_analyze_related_fields(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "related_fields"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "related_fields" in result
    assert isinstance(result["related_fields"], dict)  # Paginated structure
    assert "items" in result["related_fields"]


@pytest.mark.asyncio
async def test_analyze_api_decorators(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "api_decorators"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "api_decorators" in result
    assert isinstance(result["api_decorators"], dict)  # Paginated structure
    assert "items" in result["api_decorators"]


@pytest.mark.asyncio
async def test_analyze_custom_methods(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "custom_methods"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "custom_methods" in result
    assert isinstance(result["custom_methods"], dict)  # Paginated structure
    assert "items" in result["custom_methods"]


@pytest.mark.asyncio
async def test_analyze_state_machines(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "state_machines"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "state_machines" in result
    assert isinstance(result["state_machines"], dict)  # Paginated structure
    assert "items" in result["state_machines"]


@pytest.mark.asyncio
async def test_analyze_all_patterns(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "all"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "computed_fields" in result
    assert "related_fields" in result
    assert "api_decorators" in result
    assert "custom_methods" in result
    assert "state_machines" in result


@pytest.mark.asyncio
async def test_invalid_pattern_type(mock_odoo_env: MockOdooEnvironment) -> None:
    pattern_type = "invalid_pattern"

    result = await analyze_patterns(mock_odoo_env, pattern_type)

    assert "error" in result
    assert "unsupported" in result["error"].lower()
