from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry
from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.model.find_method import find_method_implementations
from tests.mock_types import ConcreteModelMock as MockModel


class TestFindMethodRegistryIssue:
    """Test find_method tool with focus on registry iteration issue."""

    @pytest.fixture
    def mock_env_with_registry(self):
        """Create a mock environment with a properly configured registry."""
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Set up registry with test models
        env._registry = MockRegistry()
        env._registry._models = {
            "sale.order": MockModel,
            "purchase.order": MockModel,
            "product.template": MockModel,
            "res.partner": MockModel,
        }

        return env

    @pytest.mark.asyncio
    async def test_find_method_with_iterable_registry(self, mock_env_with_registry):
        """Test that find_method works when registry is properly iterable."""
        env = mock_env_with_registry
        method_name = "create"

        # Mock execute_code to return model objects with methods
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Set up mock models with create method
            sale_order_model = MagicMock()
            sale_order_model._name = "sale.order"
            sale_order_model.create = MagicMock()

            purchase_order_model = MagicMock()
            purchase_order_model._name = "purchase.order"
            purchase_order_model.create = MagicMock()

            product_model = MagicMock()
            product_model._name = "product.template"
            # No create method

            partner_model = MagicMock()
            partner_model._name = "res.partner"
            partner_model.create = MagicMock()

            # Return appropriate model when accessed
            mock_exec.side_effect = [sale_order_model, purchase_order_model, product_model, partner_model]

            # Mock file system for source code search
            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = []  # No files to search

                # Call find_method_implementations
                result = await find_method_implementations(env, method_name, PaginationParams())

                # Should have successfully iterated through registry
                assert "error" not in result
                assert result["method_name"] == method_name
                # The actual implementation would search files, but we're testing registry iteration

    @pytest.mark.asyncio
    async def test_find_method_registry_iteration_pattern(self, mock_env_with_registry):
        """Test the specific iteration pattern used in find_method."""
        env = mock_env_with_registry

        # Track which models were accessed
        accessed_models = []

        # Mock __getitem__ to track model access
        async def mock_getitem(model_name):
            accessed_models.append(model_name)
            model = MagicMock()
            model._name = model_name
            return model

        env.__getitem__ = mock_getitem

        # Iterate through registry as find_method does
        for model_name in env.registry:
            model = await env[model_name]

        # Should have accessed all models in registry
        assert len(accessed_models) == 4
        assert "sale.order" in accessed_models
        assert "purchase.order" in accessed_models
        assert "product.template" in accessed_models
        assert "res.partner" in accessed_models

    @pytest.mark.asyncio
    async def test_find_method_with_empty_registry(self):
        """Test find_method behavior with empty registry."""
        env = HostOdooEnvironment("test", "test", "/test")
        env._registry = MockRegistry()
        env._registry._models = {}  # Empty registry

        method_name = "test_method"

        # Mock file system
        with patch("pathlib.Path.glob") as mock_glob:
            mock_glob.return_value = []

            result = await find_method_implementations(env, method_name, PaginationParams())

            # Should handle empty registry gracefully
            assert "error" not in result
            assert result["method_name"] == method_name
            assert result["models"] == []

    def test_registry_iteration_not_dict_values(self):
        """Test that registry iteration returns model names, not dict values."""
        registry = MockRegistry()
        registry._models = {"model.a": MockModel, "model.b": MockModel, "model.c": MockModel}

        # When iterating, should get model names (keys), not model objects (values)
        model_names = list(registry)

        assert all(isinstance(name, str) for name in model_names)
        assert "model.a" in model_names
        assert "model.b" in model_names
        assert "model.c" in model_names
        # Should not contain MagicMock objects
        assert not any(isinstance(item, MagicMock) for item in model_names)

    @pytest.mark.asyncio
    async def test_find_method_full_flow_with_fixed_registry(self, mock_env_with_registry):
        """Test complete find_method flow with properly iterable registry."""
        env = mock_env_with_registry
        method_name = "compute_amount"

        # Set up models with different method implementations
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Only sale.order has compute_amount
            sale_model = MagicMock()
            sale_model._name = "sale.order"
            sale_model.compute_amount = MagicMock()

            mock_exec.side_effect = [
                sale_model,
                MagicMock(_name="purchase.order"),  # No compute_amount
                MagicMock(_name="product.template"),  # No compute_amount
                MagicMock(_name="res.partner"),  # No compute_amount
            ]

            # Mock file system to find the method in source
            mock_files = [patch("pathlib.Path").start()]
            mock_file_path = MagicMock()
            mock_file_path.suffix = ".py"
            mock_file_path.read_text.return_value = '''
class SaleOrder(models.Model):
    _name = 'sale.order'
    
    def compute_amount(self):
        """Compute the total amount."""
        return sum(line.price_subtotal for line in self.order_line)
'''

            with patch("pathlib.Path.glob") as mock_glob:
                mock_glob.return_value = [mock_file_path]

                result = await find_method_implementations(env, method_name, PaginationParams())

                # Should successfully find the method
                assert "error" not in result
                assert result["method_name"] == method_name
                # Would need proper file parsing to get actual results

                # Verify all models were checked
                assert mock_exec.call_count == 4  # All 4 models in registry
