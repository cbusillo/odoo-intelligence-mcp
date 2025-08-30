from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest

from odoo_intelligence_mcp.core.env import DockerRegistry, HostOdooEnvironment, load_env_config


class TestDockerRegistryIteration:
    """Test DockerRegistry iteration issues that affect tools."""

    @pytest.fixture
    def host_env(self) -> HostOdooEnvironment:
        """Create a HostOdooEnvironment instance."""
        config = load_env_config()
        return HostOdooEnvironment(config.container_name, config.database, config.addons_path, config.db_host, config.db_port)

    def test_docker_registry_returns_empty_iterator(self, host_env: HostOdooEnvironment) -> None:
        """Test that DockerRegistry.__iter__ always returns empty iterator."""
        registry = DockerRegistry(host_env)

        # This is the current behavior - always returns empty
        items = list(registry)
        assert items == []

        # Even if we have models fetched, iteration still returns empty
        registry._models = ["res.partner", "product.template", "sale.order"]
        items = list(registry)
        assert items == []  # Still empty!

    def test_host_env_registry_property_returns_docker_registry(self, host_env: HostOdooEnvironment) -> None:
        """Test that HostOdooEnvironment.registry returns DockerRegistry."""
        registry = host_env.registry
        assert isinstance(registry, DockerRegistry)

        # And DockerRegistry always iterates as empty
        model_names = list(registry)
        assert model_names == []

    @pytest.mark.asyncio
    async def test_docker_registry_async_fetch_models(self, host_env: HostOdooEnvironment) -> None:
        """Test that DockerRegistry can fetch models asynchronously."""
        registry = DockerRegistry(host_env)

        # Mock execute_code to return model list
        with patch.object(host_env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ["res.partner", "product.template", "sale.order"]

            # Fetch models asynchronously
            models = await registry._fetch_models()
            assert models == ["res.partner", "product.template", "sale.order"]

            # But synchronous iteration still returns empty!
            sync_models = list(registry)
            assert sync_models == []

    def test_find_method_pattern_with_docker_registry(self, host_env: HostOdooEnvironment) -> None:
        """Test the pattern used by find_method with DockerRegistry."""
        # This is what find_method does:
        try:
            # noinspection PyTypeChecker
            model_names = list(host_env.registry)
        except (TypeError, AttributeError):
            model_names = []

        # With DockerRegistry, this always gives empty list
        assert model_names == []

        # So find_method will never find any models!

    def test_docker_registry_other_dict_methods(self, host_env: HostOdooEnvironment) -> None:
        """Test other dict-like methods of DockerRegistry."""
        registry = DockerRegistry(host_env)

        # All these return "empty" values
        assert len(registry) == 0
        assert "res.partner" not in registry
        assert registry["res.partner"] is None

    @pytest.mark.asyncio
    async def test_proper_async_pattern_for_docker_registry(self, host_env: HostOdooEnvironment) -> None:
        """Show the correct async pattern that should be used."""
        registry = DockerRegistry(host_env)

        # Mock execute_code
        with patch.object(host_env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ["res.partner", "product.template", "sale.order"]

            # The RIGHT way - use async method
            models = await registry._fetch_models()
            assert len(models) == 3

            # Then iterate over the fetched models
            for model_name in models:
                assert isinstance(model_name, str)

    def test_issue_demonstration_for_tools(self, host_env: HostOdooEnvironment) -> None:
        """Demonstrate the issue that affects find_method, search_decorators, etc."""
        # Tools try to do this:
        for _model_name in host_env.registry:
            # This loop NEVER executes because registry.__iter__ returns empty
            pytest.fail("This should never execute with current DockerRegistry")

        # So tools that depend on iterating env.registry find no models


class TestExpectedBehavior:
    """Tests showing what the expected behavior should be."""

    def test_registry_should_be_iterable_synchronously(self) -> None:
        """Registry should support synchronous iteration for compatibility."""

        # Create a mock registry that works correctly
        class WorkingRegistry:
            def __init__(self) -> None:
                self._models = ["res.partner", "product.template", "sale.order"]

            def __iter__(self) -> Iterator[str]:
                return iter(self._models)

            def __len__(self) -> int:
                return len(self._models)

            def __contains__(self, item: str) -> bool:
                return item in self._models

        registry = WorkingRegistry()

        # Should be able to iterate synchronously
        models = list(registry)
        assert len(models) == 3
        assert "res.partner" in models

        # Should work in for loops
        collected = []
        for model in registry:
            collected.append(model)
        assert len(collected) == 3
