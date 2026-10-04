import sys
from subprocess import CompletedProcess
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

    @pytest.mark.parametrize("returncode", [0, 1, 19])
    def test_format_propagates_failure(self, returncode: int) -> None:
        with patch.object(cli.subprocess, "run", return_value=CompletedProcess([], returncode)) as mock_run:
            if returncode:
                with pytest.raises(SystemExit) as exception:
                    cli.format_code()
                assert exception.value.code == returncode
            else:
                cli.format_code()
        mock_run.assert_called_once()

    @pytest.mark.parametrize(
        ("formatter_returncode", "lint_returncode"),
        [(0, 0), (0, 19), (7, 0), (7, 19)],
    )
    def test_check_propagates_first_failure(self, formatter_returncode: int, lint_returncode: int) -> None:
        outcomes = [CompletedProcess([], formatter_returncode), CompletedProcess([], lint_returncode)]
        with patch.object(cli.subprocess, "run", side_effect=outcomes) as mock_run, pytest.raises(SystemExit) as exception:
            cli.check()
        assert exception.value.code == (formatter_returncode or lint_returncode)
        assert mock_run.call_count == (1 if formatter_returncode else 2)

    def test_check_formats_source_and_lints_it(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        source_file = tmp_path / "module.py"
        source_file.write_text("if True: answer=1\n")
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exception:
            cli.check()

        assert exception.value.code == 0
        assert source_file.read_text() == "if True:\n    answer = 1\n"

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
