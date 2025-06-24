from typing import Any, TypeVar

T = TypeVar("T")


class ResponseBuilder:
    @staticmethod
    def success(data: T | None = None, **kwargs: Any) -> dict[str, Any]:
        response: dict[str, Any] = {"success": True}
        if data is not None:
            response["data"] = data
        response.update(kwargs)
        return response

    @staticmethod
    def error(error_message: str, error_type: str | None = None, **kwargs: Any) -> dict[str, Any]:
        response = {
            "success": False,
            "error": error_message,
        }
        if error_type:
            response["error_type"] = error_type
        response.update(kwargs)
        return response

    @staticmethod
    def from_exception(exception: Exception, **kwargs: Any) -> dict[str, Any]:
        return ResponseBuilder.error(str(exception), type(exception).__name__, **kwargs)
