# noinspection DuplicatedCode
import asyncio
import contextlib
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from odoo_intelligence_mcp.server import app, run_server


class MockStream:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.index = 0
        self.written: list[bytes] = []

    async def read(self, _n: int = -1) -> bytes:
        if self.index < len(self.messages):
            message = self.messages[self.index]
            self.index += 1
            content = json.dumps(message)
            return f"Content-Length: {len(content)}\r\n\r\n{content}".encode()
        return b""

    async def write(self, data: bytes) -> None:
        self.written.append(data)

    async def drain(self) -> None:
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_initialize_request() -> None:
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "0.1.0", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}},
    }

    read_stream = MockStream([init_request])
    write_stream = MockStream([])

    # Create a task that will run the server
    server_task = asyncio.create_task(
        app.run(read_stream, write_stream, None)  # noinspection PyTypeChecker
    )

    # Give server time to process
    await asyncio.sleep(0.1)

    # Cancel the server task
    server_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await server_task

    # Check response
    assert len(write_stream.written) > 0
    response_data = write_stream.written[0].decode()

    # Parse the response (skip headers)
    response_lines = response_data.split("\r\n")
    json_start = next(i for i, line in enumerate(response_lines) if line.strip() == "") + 1
    response_json = json.loads(response_lines[json_start])

    assert response_json["result"]["protocolVersion"] == "0.1.0"
    assert "serverInfo" in response_json["result"]
    assert response_json["result"]["serverInfo"]["name"] == "odoo-intelligence"


# noinspection DuplicatedCode
@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_list_tools_request() -> None:
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "0.1.0", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}},
    }

    list_tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    read_stream = MockStream([init_request, list_tools_request])
    write_stream = MockStream([])

    server_task = asyncio.create_task(
        app.run(read_stream, write_stream, None)  # noinspection PyTypeChecker
    )

    await asyncio.sleep(0.2)

    server_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await server_task

    # Should have 2 responses
    assert len(write_stream.written) >= 2

    # Parse the list tools response
    response_data = write_stream.written[1].decode()
    response_lines = response_data.split("\r\n")
    json_start = next(i for i, line in enumerate(response_lines) if line.strip() == "") + 1
    response_json = json.loads(response_lines[json_start])

    assert "result" in response_json
    assert "tools" in response_json["result"]
    tools = response_json["result"]["tools"]
    assert len(tools) > 0
    assert all("name" in tool for tool in tools)


# noinspection DuplicatedCode
@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_call_tool_request() -> None:
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "0.1.0", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}},
    }

    call_tool_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "model_info", "arguments": {"model_name": "res.partner"}},
    }

    # Mock the environment
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(return_value={"model": "res.partner", "name": "res.partner", "fields": {}, "methods": []})

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        read_stream = MockStream([init_request, call_tool_request])
        write_stream = MockStream([])

        server_task = asyncio.create_task(
            app.run(read_stream, write_stream, None)  # noinspection PyTypeChecker
        )

        await asyncio.sleep(0.2)

        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task

    # Should have 2 responses
    assert len(write_stream.written) >= 2

    # Parse the tool call response
    response_data = write_stream.written[1].decode()
    response_lines = response_data.split("\r\n")
    json_start = next(i for i, line in enumerate(response_lines) if line.strip() == "") + 1
    response_json = json.loads(response_lines[json_start])

    assert "result" in response_json
    assert "content" in response_json["result"]
    content = response_json["result"]["content"]
    assert len(content) > 0
    assert content[0]["type"] == "text"


# noinspection DuplicatedCode
@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_error_handling() -> None:
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "0.1.0", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}},
    }

    # Invalid method
    invalid_request = {"jsonrpc": "2.0", "id": 2, "method": "invalid/method", "params": {}}

    read_stream = MockStream([init_request, invalid_request])
    write_stream = MockStream([])

    server_task = asyncio.create_task(
        app.run(read_stream, write_stream, None)  # noinspection PyTypeChecker
    )

    await asyncio.sleep(0.2)

    server_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await server_task

    # Should have 2 responses
    assert len(write_stream.written) >= 2

    # Parse the error response
    response_data = write_stream.written[1].decode()
    response_lines = response_data.split("\r\n")
    json_start = next(i for i, line in enumerate(response_lines) if line.strip() == "") + 1
    response_json = json.loads(response_lines[json_start])

    assert "error" in response_json


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_server_function() -> None:
    with patch("odoo_intelligence_mcp.server.stdio_server") as mock_stdio:
        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio.return_value.__aenter__.return_value = (mock_read, mock_write)

        with patch("odoo_intelligence_mcp.server.app.run") as mock_run:
            mock_run.return_value = None

            await run_server()

            mock_stdio.assert_called_once()
            mock_run.assert_called_once()

            # Check initialization options
            init_options = mock_run.call_args[0][2]
            assert init_options.server_name == "odoo-intelligence"
            assert init_options.server_version == "0.1.0"
            assert hasattr(init_options.capabilities, "tools")
