import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from odoo_intelligence_mcp import cli


class TestCLIFunctions:
    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_test_function(self, mock_run: MagicMock) -> None:
        cli.test()
        mock_run.assert_called_once_with([sys.executable, "-m", "pytest"])

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_test_unit_function(self, mock_run: MagicMock) -> None:
        cli.test_unit()
        mock_run.assert_called_once_with([sys.executable, "-m", "pytest", "tests/unit", "-m", "not integration"])

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_test_integration_function(self, mock_run: MagicMock) -> None:
        cli.test_integration()
        mock_run.assert_called_once_with([sys.executable, "-m", "pytest", "tests/integration", "-m", "integration"])

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_test_cov_function(self, mock_run: MagicMock) -> None:
        cli.test_cov()
        mock_run.assert_called_once_with([sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing", "--cov-report=html"])

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_format_code_function(self, mock_run: MagicMock) -> None:
        cli.format_code()
        mock_run.assert_called_once_with([sys.executable, "-m", "ruff", "format", "."])

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_lint_function(self, mock_run: MagicMock) -> None:
        cli.lint()
        mock_run.assert_called_once_with([sys.executable, "-m", "ruff", "check", ".", "--fix"])

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_check_function(self, mock_run: MagicMock) -> None:
        with patch("odoo_intelligence_mcp.cli.format_code") as mock_format, patch("odoo_intelligence_mcp.cli.lint") as mock_lint:
            cli.check()
            mock_format.assert_called_once()
            mock_lint.assert_called_once()

    @patch("odoo_intelligence_mcp.cli.Path")
    @patch("odoo_intelligence_mcp.cli.shutil.rmtree")
    def test_clean_function(self, mock_rmtree: MagicMock, mock_path_class: MagicMock) -> None:
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.is_dir.return_value = False

        mock_dir = MagicMock()
        mock_dir.is_file.return_value = False
        mock_dir.is_dir.return_value = True

        mock_path_instance = MagicMock()
        mock_path_instance.glob.side_effect = [
            [mock_file],
            [mock_dir],
            [],
            [mock_file, mock_dir],
            [mock_file],
        ]

        mock_path_class.return_value = mock_path_instance

        cli.clean()

        assert mock_path_instance.glob.call_count == 5
        expected_patterns = [".pytest_cache", "htmlcov", ".coverage", "**/__pycache__", "**/*.pyc"]
        actual_calls = [call(pattern) for pattern in expected_patterns]
        mock_path_instance.glob.assert_has_calls(actual_calls)

        assert mock_file.unlink.call_count == 3  # mock_file appears in patterns 1, 4, and 5
        assert mock_rmtree.call_count == 2  # mock_dir appears in patterns 2 and 4
        mock_rmtree.assert_any_call(mock_dir)

    @patch("odoo_intelligence_mcp.cli.Path")
    @patch("odoo_intelligence_mcp.cli.shutil.rmtree")
    def test_clean_function_no_files(self, mock_rmtree: MagicMock, mock_path_class: MagicMock) -> None:
        mock_path_instance = MagicMock()
        mock_path_instance.glob.return_value = []
        mock_path_class.return_value = mock_path_instance

        cli.clean()

        assert mock_path_instance.glob.call_count == 5
        mock_rmtree.assert_not_called()

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_subprocess_run_with_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, ["test"])

        with pytest.raises(subprocess.CalledProcessError):
            cli.test()

    @patch("odoo_intelligence_mcp.cli.Path")
    def test_clean_handles_permission_error(self, mock_path_class: MagicMock) -> None:
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.unlink.side_effect = PermissionError("Permission denied")

        mock_path_instance = MagicMock()
        mock_path_instance.glob.side_effect = [[mock_file], [], [], [], []]
        mock_path_class.return_value = mock_path_instance

        with pytest.raises(PermissionError):
            cli.clean()

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_all_cli_commands_use_sys_executable(self, mock_run: MagicMock) -> None:
        cli.test()
        assert mock_run.call_args[0][0][0] == sys.executable

        cli.test_unit()
        assert mock_run.call_args[0][0][0] == sys.executable

        cli.test_integration()
        assert mock_run.call_args[0][0][0] == sys.executable

        cli.test_cov()
        assert mock_run.call_args[0][0][0] == sys.executable

        cli.format_code()
        assert mock_run.call_args[0][0][0] == sys.executable

        cli.lint()
        assert mock_run.call_args[0][0][0] == sys.executable
