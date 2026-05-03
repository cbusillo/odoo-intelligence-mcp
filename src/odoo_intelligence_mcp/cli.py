import shutil
import subprocess
import sys
from pathlib import Path

NO_LIVE_STACK_MARKERS = "not requires_docker and not requires_odoo"
LIVE_STACK_MARKERS = "requires_docker or requires_odoo"
CI_TEST_EXPRESSION = "not test_get_container_with_auto_start and not test_restart_container_autostart_success"


def _run_pytest(*arguments: str) -> None:
    result = subprocess.run([sys.executable, "-m", "pytest", *arguments])
    sys.exit(result.returncode)


def test() -> None:
    _run_pytest("-m", NO_LIVE_STACK_MARKERS)


def test_unit() -> None:
    _run_pytest("tests/unit", "-m", "not integration", "--no-cov")


def test_integration() -> None:
    _run_pytest("tests/integration", "-m", f"integration and {NO_LIVE_STACK_MARKERS}", "--no-cov")


def test_ci() -> None:
    _run_pytest("tests/unit", "-m", "not integration", "--no-cov", "-q", "-k", CI_TEST_EXPRESSION)


def test_live() -> None:
    _run_pytest("tests/integration", "-m", LIVE_STACK_MARKERS, "--no-cov")


def test_cov() -> None:
    _run_pytest("-m", NO_LIVE_STACK_MARKERS, "--cov", "--cov-report=term-missing", "--cov-report=html")


def test_live_cov() -> None:
    _run_pytest("tests/integration", "-m", LIVE_STACK_MARKERS, "--cov", "--cov-report=term-missing", "--cov-report=html")


def format_code() -> None:
    subprocess.run([sys.executable, "-m", "ruff", "format", "."])


def check() -> None:
    format_code()
    subprocess.run([sys.executable, "-m", "ruff", "check", "."])


def clean() -> None:
    patterns = [".pytest_cache", "htmlcov", ".coverage", "**/__pycache__", "**/*.pyc"]
    for pattern in patterns:
        for path in Path().glob(pattern):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
