import subprocess
import sys
from pathlib import Path


def test() -> None:
    subprocess.run([sys.executable, "-m", "pytest"])


def test_unit() -> None:
    subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-m", "not integration"])


def test_integration() -> None:
    subprocess.run([sys.executable, "-m", "pytest", "tests/integration", "-m", "integration"])


def test_cov() -> None:
    subprocess.run([sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing", "--cov-report=html"])


def format_code() -> None:
    subprocess.run([sys.executable, "-m", "ruff", "format", "."])


def lint() -> None:
    subprocess.run([sys.executable, "-m", "ruff", "check", ".", "--fix"])


def check() -> None:
    format_code()
    lint()


def clean() -> None:
    patterns = [".pytest_cache", "htmlcov", ".coverage", "**/__pycache__", "**/*.pyc"]
    for pattern in patterns:
        for path in Path().glob(pattern):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil

                shutil.rmtree(path)
