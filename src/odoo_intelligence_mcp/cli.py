import shutil
import subprocess
import sys
from pathlib import Path


def test() -> None:
    result = subprocess.run([sys.executable, "-m", "pytest"])
    sys.exit(result.returncode)


def test_unit() -> None:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-m", "not integration"])
    sys.exit(result.returncode)


def test_integration() -> None:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/integration", "-m", "integration"])
    sys.exit(result.returncode)


def test_cov() -> None:
    result = subprocess.run([sys.executable, "-m", "pytest", "--cov", "--cov-report=term-missing", "--cov-report=html"])
    sys.exit(result.returncode)


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
                shutil.rmtree(path)
