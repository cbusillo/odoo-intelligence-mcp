from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.development.test_runner import run_tests


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.development.test_runner.DockerClientManager")
async def test_run_module_tests(mock_docker_manager: MagicMock) -> None:
    module = "product_connect"

    # Mock the Docker client and container
    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(exit_code=0, output=(b"Ran 10 tests in 1.234s\n\nOK", b""))

    mock_docker_instance = MagicMock()
    mock_docker_instance.get_container.return_value = mock_container
    mock_docker_manager.return_value = mock_docker_instance

    result = await run_tests(module)

    assert "module" in result
    assert result["module"] == module
    assert "success" in result


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.development.test_runner.DockerClientManager")
async def test_run_specific_test_class(mock_docker_manager: MagicMock) -> None:
    module = "product_connect"
    test_class = "TestProductTemplate"

    # Mock the Docker client and container
    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(exit_code=0, output=(b"Ran 5 tests in 0.567s\n\nOK", b""))

    mock_docker_instance = MagicMock()
    mock_docker_instance.get_container.return_value = mock_container
    mock_docker_manager.return_value = mock_docker_instance

    result = await run_tests(module, test_class=test_class)

    assert "module" in result
    assert "test_class" in result
    assert result["test_class"] == test_class


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.development.test_runner.DockerClientManager")
async def test_run_specific_test_method(mock_docker_manager: MagicMock) -> None:
    module = "product_connect"
    test_class = "TestProductTemplate"
    test_method = "test_compute_display_name"

    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(exit_code=0, output=(b"Ran 1 test in 0.123s\n\nOK", b""))

    mock_docker_instance = MagicMock()
    mock_docker_instance.get_container.return_value = mock_container
    mock_docker_manager.return_value = mock_docker_instance

    result = await run_tests(module, test_class=test_class, test_method=test_method)

    assert "module" in result
    assert "test_class" in result
    assert "test_method" in result
    assert result["test_method"] == test_method


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.development.test_runner.DockerClientManager")
async def test_run_tests_with_tags(mock_docker_manager: MagicMock) -> None:
    module = "product_connect"
    test_tags = "smoke,fast"

    mock_container = MagicMock()
    mock_container.exec_run.return_value = MagicMock(exit_code=0, output=(b"Ran 3 tests in 0.456s\n\nOK", b""))

    mock_docker_instance = MagicMock()
    mock_docker_instance.get_container.return_value = mock_container
    mock_docker_manager.return_value = mock_docker_instance

    result = await run_tests(module, test_tags=test_tags)

    assert "module" in result
    assert "test_tags" in result
    assert result["test_tags"] == test_tags


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.development.test_runner.DockerClientManager")
async def test_run_tests_invalid_module(mock_docker_manager: MagicMock) -> None:
    module = "nonexistent_module"

    mock_docker_instance = MagicMock()
    mock_docker_instance.get_container.return_value = {"error": "Container not found", "hint": "Start the container"}
    mock_docker_manager.return_value = mock_docker_instance

    result = await run_tests(module)

    assert "error" in result
