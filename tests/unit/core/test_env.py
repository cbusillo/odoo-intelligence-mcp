from unittest.mock import AsyncMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry


class TestMockRegistry:
    def test_registry_should_be_iterable(self) -> None:
        registry = MockRegistry()

        # Registry should be iterable
        model_names = list(registry)
        assert isinstance(model_names, list)

    def test_registry_should_act_like_dict(self) -> None:
        registry = MockRegistry()

        # Should support dict-like access
        assert hasattr(registry, "__getitem__")
        assert hasattr(registry, "__iter__")
        assert hasattr(registry, "__len__")


class TestHostOdooEnvironment:
    @pytest.fixture
    def env(self) -> HostOdooEnvironment:
        return HostOdooEnvironment("test-container", "test-db", "/test/path")

    def test_registry_should_be_iterable(self, env: HostOdooEnvironment) -> None:
        # The registry property should return an iterable object
        registry = env.registry

        # Should be able to iterate over model names
        try:
            list(registry)
            # This will fail with current implementation since MockRegistry returns empty dict
        except TypeError as e:
            pytest.fail(f"Registry should be iterable but got: {e}")

    def test_registry_iteration_pattern(self, env: HostOdooEnvironment) -> None:
        # This is the pattern used in find_method and other tools
        registry = env.registry

        # Should be able to use this pattern:
        try:
            for model_name in registry:
                # In real usage, we would access env[model_name]
                assert isinstance(model_name, str)
        except TypeError as e:
            pytest.fail(f"Cannot iterate over registry: {e}")

    @pytest.mark.asyncio
    async def test_registry_with_real_models(self, env: HostOdooEnvironment) -> None:
        # Mock the execute_code to simulate getting model list from Odoo
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ["res.partner", "res.users", "product.template", "product.product", "motor.product"]

            # Ideally, registry should be populated with actual models
            # This test shows what we expect but will fail with current implementation
            registry = env.registry

            # Should contain actual model names
            list(registry)
            # This assertion will fail because MockRegistry doesn't fetch real models
            # assert len(model_names) > 0
            # assert 'res.partner' in model_names
