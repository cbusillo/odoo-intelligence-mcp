import subprocess
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.operations.container_restart import odoo_restart
from odoo_intelligence_mcp.tools.operations.container_status import odoo_status
from odoo_intelligence_mcp.tools.operations.module_update import odoo_update_module


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_manager_init() -> None:
    env_manager = HostOdooEnvironmentManager()

    assert env_manager.container_name == "odoo-opw-shell-1"
    assert env_manager.database == "opw"
    assert "/opt/project/addons" in env_manager.addons_path


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_execute_code() -> None:
    env_manager = HostOdooEnvironmentManager()

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": 123}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        env = await env_manager.get_environment()
        result = await env.execute_code("result = 123")

        assert result == {"result": 123}

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "exec" in call_args
        assert "-i" in call_args
        assert env_manager.container_name in call_args
        assert "/odoo/odoo-bin" in call_args
        assert "shell" in call_args


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_execute_code_error() -> None:
    env_manager = HostOdooEnvironmentManager()

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Division by zero"
        mock_run.return_value = mock_result

        env = await env_manager.get_environment()

        with pytest.raises(RuntimeError, match="Division by zero"):
            await env.execute_code("result = 1/0")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_status_check() -> None:
    with patch("subprocess.run") as mock_run:
        # Mock successful status checks
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "running"
        mock_run.return_value.stderr = ""

        result = await odoo_status()

        assert result["overall_status"] == "healthy"
        assert "containers" in result
        assert "odoo-opw-web-1" in result["containers"]
        assert result["containers"]["odoo-opw-web-1"]["status"] == "running"

        # Verify subprocess was called for each container
        assert mock_run.call_count >= 3  # web, shell, script-runner


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_restart() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        result = await odoo_restart(services="web-1")

        assert result["success"] is True
        assert "restarted" in result
        assert "web-1" in result["restarted"]

        # Verify docker compose restart was called
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "restart" in call_args
        assert "web-1" in call_args


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_module_update() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Module 'product_connect' updated successfully"
        mock_run.return_value.stderr = ""

        result = await odoo_update_module("product_connect")

        assert result["success"] is True
        assert "updated" in result["modules"]
        assert "product_connect" in result["modules"]["updated"]

        # Verify docker exec was called correctly
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "exec" in call_args
        assert "odoo-opw-script-runner-1" in call_args
        assert "/odoo/odoo-bin" in call_args
        assert "-u" in call_args
        assert "product_connect" in call_args


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_connection_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.SubprocessError("Cannot connect to Docker")

        result = await odoo_status()

        assert result["overall_status"] == "unhealthy"
        assert "errors" in result


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_environment_with_actual_docker_check() -> None:
    # This test checks if Docker is actually available
    # It's marked as docker so it can be skipped in CI
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=5)
        docker_available = result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        docker_available = False

    if not docker_available:
        pytest.skip("Docker not available")

    # If we get here, Docker is available
    # Try to check our specific containers
    result = subprocess.run(["docker", "ps", "--filter", "name=odoo-opw", "--format", "{{.Names}}"], capture_output=True, text=True)

    result.stdout.strip().split("\n") if result.stdout else []

    # Just verify we can communicate with Docker
    assert result.returncode == 0


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_odoo_shell_command_execution() -> None:
    env_manager = HostOdooEnvironmentManager()

    with patch("subprocess.run") as mock_run:
        # Mock a successful Odoo shell command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"partner_count": 42}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        env = await env_manager.get_environment()
        result = await env.execute_code("""
result = {"partner_count": env['res.partner'].search_count([])}
""")

        assert result == {"partner_count": 42}

        # Verify the command structure
        call_args = mock_run.call_args
        assert call_args[1]["input"] is not None  # Code was passed via stdin
        assert call_args[1]["timeout"] == 30  # Default timeout
