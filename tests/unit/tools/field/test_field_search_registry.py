from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry, load_env_config
from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.field import search_field_properties, search_field_type


class TestFieldSearchRegistryIssue:
    """Test field search tools with focus on registry iteration issue."""

    @pytest.fixture
    def mock_env_docker_registry(self) -> HostOdooEnvironment:
        """Create environment with DockerRegistry that returns empty iterator."""
        config = load_env_config()
        return HostOdooEnvironment(config.container_name, config.database, config.addons_path, config.db_host, config.db_port)

    @pytest.mark.asyncio
    async def test_search_field_type_with_docker_registry(self, mock_env_docker_registry: HostOdooEnvironment) -> None:
        """Test search_field_type with DockerRegistry that returns empty."""
        env = mock_env_docker_registry

        # Mock execute_code to return empty results
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"results": []}

            # Call search_field_type
            result = await search_field_type(env, "many2one", PaginationParams())

            # Due to empty results, we get no fields but with pagination structure
            assert "fields" in result
            assert result["fields"]["items"] == []
            assert result["fields"]["pagination"]["total_count"] == 0

    @pytest.mark.asyncio
    async def test_search_field_properties_with_docker_registry(self, mock_env_docker_registry: HostOdooEnvironment) -> None:
        """Test search_field_properties with DockerRegistry that returns empty."""
        env = mock_env_docker_registry

        # Mock execute_code to return empty results
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"results": []}

            # Call search_field_properties
            result = await search_field_properties(env, "computed", PaginationParams())

            # Due to empty results, we get no fields but with pagination structure
            assert result["property"] == "computed"
            assert "fields" in result
            assert result["fields"]["items"] == []
            assert result["fields"]["pagination"]["total_count"] == 0

    @pytest.mark.asyncio
    async def test_field_search_with_mock_registry(self) -> None:
        """Test field search with MockRegistry that can be populated."""
        # Create mock environment
        env = MagicMock()

        # Mock execute_code to simulate field search
        # noinspection PyUnusedLocal
        async def mock_execute_search_many2one(*args: object, **kwargs: object) -> dict[str, object]:
            return {
                "results": [
                    {
                        "model": "res.partner",
                        "description": "Contact",
                        "fields": [{"field": "company_id", "string": "Company", "required": False, "comodel_name": "res.company"}],
                    },
                    {
                        "model": "sale.order",
                        "description": "Sales Order",
                        "fields": [{"field": "partner_id", "string": "Customer", "required": False, "comodel_name": "res.partner"}],
                    },
                ]
            }

        env.execute_code = mock_execute_search_many2one

        # Test search_field_type
        result = await search_field_type(env, "many2one", PaginationParams())

        # Should find 2 many2one fields with pagination structure
        assert "fields" in result
        assert "items" in result["fields"]
        # The items will be models with their fields, not flat field list
        items = result["fields"]["items"]
        assert len(items) == 2
        model_names = [item["model"] for item in items]
        assert "res.partner" in model_names
        assert "sale.order" in model_names

        # Mock execute_code for computed field search
        # noinspection PyUnusedLocal
        async def mock_execute_search_computed(*args: object, **kwargs: object) -> dict[str, object]:
            return {
                "results": [
                    {
                        "model": "sale.order",
                        "description": "Sales Order",
                        "fields": [{"field": "amount_total", "string": "Total", "compute": "_compute_amount"}],
                    }
                ]
            }

        env.execute_code = mock_execute_search_computed

        # Test search_field_properties for computed fields
        result = await search_field_properties(env, "computed", PaginationParams())

        # Should find 1 computed field with pagination structure
        assert "fields" in result
        assert "items" in result["fields"]
        items = result["fields"]["items"]
        assert len(items) == 1
        assert items[0]["model"] == "sale.order"
        # Check that amount_total is in the fields list
        field_names = [f["field"] for f in items[0]["fields"]]
        assert "amount_total" in field_names

    @pytest.mark.asyncio
    async def test_field_search_with_host_env_and_execute_code(self) -> None:
        """Test field search when HostOdooEnvironment has execute_code."""
        config = load_env_config()
        env = HostOdooEnvironment(config.container_name, config.database, config.addons_path, config.db_host, config.db_port)

        # Mock execute_code to return required fields
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "results": [
                    {
                        "model": "product.template",
                        "description": "Product Template",
                        "fields": [{"field": "name", "string": "Name", "required": True}],
                    },
                    {
                        "model": "product.product",
                        "description": "Product",
                        "fields": [{"field": "product_tmpl_id", "string": "Product Template", "required": True}],
                    },
                ]
            }

            # Test search for required fields
            result = await search_field_properties(env, "required", PaginationParams())

            # Should find 2 required fields with pagination structure
            assert "fields" in result
            assert "items" in result["fields"]
            items = result["fields"]["items"]
            assert len(items) == 2
            model_names = [item["model"] for item in items]
            assert "product.template" in model_names
            assert "product.product" in model_names

    def test_mock_registry_cleanup(self) -> None:
        """Test that we clean up MockRegistry.models after tests."""
        # Reset MockRegistry.models to empty
        MockRegistry.models = {}

        registry = MockRegistry()
        items = list(registry)
        assert items == []  # Should be empty again
