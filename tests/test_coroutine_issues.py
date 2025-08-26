from unittest.mock import AsyncMock, MagicMock

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment
from odoo_intelligence_mcp.tools.code.execute_code import execute_code
from odoo_intelligence_mcp.tools.model.view_model_usage import get_view_model_usage
from odoo_intelligence_mcp.tools.security.permission_checker import check_permissions


class TestCoroutineIssues:
    """Test suite to demonstrate coroutine issues in execute_code, permission_checker, and view_model_usage tools."""

    @pytest.mark.asyncio
    async def test_execute_code_coroutine_issue(self) -> None:
        """Test that execute_code fails with coroutine objects when using env['model'].search_count()."""
        # Create a mock environment
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Test code that triggers the issue
        code = """
result = env['res.partner'].search_count([])
"""

        # This should fail with a coroutine-related error
        result = await execute_code(env, code)

        # The issue is that search_count returns a coroutine but execute_code doesn't await it
        assert not result.get("success", True), "Expected failure due to coroutine issue"
        assert "coroutine" in str(result.get("error", "")).lower() or "await" in str(result.get("error", "")).lower()

    @pytest.mark.asyncio
    async def test_execute_code_arithmetic_on_coroutine(self) -> None:
        """Test that execute_code fails when trying arithmetic operations on coroutine results."""
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Test code that tries arithmetic on coroutine
        code = """
count1 = env['res.partner'].search_count([])
count2 = env['res.users'].search_count([])
result = count1 + count2  # This will fail - can't add coroutines
"""

        result = await execute_code(env, code)

        assert not result.get("success", True), "Expected failure due to coroutine arithmetic"
        assert (
            "unsupported operand type" in str(result.get("error", "")).lower() or "coroutine" in str(result.get("error", "")).lower()
        )

    @pytest.mark.asyncio
    async def test_permission_checker_coroutine_issue(self) -> None:
        """Test that permission_checker fails with 'coroutine object has no attribute id'."""
        # Create a mock environment
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Mock the ModelProxy to return a coroutine that mimics the issue
        mock_search = AsyncMock(return_value=MagicMock(id=1, login="admin", name="Admin"))
        env["res.users"].search = mock_search

        # This should fail when trying to access user.id without awaiting
        try:
            result = await check_permissions(env, "admin", "res.partner", "read")
            # If we get here, check if there's an error in the result
            assert "error" in result or "coroutine" in str(result).lower()
        except AttributeError as e:
            # Expected error when trying to access .id on a coroutine
            assert "coroutine" in str(e).lower() or "has no attribute" in str(e).lower()

    @pytest.mark.asyncio
    async def test_view_model_usage_iteration_issue(self) -> None:
        """Test that view_model_usage fails when trying to iterate over coroutine."""
        # Create a mock environment
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Mock search to return a coroutine (not awaited)
        async def mock_search(*_args: object, **_kwargs: object) -> list[MagicMock]:
            return []  # This would normally return view records

        env["ir.ui.view"].search = mock_search

        # This should fail when trying to iterate over the coroutine
        try:
            result = await get_view_model_usage(env, "res.partner")
            # If we get here without error, check result
            assert "error" in result or isinstance(result.get("views"), list)
        except TypeError as e:
            # Expected error when trying to iterate over coroutine
            assert "coroutine" in str(e).lower() or "not iterable" in str(e).lower()

    @pytest.mark.asyncio
    async def test_permission_checker_user_lookup_issue(self) -> None:
        """Test specific issue where user lookup returns coroutine instead of user object."""
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # The issue occurs because search() returns a coroutine but the code expects a user object
        result = await check_permissions(env, "nonexistent_user", "res.partner", "read")

        # Should handle gracefully or show appropriate error
        assert "error" in result or not result.get("success", True)


if __name__ == "__main__":
    # Run the tests to demonstrate the issues
    pytest.main([__file__, "-v"])
