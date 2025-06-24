from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry
from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.field import search_field_properties, search_field_type
from tests.mock_types import ConcreteModelMock as MockModel


class TestFieldSearchRegistryIssue:
    """Test field search tools with focus on registry iteration issue."""

    @pytest.fixture
    def mock_env_docker_registry(self) -> HostOdooEnvironment:
        """Create environment with DockerRegistry that returns empty iterator."""
        return HostOdooEnvironment("test-container", "test-db", "/test/path")

    @pytest.mark.asyncio
    async def test_search_field_type_with_docker_registry(self, mock_env_docker_registry: HostOdooEnvironment) -> None:
        """Test search_field_type with DockerRegistry that returns empty."""
        env = mock_env_docker_registry

        # Call search_field_type
        result = await search_field_type(env, "many2one", PaginationParams())

        # Due to DockerRegistry returning empty iterator, we get no fields
        assert result["field_type"] == "many2one"
        assert result["fields"] == []
        assert result["summary"]["total_models"] == 0
        assert result["summary"]["total_fields"] == 0

    @pytest.mark.asyncio
    async def test_search_field_properties_with_docker_registry(self, mock_env_docker_registry: HostOdooEnvironment) -> None:
        """Test search_field_properties with DockerRegistry that returns empty."""
        env = mock_env_docker_registry

        # Call search_field_properties
        result = await search_field_properties(env, "computed", PaginationParams())

        # Due to DockerRegistry returning empty iterator, we get no fields
        assert result["property"] == "computed"
        assert result["fields"] == []
        assert result["summary"]["total_models"] == 0
        assert result["summary"]["total_fields"] == 0

    @pytest.mark.asyncio
    async def test_field_search_with_mock_registry(self) -> None:
        """Test field search with MockRegistry that can be populated."""
        # Create mock environment
        env = MagicMock()

        # Create a MockRegistry instance
        registry = MockRegistry()
        # Note: MockRegistry.models is a ClassVar, so we need to set it on the class
        MockRegistry.models = {"res.partner": MockModel, "sale.order": MockModel}
        env.registry = registry

        # Mock model field access
        partner_fields = {
            "name": MagicMock(type="char", string="Name"),
            "company_id": MagicMock(type="many2one", string="Company", comodel_name="res.company"),
            "email": MagicMock(type="char", string="Email"),
        }

        sale_fields = {
            "partner_id": MagicMock(type="many2one", string="Customer", comodel_name="res.partner"),
            "amount_total": MagicMock(type="float", compute="_compute_amount", string="Total"),
            "state": MagicMock(type="selection", string="Status"),
        }

        # Mock __getitem__ to return models with _fields
        def get_model(name: str) -> MagicMock:
            if name == "res.partner":
                return MagicMock(_name="res.partner", _fields=partner_fields)
            elif name == "sale.order":
                return MagicMock(_name="sale.order", _fields=sale_fields)
            return MagicMock(_fields={})

        env.__getitem__.side_effect = get_model

        # Test search_field_type
        result = await search_field_type(env, "many2one", PaginationParams())

        # Should find 2 many2one fields
        assert len(result["fields"]) == 2
        field_names = [(f["model_name"], f["field_name"]) for f in result["fields"]]
        assert ("res.partner", "company_id") in field_names
        assert ("sale.order", "partner_id") in field_names

        # Reset for next test
        env.__getitem__.side_effect = get_model

        # Test search_field_properties for computed fields
        result = await search_field_properties(env, "computed", PaginationParams())

        # Should find 1 computed field
        assert len(result["fields"]) == 1
        assert result["fields"][0]["model_name"] == "sale.order"
        assert result["fields"][0]["field_name"] == "amount_total"

    @pytest.mark.asyncio
    async def test_field_search_with_host_env_and_execute_code(self) -> None:
        """Test field search when HostOdooEnvironment has get_model_names."""
        env = HostOdooEnvironment("test", "test", "/test")

        # Add get_model_names method
        async def mock_get_model_names() -> list[str]:
            return ["product.template", "product.product"]

        env.get_model_names = mock_get_model_names

        # Mock execute_code to return models with fields
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # First call for product.template
            product_template_fields = {
                "name": MagicMock(type="char", string="Name", required=True),
                "list_price": MagicMock(type="float", string="Sales Price"),
                "categ_id": MagicMock(type="many2one", string="Category"),
            }

            # Second call for product.product
            product_product_fields = {
                "barcode": MagicMock(type="char", string="Barcode"),
                "product_tmpl_id": MagicMock(type="many2one", string="Product Template", required=True),
            }

            mock_exec.side_effect = [
                MagicMock(_name="product.template", _fields=product_template_fields),
                MagicMock(_name="product.product", _fields=product_product_fields),
            ]

            # Test search for required fields
            result = await search_field_properties(env, "required", PaginationParams())

            # Should find 2 required fields
            assert len(result["fields"]) == 2
            required_fields = [(f["model_name"], f["field_name"]) for f in result["fields"]]
            assert ("product.template", "name") in required_fields
            assert ("product.product", "product_tmpl_id") in required_fields

    def test_mock_registry_cleanup(self) -> None:
        """Test that we clean up MockRegistry.models after tests."""
        # Reset MockRegistry.models to empty
        MockRegistry.models = {}

        registry = MockRegistry()
        items = list(registry)
        assert items == []  # Should be empty again
