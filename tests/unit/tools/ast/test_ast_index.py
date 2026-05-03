from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.ast.ast_index import build_ast_index


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.ast.ast_index.DockerClientManager")
@patch("odoo_intelligence_mcp.tools.ast.ast_index.load_env_config")
async def test_build_ast_index_uses_configured_addon_roots(mock_load_env_config: MagicMock, mock_docker_class: MagicMock) -> None:
    config = MagicMock()
    config.web_container = "odoo-web-1"
    config.addons_path = "/opt/project/addons, /opt/enterprise,"
    mock_load_env_config.return_value = config
    docker_manager = mock_docker_class.return_value
    docker_manager.exec_run.return_value = {"success": True, "stdout": '{"models": {"res.partner": {"class": "Partner"}}}'}

    result = await build_ast_index()

    assert result == {"models": {"res.partner": {"class": "Partner"}}}
    docker_manager.exec_run.assert_called_once()
    container_name, command = docker_manager.exec_run.call_args.args
    assert container_name == "odoo-web-1"
    assert command[:2] == ["python3", "-c"]
    assert 'roots = ["/opt/project/addons", "/opt/enterprise"]' in command[2]
    assert docker_manager.exec_run.call_args.kwargs == {"timeout": 120}


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.ast.ast_index.DockerClientManager")
@patch("odoo_intelligence_mcp.tools.ast.ast_index.load_env_config")
async def test_build_ast_index_uses_explicit_roots(mock_load_env_config: MagicMock, mock_docker_class: MagicMock) -> None:
    config = MagicMock()
    config.web_container = "odoo-web-1"
    config.addons_path = "/unused"
    mock_load_env_config.return_value = config
    docker_manager = mock_docker_class.return_value
    docker_manager.exec_run.return_value = {"success": True, "stdout": '{"models": {}}'}

    await build_ast_index(["/custom/addons"])

    command = docker_manager.exec_run.call_args.args[1]
    assert 'roots = ["/custom/addons"]' in command[2]


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.ast.ast_index.DockerClientManager")
@patch("odoo_intelligence_mcp.tools.ast.ast_index.load_env_config")
async def test_build_ast_index_returns_exec_failure(mock_load_env_config: MagicMock, mock_docker_class: MagicMock) -> None:
    config = MagicMock()
    config.web_container = "odoo-web-1"
    config.addons_path = "/opt/project/addons"
    mock_load_env_config.return_value = config
    docker_manager = mock_docker_class.return_value
    docker_manager.exec_run.return_value = {"success": False, "stderr": "no container", "error": "DockerError"}

    result = await build_ast_index()

    assert result == {"success": False, "error": "no container", "error_type": "DockerError", "container": "odoo-web-1"}


@pytest.mark.asyncio
@patch("odoo_intelligence_mcp.tools.ast.ast_index.DockerClientManager")
@patch("odoo_intelligence_mcp.tools.ast.ast_index.load_env_config")
async def test_build_ast_index_returns_parse_failure(mock_load_env_config: MagicMock, mock_docker_class: MagicMock) -> None:
    config = MagicMock()
    config.web_container = "odoo-web-1"
    config.addons_path = "/opt/project/addons"
    mock_load_env_config.return_value = config
    docker_manager = mock_docker_class.return_value
    docker_manager.exec_run.return_value = {"success": True, "stdout": "not json"}

    result = await build_ast_index()

    assert result["success"] is False
    assert result["error"].startswith("Failed to parse AST index:")
    assert result["error_type"] == "JSONDecodeError"
