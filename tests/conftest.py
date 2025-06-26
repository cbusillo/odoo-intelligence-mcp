import asyncio
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from tests.fixtures import *  # noqa: F403


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_odoo_env(mock_res_partner_data: dict[str, Any]) -> MagicMock:
    env = MagicMock()
    env.__getitem__.return_value = MagicMock()

    # Mock execute_code as an async method
    async def mock_execute_code(code: str) -> dict[str, Any]:
        # Simulate actual code execution behavior
        try:
            # Check for syntax errors
            compile(code, "<test>", "exec")
            
            # Mock specific code patterns
            if "result = 2 + 2" in code:
                return {"success": True, "result": 4}
            elif "1 / 0" in code:
                return {"success": False, "error": "division by zero", "error_type": "ZeroDivisionError"}
            elif "res.partner" in code and "search" in code:
                return {"success": True, "result": [{"name": "Partner 1", "email": "p1@test.com"}, {"name": "Partner 2", "email": "p2@test.com"}]}
            elif "datetime" in code:
                return {"success": True, "result": {"current": "2024-01-01", "formatted": "Monday"}}
            elif "import non_existent_module" in code:
                return {"success": False, "error": "No module named 'non_existent_module'", "error_type": "ModuleNotFoundError"}
            elif "calculations" in code:
                return {"success": True, "result": {"calculation": 155, "text": "Result is 155"}}
            elif "env['res.partner']" in code and "limit=1" in code:
                return {"success": True, "result_type": "recordset", "model": "res.partner", "count": 1, "ids": [1], "display_names": ["Test Partner"]}
            elif code.strip() == "":
                return {"success": True, "message": "Code executed successfully. Assign to 'result' variable to see output."}
            elif "result = 10 + 45" in code:
                return {"success": True, "result": 55}
            elif "lambda" in code:
                return {"success": True, "result": "<lambda>", "result_type": "function"}
            elif "product.template" in code and "mapped" in code:
                return {"success": True, "result": [100.0, 200.0, 150.0]}
            elif "count_draft" in code:
                return {"success": True, "result": {"total": 30, "by_state": {"draft": 10, "confirmed": 15, "done": 5}}}
            elif "search_count" in code:
                return {"success": True, "result": {"counts": {"draft": 10, "confirmed": 15}, "total": 25}}
            else:
                return {"success": True}
        except SyntaxError:
            return {"success": False, "error": "invalid syntax", "error_type": "SyntaxError"}

    env.execute_code = mock_execute_code
    return env


@pytest.fixture
def mock_docker_client() -> MagicMock:
    client = MagicMock()
    container = MagicMock()
    container.exec_run.return_value = (0, b"Success")
    client.containers.get.return_value = container
    return client


@pytest_asyncio.fixture
async def async_mock_odoo_env() -> AsyncMock:
    env = AsyncMock()
    env.__getitem__.return_value = AsyncMock()
    return env


@pytest.fixture
def sample_model_data() -> dict[str, Any]:
    return {
        "name": "product.template",
        "model": "product.template",
        "fields": {
            "name": {"type": "char", "string": "Name", "required": True},
            "list_price": {"type": "float", "string": "Sales Price"},
            "standard_price": {"type": "float", "string": "Cost"},
        },
        "methods": ["create", "write", "unlink"],
        "_inherit": ["mail.thread", "mail.activity.mixin"],
    }


@pytest.fixture
def temp_test_dir(tmp_path: Path) -> Path:
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    return test_dir


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    return


@pytest.fixture
def mock_mcp_context() -> dict[str, Any]:
    return {
        "server_name": "odoo_intelligence_mcp",
        "request_id": "test-request-123",
    }


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "requires_docker: mark test as requiring Docker to be running")
    config.addinivalue_line("markers", "requires_odoo: mark test as requiring Odoo instance")
