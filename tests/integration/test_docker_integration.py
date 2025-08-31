import subprocess
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager, load_env_config
from odoo_intelligence_mcp.tools.operations.container_restart import odoo_restart
from odoo_intelligence_mcp.tools.operations.container_status import odoo_status
from odoo_intelligence_mcp.tools.operations.module_update import odoo_update_module
from odoo_intelligence_mcp.utils.error_utils import DockerConnectionError


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_manager_init() -> None:
    config = load_env_config()
    env_manager = HostOdooEnvironmentManager()

    expected_container = config.container_name
    expected_db = config.database
    expected_addons = config.addons_path

    assert env_manager.container_name == expected_container
    assert env_manager.database == expected_db
    assert any(path in env_manager.addons_path for path in expected_addons.split(","))


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_host_odoo_environment_execute_code() -> None:
    env_manager = HostOdooEnvironmentManager()

    with patch("subprocess.run") as mock_run:
        # Mock responses for container operations
        def side_effect(*args: object, **kwargs: object) -> MagicMock:
            cmd = args[0] if args else []
            # Handle docker inspect for status check
            if "inspect" in cmd and "--format" in cmd and "State.Status" in str(cmd):
                return MagicMock(returncode=0, stdout="running\n", stderr="")
            # Handle docker inspect for health check
            if "inspect" in cmd and "--format" in cmd and "State.Health.Status" in str(cmd):
                return MagicMock(returncode=0, stdout="healthy\n", stderr="")
            # Handle docker exec for code execution
            if "exec" in cmd:
                return MagicMock(returncode=0, stdout='{"result": 123}', stderr="")
            # Default response
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        env = await env_manager.get_environment()
        result = await env.execute_code("result = 123")

        assert result == {"result": 123}

        # Verify subprocess was called (at least for status check and execute)
        assert mock_run.call_count >= 2

        # Find the exec call in the call list
        exec_call = None
        for call in mock_run.call_args_list:
            if call[0] and "exec" in call[0][0]:
                exec_call = call[0][0]
                break

        assert exec_call is not None
        assert "docker" in exec_call
        assert "exec" in exec_call
        assert "-i" in exec_call
        assert env_manager.container_name in exec_call
        assert "/odoo/odoo-bin" in exec_call
        assert "shell" in exec_call


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

        # Get expected values from config
        config = load_env_config()
        expected_web_container = config.web_container

        print(f"Result: {result}")
        print(f"Expected container: {expected_web_container}")

        assert result["success"] is True
        assert result["data"]["overall_status"] == "healthy"
        assert "containers" in result["data"]
        assert expected_web_container in result["data"]["containers"]
        assert result["data"]["containers"][expected_web_container]["status"] == "running"

        # Verify get_container was called for each container
        assert mock_docker_manager.get_container.call_count >= 3  # web, shell, script-runner


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.docker
async def test_docker_container_restart() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.container_restart.DockerClientManager") as mock_docker_manager_class:
        # Mock Docker client manager
        mock_docker_manager = MagicMock()
        mock_docker_manager_class.return_value = mock_docker_manager

        # Mock successful container restart operation - returns dict with success flag
        mock_docker_manager.handle_container_operation.return_value = {"success": True, "status": "running"}

        result = await odoo_restart(services="web-1")

        assert result["success"] is True
        assert "data" in result
        assert "services" in result["data"]


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
    config = load_env_config()
    expected_prefix = config.container_prefix
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
        assert call_args[1]["timeout"] == 60  # Default timeout increased for stability
