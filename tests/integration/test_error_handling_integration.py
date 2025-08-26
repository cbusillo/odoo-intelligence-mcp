import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import TextContent

from odoo_intelligence_mcp.server import handle_call_tool
from odoo_intelligence_mcp.utils.error_utils import (
    DockerConnectionError,
    FieldNotFoundError,
    InvalidArgumentError,
    ModelNotFoundError,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_model_not_found_error() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(side_effect=ModelNotFoundError("invalid.model"))

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("model_info", {"model_name": "invalid.model"})

    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    content = json.loads(result[0].text)

    assert content["success"] is False
    assert "invalid.model" in content["error"]
    assert content["error_type"] == "ModelNotFoundError"
    assert content["model"] == "invalid.model"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_field_not_found_error() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(side_effect=FieldNotFoundError("res.partner", "invalid_field"))

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("field_usages", {"model_name": "res.partner", "field_name": "invalid_field"})

    assert len(result) == 1
    content = json.loads(result[0].text)

    assert content["success"] is False
    assert "invalid_field" in content["error"]
    assert content["error_type"] == "FieldNotFoundError"
    assert content["model"] == "res.partner"
    assert content["field"] == "invalid_field"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_docker_connection_error() -> None:
    AsyncMock()

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment") as mock_get_env:
        from odoo_intelligence_mcp.core.env import load_env_config

        config = load_env_config()
        container_name = config["container_name"]
        mock_get_env.side_effect = DockerConnectionError(container_name, "Container not running")

        result = await handle_call_tool("model_info", {"model_name": "res.partner"})

    assert len(result) == 1
    content = json.loads(result[0].text)

    assert content["success"] is False
    from odoo_intelligence_mcp.core.env import load_env_config

    config = load_env_config()
    container_name = config["container_name"]

    assert container_name in content["error"]
    assert "Container not running" in content["error"]
    assert content["error_type"] == "DockerConnectionError"
    assert content["container"] == container_name


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_invalid_argument_validation() -> None:
    # Test with empty model name
    result = await handle_call_tool("model_info", {"model_name": ""})

    assert len(result) == 1
    content = json.loads(result[0].text)

    assert content["success"] is False
    assert "model_name" in content["error"]
    assert content["error_type"] == "InvalidArgumentError"
    assert content["argument"] == "model_name"
    assert content["expected_type"] == "non-empty string"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_invalid_model_name_format() -> None:
    # Test with invalid model name format
    result = await handle_call_tool("model_info", {"model_name": "res.partner!"})

    assert len(result) == 1
    content = json.loads(result[0].text)

    assert content["success"] is False
    assert content["error_type"] == "InvalidArgumentError"
    assert content["argument"] == "model_name"
    assert "valid Odoo model name" in content["expected_type"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_call_tool_unexpected_error() -> None:
    mock_env = AsyncMock()
    mock_env.execute_code = AsyncMock(side_effect=RuntimeError("Unexpected runtime error"))

    with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
        result = await handle_call_tool("model_info", {"model_name": "res.partner"})

    assert len(result) == 1
    content = json.loads(result[0].text)

    assert content["success"] is False
    assert "Unexpected runtime error" in content["error"]
    assert content["error_type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_messages_are_user_friendly() -> None:
    # Test that error messages are informative and user-friendly
    test_cases = [
        (ModelNotFoundError("invalid.model"), "Model 'invalid.model' not found in Odoo registry"),
        (FieldNotFoundError("res.partner", "invalid_field"), "Field 'invalid_field' not found in model 'res.partner'"),
        (
            DockerConnectionError("container", "Connection refused"),
            "Failed to connect to Docker container 'container': Connection refused",
        ),
        (InvalidArgumentError("param", "string", 123), "Invalid argument 'param': expected string, got int"),
    ]

    for error, expected_message in test_cases:
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(side_effect=error)

        with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", return_value=mock_env):
            result = await handle_call_tool("model_info", {"model_name": "test"})

        content = json.loads(result[0].text)
        assert content["error"] == expected_message
