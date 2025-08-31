from typing import cast
from unittest.mock import MagicMock, Mock

import pytest

from odoo_intelligence_mcp.services.base_service import (
    BaseService,
    ServiceError,
    ServiceExecutionError,
    ServiceValidationError,
)
from odoo_intelligence_mcp.type_defs.odoo_types import Environment


class ConcreteService(BaseService):
    def get_service_name(self) -> str:
        return "TestService"


class TestServiceExceptions:
    def test_service_error_inheritance(self) -> None:
        assert issubclass(ServiceError, Exception)
        error = ServiceError("Test error")
        assert str(error) == "Test error"

    def test_service_validation_error_inheritance(self) -> None:
        assert issubclass(ServiceValidationError, ServiceError)
        error = ServiceValidationError("Validation failed")
        assert str(error) == "Validation failed"

    def test_service_execution_error_inheritance(self) -> None:
        assert issubclass(ServiceExecutionError, ServiceError)
        error = ServiceExecutionError("Execution failed")
        assert str(error) == "Execution failed"


class TestBaseService:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        env = MagicMock()
        env.__contains__ = MagicMock(return_value=True)
        env.__getitem__ = MagicMock()
        return env

    @pytest.fixture
    def service(self, mock_env: MagicMock) -> ConcreteService:
        return ConcreteService(cast(Environment, mock_env))

    def test_init(self, mock_env: MagicMock) -> None:
        service = ConcreteService(cast(Environment, mock_env))
        assert service.env == mock_env
        assert service._cache == {}

    def test_get_service_name(self, service: ConcreteService) -> None:
        assert service.get_service_name() == "TestService"

    def test_clear_cache(self, service: ConcreteService) -> None:
        service._cache = {"key1": "value1", "key2": "value2"}
        service.clear_cache()
        assert service._cache == {}

    def test_get_cached_existing_key(self, service: ConcreteService) -> None:
        service._cache["test_key"] = "test_value"
        result = service._get_cached("test_key")
        assert result == "test_value"

    def test_get_cached_missing_key(self, service: ConcreteService) -> None:
        result = service._get_cached("nonexistent_key")
        assert result is None

    def test_set_cached(self, service: ConcreteService) -> None:
        service._set_cached("new_key", "new_value")
        assert service._cache["new_key"] == "new_value"

    def test_set_cached_overwrites(self, service: ConcreteService) -> None:
        service._cache["key"] = "old_value"
        service._set_cached("key", "new_value")
        assert service._cache["key"] == "new_value"

    def test_validate_model_exists_success(self, service: ConcreteService, mock_env: MagicMock) -> None:
        mock_env.__contains__.return_value = True
        service._validate_model_exists("sale.order")
        mock_env.__contains__.assert_called_once_with("sale.order")

    def test_validate_model_exists_failure(self, service: ConcreteService, mock_env: MagicMock) -> None:
        mock_env.__contains__.return_value = False
        with pytest.raises(ServiceValidationError) as exc_info:
            service._validate_model_exists("nonexistent.model")
        assert "Model 'nonexistent.model' not found" in str(exc_info.value)

    def test_validate_field_exists_success(self, service: ConcreteService, mock_env: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model._fields = {"name": "field_obj", "partner_id": "field_obj"}
        mock_env.__getitem__.return_value = mock_model
        mock_env.__contains__.return_value = True

        service._validate_field_exists("sale.order", "name")
        mock_env.__contains__.assert_called_once_with("sale.order")

    def test_validate_field_exists_model_not_found(self, service: ConcreteService, mock_env: MagicMock) -> None:
        mock_env.__contains__.return_value = False
        with pytest.raises(ServiceValidationError) as exc_info:
            service._validate_field_exists("nonexistent.model", "field")
        assert "Model 'nonexistent.model' not found" in str(exc_info.value)

    def test_validate_field_exists_field_not_found(self, service: ConcreteService, mock_env: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model._fields = {"name": "field_obj"}
        mock_env.__getitem__.return_value = mock_model
        mock_env.__contains__.return_value = True

        with pytest.raises(ServiceValidationError) as exc_info:
            service._validate_field_exists("sale.order", "nonexistent_field")
        assert "Field 'nonexistent_field' not found on model 'sale.order'" in str(exc_info.value)

    def test_cache_workflow(self, service: ConcreteService) -> None:
        assert service._get_cached("key") is None

        service._set_cached("key", {"data": "value"})
        assert service._get_cached("key") == {"data": "value"}

        service._set_cached("key2", [1, 2, 3])
        assert service._get_cached("key2") == [1, 2, 3]

        service.clear_cache()
        assert service._get_cached("key") is None
        assert service._get_cached("key2") is None

    def test_multiple_cache_entries(self, service: ConcreteService) -> None:
        for i in range(10):
            service._set_cached(f"key_{i}", f"value_{i}")

        assert len(service._cache) == 10
        assert service._get_cached("key_5") == "value_5"

        service.clear_cache()
        assert len(service._cache) == 0

    def test_cache_complex_objects(self, service: ConcreteService) -> None:
        complex_obj = {
            "list": [1, 2, {"nested": True}],
            "dict": {"a": 1, "b": 2},
            "tuple": (1, 2, 3),
        }
        service._set_cached("complex", complex_obj)
        retrieved = service._get_cached("complex")
        assert retrieved == complex_obj
        assert retrieved is complex_obj  # Should be the same object reference

    def test_abstract_method_enforcement(self) -> None:
        class IncompleteService(BaseService):
            pass

        mock_env = MagicMock()
        with pytest.raises(TypeError) as exc_info:
            IncompleteService(mock_env)  # type: ignore
        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_env_property_access(self, service: ConcreteService, mock_env: MagicMock) -> None:
        assert service.env is mock_env
        mock_env.some_method = Mock(return_value="result")
        assert service.env.some_method() == "result"
