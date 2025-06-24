import pytest

from odoo_intelligence_mcp.utils.error_utils import (
    CodeExecutionError,
    DockerConnectionError,
    FieldNotFoundError,
    InvalidArgumentError,
    ModelNotFoundError,
    create_error_response,
    validate_field_name,
    validate_model_name,
)


class TestErrorUtils:
    def test_model_not_found_error(self) -> None:
        error = ModelNotFoundError("invalid.model")
        assert str(error) == "Model 'invalid.model' not found in Odoo registry"
        assert error.model_name == "invalid.model"

    def test_field_not_found_error(self) -> None:
        error = FieldNotFoundError("res.partner", "invalid_field")
        assert str(error) == "Field 'invalid_field' not found in model 'res.partner'"
        assert error.model_name == "res.partner"
        assert error.field_name == "invalid_field"

    def test_docker_connection_error(self) -> None:
        error = DockerConnectionError("odoo-container", "Connection refused")
        assert str(error) == "Failed to connect to Docker container 'odoo-container': Connection refused"
        assert error.container_name == "odoo-container"

    def test_code_execution_error(self) -> None:
        code = "result = 1/0"
        error = CodeExecutionError(code, "Division by zero")
        assert str(error) == "Code execution failed: Division by zero"
        assert error.code == code
        assert error.error == "Division by zero"

    def test_invalid_argument_error(self) -> None:
        error = InvalidArgumentError("model_name", "string", 123)
        assert str(error) == "Invalid argument 'model_name': expected string, got int"
        assert error.arg_name == "model_name"
        assert error.expected_type == "string"
        assert error.actual_value == 123

    def test_create_error_response_model_not_found(self) -> None:
        error = ModelNotFoundError("invalid.model")
        response = create_error_response(error)

        assert response["success"] is False
        assert response["error"] == "Model 'invalid.model' not found in Odoo registry"
        assert response["error_type"] == "ModelNotFoundError"
        assert response["model"] == "invalid.model"

    def test_create_error_response_field_not_found(self) -> None:
        error = FieldNotFoundError("res.partner", "invalid_field")
        response = create_error_response(error)

        assert response["success"] is False
        assert response["error"] == "Field 'invalid_field' not found in model 'res.partner'"
        assert response["error_type"] == "FieldNotFoundError"
        assert response["model"] == "res.partner"
        assert response["field"] == "invalid_field"

    def test_create_error_response_generic_exception(self) -> None:
        error = ValueError("Something went wrong")
        response = create_error_response(error)

        assert response["success"] is False
        assert response["error"] == "Something went wrong"
        assert response["error_type"] == "ValueError"

    def test_create_error_response_without_type(self) -> None:
        error = ValueError("Something went wrong")
        response = create_error_response(error, include_type=False)

        assert response["success"] is False
        assert response["error"] == "Something went wrong"
        assert "error_type" not in response

    def test_validate_model_name_valid(self) -> None:
        # Should not raise
        validate_model_name("res.partner")
        validate_model_name("product.template")
        validate_model_name("sale.order.line")
        validate_model_name("motor.product")

    def test_validate_model_name_empty(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_model_name("")

        assert exc_info.value.arg_name == "model_name"
        assert exc_info.value.expected_type == "non-empty string"

    def test_validate_model_name_not_string(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_model_name(123)  # type: ignore

        assert exc_info.value.arg_name == "model_name"
        assert exc_info.value.expected_type == "string"

    def test_validate_model_name_invalid_format(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_model_name("res.partner!")

        assert exc_info.value.arg_name == "model_name"
        assert "valid Odoo model name" in exc_info.value.expected_type

    def test_validate_field_name_valid(self) -> None:
        # Should not raise
        validate_field_name("name")
        validate_field_name("partner_id")
        validate_field_name("state")
        validate_field_name("x_custom_field")

    def test_validate_field_name_empty(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_field_name("")

        assert exc_info.value.arg_name == "field_name"
        assert exc_info.value.expected_type == "non-empty string"

    def test_validate_field_name_not_string(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_field_name(None)  # type: ignore

        assert exc_info.value.arg_name == "field_name"
        assert exc_info.value.expected_type == "non-empty string"

    def test_validate_field_name_invalid_format(self) -> None:
        with pytest.raises(InvalidArgumentError) as exc_info:
            validate_field_name("field-name")

        assert exc_info.value.arg_name == "field_name"
        assert "valid field name" in exc_info.value.expected_type
