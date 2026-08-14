import shutil
import subprocess
import sys
from pathlib import Path

NO_LIVE_STACK_MARKERS = "not requires_docker and not requires_odoo"
LIVE_STACK_MARKERS = "requires_docker or requires_odoo"
COVERAGE_REPORT_ARGUMENTS = ("--cov", "--cov-report=term-missing", "--cov-report=html", "--cov-report=xml")
CI_COVERAGE_REPORT_ARGUMENTS = ("--cov", "--cov-report=term-missing", "--cov-report=xml")
LIVE_COVERAGE_FAIL_UNDER = 0


def _run_pytest(*arguments: str) -> None:
    result = subprocess.run([sys.executable, "-m", "pytest", *arguments])
    sys.exit(result.returncode)


def test() -> None:
    _run_pytest("-m", NO_LIVE_STACK_MARKERS)


def test_unit() -> None:
    _run_pytest("tests/unit", "-m", "not integration")


def test_integration() -> None:
    _run_pytest("tests/integration", "-m", f"integration and {NO_LIVE_STACK_MARKERS}")


def test_ci() -> None:
    _run_pytest("tests/unit", "-m", "not integration", "-q")


def test_live() -> None:
    _run_pytest("tests/integration", "-m", LIVE_STACK_MARKERS)


def test_cov() -> None:
    _run_pytest("-m", NO_LIVE_STACK_MARKERS, *COVERAGE_REPORT_ARGUMENTS)


def test_cov_ci() -> None:
    _run_pytest("-m", NO_LIVE_STACK_MARKERS, *CI_COVERAGE_REPORT_ARGUMENTS)


def test_live_cov() -> None:
    _run_pytest(
        "tests/integration",
        "-m",
        LIVE_STACK_MARKERS,
        *COVERAGE_REPORT_ARGUMENTS,
        f"--cov-fail-under={LIVE_COVERAGE_FAIL_UNDER}",
    )


def format_code() -> None:
    subprocess.run([sys.executable, "-m", "ruff", "format", "."])


def check() -> None:
    format_code()
    subprocess.run([sys.executable, "-m", "ruff", "check", "."])


def clean() -> None:
    patterns = [".pytest_cache", "htmlcov", ".coverage", ".coverage.*", "coverage.xml", "**/__pycache__", "**/*.pyc"]
    for pattern in patterns:
        for path in Path().glob(pattern):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
