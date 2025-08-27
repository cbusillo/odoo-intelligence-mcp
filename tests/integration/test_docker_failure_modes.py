import asyncio
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.utils.error_utils import DockerConnectionError


class TestDockerFailureModes:
    @pytest.mark.asyncio
    async def test_container_not_running(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: No such container: odoo-script-runner-1")

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1 + 1")

            assert "container" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_container_start_timeout(self) -> None:
        with patch("subprocess.run") as mock_run:

            def side_effect(*args, **kwargs):
                if "start" in args[0]:
                    raise subprocess.TimeoutExpired(args[0], 30)
                return MagicMock(returncode=1, stdout="", stderr="Container not running")

            mock_run.side_effect = side_effect

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            with pytest.raises(DockerConnectionError):
                await env.execute_code("result = 1")

    @pytest.mark.asyncio
    async def test_docker_daemon_not_running(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("docker command not found")

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "docker" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_network_connectivity_issue(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=125, stdout="", stderr="docker: Error response from daemon: network not found"
            )

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "network" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_odoo_shell_crash(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='Traceback (most recent call last):\n  File "/odoo/odoo-bin", line 8\nOSError: Database connection failed',
                stderr="",
            )

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            result = await env.execute_code("result = env['res.partner'].search([])")

            assert "error" in result or "Traceback" in str(result)

    @pytest.mark.asyncio
    async def test_partial_output_recovery(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"result": 42, "partial": true', stderr="Warning: Output truncated"
            )

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            result = await env.execute_code("result = 42")

            assert isinstance(result, (dict, str))

    @pytest.mark.asyncio
    async def test_concurrent_container_access(self) -> None:
        with patch("subprocess.run") as mock_run:
            call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    return MagicMock(returncode=0, stdout='{"result": ' + str(call_count) + "}", stderr="")
                raise subprocess.TimeoutExpired(args[0], 5)

            mock_run.side_effect = side_effect

            env = HostOdooEnvironment("odoo", "odoo", "/test")

            tasks = [env.execute_code(f"result = {i}") for i in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            assert sum(1 for r in results if not isinstance(r, Exception)) >= 2

    @pytest.mark.asyncio
    async def test_container_restart_during_execution(self) -> None:
        with patch("subprocess.run") as mock_run:
            attempts = 0

            def side_effect(*args, **kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    return MagicMock(returncode=125, stdout="", stderr="Container restarting")
                return MagicMock(returncode=0, stdout='{"result": "success"}', stderr="")

            mock_run.side_effect = side_effect

            manager = HostOdooEnvironmentManager()
            env = await manager.get_environment()

            with pytest.raises(DockerConnectionError):
                await env.execute_code("result = 1")

    @pytest.mark.asyncio
    async def test_memory_exhaustion(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=137, stdout="", stderr="Killed")

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = list(range(10**9))")

            assert "137" in str(exc_info.value) or "killed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_permission_denied(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=126, stdout="", stderr="docker: permission denied while trying to connect to the Docker daemon"
            )

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "permission" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_container_name_format(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=125, stdout="", stderr="Error: Invalid container name")

            env = HostOdooEnvironment("invalid/name", "odoo", "/test")
            with pytest.raises(DockerConnectionError):
                await env.execute_code("result = 1")

    @pytest.mark.asyncio
    async def test_database_lock_timeout(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"error": "OperationalError: could not obtain lock on row"}', stderr=""
            )

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            result = await env.execute_code("result = env['res.partner'].create({'name': 'Test'})")

            assert "error" in str(result).lower() or "lock" in str(result).lower()

    @pytest.mark.asyncio
    async def test_corrupted_json_response(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"result": "test", "data": {corrupted json here}', stderr="")

            env = HostOdooEnvironment("odoo", "odoo", "/test")
            result = await env.execute_code("result = 'test'")

            assert result is not None

    @pytest.mark.asyncio
    async def test_environment_cleanup_on_failure(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            manager = HostOdooEnvironmentManager()

            with pytest.raises(Exception):
                env = await manager.get_environment()
                await env.execute_code("result = 1")

            assert manager._cached_env is None or hasattr(manager, "_cleanup_called")
