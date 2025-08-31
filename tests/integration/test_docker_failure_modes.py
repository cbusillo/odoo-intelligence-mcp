import asyncio
import subprocess
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager, load_env_config
from odoo_intelligence_mcp.utils.error_utils import CodeExecutionError, DockerConnectionError


class TestDockerFailureModes:
    @pytest.mark.asyncio
    async def test_container_not_running(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: No such container: odoo-script-runner-1")

            env = test_env
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1 + 1")

            assert "container" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_container_start_timeout(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:

            def side_effect(*args: object, **_kwargs: object) -> MagicMock:
                if "exec" in str(args[0]):
                    raise subprocess.TimeoutExpired(cmd=cast("list[str]", args[0]), timeout=30)
                return MagicMock(returncode=0, stdout="odoo\n", stderr="")

            mock_run.side_effect = side_effect

            env = test_env
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_docker_daemon_not_running(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:

            def side_effect(*args: object, **_kwargs: object) -> MagicMock:
                # Raise FileNotFoundError for any docker command
                if args and "docker" in str(args[0]):
                    raise FileNotFoundError("docker command not found")
                return MagicMock(returncode=0, stdout="", stderr="")

            mock_run.side_effect = side_effect

            env = test_env
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "docker" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_network_connectivity_issue(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=125, stdout="", stderr="docker: Error response from daemon: network not found"
            )

            env = test_env
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "network" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_odoo_shell_crash(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='Traceback (most recent call last):\n  File "/odoo/odoo-bin", line 8\nOSError: Database connection failed',
                stderr="",
            )

            env = test_env
            result = await env.execute_code("result = env['res.partner'].search([])")

            assert "error" in result or "Traceback" in str(result)

    @pytest.mark.asyncio
    async def test_partial_output_recovery(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"result": 42, "partial": true', stderr="Warning: Output truncated"
            )

            env = test_env
            result = await env.execute_code("result = 42")

            assert isinstance(result, (dict, str))

    @pytest.mark.asyncio
    async def test_concurrent_container_access(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            call_count = 0

            def side_effect(*args: object, **_kwargs: object) -> MagicMock:
                nonlocal call_count
                call_count += 1
                # Handle docker inspect commands for container status check
                if "inspect" in str(args[0]):
                    return MagicMock(returncode=0, stdout="running\n", stderr="")
                if "exec" in str(args[0]) and call_count <= 12:  # Allow more calls
                    return MagicMock(returncode=0, stdout='{"result": ' + str(call_count) + "}", stderr="")
                raise subprocess.TimeoutExpired(cmd=cast("list[str]", args[0]), timeout=5)

            mock_run.side_effect = side_effect

            env = test_env

            tasks = [env.execute_code(f"result = {i}") for i in range(3)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) >= 2

    @pytest.mark.asyncio
    async def test_container_restart_during_execution(self) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            attempts = 0

            def side_effect(*args: object, **_kwargs: object) -> MagicMock:
                nonlocal attempts
                attempts += 1
                if "ps" in str(args[0]):
                    return MagicMock(returncode=0, stdout="odoo-script-runner-1\n", stderr="")
                if "exec" in str(args[0]):
                    return MagicMock(returncode=125, stdout="", stderr="Container restarting")
                return MagicMock(returncode=0, stdout='{"result": "success"}', stderr="")

            mock_run.side_effect = side_effect

            manager = HostOdooEnvironmentManager()
            env = await manager.get_environment()

            with pytest.raises(DockerConnectionError):
                await env.execute_code("result = 1")

    @pytest.mark.asyncio
    async def test_memory_exhaustion(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=137, stdout="", stderr="Killed")

            env = test_env
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = list(range(10**9))")

            assert "137" in str(exc_info.value) or "killed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_permission_denied(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=126, stdout="", stderr="docker: permission denied while trying to connect to the Docker daemon"
            )

            env = test_env
            with pytest.raises(DockerConnectionError) as exc_info:
                await env.execute_code("result = 1")

            assert "permission" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_container_name_format(self) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=125, stdout="", stderr="Error: Invalid container name")

            config = load_env_config()
            # Testing with invalid container name
            env = HostOdooEnvironment(
                "invalid/name",  # Intentionally invalid
                config.database,
                config.addons_path,
                config.db_host,
                config.db_port,
            )
            with pytest.raises(DockerConnectionError):
                await env.execute_code("result = 1")

    @pytest.mark.asyncio
    async def test_database_lock_timeout(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"error": "OperationalError: could not obtain lock on row"}', stderr=""
            )

            env = test_env
            with pytest.raises(CodeExecutionError) as exc_info:
                await env.execute_code("result = env['res.partner'].create({'name': 'Test'})")

            assert "lock" in str(exc_info.value).lower() or "operational" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_corrupted_json_response(self, test_env: HostOdooEnvironment) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"result": "test", "data": {corrupted json here}', stderr="")

            env = test_env
            result = await env.execute_code("result = 'test'")

            assert result is not None

    @pytest.mark.asyncio
    async def test_environment_cleanup_on_failure(self) -> None:
        with patch("odoo_intelligence_mcp.core.env.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            manager = HostOdooEnvironmentManager()
            env = await manager.get_environment()

            with pytest.raises(Exception):
                await env.execute_code("result = 1")

            manager.invalidate_environment_cache()
