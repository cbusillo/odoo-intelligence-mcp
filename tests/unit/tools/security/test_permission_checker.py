from typing import Any
from unittest.mock import MagicMock

import pytest

from odoo_intelligence_mcp.tools.security.permission_checker import check_permissions


# noinspection PyUnusedLocal
class TestPermissionCheckerCoroutineFix:
    """
    Test suite demonstrating coroutine issues in permission_checker and defining expected behavior.

    The main issues are:
    1. User lookup via search() returns a coroutine that isn't awaited
    2. Accessing user.id and other attributes on coroutine objects
    3. browse() operations returning coroutines
    """

    @pytest.mark.asyncio
    async def test_permission_checker_handles_user_search(self, mock_odoo_env: MagicMock) -> None:
        """Test that permission_checker properly handles user search returning coroutines."""
        user_login = "test_user"
        model_name = "res.partner"
        operation = "read"

        mock_execute_response = {
            "user": {"id": 123, "login": user_login, "name": "Test User", "active": True},
            "model": model_name,
            "operation": operation,
            "permissions": {"read": True, "write": False, "create": False, "unlink": False},
            "groups": [
                {"id": 1, "name": "Internal User", "category": "User Types"},
                {"id": 2, "name": "Sales / User", "category": "Sales"},
            ],
            "model_access_rules": [
                {
                    "name": "res.partner.user",
                    "group": "Internal User",
                    "permissions": {"read": True, "write": False, "create": False, "unlink": False},
                    "user_has_group": True,
                }
            ],
            "record_rules": [],
            "access_summary": {
                "has_model_access": True,
                "applicable_record_rules_count": 0,
                "likely_has_access": True,
                "recommendation": "User has read access with no record rules restrictions.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        assert "error" not in result
        assert result["user"]["id"] == 123
        assert result["user"]["login"] == user_login
        assert result["user"]["name"] == "Test User"
        assert result["user"]["active"] is True
        assert len(result["groups"]) == 2
        assert result["permissions"]["read"] is True
        assert result["access_summary"]["has_model_access"] is True

    @pytest.mark.asyncio
    async def test_permission_checker_handles_user_browse_by_id(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker when user is specified by ID using browse()."""
        user_id = "123"  # String ID
        model_name = "sale.order"
        operation = "write"

        mock_execute_response = {
            "user": {"id": 123, "login": "sales_user", "name": "Sales User", "active": True},
            "model": model_name,
            "operation": operation,
            "permissions": {"read": True, "write": True, "create": False, "unlink": False},
            "groups": [{"id": 3, "name": "Sales / Manager", "category": "Sales"}],
            "model_access_rules": [],
            "record_rules": [],
            "access_summary": {
                "has_model_access": True,
                "applicable_record_rules_count": 0,
                "likely_has_access": True,
                "recommendation": "User has write access with no record rules restrictions.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_id, model_name, operation)

        assert "error" not in result
        assert result["user"]["id"] == 123
        assert result["user"]["login"] == "sales_user"
        assert result["user"]["name"] == "Sales User"

    @pytest.mark.asyncio
    async def test_permission_checker_handles_record_access_check(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker with specific record ID using browse()."""
        user_login = "user"
        model_name = "project.task"
        operation = "write"
        record_id = 456

        mock_execute_response = {
            "user": {"id": 10, "login": user_login, "name": "Regular User", "active": True},
            "model": model_name,
            "operation": operation,
            "record_id": record_id,
            "permissions": {"read": True, "write": True, "create": False, "unlink": False},
            "groups": [{"id": 4, "name": "Project / User", "category": "Project"}],
            "model_access_rules": [],
            "record_rules": [],
            "record_access": {"record_id": record_id, "exists": True, "can_read": True, "can_write": False},
            "access_summary": {
                "has_model_access": True,
                "applicable_record_rules_count": 0,
                "likely_has_access": True,
                "recommendation": "User has write access with record restrictions.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation, record_id)

        assert "error" not in result
        assert result["record_id"] == record_id
        assert result["record_access"]["exists"] is True
        assert result["record_access"]["can_read"] is True
        assert result["record_access"]["can_write"] is False  # No write access

    @pytest.mark.asyncio
    async def test_permission_checker_handles_model_access_rules(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker with complex model access rules."""
        user_login = "accountant"
        model_name = "account.move"
        operation = "create"

        mock_execute_response = {
            "user": {"id": 20, "login": user_login, "name": "Accountant User", "active": True},
            "model": model_name,
            "operation": operation,
            "permissions": {"read": True, "write": True, "create": True, "unlink": False},
            "groups": [
                {"id": 1, "name": "Internal User", "category": "User Types"},
                {"id": 5, "name": "Accounting / Accountant", "category": "Accounting"},
                {"id": 6, "name": "Sales / User", "category": "Sales"},
            ],
            "model_access_rules": [
                {
                    "name": "account.move.user",
                    "group": "Internal User",
                    "permissions": {"read": True, "write": False, "create": False, "unlink": False},
                    "user_has_group": True,
                },
                {
                    "name": "account.move.accountant",
                    "group": "Accounting / Accountant",
                    "permissions": {"read": True, "write": True, "create": True, "unlink": False},
                    "user_has_group": True,
                },
                {
                    "name": "account.move.sales",
                    "group": "Sales / User",
                    "permissions": {"read": True, "write": False, "create": False, "unlink": False},
                    "user_has_group": True,
                },
            ],
            "record_rules": [],
            "access_summary": {
                "has_model_access": True,
                "applicable_record_rules_count": 0,
                "likely_has_access": True,
                "recommendation": "User has create access with no record rules restrictions.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        assert "error" not in result
        assert len(result["model_access_rules"]) == 3

        # Check that user has create access through accountant group
        accountant_rule = next(r for r in result["model_access_rules"] if r["name"] == "account.move.accountant")
        assert accountant_rule["permissions"]["create"] is True
        assert accountant_rule["user_has_group"] is True

        # Verify summary indicates create access
        assert result["permissions"]["create"] is True
        assert result["access_summary"]["has_model_access"] is True

    @pytest.mark.asyncio
    async def test_permission_checker_handles_record_rules(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker with record rules (row-level security)."""
        user_login = "salesperson"
        model_name = "sale.order"
        operation = "write"

        mock_execute_response = {
            "user": {"id": 30, "login": user_login, "name": "Sales Person", "active": True},
            "model": model_name,
            "operation": operation,
            "permissions": {"read": True, "write": True, "create": True, "unlink": True},
            "groups": [
                {"id": 7, "name": "Sales / User", "category": "Sales"},
                {"id": 8, "name": "Sales / Own Documents Only", "category": "Sales"},
            ],
            "model_access_rules": [],
            "record_rules": [
                {
                    "name": "sale.order.personal.rule",
                    "domain": "[('user_id','=',user.id)]",
                    "groups": ["Sales / Own Documents Only"],
                    "global": False,
                    "permissions": {"read": True, "write": True, "create": True, "unlink": True},
                    "applies_to_user": True,
                },
                {
                    "name": "sale.order.company.rule",
                    "domain": "[('company_id','in',user.company_ids.ids)]",
                    "groups": [],
                    "global": True,
                    "permissions": {"read": True, "write": True, "create": True, "unlink": True},
                    "applies_to_user": True,
                },
            ],
            "access_summary": {
                "has_model_access": True,
                "applicable_record_rules_count": 2,
                "likely_has_access": True,
                "recommendation": "User has write access. Check record rules if specific records are inaccessible.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        assert "error" not in result
        assert len(result["record_rules"]) == 2

        # Check personal rule
        personal_rule = next(r for r in result["record_rules"] if "personal" in r["name"])
        assert personal_rule["applies_to_user"] is True
        assert personal_rule["permissions"]["write"] is True
        assert "[('user_id','=',user.id)]" in personal_rule["domain"]

        # Check global rule
        global_rule = next(r for r in result["record_rules"] if "company" in r["name"])
        assert global_rule["applies_to_user"] is True
        assert global_rule["global"] is True

    @pytest.mark.asyncio
    async def test_permission_checker_handles_nonexistent_user(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker when user doesn't exist."""
        user_login = "nonexistent_user"
        model_name = "res.partner"
        operation = "read"

        mock_execute_response = {
            "error": f"User with login '{user_login}' not found. Try using the user ID instead of login, or verify the login exists."
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        assert "error" in result
        assert f"User with login '{user_login}' not found" in result["error"]

    @pytest.mark.asyncio
    async def test_permission_checker_handles_exception_in_access_check(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker when access check raises exception."""
        user_login = "restricted_user"
        model_name = "hr.employee.private"
        operation = "read"

        mock_execute_response = {
            "user": {"id": 40, "login": user_login, "name": "Restricted User", "active": True},
            "model": model_name,
            "operation": operation,
            "permissions": {"read": False, "write": False, "create": False, "unlink": False},
            "read_error": "Access Denied: Insufficient privileges",
            "groups": [],
            "model_access_rules": [],
            "record_rules": [],
            "access_summary": {
                "has_model_access": False,
                "applicable_record_rules_count": 0,
                "likely_has_access": False,
                "recommendation": "User lacks read access. No model access rules grant read permission for this user.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        assert "error" not in result  # Main function shouldn't crash
        assert result["permissions"]["read"] is False
        assert "Access Denied" in result.get("read_error", "")

    @pytest.mark.asyncio
    async def test_permission_checker_complex_scenario(self, mock_odoo_env: MagicMock) -> None:
        """Test complex real-world scenario with multiple permission layers."""
        user_login = "project_manager"
        model_name = "project.project"
        operation = "write"
        record_id = 100

        mock_execute_response = {
            "user": {"id": 50, "login": user_login, "name": "Project Manager", "active": True},
            "model": model_name,
            "operation": operation,
            "record_id": record_id,
            "permissions": {"read": True, "write": True, "create": True, "unlink": True},
            "groups": [
                {"id": 1, "name": "Internal User", "category": "User Types"},
                {"id": 10, "name": "Project / User", "category": "Project"},
                {"id": 11, "name": "Project / Manager", "category": "Project"},
            ],
            "model_access_rules": [
                {
                    "name": "project.project.user",
                    "group": "Project / User",
                    "permissions": {"read": True, "write": False, "create": False, "unlink": False},
                    "user_has_group": True,
                },
                {
                    "name": "project.project.manager",
                    "group": "Project / Manager",
                    "permissions": {"read": True, "write": True, "create": True, "unlink": True},
                    "user_has_group": True,
                },
            ],
            "record_rules": [
                {
                    "name": "project.project.visibility.followers",
                    "domain": "['|', ('privacy_visibility', '!=', 'followers'), "
                    "('message_partner_ids', 'in', [user.partner_id.id])]",
                    "groups": ["Internal User"],
                    "global": False,
                    "permissions": {"read": True, "write": False, "create": False, "unlink": False},
                    "applies_to_user": True,
                },
                {
                    "name": "project.project.manager.all",
                    "domain": "[(1, '=', 1)]",
                    "groups": ["Project / Manager"],
                    "global": False,
                    "permissions": {"read": True, "write": True, "create": True, "unlink": True},
                    "applies_to_user": True,
                },
            ],
            "record_access": {
                "record_id": record_id,
                "exists": True,
                "can_read": True,
                "can_write": True,
                "can_unlink": True,
            },
            "access_summary": {
                "has_model_access": True,
                "applicable_record_rules_count": 2,
                "likely_has_access": True,
                "recommendation": "User has write access. Check record rules if specific records are inaccessible.",
            },
        }

        async def mock_execute_code(code: str) -> dict[str, Any]:
            return mock_execute_response

        mock_odoo_env.execute_code = mock_execute_code

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation, record_id)

        assert "error" not in result

        # User should have write access through manager group
        assert result["permissions"]["write"] is True
        assert result["access_summary"]["has_model_access"] is True

        # Record-specific access should be granted
        assert result["record_access"]["exists"] is True
        assert result["record_access"]["can_write"] is True

        # Should have both user and manager access rules
        assert len(result["model_access_rules"]) == 2
        manager_rule = next(r for r in result["model_access_rules"] if "manager" in r["name"])
        assert manager_rule["permissions"]["write"] is True
        assert manager_rule["user_has_group"] is True

        # Should have applicable record rules
        assert len(result["record_rules"]) == 2
        manager_record_rule = next(r for r in result["record_rules"] if "manager" in r["name"])
        assert manager_record_rule["applies_to_user"] is True
        assert manager_record_rule["permissions"]["write"] is True
