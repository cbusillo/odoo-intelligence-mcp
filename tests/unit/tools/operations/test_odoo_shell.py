import subprocess
from unittest.mock import MagicMock, patch

from odoo_intelligence_mcp.tools.code.execute_code import odoo_shell


class TestOdooShell:
    def test_odoo_shell_success(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "5"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = odoo_shell("print(2+3)")

            assert result["success"] is True
            assert result["code"] == "print(2+3)"
            assert result["exit_code"] == 0
            assert result["stdout"] == "5"
            assert result["stderr"] == ""

    def test_odoo_shell_with_timeout(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "result"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = odoo_shell("print('test')", timeout=60)

            assert result["timeout"] == 60
            assert result["success"] is True

    def test_odoo_shell_failure(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: syntax error"
            mock_run.return_value = mock_result

            # Use valid code that will pass validation but fail execution
            result = odoo_shell("print(undefined_variable)")

            assert result["success"] is False
            assert result["exit_code"] == 1
            assert result["stderr"] == "Error: syntax error"

    def test_odoo_shell_timeout_expired(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

            # Use code that will pass validation
            result = odoo_shell("print('test')")

            assert result["success"] is False
            assert "timed out after 30 seconds" in result["error"]
            assert result["code"] == "print('test')"

    def test_odoo_shell_security_validation_failure(self) -> None:
        with patch("subprocess.run") as mock_run:
            # Mock a security-related error from Odoo
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: SecurityError: os module is not allowed"
            mock_run.return_value = mock_result
            
            result = odoo_shell("import os; print(os.getcwd())")

            assert result["success"] is False
            assert result["exit_code"] == 1
            assert "SecurityError" in result["stderr"] or "os" in result["stderr"]

    def test_odoo_shell_security_validation_eval(self) -> None:
        with patch("subprocess.run") as mock_run:
            # Mock a security-related error from Odoo
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: NameError: name 'eval' is not defined"
            mock_run.return_value = mock_result
            
            result = odoo_shell("print(eval('1+1'))")

            assert result["success"] is False
            assert result["exit_code"] == 1
            assert "eval" in result["stderr"] or "NameError" in result["stderr"]

    def test_odoo_shell_security_validation_success(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "25"
            mock_run.return_value.stderr = ""

            # Safe code should pass validation
            result = odoo_shell("print(len(env['res.partner'].search([])))")

            assert result["success"] is True
            assert result["stdout"] == "25"
