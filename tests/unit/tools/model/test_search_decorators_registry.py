from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry
from odoo_intelligence_mcp.tools.model import search_decorators
from tests.mock_types import ConcreteModelMock as MockModel


class TestSearchDecoratorsRegistryFix:
    """Test search_decorators with focus on registry iteration issue."""

    @pytest.fixture
    def mock_env_with_registry(self):
        """Create a mock environment with a properly configured registry."""
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Since HostOdooEnvironment.registry returns DockerRegistry which always
        # returns empty iterator, we need to test with a different approach
        return env

    @pytest.mark.asyncio
    async def test_search_decorators_with_host_env_no_get_model_names(self, mock_env_with_registry):
        """Test search_decorators when env doesn't have get_model_names (falls back to registry)."""
        env = mock_env_with_registry

        # HostOdooEnvironment doesn't have get_model_names by default
        # so it will use the fallback to registry iteration

        # Call search_decorators
        result = await search_decorators(env, "depends")

        # Due to DockerRegistry always returning empty iterator,
        # we expect no results
        assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_search_decorators_with_mock_registry(self):
        """Test search_decorators with MockRegistry that has models."""
        # Create a mock environment with MockRegistry
        env = MagicMock()
        env.registry = MockRegistry()

        # MockRegistry.models is a ClassVar, we need to set it properly
        MockRegistry.models = {"sale.order": MockModel, "product.template": MockModel}

        # Mock model access
        sale_order = MagicMock()
        sale_order._description = "Sales Order"

        # Create a method with _depends attribute
        compute_amount = MagicMock()
        compute_amount._depends = ["order_line.price_total"]
        compute_amount.__name__ = "_compute_amount"

        # Set up the model class
        sale_order_class = type(sale_order)
        sale_order_class._compute_amount = compute_amount

        product_template = MagicMock()
        product_template._description = "Product Template"

        env.__getitem__.side_effect = lambda name: {"sale.order": sale_order, "product.template": product_template}.get(name)

        # Now test - should iterate through registry
        result = await search_decorators(env, "depends")

        # Should have attempted to search both models
        assert env.__getitem__.call_count == 2
        env.__getitem__.assert_any_call("sale.order")
        env.__getitem__.assert_any_call("product.template")

    @pytest.mark.asyncio
    async def test_search_decorators_fallback_with_registry_models_attr(self):
        """Test the specific fallback in search_decorators line 18."""
        env = MagicMock()

        # Create registry with models attribute (not the same as MockRegistry)
        registry = MagicMock()
        registry.models = ["model.one", "model.two", "model.three"]
        env.registry = registry

        # Mock models
        env.__getitem__.return_value = MagicMock(_description="Test Model")

        result = await search_decorators(env, "onchange")

        # Should have accessed all three models
        assert env.__getitem__.call_count == 3

    @pytest.mark.asyncio
    async def test_search_decorators_with_type_error(self):
        """Test search_decorators when registry iteration raises TypeError."""
        env = MagicMock()

        # Make registry raise TypeError when trying to iterate
        class BadRegistry:
            def __iter__(self):
                raise TypeError("Cannot iterate")

        env.registry = BadRegistry()

        # Mock model access (though it shouldn't be called)
        env.__getitem__.return_value = MagicMock()

        # Should handle the error gracefully
        result = await search_decorators(env, "constrains")

        assert result == {"results": []}
        # Should not have tried to access any models
        env.__getitem__.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_decorators_with_get_model_names(self):
        """Test search_decorators when env has get_model_names method."""
        env = MagicMock()

        # Add async get_model_names method
        async def mock_get_model_names():
            return ["res.partner", "res.users", "product.product"]

        env.get_model_names = mock_get_model_names

        # Mock models
        env.__getitem__.return_value = MagicMock(_description="Test Model")

        result = await search_decorators(env, "model_create_multi")

        # Should have used get_model_names and accessed all models
        assert env.__getitem__.call_count == 3
        env.__getitem__.assert_any_call("res.partner")
        env.__getitem__.assert_any_call("res.users")
        env.__getitem__.assert_any_call("product.product")
