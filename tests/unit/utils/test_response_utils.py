from typing import Any

from odoo_intelligence_mcp.utils.response_utils import ResponseBuilder


class TestResponseBuilder:
    def test_success_with_no_data(self) -> None:
        result = ResponseBuilder.success()
        assert result == {"success": True}

    def test_success_with_data(self) -> None:
        test_data = {"key": "value", "number": 42}
        result = ResponseBuilder.success(test_data)
        assert result == {"success": True, "data": test_data}

    def test_success_with_kwargs_as_data(self) -> None:
        result = ResponseBuilder.success(key="value", number=42)
        assert result == {"success": True, "data": {"key": "value", "number": 42}}

    def test_success_with_none_data_and_kwargs(self) -> None:
        result = ResponseBuilder.success(None, key="value", number=42)
        assert result == {"success": True, "data": {"key": "value", "number": 42}}

    def test_error_basic(self) -> None:
        result = ResponseBuilder.error("Something went wrong")
        assert result == {"success": False, "error": "Something went wrong"}

    def test_error_with_type(self) -> None:
        result = ResponseBuilder.error("Invalid input", "ValidationError")
        assert result == {"success": False, "error": "Invalid input", "error_type": "ValidationError"}

    def test_error_with_additional_kwargs(self) -> None:
        result = ResponseBuilder.error("Database error", "DatabaseError", code=500, details="Connection lost")
        assert result == {
            "success": False,
            "error": "Database error",
            "error_type": "DatabaseError",
            "code": 500,
            "details": "Connection lost",
        }

    def test_from_exception_basic(self) -> None:
        exception = ValueError("Invalid value provided")
        result = ResponseBuilder.from_exception(exception)
        assert result == {"success": False, "error": "Invalid value provided", "error_type": "ValueError"}

    def test_from_exception_with_kwargs(self) -> None:
        exception = KeyError("missing_key")
        result = ResponseBuilder.from_exception(exception, context="user_data", retry=True)
        assert result == {
            "success": False,
            "error": "'missing_key'",
            "error_type": "KeyError",
            "context": "user_data",
            "retry": True,
        }

    def test_from_exception_custom_exception(self) -> None:
        class CustomError(Exception):
            pass

        exception = CustomError("Custom error message")
        result = ResponseBuilder.from_exception(exception)
        assert result == {"success": False, "error": "Custom error message", "error_type": "CustomError"}

    def test_success_with_complex_data_structure(self) -> None:
        complex_data = {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}], "count": 2, "metadata": {"version": "1.0"}}
        result = ResponseBuilder.success(complex_data)
        assert result == {"success": True, "data": complex_data}

    def test_success_with_empty_string_data(self) -> None:
        result = ResponseBuilder.success("")
        assert result == {"success": True, "data": ""}

    def test_success_with_zero_data(self) -> None:
        result = ResponseBuilder.success(0)
        assert result == {"success": True, "data": 0}

    def test_success_with_false_data(self) -> None:
        result = ResponseBuilder.success(False)
        assert result == {"success": True, "data": False}

    def test_error_with_empty_message(self) -> None:
        result = ResponseBuilder.error("")
        assert result == {"success": False, "error": ""}

    def test_error_with_none_type(self) -> None:
        result = ResponseBuilder.error("Error occurred", None)
        assert result == {"success": False, "error": "Error occurred"}

    def test_type_consistency(self) -> None:
        success_result: dict[str, Any] = ResponseBuilder.success({"test": True})
        assert isinstance(success_result, dict)
        assert isinstance(success_result["success"], bool)

        error_result: dict[str, Any] = ResponseBuilder.error("Test error")
        assert isinstance(error_result, dict)
        assert isinstance(error_result["success"], bool)
        assert isinstance(error_result["error"], str)
