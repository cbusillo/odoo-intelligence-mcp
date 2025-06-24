from unittest.mock import AsyncMock, MagicMock

import pytest

from odoo_intelligence_mcp.tools.security.permission_checker import check_permissions


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

        # Mock user object
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.login = user_login
        mock_user.name = "Test User"
        mock_user.active = True
        mock_user.groups_id = [
            MagicMock(id=1, name="Internal User", category_id=MagicMock(name="User Types")),
            MagicMock(id=2, name="Sales / User", category_id=MagicMock(name="Sales")),
        ]

        # Mock user model with async search
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[mock_user])

        # Mock partner model
        mock_partner_model = MagicMock()
        mock_partner_model._name = model_name
        mock_partner_model.check_access_rights = MagicMock(return_value=True)

        # Mock model access records
        mock_access_records = [
            MagicMock(
                name="res.partner.user",
                group_id=MagicMock(name="Internal User"),
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            )
        ]

        # Mock model access search
        mock_model_access = MagicMock()
        mock_model_access.search = AsyncMock(return_value=mock_access_records)

        # Mock rule records
        mock_rule_records = []
        mock_rule_model = MagicMock()
        mock_rule_model.search = AsyncMock(return_value=mock_rule_records)

        # Setup environment
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            # Return a new environment with the specified user
            new_env = MagicMock()
            new_env.__getitem__.side_effect = lambda key: {
                model_name: mock_partner_model,
                "res.users": mock_user_model,
                "ir.model.access": mock_model_access,
                "ir.rule": mock_rule_model,
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_partner_model,
            "ir.model.access": mock_model_access,
            "ir.rule": mock_rule_model,
        }.get(key, MagicMock())

        # Execute the function
        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        # Expected behavior: Should handle async search and access user attributes
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

        # Mock user object
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.login = "sales_user"
        mock_user.name = "Sales User"
        mock_user.active = True
        mock_user.groups_id = [
            MagicMock(id=3, name="Sales / Manager", category_id=MagicMock(name="Sales")),
        ]

        # Mock user model with async browse
        mock_user_model = MagicMock()
        mock_user_model.browse = AsyncMock(return_value=mock_user)
        mock_user_model.search = AsyncMock(return_value=[])  # Empty search result to trigger ID lookup

        # Mock sale order model
        mock_sale_model = MagicMock()
        mock_sale_model._name = model_name
        mock_sale_model.check_access_rights = MagicMock(return_value=True)

        # Setup environment mocks
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            new_env = MagicMock()
            new_env.__getitem__.side_effect = lambda key: {
                model_name: mock_sale_model,
                "res.users": mock_user_model,
                "ir.model.access": MagicMock(search=AsyncMock(return_value=[])),
                "ir.rule": MagicMock(search=AsyncMock(return_value=[])),
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_sale_model,
            "ir.model.access": MagicMock(search=AsyncMock(return_value=[])),
            "ir.rule": MagicMock(search=AsyncMock(return_value=[])),
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_id, model_name, operation)

        # Expected behavior: Should handle async browse and access user attributes
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

        # Mock user
        mock_user = MagicMock()
        mock_user.id = 10
        mock_user.login = user_login
        mock_user.name = "Regular User"
        mock_user.active = True
        mock_user.groups_id = [
            MagicMock(id=4, name="Project / User", category_id=MagicMock(name="Project")),
        ]

        # Mock task record
        mock_task = MagicMock()
        mock_task.id = record_id
        mock_task.exists = MagicMock(return_value=True)
        mock_task.read = MagicMock(return_value=[{"id": record_id}])
        mock_task.check_access = MagicMock(side_effect=lambda op: op == "read")  # Only read access

        # Mock task model
        mock_task_model = MagicMock()
        mock_task_model._name = model_name
        mock_task_model.browse = AsyncMock(return_value=mock_task)
        mock_task_model.check_access_rights = MagicMock(return_value=True)

        # Mock user model
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[mock_user])

        # Setup environment
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            new_env = MagicMock()
            new_env.__getitem__.side_effect = lambda key: {
                model_name: mock_task_model,
                "res.users": mock_user_model,
                "ir.model.access": MagicMock(search=AsyncMock(return_value=[])),
                "ir.rule": MagicMock(search=AsyncMock(return_value=[])),
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_task_model,
            "ir.model.access": MagicMock(search=AsyncMock(return_value=[])),
            "ir.rule": MagicMock(search=AsyncMock(return_value=[])),
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation, record_id)

        # Expected behavior: Should check record-specific permissions
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

        # Mock user with multiple groups
        mock_user = MagicMock()
        mock_user.id = 20
        mock_user.login = user_login
        mock_user.name = "Accountant User"
        mock_user.active = True

        # Create group objects
        group_internal = MagicMock(id=1, name="Internal User", category_id=MagicMock(name="User Types"))
        group_accountant = MagicMock(id=5, name="Accounting / Accountant", category_id=MagicMock(name="Accounting"))
        group_sales = MagicMock(id=6, name="Sales / User", category_id=MagicMock(name="Sales"))

        mock_user.groups_id = [group_internal, group_accountant, group_sales]

        # Mock model access records with different group permissions
        mock_access_records = [
            MagicMock(
                name="account.move.user",
                group_id=group_internal,
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            ),
            MagicMock(
                name="account.move.accountant",
                group_id=group_accountant,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=False,
            ),
            MagicMock(
                name="account.move.sales",
                group_id=group_sales,
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            ),
        ]

        # Mock models
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[mock_user])

        mock_move_model = MagicMock()
        mock_move_model._name = model_name
        mock_move_model.check_access_rights = MagicMock(return_value=True)

        mock_model_access = MagicMock()
        mock_model_access.search = AsyncMock(return_value=mock_access_records)

        mock_rule_model = MagicMock()
        mock_rule_model.search = AsyncMock(return_value=[])

        # Setup environment
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            new_env = MagicMock()
            new_env.__getitem__.side_effect = lambda key: {
                model_name: mock_move_model,
                "res.users": mock_user_model,
                "ir.model.access": mock_model_access,
                "ir.rule": mock_rule_model,
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_move_model,
            "ir.model.access": mock_model_access,
            "ir.rule": mock_rule_model,
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        # Expected behavior: Should aggregate permissions from all groups
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

        # Mock user
        mock_user = MagicMock()
        mock_user.id = 30
        mock_user.login = user_login
        mock_user.name = "Sales Person"
        mock_user.active = True

        sales_group = MagicMock(id=7, name="Sales / User", category_id=MagicMock(name="Sales"))
        own_docs_group = MagicMock(id=8, name="Sales / Own Documents Only", category_id=MagicMock(name="Sales"))

        mock_user.groups_id = [sales_group, own_docs_group]

        # Mock record rules
        mock_rule_records = [
            MagicMock(
                name="sale.order.personal.rule",
                domain_force="[('user_id','=',user.id)]",
                groups=[own_docs_group],
                global_rule=False,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=True,
            ),
            MagicMock(
                name="sale.order.company.rule",
                domain_force="[('company_id','in',user.company_ids.ids)]",
                groups=[],  # Empty groups = global rule
                global_rule=True,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=True,
            ),
        ]

        # Mock models
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[mock_user])

        mock_sale_model = MagicMock()
        mock_sale_model._name = model_name
        mock_sale_model.check_access_rights = MagicMock(return_value=True)

        mock_model_access = MagicMock()
        mock_model_access.search = AsyncMock(return_value=[])

        mock_rule_model = MagicMock()
        mock_rule_model.search = AsyncMock(return_value=mock_rule_records)

        # Setup environment
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            new_env = MagicMock()
            new_env.__getitem__.side_effect = lambda key: {
                model_name: mock_sale_model,
                "res.users": mock_user_model,
                "ir.model.access": mock_model_access,
                "ir.rule": mock_rule_model,
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_sale_model,
            "ir.model.access": mock_model_access,
            "ir.rule": mock_rule_model,
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        # Expected behavior: Should analyze record rules
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

        # Mock user model returning empty search result
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[])
        mock_user_model.browse = AsyncMock(return_value=MagicMock(exists=MagicMock(return_value=False)))

        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: MagicMock(_name=model_name),
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        # Expected behavior: Should return error for nonexistent user
        assert "error" in result
        assert f"User {user_login} not found" in result["error"]

    @pytest.mark.asyncio
    async def test_permission_checker_handles_exception_in_access_check(self, mock_odoo_env: MagicMock) -> None:
        """Test permission_checker when access check raises exception."""
        user_login = "restricted_user"
        model_name = "hr.employee.private"
        operation = "read"

        # Mock user
        mock_user = MagicMock()
        mock_user.id = 40
        mock_user.login = user_login
        mock_user.name = "Restricted User"
        mock_user.active = True
        mock_user.groups_id = []

        # Mock model that raises exception on access check
        mock_private_model = MagicMock()
        mock_private_model._name = model_name
        mock_private_model.check_access_rights = MagicMock(side_effect=Exception("Access Denied: Insufficient privileges"))

        # Mock models
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[mock_user])

        # Setup environment with access check that fails
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            new_env = MagicMock()
            private_model_copy = MagicMock()
            private_model_copy._name = model_name
            private_model_copy.check_access = MagicMock(side_effect=Exception("Access Denied"))

            new_env.__getitem__.side_effect = lambda key: {
                model_name: private_model_copy,
                "res.users": mock_user_model,
                "ir.model.access": MagicMock(search=AsyncMock(return_value=[])),
                "ir.rule": MagicMock(search=AsyncMock(return_value=[])),
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_private_model,
            "ir.model.access": MagicMock(search=AsyncMock(return_value=[])),
            "ir.rule": MagicMock(search=AsyncMock(return_value=[])),
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation)

        # Expected behavior: Should handle exception gracefully
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

        # Mock user with complex group membership
        mock_user = MagicMock()
        mock_user.id = 50
        mock_user.login = user_login
        mock_user.name = "Project Manager"
        mock_user.active = True

        # Groups
        internal_group = MagicMock(id=1, name="Internal User", category_id=MagicMock(name="User Types"))
        project_user = MagicMock(id=10, name="Project / User", category_id=MagicMock(name="Project"))
        project_manager = MagicMock(id=11, name="Project / Manager", category_id=MagicMock(name="Project"))

        mock_user.groups_id = [internal_group, project_user, project_manager]

        # Mock project record
        mock_project = MagicMock()
        mock_project.id = record_id
        mock_project.exists = MagicMock(return_value=True)
        mock_project.read = MagicMock(return_value=[{"id": record_id}])
        mock_project.check_access = MagicMock(return_value=True)  # Has all access

        # Model access rules
        mock_access_records = [
            MagicMock(
                name="project.project.user",
                group_id=project_user,
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            ),
            MagicMock(
                name="project.project.manager",
                group_id=project_manager,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=True,
            ),
        ]

        # Record rules
        mock_rule_records = [
            MagicMock(
                name="project.project.visibility.followers",
                domain_force="['|', ('privacy_visibility', '!=', 'followers'), ('message_partner_ids', 'in', [user.partner_id.id])]",
                groups=[internal_group],
                global_rule=False,
                perm_read=True,
                perm_write=False,
                perm_create=False,
                perm_unlink=False,
            ),
            MagicMock(
                name="project.project.manager.all",
                domain_force="[(1, '=', 1)]",  # All records
                groups=[project_manager],
                global_rule=False,
                perm_read=True,
                perm_write=True,
                perm_create=True,
                perm_unlink=True,
            ),
        ]

        # Mock models
        mock_user_model = MagicMock()
        mock_user_model.search = AsyncMock(return_value=[mock_user])

        mock_project_model = MagicMock()
        mock_project_model._name = model_name
        mock_project_model.check_access_rights = MagicMock(return_value=True)
        mock_project_model.browse = AsyncMock(return_value=mock_project)

        mock_model_access = MagicMock()
        mock_model_access.search = AsyncMock(return_value=mock_access_records)

        mock_rule_model = MagicMock()
        mock_rule_model.search = AsyncMock(return_value=mock_rule_records)

        # Setup environment
        def mock_env_call(user: MagicMock | None = None) -> MagicMock:
            new_env = MagicMock()
            new_env.__getitem__.side_effect = lambda key: {
                model_name: mock_project_model,
                "res.users": mock_user_model,
                "ir.model.access": mock_model_access,
                "ir.rule": mock_rule_model,
            }.get(key, MagicMock())
            return new_env

        mock_odoo_env.__call__.side_effect = mock_env_call
        mock_odoo_env.__getitem__.side_effect = lambda key: {
            "res.users": mock_user_model,
            model_name: mock_project_model,
            "ir.model.access": mock_model_access,
            "ir.rule": mock_rule_model,
        }.get(key, MagicMock())

        result = await check_permissions(mock_odoo_env, user_login, model_name, operation, record_id)

        # Expected behavior: Complex permission analysis
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
