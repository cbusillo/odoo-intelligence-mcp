from typing import Any
from unittest.mock import AsyncMock

import pytest

from odoo_intelligence_mcp.utils.error_utils import (
    CodeExecutionError,
    DockerConnectionError,
    FieldNotFoundError,
    InvalidArgumentError,
    ModelNotFoundError,
    OdooMCPError,
    create_error_response,
    handle_tool_error,
    validate_field_name,
    validate_method_name,
    validate_model_name,
)


class TestCustomExceptions:
    def test_odoo_mcp_error(self) -> None:
        error = OdooMCPError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_model_not_found_error(self) -> None:
        error = ModelNotFoundError("test.model")
        assert str(error) == "Model 'test.model' not found in Odoo registry"
        assert error.model_name == "test.model"
        assert isinstance(error, OdooMCPError)

    def test_field_not_found_error(self) -> None:
        error = FieldNotFoundError("test.model", "test_field")
        assert str(error) == "Field 'test_field' not found in model 'test.model'"
        assert error.model_name == "test.model"
        assert error.field_name == "test_field"
        assert isinstance(error, OdooMCPError)

    def test_docker_connection_error(self) -> None:
        error = DockerConnectionError("test-container", "Connection refused")
        assert str(error) == "Failed to connect to Docker container 'test-container': Connection refused"
        assert error.container_name == "test-container"
        assert isinstance(error, OdooMCPError)

    def test_code_execution_error(self) -> None:
        error = CodeExecutionError("print('hello')", "SyntaxError: invalid syntax")
        assert str(error) == "Code execution failed: SyntaxError: invalid syntax"
        assert error.code == "print('hello')"
        assert error.error == "SyntaxError: invalid syntax"
        assert isinstance(error, OdooMCPError)

    def test_invalid_argument_error(self) -> None:
        error = InvalidArgumentError("count", "int", "abc")
        assert str(error) == "Invalid argument 'count': expected int, got str"
        assert error.arg_name == "count"
        assert error.expected_type == "int"
        assert error.actual_value == "abc"
        assert isinstance(error, OdooMCPError)


def test_create_error_response_basic() -> None:
    error = ValueError("Test error")
    response = create_error_response(error)
    
    assert response["success"] is False
    assert response["error"] == "Test error"
    assert response["error_type"] == "ValueError"


def test_create_error_response_without_type() -> None:
    error = ValueError("Test error")
    response = create_error_response(error, include_type=False)
    
    assert response["success"] is False
    assert response["error"] == "Test error"
    assert "error_type" not in response


def test_create_error_response_with_odoo_error() -> None:
    error = ModelNotFoundError("test.model")
    response = create_error_response(error)
    
    assert response["success"] is False
    assert response["error"] == "Model 'test.model' not found in Odoo registry"
    assert response["error_type"] == "ModelNotFoundError"


def test_create_error_response_with_field_error() -> None:
    error = FieldNotFoundError("test.model", "test_field")
    response = create_error_response(error)
    
    assert response["success"] is False
    assert response["error"] == "Field 'test_field' not found in model 'test.model'"
    assert response["error_type"] == "FieldNotFoundError"
    assert response["model"] == "test.model"
    assert response["field"] == "test_field"


def test_create_error_response_with_docker_error() -> None:
    error = DockerConnectionError("test-container", "Connection refused")
    response = create_error_response(error)
    
    assert response["success"] is False
    assert response["error_type"] == "DockerConnectionError"
    assert response["container"] == "test-container"


def test_create_error_response_with_code_error() -> None:
    error = CodeExecutionError("print('hello')", "SyntaxError")
    response = create_error_response(error)
    
    assert response["success"] is False
    assert response["error_type"] == "CodeExecutionError"
    assert response["code"] == "print('hello')"
    assert response["execution_error"] == "SyntaxError"


def test_create_error_response_with_invalid_arg_error() -> None:
    error = InvalidArgumentError("count", "int", "abc")
    response = create_error_response(error)
    
    assert response["success"] is False
    assert response["error_type"] == "InvalidArgumentError"
    assert response["argument"] == "count"
    assert response["expected_type"] == "int"


@pytest.mark.asyncio
async def test_handle_tool_error_with_success() -> None:
    @handle_tool_error
    async def successful_tool() -> dict[str, Any]:
        return {"success": True, "data": "result"}
    
    result = await successful_tool()
    assert result == {"success": True, "data": "result"}


@pytest.mark.asyncio
async def test_handle_tool_error_with_odoo_error() -> None:
    @handle_tool_error
    async def failing_tool() -> dict[str, Any]:
        raise ModelNotFoundError("test.model")
    
    result = await failing_tool()
    assert result["success"] is False
    assert "Model 'test.model' not found" in result["error"]
    assert result["error_type"] == "ModelNotFoundError"


@pytest.mark.asyncio
async def test_handle_tool_error_with_generic_exception() -> None:
    @handle_tool_error
    async def failing_tool() -> dict[str, Any]:
        raise ValueError("Something went wrong")
    
    result = await failing_tool()
    assert result["success"] is False
    assert result["error"] == "Something went wrong"
    assert result["error_type"] == "ValueError"


def test_validate_model_name_valid() -> None:
    # Should not raise for valid model names
    validate_model_name("res.partner")
    validate_model_name("product.template")
    validate_model_name("sale.order.line")
    validate_model_name("hr_employee")


def test_validate_model_name_invalid_type() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_model_name(123)  # type: ignore
    assert exc_info.value.arg_name == "model_name"
    assert exc_info.value.expected_type == "string"


def test_validate_model_name_empty() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_model_name("")
    assert exc_info.value.arg_name == "model_name"
    assert "non-empty string" in exc_info.value.expected_type


def test_validate_model_name_invalid_format() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_model_name("res.partner!")
    assert exc_info.value.arg_name == "model_name"
    assert "valid Odoo model name" in exc_info.value.expected_type


def test_validate_field_name_valid() -> None:
    # Should not raise for valid field names
    validate_field_name("name")
    validate_field_name("partner_id")
    validate_field_name("order_line_ids")
    validate_field_name("x_custom_field")


def test_validate_field_name_invalid_type() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_field_name(123)  # type: ignore
    assert exc_info.value.arg_name == "field_name"


def test_validate_field_name_empty() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_field_name("")
    assert exc_info.value.arg_name == "field_name"
    assert "non-empty string" in exc_info.value.expected_type


def test_validate_field_name_invalid_format() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_field_name("field-name")
    assert exc_info.value.arg_name == "field_name"
    assert "valid field name" in exc_info.value.expected_type


def test_validate_method_name_valid() -> None:
    # Should not raise for valid method names
    validate_method_name("create")
    validate_method_name("_compute_total")
    validate_method_name("action_confirm")
    validate_method_name("onchange_partner_id")


def test_validate_method_name_empty() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_method_name("")
    assert exc_info.value.arg_name == "method_name"
    assert "non-empty string" in exc_info.value.expected_type


def test_validate_method_name_invalid_format() -> None:
    with pytest.raises(InvalidArgumentError) as exc_info:
        validate_method_name("method-name")
    assert exc_info.value.arg_name == "method_name"
    assert "valid method name" in exc_info.value.expected_type