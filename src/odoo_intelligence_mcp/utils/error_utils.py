from typing import Any, TypeVar

T = TypeVar("T")


class OdooMCPError(Exception):
    pass


class ModelNotFoundError(OdooMCPError):
    def __init__(self, model_name: str) -> None:
        super().__init__(f"Model '{model_name}' not found in Odoo registry")
        self.model_name = model_name


class FieldNotFoundError(OdooMCPError):
    def __init__(self, model_name: str, field_name: str) -> None:
        super().__init__(f"Field '{field_name}' not found in model '{model_name}'")
        self.model_name = model_name
        self.field_name = field_name


class DockerConnectionError(OdooMCPError):
    def __init__(self, container_name: str, message: str) -> None:
        super().__init__(f"Failed to connect to Docker container '{container_name}': {message}")
        self.container_name = container_name


class CodeExecutionError(OdooMCPError):
    def __init__(self, code: str, error: str) -> None:
        super().__init__(f"Code execution failed: {error}")
        self.code = code
        self.error = error


class InvalidArgumentError(OdooMCPError):
    def __init__(self, arg_name: str, expected_type: str, actual_value: Any) -> None:
        super().__init__(f"Invalid argument '{arg_name}': expected {expected_type}, got {type(actual_value).__name__}")
        self.arg_name = arg_name
        self.expected_type = expected_type
        self.actual_value = actual_value


def create_error_response(error: Exception, include_type: bool = True) -> dict[str, Any]:
    response = {
        "success": False,
        "error": str(error),
    }

    if include_type:
        response["error_type"] = type(error).__name__

    # Add specific error details based on error type
    if isinstance(error, ModelNotFoundError):
        response["model"] = error.model_name
    elif isinstance(error, FieldNotFoundError):
        response["model"] = error.model_name
        response["field"] = error.field_name
    elif isinstance(error, DockerConnectionError):
        response["container"] = error.container_name
    elif isinstance(error, CodeExecutionError):
        response["code"] = error.code
        response["execution_error"] = error.error
    elif isinstance(error, InvalidArgumentError):
        response["argument"] = error.arg_name
        response["expected_type"] = error.expected_type

    return response


def handle_tool_error[T](func: T) -> T:
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return await func(*args, **kwargs)
        except OdooMCPError as e:
            return create_error_response(e)
        except Exception as e:
            # For unexpected errors, provide a generic response
            return create_error_response(e)

    return wrapper  # type: ignore


def validate_model_name(model_name: str) -> None:
    if not model_name:
        raise InvalidArgumentError("model_name", "non-empty string", model_name)

    # Basic validation for model name format
    if not all(part.replace("_", "").isalnum() for part in model_name.split(".")):
        raise InvalidArgumentError("model_name", "valid Odoo model name (e.g., 'res.partner', 'product.template')", model_name)


def validate_field_name(field_name: str) -> None:
    if not field_name:
        raise InvalidArgumentError("field_name", "non-empty string", field_name)

    # Basic validation for field name format
    if not field_name.replace("_", "").isalnum():
        raise InvalidArgumentError("field_name", "valid field name (alphanumeric with underscores)", field_name)


def validate_method_name(method_name: str) -> None:
    if not method_name:
        raise InvalidArgumentError("method_name", "non-empty string", method_name)

    # Basic validation for method name format
    if not method_name.replace("_", "").isalnum():
        raise InvalidArgumentError("method_name", "valid method name (alphanumeric with underscores)", method_name)
