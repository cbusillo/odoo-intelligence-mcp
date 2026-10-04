import asyncio
import threading
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from odoo_intelligence_mcp import server

if TYPE_CHECKING:
    from odoo_intelligence_mcp.core.env import HostOdooEnvironment


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cancelled_docker_tool_keeps_mcp_session_open(test_env: HostOdooEnvironment, monkeypatch: pytest.MonkeyPatch) -> None:
    operation_started = threading.Event()
    finish_operation = threading.Event()
    scope_ready = asyncio.get_running_loop().create_future()
    request_finished = asyncio.Event()
    mock_env = MagicMock()
    mock_env.execute_code = test_env.execute_code
    mock_env.cr = None

    def execute_operation(code: str) -> dict[str, object]:
        operation_started.set()
        assert finish_operation.wait(timeout=2)
        return {"completed": True}

    monkeypatch.setattr(test_env, "_execute_code", execute_operation)
    monkeypatch.setattr(server.odoo_env_manager, "get_environment", AsyncMock(return_value=mock_env))

    with anyio.fail_after(5):
        async with create_client_server_memory_streams() as (client_streams, server_streams), anyio.create_task_group() as group:
            group.start_soon(server.app.run, *server_streams, server.app.create_initialization_options())
            async with ClientSession(*client_streams) as session:
                await session.initialize()

                async def execute_request() -> None:
                    with anyio.CancelScope() as scope:
                        scope_ready.set_result(scope)
                        await session.call_tool("execute_code", {"code": "result = True"})
                    request_finished.set()

                group.start_soon(execute_request)
                try:
                    scope = await scope_ready
                    assert await asyncio.to_thread(operation_started.wait, 1)
                    scope.cancel()
                    await request_finished.wait()
                finally:
                    finish_operation.set()
                response = await session.call_tool("execute_code", {"code": "result = True"})
                assert not response.is_error
                tools = await session.list_tools()
                assert tools.tools
            group.cancel_scope.cancel()
