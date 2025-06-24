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
        # Return appropriate data based on the code
        if "res.partner" in code:
            return mock_res_partner_data
        return {"success": True}

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
