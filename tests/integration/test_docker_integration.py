import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.operations.container_restart import odoo_restart
from odoo_intelligence_mcp.tools.operations.container_status import odoo_status
from odoo_intelligence_mcp.tools.operations.module_update import odoo_update_module
from odoo_intelligence_mcp.utils.error_utils import DockerConnectionError


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_manager_init() -> None:
    env_manager = HostOdooEnvironmentManager()

    # Get expected values from environment or defaults
    expected_prefix = os.getenv("ODOO_CONTAINER_PREFIX", "odoo")
    expected_container = f"{expected_prefix}-script-runner-1"
    expected_db = os.getenv("ODOO_DB_NAME", "odoo")
    expected_addons = os.getenv("ODOO_ADDONS_PATH", "/opt/project/addons,/odoo/addons,/volumes/enterprise")

    assert env_manager.container_name == expected_container
    assert env_manager.database == expected_db
    assert any(path in env_manager.addons_path for path in expected_addons.split(","))


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_execute_code() -> None:
    env_manager = HostOdooEnvironmentManager()

    with patch("subprocess.run") as mock_run:
        # Mock responses for container check (not found), start (success), and execute (success)
        mock_results = [
            # Container check - not found
            MagicMock(returncode=0, stdout="", stderr=""),
            # Container start - success
            MagicMock(returncode=0, stdout="odoo-script-runner-1\n", stderr=""),
            # Code execution - success
            MagicMock(returncode=0, stdout='{"result": 123}', stderr=""),
        ]
        mock_run.side_effect = mock_results

        env = await env_manager.get_environment()
        result = await env.execute_code("result = 123")

        assert result == {"result": 123}

        # Verify subprocess was called 3 times (check, start, execute)
        assert mock_run.call_count == 3

        # Check the final call was the code execution
        final_call_args = mock_run.call_args_list[-1][0][0]
        assert "docker" in final_call_args
        assert "exec" in final_call_args
        assert "-i" in final_call_args
        assert env_manager.container_name in final_call_args
        assert "/odoo/odoo-bin" in final_call_args
        assert "shell" in final_call_args


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

        with pytest.raises(DockerConnectionError, match="Division by zero"):
            await env.execute_code("result = 1/0")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_status_check() -> None:
    with (
        patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager") as mock_docker_manager_class,
        patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_docker_manager_class2,
    ):
        # Mock Docker client manager and container
        mock_docker_manager = MagicMock()
        mock_docker_manager_class.return_value = mock_docker_manager
        mock_docker_manager_class2.return_value = mock_docker_manager

        # Mock successful ping
        mock_docker_manager.client.ping.return_value = None

        # Mock containers with running status - create multiple instances for each call
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_docker_manager.get_container.return_value = mock_container

        result = await odoo_status()

        # Get expected values from environment or defaults
        expected_prefix = os.getenv("ODOO_CONTAINER_PREFIX", "odoo")
        expected_web_container = f"{expected_prefix}-web-1"

        print(f"Result: {result}")
        print(f"Expected container: {expected_web_container}")

        assert result["overall_status"] == "healthy"
        assert "containers" in result
        assert expected_web_container in result["containers"]
        assert result["containers"][expected_web_container]["status"] == "running"

        # Verify get_container was called for each container
        assert mock_docker_manager.get_container.call_count >= 3  # web, shell, script-runner


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_restart() -> None:
    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager") as mock_docker_manager_class:
        # Mock Docker client manager
        mock_docker_manager = MagicMock()
        mock_docker_manager_class.return_value = mock_docker_manager

        # Mock successful container restart operation
        mock_docker_manager.handle_container_operation.return_value = {"success": True, "status": "running"}

        result = await odoo_restart(services="web-1")

        assert result["success"] is True
        assert "services" in result


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_module_update() -> None:
    with patch("docker.from_env") as mock_docker_from_env:
        # Mock Docker client
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        # Mock container
        mock_container = MagicMock()
        mock_client.containers.get.return_value = mock_container

        # Mock successful exec_run
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"Module 'product_connect' updated successfully", b"")
        mock_container.exec_run.return_value = mock_exec_result

        result = await odoo_update_module("product_connect")

        assert result["success"] is True
        assert "modules" in result
        assert "product_connect" in result["modules"]
        assert result["operation"] == "update"

        # Verify container.exec_run was called
        mock_container.exec_run.assert_called_once()
        call_args = mock_container.exec_run.call_args[0][0]
        assert "/odoo/odoo-bin" in call_args
        assert "-u" in call_args
        assert "product_connect" in call_args


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_connection_failure() -> None:
    with (
        patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager") as mock_docker_manager_class,
        patch("odoo_intelligence_mcp.tools.operations.container_status.DockerClientManager") as mock_docker_manager_class2,
    ):
        # Mock Docker client manager to raise connection error
        mock_docker_manager = MagicMock()
        mock_docker_manager_class.return_value = mock_docker_manager
        mock_docker_manager_class2.return_value = mock_docker_manager

        # Mock Docker client ping to fail
        mock_docker_manager.client.ping.side_effect = Exception("Cannot connect to Docker")

        result = await odoo_status()

        assert result["success"] is False
        assert "error" in result


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
    expected_prefix = os.getenv("ODOO_CONTAINER_PREFIX", "odoo")
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={expected_prefix}", "--format", "{{.Names}}"], capture_output=True, text=True
    )

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
