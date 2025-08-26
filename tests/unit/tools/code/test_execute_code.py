from unittest.mock import AsyncMock, MagicMock

import pytest

from odoo_intelligence_mcp.tools.code.execute_code import execute_code


@pytest.mark.asyncio
async def test_execute_python_code_success(mock_odoo_env: MagicMock) -> None:
    code = "result = 2 + 2"

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert result["result"] == 4


@pytest.mark.asyncio
async def test_execute_python_code_syntax_error(mock_odoo_env: MagicMock) -> None:
    code = "print('hello world'"

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is False
    assert "SyntaxError" in result["error"]
    assert result["error_type"] == "SyntaxError"


@pytest.mark.asyncio
async def test_execute_python_code_runtime_error(mock_odoo_env: MagicMock) -> None:
    code = "result = 1 / 0"  # Division by zero

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is False
    assert "ZeroDivisionError" in result["error"]
    assert "division by zero" in result["error"]
    assert result["error_type"] == "ZeroDivisionError"


@pytest.mark.asyncio
async def test_execute_python_code_with_odoo_operations(mock_odoo_env: MagicMock) -> None:
    code = """
partners = env['res.partner'].search([('is_company', '=', True)], limit=5)
result = [{'name': p.name, 'email': p.email} for p in partners]
"""

    # Mock the partner model and search results
    mock_partners = MagicMock()
    mock_partners.__iter__.return_value = [
        MagicMock(name="Company A", email="info@companya.com"),
        MagicMock(name="Company B", email="contact@companyb.com"),
        MagicMock(name="Company C", email="hello@companyc.com"),
    ]
    mock_partners.__len__.return_value = 3

    mock_partner_model = MagicMock()
    mock_partner_model.search.return_value = mock_partners
    mock_odoo_env.__getitem__.return_value = mock_partner_model

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    result_data = result["result"]
    assert isinstance(result_data, list)
    assert len(result_data) == 3
    assert result_data[0]["name"] == "Company A"


@pytest.mark.asyncio
async def test_execute_python_code_with_imports(mock_odoo_env: MagicMock) -> None:
    code = """
from datetime import datetime, timedelta

now = datetime.now()
future = now + timedelta(days=30)
result = {
    'current': now.isoformat(),
    'future': future.isoformat(),
    'days_diff': (future - now).days
}
"""

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert isinstance(result["result"], dict)
    assert "current" in result["result"]
    assert "future" in result["result"]
    assert result["result"]["days_diff"] == 30


@pytest.mark.asyncio
async def test_execute_python_code_import_error(mock_odoo_env: MagicMock) -> None:
    code = "import some_nonexistent_module; result = 1"

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is False
    assert "ModuleNotFoundError" in result["error"] or "ImportError" in result["error"]
    assert result["error_type"] in ["ModuleNotFoundError", "ImportError"]


@pytest.mark.asyncio
async def test_execute_python_code_no_result(mock_odoo_env: MagicMock) -> None:
    code = "x = 10; y = 20"  # No result assignment

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert result["message"] == "Code executed successfully. Assign to 'result' variable to see output."


@pytest.mark.asyncio
async def test_execute_python_code_multiple_statements(mock_odoo_env: MagicMock) -> None:
    code = """
# Multiple operations
x = 10
y = 20
z = x + y

# Create a record
partner = env['res.partner'].create({
    'name': 'Test Partner',
    'email': 'test@example.com'
})

# Query data
count = env['res.partner'].search_count([('name', 'ilike', 'test')])

result = {
    'calculation': z,
    'partner_id': partner.id,
    'test_partners_count': count
}
"""

    # Mock partner creation and search
    mock_partner = MagicMock()
    mock_partner.id = 123

    mock_partner_model = MagicMock()
    mock_partner_model.create.return_value = mock_partner
    mock_partner_model.search_count.return_value = 1

    mock_odoo_env.__getitem__.return_value = mock_partner_model

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert result["result"]["calculation"] == 30
    assert result["result"]["partner_id"] == 123
    assert result["result"]["test_partners_count"] == 1


@pytest.mark.asyncio
async def test_execute_python_code_with_recordset_result(mock_odoo_env: MagicMock) -> None:
    code = "result = env['res.partner'].search([])"

    # Mock a recordset result
    mock_records = [
        MagicMock(display_name="Partner 1"),
        MagicMock(display_name="Partner 2"),
        MagicMock(display_name="Partner 3"),
        MagicMock(display_name="Partner 4"),
        MagicMock(display_name="Partner 5"),
    ]

    mock_recordset = MagicMock()
    mock_recordset._name = "res.partner"
    mock_recordset.__len__.return_value = 5
    mock_recordset.ids = [1, 2, 3, 4, 5]
    mock_recordset.__iter__.return_value = iter(mock_records[:2])  # Only iterate first 2 for display_names
    mock_recordset.__getitem__.side_effect = lambda i: mock_records[i]

    mock_partner_model = MagicMock()
    mock_partner_model.search.return_value = mock_recordset
    mock_odoo_env.__getitem__.return_value = mock_partner_model

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert result["result_type"] == "recordset"
    assert result["model"] == "res.partner"
    assert result["count"] == 5
    assert result["ids"] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_execute_python_code_empty_code(mock_odoo_env: MagicMock) -> None:
    code = ""

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert result["message"] == "Code executed successfully. Assign to 'result' variable to see output."


@pytest.mark.asyncio
async def test_execute_python_code_with_print_and_result(mock_odoo_env: MagicMock) -> None:
    code = "result = sum(range(1, 11))"

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert result["result"] == 55


@pytest.mark.asyncio
async def test_execute_python_code_with_non_serializable_result(mock_odoo_env: MagicMock) -> None:
    code = "result = lambda x: x + 1"  # Lambda is not JSON serializable

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    assert "<lambda>" in result["result"]
    assert result["result_type"] == "function"


@pytest.mark.asyncio
async def test_execute_python_code_complex_odoo_query(mock_odoo_env: MagicMock) -> None:
    code = """
# Complex query with joins and aggregations
query = '''
    SELECT p.name, COUNT(so.id) as order_count, SUM(so.amount_total) as total_sales
    FROM res_partner p
    LEFT JOIN sale_order so ON so.partner_id = p.id
    WHERE p.is_company = true
    GROUP BY p.id, p.name
    HAVING COUNT(so.id) > 0
    ORDER BY total_sales DESC
    LIMIT 10
'''

env.cr.execute(query)
result = env.cr.dictfetchall()
"""

    # Mock cursor operations
    mock_cursor = MagicMock()
    mock_cursor.dictfetchall.return_value = [
        {"name": "Big Corp", "order_count": 15, "total_sales": 50000.0},
        {"name": "Medium Co", "order_count": 8, "total_sales": 25000.0},
        {"name": "Small Ltd", "order_count": 3, "total_sales": 12000.0},
    ]
    mock_odoo_env.cr = mock_cursor

    result = await execute_code(mock_odoo_env, code)

    assert result["success"] is True
    result_data = result["result"]
    assert isinstance(result_data, list)
    assert len(result_data) == 3
    assert result_data[0]["name"] == "Big Corp"
    assert result_data[0]["total_sales"] == 50000.0


# Tests for async/coroutine handling from test_execute_code_fix.py
class TestExecuteCodeCoroutineHandling:
    """Test suite for coroutine/async handling in execute_code."""

    @pytest.mark.asyncio
    async def test_execute_code_handles_search_count_in_arithmetic(self, mock_odoo_env: MagicMock) -> None:
        """Test that execute_code properly handles search_count() in arithmetic operations."""
        code = """
products = env['product.template'].search_count([])
motors = env['motor'].search_count([])
result = {
    'total': products + motors,
    'ratio': motors / products if products else 0,
    'difference': products - motors,
    'product': products * 2
}
"""

        # Mock the models to return AsyncMock search_count methods
        mock_product_model = MagicMock()
        mock_product_model.search_count = AsyncMock(return_value=100)

        mock_motor_model = MagicMock()
        mock_motor_model.search_count = AsyncMock(return_value=25)

        mock_odoo_env.__getitem__.side_effect = lambda key: {"product.template": mock_product_model, "motor": mock_motor_model}.get(
            key, MagicMock()
        )

        # Execute the code
        result = await execute_code(mock_odoo_env, code)

        # Expected behavior: Should handle coroutines properly
        assert result["success"] is True
        assert "error" not in result
        assert isinstance(result["result"], dict)
        assert result["result"]["total"] == 125
        assert result["result"]["ratio"] == 0.25
        assert result["result"]["difference"] == 75
        assert result["result"]["product"] == 200

    @pytest.mark.asyncio
    async def test_execute_code_handles_mixed_async_operations(self, mock_odoo_env: MagicMock) -> None:
        """Test complex code with multiple async operations."""
        code = """
# Complex operations mixing different async calls
total_partners = env['res.partner'].search_count([])
total_users = env['res.users'].search_count([])

# Get active users
active_users = env['res.users'].search([('active', '=', True)])
admin_user = env['res.users'].browse(1)

# Create summary
result = {
    'counts': {
        'partners': total_partners,
        'users': total_users,
        'ratio': total_partners / total_users if total_users else 0
    },
    'active_users': len(active_users),
    'admin': {
        'id': admin_user.id,
        'name': admin_user.name,
        'login': admin_user.login
    }
}
"""

        # Mock the models
        mock_partner_model = MagicMock()
        mock_partner_model.search_count = AsyncMock(return_value=150)

        mock_users_recordset = MagicMock()
        mock_users_recordset.__len__.return_value = 10

        mock_admin = MagicMock(id=1, name="Administrator", login="admin")

        mock_user_model = MagicMock()
        mock_user_model.search_count = AsyncMock(return_value=10)
        mock_user_model.search = AsyncMock(return_value=mock_users_recordset)
        mock_user_model.browse = AsyncMock(return_value=mock_admin)

        mock_odoo_env.__getitem__.side_effect = lambda key: {"res.partner": mock_partner_model, "res.users": mock_user_model}.get(
            key, MagicMock()
        )

        result = await execute_code(mock_odoo_env, code)

        # Expected behavior: All async operations should work
        assert result["success"] is True
        assert result["result"]["counts"]["partners"] == 150
        assert result["result"]["counts"]["users"] == 10
        assert result["result"]["counts"]["ratio"] == 15.0
        assert result["result"]["active_users"] == 10
        assert result["result"]["admin"]["name"] == "Administrator"
