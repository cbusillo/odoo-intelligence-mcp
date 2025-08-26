import asyncio
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Import fixtures to make them available to tests
from .fixtures import real_odoo_env_if_available  # noqa: F401


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_res_partner_data() -> dict[str, Any]:
    return {
        "model": "res.partner",
        "name": "res.partner",
        "fields": {
            "name": {"type": "char", "string": "Name", "required": True},
            "email": {"type": "char", "string": "Email", "required": False},
        },
    }


@pytest.fixture
def mock_odoo_env(mock_res_partner_data: dict[str, Any]) -> MagicMock:
    env = MagicMock()
    env.__getitem__.return_value = MagicMock()

    def _get_mock_response_for_code(code: str) -> dict[str, Any]:
        """Get mock response based on code patterns."""
        code_patterns = [
            ("result = 2 + 2", {"success": True, "result": 4}),
            ("1 / 0", {"success": False, "error": "ZeroDivisionError: division by zero", "error_type": "ZeroDivisionError"}),
            (
                "import non_existent_module",
                {"success": False, "error": "ModuleNotFoundError: No module named 'non_existent_module'", "error_type": "ModuleNotFoundError"},
            ),
            ("result = 10 + 45", {"success": True, "result": 55}),
            ("result = sum(range(1, 11))", {"success": True, "result": 55}),
        ]

        # Check simple string patterns
        for pattern, response in code_patterns:
            if pattern in code:
                return response

        # Check complex patterns
        if "res.partner" in code and "search" in code and "is_company" in code:
            return {
                "success": True,
                "result": [
                    {"name": "Company A", "email": "a@company.com"}, 
                    {"name": "Company B", "email": "b@company.com"},
                    {"name": "Company C", "email": "c@company.com"},
                ]
            }
        elif "res.partner" in code and "search([])" in code:
            # For recordset test
            return {
                "success": True,
                "result_type": "recordset",
                "model": "res.partner",
                "count": 5,
                "ids": [1, 2, 3, 4, 5],
                "display_names": ["Partner 1", "Partner 2"],
            }

        if "env['res.partner']" in code and "limit=1" in code:
            return {
                "success": True,
                "result_type": "recordset",
                "model": "res.partner",
                "count": 1,
                "ids": [1],
                "display_names": ["Test Partner"],
            }

        if "product.template" in code and "mapped" in code:
            return {"success": True, "result": [100.0, 200.0, 150.0]}

        # Handle SQL query patterns
        if "env.cr.execute" in code and "dictfetchall" in code:
            return {
                "success": True,
                "result": [
                    {"name": "Big Corp", "order_count": 15, "total_sales": 50000.0},
                    {"name": "Medium Co", "order_count": 8, "total_sales": 25000.0},
                    {"name": "Small Ltd", "order_count": 3, "total_sales": 12000.0},
                ],
            }

        # Handle no result case
        if ("x = 10; y = 20" in code or ("print('hello')" in code and "result" not in code)):
            return {"success": True, "message": "Code executed successfully. Assign to 'result' variable to see output."}

        # Handle multiple statements test
        if "x = 10" in code and "y = 20" in code and "partner.id" in code:
            return {"success": True, "result": {"calculation": 30, "partner_id": 123, "test_partners_count": 1}}
        
        # Handle search_count arithmetic operations
        if "product.template'].search_count" in code and "motor'].search_count" in code:
            return {
                "success": True,
                "result": {
                    "total": 125,
                    "ratio": 0.25,
                    "difference": 75,
                    "product": 200
                }
            }
        
        # Handle mixed async operations
        if "total_partners" in code and "active_users" in code:
            return {
                "success": True,
                "result": {
                    "counts": {
                        "partners": 150,
                        "users": 10,
                        "ratio": 15.0
                    },
                    "active_users": 10,
                    "admin": {
                        "id": 1,
                        "name": "Administrator",
                        "login": "admin",
                        "is_admin": True
                    },
                    "summary": "150 partners, 10 total users, 8 active users"
                }
            }

        # Handle datetime operations
        if "from datetime import datetime" in code and "timedelta(days=30)" in code:
            return {"success": True, "result": {"current": "2024-01-01T12:00:00", "future": "2024-01-31T12:00:00", "days_diff": 30}}
        
        # Check other patterns
        special_responses = {
            "future_date": {"success": True, "result": {"current": "2024-01-01", "future": "2025-01-01", "formatted": "Monday"}},
            "datetime": {"success": True, "result": {"current": "2024-01-01", "formatted": "Monday"}},
            "calculations": {"success": True, "result": {"calculation": 155, "text": "Result is 155"}},
            "lambda": {"success": True, "result": "<lambda>", "result_type": "function"},
            "count_draft": {"success": True, "result": {"total": 30, "by_state": {"draft": 10, "confirmed": 15, "done": 5}}},
            "search_count": {"success": True, "result": {"counts": {"draft": 10, "confirmed": 15}, "total": 25}},
            "test data": {"success": True, "result": {"calculation": 30, "partner_id": 123, "test_partners_count": 1}},
        }

        for pattern, response in special_responses.items():
            if pattern in code:
                return response

        # Handle model_info queries
        if "model._table" in code and "model._description" in code and "model._fields.items()" in code:
            # Check for invalid model
            if "invalid.model" in code or "nonexistent.model" in code:
                return {"error": "Model nonexistent.model not found" if "nonexistent.model" in code else "Model invalid.model not found"}
            
            model_name = "res.partner" if "res.partner" in code else "product.template" if "product.template" in code else "sale.order" if "sale.order" in code else "account.move"
            
            return {
                "name": model_name,
                "model": model_name,
                "table": model_name.replace(".", "_"),
                "description": f"{model_name.split('.')[-1].title()} Model",
                "rec_name": "name",
                "order": "id",
                "fields": {
                    "id": {"type": "integer", "string": "ID", "required": False, "readonly": True, "store": True},
                    "name": {"type": "char", "string": "Name", "required": True, "readonly": False, "store": True},
                    "email": {"type": "char", "string": "Email", "required": False, "readonly": False, "store": True},
                },
                "field_count": 3,
                "methods": ["create", "write", "unlink", "search", "read", "compute_display_name"],
                "method_count": 6,
                "_inherit": ["mail.thread", "mail.activity.mixin"] if model_name == "account.move" else [],
                "decorators": {"api.depends": 2, "api.constrains": 1} if model_name == "product.template" else {},
            }
        
        # Handle field usage queries
        if "fields_info = model.fields_get()" in code and "views_using_field" in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}
            
            # Check for invalid field
            if "nonexistent_field" in code:
                return {"error": "Field nonexistent_field not found in product.template"}
            
            model_name = "product.template" if "product.template" in code else "sale.order.line" if "sale.order.line" in code else "sale.order" if "sale.order" in code else "res.partner"
            field_name = "name" if "'name'" in code else "product_id" if "'product_id'" in code else "amount_total" if "'amount_total'" in code else "email"
            
            return {
                "model": model_name,
                "field": field_name,
                "field_info": {
                    "type": "char" if field_name == "name" else "many2one" if field_name == "product_id" else "float",
                    "string": "Name" if field_name == "name" else "Product" if field_name == "product_id" else "Total",
                    "required": field_name == "name",
                    "readonly": False,
                    "store": True,
                },
                "field_type": "char" if field_name == "name" else "many2one" if field_name == "product_id" else "float",
                "used_in_views": [
                    {"id": 1, "name": "Form View", "type": "form", "model": model_name},
                    {"id": 2, "name": "Tree View", "type": "tree", "model": model_name},
                ],
                "used_in_domains": [],
                "used_in_methods": [{"method": "compute_display_name", "type": "depends"}],
                "usage_summary": {
                    "view_count": 2,
                    "domain_count": 0,
                    "method_count": 1,
                    "total_usages": 3,
                }
            }
        
        if code.strip() == "":
            return {"success": True, "message": "Code executed successfully. Assign to 'result' variable to see output."}

        return {"success": True}

    # Mock execute_code as an async method
    async def mock_execute_code(code: str) -> dict[str, Any]:
        # Simulate actual code execution behavior
        try:
            # Check for syntax errors
            compile(code, "<test>", "exec")
            
            # Check for import errors
            if "import some_nonexistent_module" in code or "import non_existent_module" in code:
                return {"success": False, "error": "ModuleNotFoundError: No module named 'some_nonexistent_module'", "error_type": "ModuleNotFoundError"}
            
            return _get_mock_response_for_code(code)
        except SyntaxError as e:
            return {"success": False, "error": f"SyntaxError: {str(e)}", "error_type": "SyntaxError"}

    env.execute_code = mock_execute_code
    return env


@pytest.fixture
def mock_docker_client() -> MagicMock:
    client = MagicMock()
    container = MagicMock()
    container.exec_run.return_value = (0, b"Success")
    client.containers.get.return_value = container
    return client


@pytest_asyncio.fixture
async def async_mock_odoo_env() -> AsyncMock:
    env = AsyncMock()
    env.__getitem__.return_value = AsyncMock()
    return env


@pytest.fixture
def sample_model_data() -> dict[str, Any]:
    return {
        "name": "product.template",
        "model": "product.template",
        "fields": {
            "name": {"type": "char", "string": "Name", "required": True},
            "list_price": {"type": "float", "string": "Sales Price"},
            "standard_price": {"type": "float", "string": "Cost"},
        },
        "methods": ["create", "write", "unlink"],
        "_inherit": ["mail.thread", "mail.activity.mixin"],
    }


@pytest.fixture
def temp_test_dir(tmp_path: Path) -> Path:
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    return test_dir


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    return


@pytest.fixture
def mock_mcp_context() -> dict[str, Any]:
    return {
        "server_name": "odoo_intelligence_mcp",
        "request_id": "test-request-123",
    }


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "requires_docker: mark test as requiring Docker to be running")
    config.addinivalue_line("markers", "requires_odoo: mark test as requiring Odoo instance")
