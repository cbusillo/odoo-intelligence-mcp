import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp import cli

if TYPE_CHECKING:
    from pathlib import Path


class TestCLIFunctions:
    @pytest.mark.parametrize("returncode", [0, 1, 5])
    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_test_commands_exit_with_pytest_returncode(self, mock_run: MagicMock, returncode: int) -> None:
        mock_run.return_value.returncode = returncode
        with pytest.raises(SystemExit) as exc_info:
            cli.test()
        assert exc_info.value.code == returncode
        assert mock_run.call_args[0][0][:3] == [sys.executable, "-m", "pytest"]

    @patch("odoo_intelligence_mcp.cli.subprocess.run")
    def test_check_formats_before_linting(self, mock_run: MagicMock) -> None:
        with patch("odoo_intelligence_mcp.cli.format_code") as mock_format:
            cli.check()
            mock_format.assert_called_once()
            assert mock_run.call_args[0][0][:3] == [sys.executable, "-m", "ruff"]

    def test_clean_removes_generated_artifacts_and_keeps_sources(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source_file = tmp_path / "src" / "package" / "module.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("value = 1\n")
        bytecode_directory = source_file.parent / "__pycache__"
        bytecode_directory.mkdir()
        (bytecode_directory / "module.cpython-314.pyc").write_bytes(b"")
        stray_bytecode = source_file.parent / "stray.pyc"
        stray_bytecode.write_bytes(b"")
        (tmp_path / ".pytest_cache").mkdir()
        (tmp_path / "htmlcov").mkdir()
        (tmp_path / "coverage.xml").write_text("<coverage/>")
        (tmp_path / ".coverage").write_text("")
        monkeypatch.chdir(tmp_path)

        cli.clean()

        assert source_file.exists()
        assert not bytecode_directory.exists()
        assert not stray_bytecode.exists()
        assert not (tmp_path / ".pytest_cache").exists()
        assert not (tmp_path / "htmlcov").exists()
        assert not (tmp_path / "coverage.xml").exists()
        assert not (tmp_path / ".coverage").exists()
