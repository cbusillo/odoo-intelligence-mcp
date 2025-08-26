from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from ..type_defs.odoo_types import Environment

T = TypeVar("T")


class ServiceError(Exception):
    pass


class ServiceValidationError(ServiceError):
    pass


class ServiceExecutionError(ServiceError):
    pass


class BaseService(ABC):
    def __init__(self, env: Environment) -> None:
        self.env = env
        self._cache: dict[str, Any] = {}

    @abstractmethod
    def get_service_name(self) -> str:
        pass

    def clear_cache(self) -> None:
        self._cache.clear()

    def _get_cached(self, key: str) -> Any | None:
        return self._cache.get(key)

    def _set_cached(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def _validate_model_exists(self, model_name: str) -> None:
        if model_name not in self.env:
            raise ServiceValidationError(f"Model '{model_name}' not found in Odoo environment")

    def _validate_field_exists(self, model_name: str, field_name: str) -> None:
        self._validate_model_exists(model_name)
        model = self.env[model_name]
        # noinspection PyProtectedMember
        if field_name not in model._fields:
            raise ServiceValidationError(f"Field '{field_name}' not found on model '{model_name}'")

    def _safe_execute(self, operation: str, func: Callable[..., Any], *args: object, **kwargs: object) -> Any:
        try:
            return func(*args, **kwargs)
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceExecutionError(f"Failed to execute {operation} in {self.get_service_name()}: {e!s}") from e

    @staticmethod
    def _paginate_results(items: list[Any], page: int = 1, page_size: int = 100) -> dict[str, Any]:
        total_items = len(items)
        total_pages = (total_items + page_size - 1) // page_size

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        return {
            "items": items[start_idx:end_idx],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1,
            },
        }

    def _format_error_response(self, error: Exception) -> dict[str, Any]:
        error_type = type(error).__name__
        return {
            "error": True,
            "error_type": error_type,
            "message": str(error),
            "service": self.get_service_name(),
        }
