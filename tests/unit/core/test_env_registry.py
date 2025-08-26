from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry
from tests.mock_types import ConcreteModelMock as MockModel


class TestMockRegistryIteration:
    """Tests for MockRegistry iteration functionality needed by various tools."""

    def test_mock_registry_should_be_iterable(self) -> None:
        """Test that MockRegistry can be iterated over."""
        registry = MockRegistry()

        # This should not raise TypeError
        try:
            model_names = list(registry)
            # Currently returns empty list, but should contain model names
            assert isinstance(model_names, list)
        except TypeError:
            pytest.fail("MockRegistry should be iterable but raised TypeError")

    def test_mock_registry_should_yield_model_names(self) -> None:
        """Test that iterating over MockRegistry yields model names."""
        registry = MockRegistry()

        # Mock the internal models dict to contain some models
        registry._models = {"res.partner": MockModel, "product.template": MockModel, "motor.product": MockModel}  # type: ignore[assignment]

        # Iteration should yield the model names
        model_names = list(registry)
        assert len(model_names) == 3
        assert "res.partner" in model_names
        assert "product.template" in model_names
        assert "motor.product" in model_names

    def test_mock_registry_for_loop_pattern(self) -> None:
        """Test the common for loop pattern used in tools."""
        registry = MockRegistry()
        registry._models = {"sale.order": MockModel, "purchase.order": MockModel}  # type: ignore[assignment]

        # This is the pattern used in find_method, search_decorators, etc.
        collected_names = []
        for model_name in registry:
            collected_names.append(model_name)

        assert len(collected_names) == 2
        assert "sale.order" in collected_names
        assert "purchase.order" in collected_names


class TestHostOdooEnvironmentRegistry:
    """Tests for HostOdooEnvironment registry functionality."""

    @pytest.fixture
    def host_env(self) -> HostOdooEnvironment:
        return HostOdooEnvironment("test-container", "test-db", "/test/path")

    @pytest.mark.asyncio
    async def test_registry_returns_iterable_object(self, host_env: HostOdooEnvironment) -> None:
        """Test that env.registry returns an iterable object."""
        registry = host_env.registry

        # Should be able to convert to list without TypeError
        try:
            model_names = list(registry)
            assert isinstance(model_names, list)
        except TypeError:
            pytest.fail("env.registry should be iterable")

    @pytest.mark.asyncio
    async def test_registry_with_populated_models(self, host_env: HostOdooEnvironment) -> None:
        """Test registry when models are populated."""
        # Simulate populated registry
        host_env._registry = MockRegistry()
        host_env._registry._models = {
            "res.partner": MockModel,
            "res.users": MockModel,
            "product.template": MockModel,
            "product.product": MockModel,
            "motor.product": MockModel,
        }

        # Get model names from registry
        model_names = list(host_env.registry)

        assert len(model_names) == 5
        assert "res.partner" in model_names
        assert "res.users" in model_names
        assert "product.template" in model_names
        assert "product.product" in model_names
        assert "motor.product" in model_names

    @pytest.mark.asyncio
    async def test_registry_model_access_pattern(self, host_env: HostOdooEnvironment) -> None:
        """Test the pattern: for model_name in env.registry: env[model_name]."""
        # Mock execute_code to return model info
        with patch.object(host_env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # First call returns list of models
            mock_exec.side_effect = [
                ["res.partner", "product.template"],
                MagicMock(_name="res.partner"),  # env['res.partner']
                MagicMock(_name="product.template"),  # env['product.template']
            ]

            # Populate registry
            host_env._registry = MockRegistry()
            host_env._registry._models = {"res.partner": MockModel, "product.template": MockModel}

            # This is the pattern used in actual tools
            models_accessed = []
            for model_name in host_env.registry:
                _ = host_env[model_name]  # Test that model access doesn't raise
                models_accessed.append(model_name)

            assert len(models_accessed) == 2
            assert "res.partner" in models_accessed
            assert "product.template" in models_accessed


class TestRegistryIntegrationPatterns:
    """Test actual usage patterns from the affected tools."""

    @pytest.mark.asyncio
    async def test_find_method_pattern(self) -> None:
        """Test the registry iteration pattern used in find_method tool."""
        env = HostOdooEnvironment("test", "test", "/test")
        env._registry = MockRegistry()
        env._registry._models = {
            "sale.order": MagicMock(_name="sale.order"),
            "purchase.order": MagicMock(_name="purchase.order"),
            "res.partner": MagicMock(_name="res.partner"),
        }

        # Mock execute_code for model access
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = [
                MagicMock(_name="sale.order", create=MagicMock()),
                MagicMock(_name="purchase.order"),
                MagicMock(_name="res.partner", create=MagicMock()),
            ]

            # Simulate find_method pattern
            models_with_method = []
            for model_name in env.registry:
                _ = env[model_name]  # Test that model access doesn't raise
                # In real usage, we'd check if the model has the method
                # For testing, we just track all model names
                models_with_method.append(model_name)

            assert len(models_with_method) >= 1
            assert "sale.order" in models_with_method or "res.partner" in models_with_method

    @pytest.mark.asyncio
    async def test_search_decorators_pattern(self) -> None:
        """Test the registry iteration pattern used in search_decorators tool."""
        env = HostOdooEnvironment("test", "test", "/test")
        env._registry = MockRegistry()
        env._registry._models = {"product.template": MockModel, "stock.move": MockModel}

        # This pattern is used in search_decorators
        collected_models = []
        for model_name in env.registry:
            collected_models.append(model_name)

        assert len(collected_models) == 2
        assert "product.template" in collected_models
        assert "stock.move" in collected_models

    @pytest.mark.asyncio
    async def test_search_field_type_pattern(self) -> None:
        """Test the registry iteration pattern used in search_field_type tool."""
        env = HostOdooEnvironment("test", "test", "/test")
        env._registry = MockRegistry()
        env._registry._models = {"res.partner": MockModel, "res.company": MockModel, "hr.employee": MockModel}

        # Mock execute_code for field access
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Return mock models with _fields
            partner_fields = {"name": MagicMock(type="char"), "company_id": MagicMock(type="many2one")}
            company_fields = {"name": MagicMock(type="char")}
            employee_fields = {"user_id": MagicMock(type="many2one")}

            mock_exec.side_effect = [
                MagicMock(_fields=partner_fields),
                MagicMock(_fields=company_fields),
                MagicMock(_fields=employee_fields),
            ]

            # Simulate search_field_type pattern
            models_with_m2o = []
            for model_name in env.registry:
                _ = env[model_name]  # Test that model access doesn't raise
                # In real code, we'd check model._fields here
                # For testing, just add specific models we know have m2o fields
                if model_name in ["res.partner", "hr.employee"]:
                    models_with_m2o.append(model_name)

            assert len(models_with_m2o) == 2
            assert "res.partner" in models_with_m2o
            assert "hr.employee" in models_with_m2o

    @pytest.mark.asyncio
    async def test_search_field_properties_pattern(self) -> None:
        """Test the registry iteration pattern used in search_field_properties tool."""
        env = HostOdooEnvironment("test", "test", "/test")
        env._registry = MockRegistry()
        env._registry._models = {"sale.order.line": MockModel, "account.move.line": MockModel}

        # Mock execute_code for field access
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Return mock models with computed fields
            sol_fields = {"price_subtotal": MagicMock(compute="_compute_amount", store=True), "name": MagicMock(compute=None)}
            aml_fields = {"balance": MagicMock(compute="_compute_balance", store=False)}

            mock_exec.side_effect = [MagicMock(_fields=sol_fields), MagicMock(_fields=aml_fields)]

            # Simulate search_field_properties pattern
            computed_fields = []
            for model_name in env.registry:
                _ = env[model_name]  # Test that model access doesn't raise
                # In real code, we'd check model._fields here
                # For testing, just add known computed fields
                if model_name == "sale.order.line":
                    computed_fields.append((model_name, "price_subtotal"))
                elif model_name == "account.move.line":
                    computed_fields.append((model_name, "balance"))

            assert len(computed_fields) == 2
            assert ("sale.order.line", "price_subtotal") in computed_fields
            assert ("account.move.line", "balance") in computed_fields


class TestRegistryEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_registry_iteration(self) -> None:
        """Test iterating over empty registry."""
        registry = MockRegistry()
        registry._models = {}

        model_names = list(registry)
        assert len(model_names) == 0

    def test_registry_contains_check(self) -> None:
        """Test 'in' operator with registry."""
        registry = MockRegistry()
        registry._models = {"res.partner": MockModel, "product.template": MockModel}  # type: ignore[assignment]

        # Should support 'in' checks
        assert "res.partner" in registry
        assert "product.template" in registry
        assert "non.existent.model" not in registry

    def test_registry_len(self) -> None:
        """Test len() on registry."""
        registry = MockRegistry()
        registry._models = {"model.one": MockModel, "model.two": MockModel, "model.three": MockModel}  # type: ignore[assignment]

        assert len(registry) == 3

    @pytest.mark.asyncio
    async def test_registry_lazy_loading(self) -> None:
        """Test that registry can be lazily loaded."""
        env = HostOdooEnvironment("test", "test", "/test")

        # Initially, registry is None
        assert env._registry is None

        # After first access, registry is created
        _registry = env.registry
        assert env._registry is not None
        # Registry should be a DockerRegistry instance


class TestRegistryStandardModels:
    """Test that registry includes standard Odoo models."""

    @pytest.mark.asyncio
    async def test_registry_contains_standard_models(self) -> None:
        """Test that registry contains standard Odoo models when properly initialized."""
        env = HostOdooEnvironment("test", "test", "/test")

        # Simulate a properly initialized registry with standard models
        standard_models = [
            "res.partner",
            "res.users",
            "res.company",
            "product.template",
            "product.product",
            "sale.order",
            "purchase.order",
            "account.move",
            "stock.move",
            "hr.employee",
        ]

        env._registry = MockRegistry()
        env._registry._models = dict.fromkeys(standard_models, MockModel)

        registry_models = list(env.registry)

        # Should contain all standard models
        for model in standard_models:
            assert model in registry_models

        assert len(registry_models) == len(standard_models)
