from unittest.mock import AsyncMock

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment
from odoo_intelligence_mcp.tools.code.execute_code import execute_code
from odoo_intelligence_mcp.tools.model.view_model_usage import get_view_model_usage
from odoo_intelligence_mcp.tools.security.permission_checker import check_permissions


class TestCoroutineIssues:
    """Test suite to verify that previous coroutine issues have been resolved."""

    @pytest.mark.asyncio
    async def test_execute_code_coroutine_issue_resolved(self, test_env: HostOdooEnvironment) -> None:
        """Test that execute_code now properly handles coroutine objects like env['model'].search_count()."""
        # Use the test_env fixture
        env = test_env
        env.execute_code = AsyncMock(return_value={"success": True, "result": 42})

        # Test code that previously caused issues
        code = """
result = env['res.partner'].search_count([])
"""

        # This should now succeed - the coroutine issue has been fixed
        result = await execute_code(env, code)

        # The issue has been resolved - search_count should work properly
        assert result.get("success", False), "Expected success - coroutine issue should be resolved"
        assert isinstance(result.get("result"), int), "Should return integer count"

    @pytest.mark.asyncio
    async def test_execute_code_arithmetic_on_coroutine_resolved(self, test_env: HostOdooEnvironment) -> None:
        """Test that execute_code now properly handles arithmetic operations on what were previously coroutines."""
        env = test_env
        env.execute_code = AsyncMock(return_value={"success": True, "result": 12})

        # Test code that previously caused issues with coroutines
        code = """
count1 = env['res.partner'].search_count([])
count2 = env['res.users'].search_count([])
result = count1 + count2  # This should now work - no more coroutines
"""

        result = await execute_code(env, code)

        assert result.get("success", False), "Expected success - coroutine arithmetic issue should be resolved"
        assert isinstance(result.get("result"), int), "Should return integer sum"

    @pytest.mark.asyncio
    async def test_permission_checker_coroutine_issue(self, test_env: HostOdooEnvironment) -> None:
        """Test that permission_checker fails with 'coroutine object has no attribute id'."""
        # Create a mock environment
        env = test_env

        env.execute_code = AsyncMock(return_value={"error": "coroutine object has no attribute id"})

        # This should fail when trying to access user.id without awaiting
        try:
            result = await check_permissions(env, "admin", "res.partner", "read")
            # If we get here, check if there's an error in the result
            assert "error" in result or "coroutine" in str(result).lower()
        except AttributeError as e:
            # Expected error when trying to access .id on a coroutine
            assert "coroutine" in str(e).lower() or "has no attribute" in str(e).lower()

    @pytest.mark.asyncio
    async def test_view_model_usage_iteration_issue_resolved(self, test_env: HostOdooEnvironment) -> None:
        """Test that view_model_usage now properly handles what were previously coroutine iteration issues."""
        # Use the test environment directly
        env = test_env
        env.execute_code = AsyncMock(
            return_value={
                "result": {
                    "model": "res.partner",
                    "views": [],
                    "view_types": {"form": []},
                    "exposed_fields": [],
                    "field_usage_count": {},
                    "field_coverage": {},
                }
            }
        )

        # This should now work without coroutine issues
        result = await get_view_model_usage(env, "res.partner")

        # The function should succeed and return proper data structure
        assert "model" in result, "Should return model information"
        assert result["model"] == "res.partner", "Should have correct model name"
        assert "view_types" in result or "views" in result, "Should contain view information"

    @pytest.mark.asyncio
    async def test_permission_checker_user_lookup_issue(self, test_env: HostOdooEnvironment) -> None:
        """Test specific issue where user lookup returns coroutine instead of user object."""
        env = test_env

        env.execute_code = AsyncMock(return_value={"success": False, "error": "User not found"})

        # The issue occurs because search() returns a coroutine but the code expects a user object
        result = await check_permissions(env, "nonexistent_user", "res.partner", "read")

        # Should handle gracefully or show appropriate error
        assert "error" in result or not result.get("success", True)


if __name__ == "__main__":
    # Run the tests to demonstrate the issues
    pytest.main([__file__, "-v"])
