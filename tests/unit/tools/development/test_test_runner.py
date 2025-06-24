import pytest

from odoo_intelligence_mcp.tools.development.test_runner import run_tests


@pytest.mark.asyncio
async def test_run_module_tests() -> None:
    module = "product_connect"

    result = await run_tests(module)

    assert "module" in result
    assert result["module"] == module
    assert "success" in result


@pytest.mark.asyncio
async def test_run_specific_test_class() -> None:
    module = "product_connect"
    test_class = "TestProductTemplate"

    result = await run_tests(module, test_class=test_class)

    assert "module" in result
    assert "test_class" in result
    assert result["test_class"] == test_class


@pytest.mark.asyncio
async def test_run_specific_test_method() -> None:
    module = "product_connect"
    test_class = "TestProductTemplate"
    test_method = "test_compute_display_name"

    result = await run_tests(module, test_class=test_class, test_method=test_method)

    assert "module" in result
    assert "test_class" in result
    assert "test_method" in result
    assert result["test_method"] == test_method


@pytest.mark.asyncio
async def test_run_tests_with_tags() -> None:
    module = "product_connect"
    test_tags = "smoke,fast"

    result = await run_tests(module, test_tags=test_tags)

    assert "module" in result
    assert "test_tags" in result
    assert result["test_tags"] == test_tags


@pytest.mark.asyncio
async def test_run_tests_invalid_module() -> None:
    module = "nonexistent_module"

    result = await run_tests(module)

    assert "success" in result
    assert result["success"] is False
    assert "error" in result
