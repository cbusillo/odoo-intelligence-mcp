import asyncio
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from odoo_intelligence_mcp.core.env import EnvConfig, HostOdooEnvironment, load_env_config

# Import fixtures to make them available to tests
from .fixtures import mock_docker_run, real_odoo_env_if_available  # noqa: F401


@pytest.fixture
def env_config() -> EnvConfig:
    return load_env_config()


@pytest.fixture(scope="session", autouse=True)
def _ensure_container_prefix() -> Generator[None, None, None]:
    explicit = any(
        os.getenv(key) for key in ("ODOO_PROJECT_NAME", "ODOO_CONTAINER_NAME", "ODOO_SCRIPT_RUNNER_CONTAINER", "ODOO_WEB_CONTAINER")
    )
    if explicit:
        yield
        return
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("ODOO_PROJECT_NAME", "odoo")
    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture
def test_env(env_config: EnvConfig) -> HostOdooEnvironment:
    return HostOdooEnvironment(
        env_config.container_name, env_config.database, env_config.addons_path, env_config.db_host, env_config.db_port
    )


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_res_partner_data() -> dict[str, Any]:
    return {
        "model": "res.partner",
        "name": "res.partner",
        "table": "res_partner",
        "description": "Contact",
        "rec_name": "display_name",
        "order": "display_name",
        "fields": {
            "id": {
                "type": "integer",
                "string": "ID",
                "required": False,
                "readonly": True,
                "store": True,
                "searchable": True,
                "sortable": True,
                "index": True,
            },
            "name": {
                "type": "char",
                "string": "Name",
                "required": True,
                "readonly": False,
                "store": True,
                "translate": False,
                "size": False,
                "help": "",
            },
            "display_name": {
                "type": "char",
                "string": "Display Name",
                "required": False,
                "readonly": True,
                "store": False,
                "compute": "_compute_display_name",
                "depends": ["name", "parent_id.display_name"],
            },
            "email": {"type": "char", "string": "Email", "required": False, "readonly": False, "store": True, "help": ""},
            "phone": {"type": "char", "string": "Phone", "required": False, "readonly": False, "store": True},
            "mobile": {"type": "char", "string": "Mobile", "required": False, "readonly": False, "store": True},
            "is_company": {
                "type": "boolean",
                "string": "Is a Company",
                "required": False,
                "readonly": False,
                "store": True,
                "default": False,
            },
            "parent_id": {
                "type": "many2one",
                "string": "Related Company",
                "required": False,
                "readonly": False,
                "store": True,
                "relation": "res.partner",
                "domain": "[('is_company', '=', True)]",
                "ondelete": "restrict",
            },
            "child_ids": {
                "type": "one2many",
                "string": "Contacts",
                "required": False,
                "readonly": False,
                "store": False,
                "relation": "res.partner",
                "relation_field": "parent_id",
            },
            "user_ids": {
                "type": "one2many",
                "string": "Users",
                "required": False,
                "readonly": True,
                "store": False,
                "relation": "res.users",
                "relation_field": "partner_id",
            },
            "company_id": {
                "type": "many2one",
                "string": "Company",
                "required": False,
                "readonly": False,
                "store": True,
                "relation": "res.company",
                "ondelete": "cascade",
            },
            "create_date": {"type": "datetime", "string": "Created on", "required": False, "readonly": True, "store": True},
            "write_date": {"type": "datetime", "string": "Last Updated on", "required": False, "readonly": True, "store": True},
            "active": {"type": "boolean", "string": "Active", "required": False, "readonly": False, "store": True, "default": True},
        },
        "field_count": 14,
        "methods": ["create", "write", "unlink", "search", "read", "name_get", "name_search", "_compute_display_name"],
        "method_count": 8,
        "_inherit": ["mail.thread", "mail.activity.mixin", "image.mixin"],
        "decorators": {
            "api.depends": 3,
            "api.constrains": 2,
            "api.onchange": 1,
            "api.model": 5,
        },
    }


def create_paginated_response(items: list[dict[str, Any]], page: int = 1, page_size: int = 100) -> dict[str, Any]:
    """Helper to create paginated response structure."""
    total_count = len(items)
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    return {
        "items": items[start_idx:end_idx],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next_page": page < total_pages,
            "has_previous_page": page > 1,
            "filter_applied": None,
        },
    }


@pytest.fixture
def mock_odoo_env(mock_res_partner_data: dict[str, Any]) -> MagicMock:
    env = MagicMock()
    env.__getitem__.return_value = MagicMock()

    def _get_mock_response_for_code(code: str) -> dict[str, Any]:
        """Get mock response based on code patterns."""
        # Check for invalid models
        if "invalid.model" in code or "nonexistent.model" in code:
            model = "nonexistent.model" if "nonexistent.model" in code else "invalid.model"
            return {"error": f"Model {model} not found"}
        code_patterns = [
            ("result = 2 + 2", {"success": True, "result": 4}),
            ("1 / 0", {"success": False, "error": "ZeroDivisionError: division by zero", "error_type": "ZeroDivisionError"}),
            (
                "import non_existent_module",
                {
                    "success": False,
                    "error": "ModuleNotFoundError: No module named 'non_existent_module'",
                    "error_type": "ModuleNotFoundError",
                },
            ),
            ("result = 10 + 45", {"success": True, "result": 55}),
            ("result = sum(range(1, 11))", {"success": True, "result": 55}),
            ("result = lambda x: x + 1", {"success": True, "result": "<lambda>", "result_type": "function"}),
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
                ],
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

        if "product.template" in code and "mapped" in code and "from collections import Counter" not in code:
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
        if "x = 10; y = 20" in code or ("print('hello')" in code and "result" not in code):
            return {"success": True, "message": "Code executed successfully. Assign to 'result' variable to see output."}

        # Handle multiple statements test
        if "x = 10" in code and "y = 20" in code and "partner.id" in code:
            return {"success": True, "result": {"calculation": 30, "partner_id": 123, "test_partners_count": 1}}

        # Handle search_count arithmetic operations
        if "product.template'].search_count" in code and "motor'].search_count" in code:
            return {"success": True, "result": {"total": 125, "ratio": 0.25, "difference": 75, "product": 200}}

        # Handle mixed async operations
        if "total_partners" in code and "active_users" in code:
            return {
                "success": True,
                "result": {
                    "counts": {"partners": 150, "users": 10, "ratio": 15.0},
                    "active_users": 10,
                    "admin": {"id": 1, "name": "Administrator", "login": "admin", "is_admin": True},
                    "summary": "150 partners, 10 total users, 8 active users",
                },
            }

        # Handle datetime operations
        if "from datetime import datetime" in code and "timedelta(days=30)" in code:
            return {"success": True, "result": {"current": "2024-01-01T12:00:00", "future": "2024-01-31T12:00:00", "days_diff": 30}}

        # Check other patterns
        special_responses = {
            "future_date": {"success": True, "result": {"current": "2024-01-01", "future": "2025-01-01", "formatted": "Monday"}},
            # Remove the datetime pattern that's too broad
            "calculations": {"success": True, "result": {"calculation": 155, "text": "Result is 155"}},
            # Remove lambda pattern too
            "count_draft": {"success": True, "result": {"total": 30, "by_state": {"draft": 10, "confirmed": 15, "done": 5}}},
            "test data": {"success": True, "result": {"calculation": 30, "partner_id": 123, "test_partners_count": 1}},
        }

        for pattern, response in special_responses.items():
            if pattern in code:
                return response

        # Handle model_info queries
        if "model._table" in code and "model._description" in code and "sorted(model._fields.keys())" in code:
            # Check for invalid model
            if "invalid.model" in code or "nonexistent.model" in code:
                return {
                    "error": "Model nonexistent.model not found" if "nonexistent.model" in code else "Model invalid.model not found"
                }

            model_name = (
                "res.partner"
                if "res.partner" in code
                else "product.template"
                if "product.template" in code
                else "sale.order"
                if "sale.order" in code
                else "account.move"
            )

            return {
                "name": model_name,
                "model": model_name,
                "table": model_name.replace(".", "_"),
                "description": f"{model_name.split('.')[-1].title().replace('_', ' ')} Model",
                "rec_name": "name",
                "order": "id",
                "total_field_count": 3,
                "fields": {
                    "id": {"type": "integer", "string": "ID", "required": False, "readonly": True, "store": True},
                    "name": {"type": "char", "string": "Name", "required": True, "readonly": False, "store": True},
                    "email": {"type": "char", "string": "Email", "required": False, "readonly": False, "store": True},
                },
                "displayed_field_count": 3,
                "pagination": {"page": 1, "page_size": 25, "total_count": 3, "has_next": False, "has_previous": False},
                "methods_sample": ["create", "write", "unlink", "search", "read"],
                "total_method_count": 20,
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

            model_name = (
                "product.template"
                if "product.template" in code
                else "sale.order.line"
                if "sale.order.line" in code
                else "sale.order"
                if "sale.order" in code
                else "res.partner"
            )
            field_name = (
                "name"
                if "'name'" in code
                else "product_id"
                if "'product_id'" in code
                else "amount_total"
                if "'amount_total'" in code
                else "email"
            )

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
                },
            }

        # Handle model relationships queries
        if "many2one_fields = []" in code and "one2many_fields = []" in code and "many2many_fields = []" in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}

            model_name = (
                "sale.order"
                if "sale.order" in code
                else "sale.order.line"
                if "sale.order.line" in code
                else "res.partner"
                if "res.partner" in code
                else "product.template"
            )

            return {
                "model": model_name,
                "many2one_fields": [
                    {
                        "field_name": "partner_id",
                        "target_model": "res.partner",
                        "string": "Customer",
                        "required": True,
                        "ondelete": "restrict",
                    },
                    {
                        "field_name": "user_id",
                        "target_model": "res.users",
                        "string": "Salesperson",
                        "required": False,
                        "ondelete": "set null",
                    },
                ],
                "one2many_fields": [
                    {
                        "field_name": "order_line",
                        "target_model": "sale.order.line",
                        "inverse_field": "order_id",
                        "string": "Order Lines",
                    },
                ],
                "many2many_fields": [
                    {"field_name": "tag_ids", "target_model": "crm.tag", "relation_table": "sale_order_tag_rel", "string": "Tags"},
                ],
                "reverse_many2one": [],
                "reverse_one2many": [],
                "reverse_many2many": [],
                "relationship_summary": {
                    "many2one_count": 2,
                    "one2many_count": 1,
                    "many2many_count": 1,
                    "total_relationships": 4,
                    "reverse_many2one_count": 0,
                    "reverse_one2many_count": 0,
                    "reverse_many2many_count": 0,
                },
            }

        # Handle search_models queries
        if "exact_matches = []" in code and "partial_matches = []" in code and "description_matches = []" in code:
            pattern = None
            if "'res.partner'" in code:
                pattern = "res.partner"
            elif "'sale'" in code:
                pattern = "sale"
            elif "'partner'" in code:
                pattern = "partner"
            elif "'product'" in code:
                pattern = "product"
            elif "'account'" in code:
                pattern = "account"
            elif "'xyznomatch'" in code:
                pattern = "xyznomatch"

            if pattern == "xyznomatch":
                return {
                    "pattern": pattern,
                    "total_models": 0,
                    "exact_matches": [],
                    "partial_matches": [],
                    "description_matches": [],
                }

            exact_matches = []
            partial_matches = []
            description_matches = []

            if pattern == "res.partner":
                exact_matches = [
                    {
                        "name": "res.partner",
                        "description": "Partner Model",
                        "table": "res_partner",
                        "transient": False,
                        "abstract": False,
                    }
                ]
            elif pattern == "sale":
                partial_matches = [
                    {
                        "name": "sale.order",
                        "description": "Sales Order",
                        "table": "sale_order",
                        "transient": False,
                        "abstract": False,
                    },
                    {
                        "name": "sale.order.line",
                        "description": "Sales Order Line",
                        "table": "sale_order_line",
                        "transient": False,
                        "abstract": False,
                    },
                ]
            elif pattern == "partner":
                description_matches = [
                    {"name": "res.partner", "description": "Partner", "table": "res_partner", "transient": False, "abstract": False}
                ]
            elif pattern == "product":
                partial_matches = [
                    {
                        "name": "product.template",
                        "description": "Product Template",
                        "table": "product_template",
                        "transient": False,
                        "abstract": False,
                    },
                    {
                        "name": "product.product",
                        "description": "Product",
                        "table": "product_product",
                        "transient": False,
                        "abstract": False,
                    },
                ]
            elif pattern == "account":
                partial_matches = [
                    {
                        "name": "account.move",
                        "description": "Account Move",
                        "table": "account_move",
                        "transient": False,
                        "abstract": False,
                    },
                    {
                        "name": "account.move.line",
                        "description": "Account Move Line",
                        "table": "account_move_line",
                        "transient": False,
                        "abstract": False,
                    },
                ]

            return {
                "pattern": pattern or "test",
                "total_models": 100,  # Arbitrary total for testing
                "exact_matches": exact_matches,
                "partial_matches": partial_matches,
                "description_matches": description_matches,
            }

        # Handle performance analysis queries
        if "for field_name, field in model._fields.items():" in code and '"performance_issues": issues' in code:
            # Check for invalid model
            if "nonexistent.model" in code:
                return {"error": "Model nonexistent.model not found"}

            model_name = (
                "sale.order"
                if "sale.order" in code
                else "sale.order.line"
                if "sale.order.line" in code
                else "product.template"
                if "product.template" in code
                else "account.move"
                if "account.move" in code
                else "res.partner"
            )

            issues = []
            if model_name == "sale.order.line":
                issues.append(
                    {
                        "type": "potential_n_plus_1",
                        "field": "product_id",
                        "field_type": "many2one",
                        "description": "Non-stored relational field 'product_id' might cause N+1 queries when accessed in loops",
                        "severity": "medium",
                    }
                )

            if model_name == "account.move":
                issues.append(
                    {
                        "type": "missing_index",
                        "field": "date",
                        "description": "Field 'date' is frequently queried but may lack proper indexing",
                        "severity": "low",
                    }
                )

            return {
                "model": model_name,
                "performance_issues": issues,
                "issue_count": len(issues),
                "recommendations": [
                    "Consider adding database indexes on frequently queried fields",
                    "Use prefetch_fields parameter for related fields in loops",
                    "Batch operations instead of individual record processing",
                    "Store computed fields that are frequently accessed",
                    "Use SQL queries for complex aggregations instead of ORM",
                    "Implement proper caching for expensive computations",
                ],
                "field_analysis": {} if model_name != "account.move" else {"analyzed_fields": 10},
            }

        # Handle pattern analysis queries
        if '"computed_fields": []' in code and '"related_fields": []' in code and '"api_decorators": []' in code:
            # Check for invalid pattern type
            if "'invalid_pattern'" in code:
                return {"error": "Unsupported pattern type: invalid_pattern"}

            return {"computed_fields": [], "related_fields": [], "api_decorators": [], "custom_methods": [], "state_machines": []}

        # Handle workflow states queries
        if "workflow_analysis = {" in code and "state_fields" in code and "state_transitions" in code:
            # Check for invalid model
            if "nonexistent.model" in code:
                return {"error": "Model nonexistent.model not found"}

            model_name = (
                "sale.order"
                if "sale.order" in code
                else "purchase.order"
                if "purchase.order" in code
                else "account.move"
                if "account.move" in code
                else "mrp.production"
                if "mrp.production" in code
                else "stock.picking"
                if "stock.picking" in code
                else "project.task"
                if "project.task" in code
                else "product.template"
                if "product.template" in code
                else "res.partner"
            )

            return {
                "model": model_name,
                "state_fields": {},
                "state_transitions": [],
                "button_actions": [],
                "automated_transitions": [],
                "state_dependencies": {},
                "summary": {
                    "has_workflow": model_name != "product.template",
                    "state_field_count": 1 if model_name != "product.template" else 0,
                    "transition_count": 3 if model_name in ["sale.order", "account.move"] else 0,
                    "button_count": 2 if model_name == "mrp.production" else 0,
                    "automated_count": 1 if model_name == "stock.picking" else 0,
                },
            }

        # Handle field dependencies queries
        if "# Get field info using fields_get()" in code and "dependent_fields" in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}

            # Check for invalid field
            if "nonexistent_field" in code:
                return {"error": "Field nonexistent_field not found in res.partner"}

            # Extract model_name and field_name from the code
            model_name = None
            field_name = None

            # Look for model_name = 'xxx' pattern
            import re

            model_match = re.search(r"model_name = ['\"]([^'\"]+)['\"]", code)
            if model_match:
                model_name = model_match.group(1)

            field_match = re.search(r"field_name = ['\"]([^'\"]+)['\"]", code)
            if field_match:
                field_name = field_match.group(1)

            if not model_name:
                model_name = "res.partner"
            if not field_name:
                field_name = "name"

            return {
                "field": field_name,
                "model": model_name,
                "type": "many2one" if field_name in ["partner_id", "product_id"] else "char",
                "direct_dependencies": [],
                "indirect_dependencies": [],
                "dependent_fields": [],
                "dependency_chain": [],
                "summary": {
                    "total_dependents": 0,
                    "total_dependencies": 0,
                    "is_computed": False,
                    "is_related": False,
                },
            }

        # Handle field value analyzer queries
        if "from collections import Counter" in code and "model_obj.search(domain, limit=sample_size)" in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}

            # Check for invalid field
            if "nonexistent_field" in code:
                return {"error": "Field nonexistent_field not found in res.partner"}

            # Extract model and field from code
            import re

            model_match = re.search(r"model_name = ['\"]([^'\"]+)['\"]", code)
            field_match = re.search(r"field_name = ['\"]([^'\"]+)['\"]", code)

            model_name = model_match.group(1) if model_match else "product.template"
            field_name = field_match.group(1) if field_match else "name"

            # Return the correct structure that matches what the actual function returns
            return {
                "model": model_name,
                "field": field_name,
                "field_info": {
                    "type": "selection" if field_name == "state" else "char",
                    "string": field_name.replace("_", " ").title(),
                    "required": False,
                    "readonly": False,
                    "store": True,
                    "compute": None,
                    "relation": None,
                },
                "statistics": {
                    "total_records": 100,
                    "sample_size": 100,
                    "null_count": 5,
                    "empty_count": 3,
                    "unique_count": 10,
                    "null_percentage": 5.0,
                    "unique_percentage": 10.53,
                },
                "value_distribution": [("Value1", 20), ("Value2", 15), ("Value3", 10)],
                "sample_values": ["Value1", "Value2", "Value3", None, "", "Value4"],
                "analysis": {
                    "total_records": 100,
                    "analyzed_records": 100,
                    "unique_values": 10,
                    "null_count": 5,
                    "empty_count": 3,
                    "value_distribution": {},
                    "most_common": [],
                    "least_common": [],
                },
            }

        # Handle search_field_properties queries
        if "property_type = " in code and "model_names = list(env.registry.models.keys())" in code:
            # Extract property_type from code
            import re

            property_match = re.search(r"property_type = ['\"]([^'\"]+)['\"]", code)
            property_type = property_match.group(1) if property_match else "computed"

            return {
                "results": [
                    {
                        "model": "sale.order",
                        "description": "Sales Order",
                        "fields": [
                            {
                                "field": f"test_{property_type}_field",
                                "type": "char",
                                "string": f"Test {property_type.title()} Field",
                                "compute_method": "_compute_test" if property_type == "computed" else None,
                                "related_path": "partner_id.name" if property_type == "related" else None,
                                "stored": "True" if property_type == "computed" else None,
                            }
                        ],
                    },
                    {
                        "model": "res.partner",
                        "description": "Contact",
                        "fields": [
                            {
                                "field": f"{property_type}_email",
                                "type": "char",
                                "string": f"{property_type.title()} Email",
                            }
                        ],
                    },
                ]
            }

        # Handle resolve dynamic fields queries
        if '"computed_fields": {}' in code and '"related_fields": {}' in code and '"runtime_fields": []' in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}

            # Extract model_name from code
            import re

            model_match = re.search(r"model_name = ['\"]([^'\"]+)['\"]", code)
            model_name = model_match.group(1) if model_match else "sale.order"

            return {
                "model": model_name,
                "computed_fields": create_paginated_response([]),
                "related_fields": create_paginated_response([]),
                "field_dependencies": {},
                "runtime_fields": [],
                "reverse_dependencies": {},
                "dependency_graph": create_paginated_response([]),
                "summary": {
                    "total_computed": 0,
                    "total_related": 0,
                    "total_dependencies": 0,
                },
            }

        # Handle search decorator queries
        if "decorator = " in code and "inspect.getmembers(model_class, inspect.isfunction)" in code:
            # Extract decorator type from code
            import re

            decorator_match = re.search(r"decorator = ['\"]([^'\"]+)['\"]", code)
            decorator_type = decorator_match.group(1) if decorator_match else "depends"

            # Return empty results for invalid decorator types
            if decorator_type not in ["depends", "constrains", "onchange", "model_create_multi"]:
                return {"results": []}

            return {
                "results": [
                    {
                        "model": "sale.order",
                        "description": "Sales Order",
                        "methods": [{"method": "_compute_depends", "depends_on": ["field1", "field2"], "signature": "(self)"}],
                    }
                ]
            }

        # Handle search field properties queries
        if "fields_by_property = []" in code and "'property': property_type" in code:
            # Check for invalid property
            if "invalid_property" in code:
                return {"error": "Unsupported property type: invalid_property"}

            property_type = (
                "computed"
                if "'computed'" in code
                else "related"
                if "'related'" in code
                else "stored"
                if "'stored'" in code
                else "required"
                if "'required'" in code
                else "readonly"
            )

            return {
                "property": property_type,
                "fields": [],
                "total_fields": 0,
                "models_scanned": 100,
            }

        # Handle search_field_properties queries first (more specific)
        if "model_names = list(env.registry.models.keys())" in code and "field_data.get('compute')" in code:
            # Extract property_type from code
            import re

            property_match = re.search(r"property_type = ['\"]([^'\"]+)['\"]", code)
            property_type = property_match.group(1) if property_match else "computed"

            if property_type == "invalid_property":
                return {"error": "Invalid property type. Valid properties: computed, related, stored, required, readonly"}

            return {
                "property": property_type,
                "fields": create_paginated_response(
                    [
                        {"model": "sale.order", "field": "amount_total", "type": "float"},
                        {"model": "res.partner", "field": "display_name", "type": "char"},
                    ]
                ),
                "total_fields": 2,
                "models_scanned": 100,
            }

        # Handle find_method queries
        if "model_names = list(env.registry.models.keys())" in code and "hasattr(model_class, method_name)" in code:
            # Extract method_name from code
            import re

            method_match = re.search(r"method_name = ['\"]([^'\"]+)['\"]", code)
            method_name = method_match.group(1) if method_match else "create"

            if method_name == "nonexistent_method":
                return {"implementations": {"items": [], "pagination": {}}}  # Return empty implementations

            # Return list of implementations (the function wraps this in the result dict)
            implementations_list: list[dict[str, Any]] = [
                {
                    "model": "sale.order",
                    "module": "odoo.addons.sale.models.sale_order",
                    "signature": "(self, vals)",
                    "doc": "",
                    "source_preview": "  1: def create(self, vals):\n  2:     # Implementation",
                    "has_super": True,
                },
                {
                    "model": "res.partner",
                    "module": "odoo.addons.base.models.res_partner",
                    "signature": "(self, vals)",
                    "doc": "",
                    "source_preview": "  1: def create(self, vals):\n  2:     # Implementation",
                    "has_super": False,
                },
            ]
            return {"implementations": {"items": implementations_list, "pagination": {}}}

        # Handle search_decorators queries
        if "model_names = list(env.registry.models.keys())" in code and "for name, method in inspect.getmembers" in code:
            # Extract decorator from code
            import re

            decorator_match = re.search(r"decorator = ['\"]([^'\"]+)['\"]", code)
            decorator = decorator_match.group(1) if decorator_match else "depends"

            if decorator == "invalid_decorator":
                return {"decorator": decorator, "methods": [], "total_matches": 0}

            return {
                "decorator": decorator,
                "methods": [
                    {
                        "model": "sale.order",
                        "methods": [
                            {
                                "method": f"_compute_{decorator}",
                                f"{decorator}_on" if decorator == "depends" else decorator: ["field1", "field2"],
                                "signature": "(self)",
                            }
                        ],
                    }
                ],
                "total_matches": 1,
            }

        # Handle view_model_usage queries
        if '"exposed_fields": set()' in code and 'views = env["ir.ui.view"].search' in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}

            # Extract model_name from code
            import re

            model_match = re.search(r"model_name = ['\"]([^'\"]+)['\"]", code)
            model_name = model_match.group(1) if model_match else "res.partner"

            return {
                "model": model_name,
                "views": [
                    {
                        "name": f"{model_name}.form",
                        "type": "form",
                        "xml_id": f"{model_name.split('.')[0]}.view_form",
                        "module": model_name.split(".")[0],
                        "fields": ["name", "partner_id"],
                    },
                    {
                        "name": f"{model_name}.tree",
                        "type": "tree",
                        "xml_id": f"{model_name.split('.')[0]}.view_tree",
                        "module": model_name.split(".")[0],
                        "fields": ["name", "state"],
                    },
                ],
                "exposed_fields": ["name", "partner_id", "state"],
                "view_types": {"form": 1, "tree": 1},
                "field_usage_count": {"name": 2, "partner_id": 1, "state": 1},
                "field_coverage": {
                    "total_fields": 10,
                    "exposed_fields": 3,
                    "coverage_percentage": 30.0,
                    "unexposed_fields": ["create_date", "write_date", "create_uid", "write_uid", "active", "company_id", "user_id"],
                },
                "buttons": [],
                "actions": [],
            }

        # Handle inheritance chain queries
        if "mro_entries = []" in code and "inherits_list = getattr(model_class" in code:
            # Check for invalid model
            if "invalid.model" in code:
                return {"error": "Model invalid.model not found"}

            model_name = (
                "product.template"
                if "product.template" in code
                else "product.product"
                if "product.product" in code
                else "mail.thread"
                if "mail.thread" in code
                else "sale.order"
                if "sale.order" in code
                else "res.partner"
                if "res.partner" in code
                else "account.move"
            )

            return {
                "model": model_name,
                "mro": [
                    {
                        "class": model_name.split(".")[-1].title(),
                        "model": model_name,
                        "module": f"odoo.addons.{model_name.split('.')[0]}.models.{model_name.split('.')[-1]}",
                    },
                    {"class": "Model", "model": "base", "module": "odoo.models"},
                ],
                "inherits": [],
                "inherits_from": {},
                "inherited_fields": {
                    "create_date": {"from_model": "base", "type": "datetime", "string": "Created on", "original_field": None}
                },
                "inheriting_models": [],
                "overridden_methods": [],
                "inherited_methods": {"create": "base", "write": "base", "unlink": "base"},
                "summary": {
                    "total_inherited_fields": 1,
                    "total_models_inheriting": 0,
                    "total_overridden_methods": 0,
                    "inheritance_depth": 1,
                    "uses_delegation": False,
                    "uses_prototype": False,
                },
            }

        if code.strip() == "":
            return {"success": True, "message": "Code executed successfully. Assign to 'result' variable to see output."}

        return {"success": True}

    # Mock execute_code as an async method
    async def mock_execute_code(code: str) -> dict[str, object] | list[object] | str | int | float | bool | None:
        # Simulate actual code execution behavior
        try:
            # Check for syntax errors
            compile(code, "<test>", "exec")

            # Check for import errors
            if "import some_nonexistent_module" in code or "import non_existent_module" in code:
                return {
                    "success": False,
                    "error": "ModuleNotFoundError: No module named 'some_nonexistent_module'",
                    "error_type": "ModuleNotFoundError",
                }

            return _get_mock_response_for_code(code)
        except SyntaxError as e:
            return {"success": False, "error": f"SyntaxError: {e!s}", "error_type": "SyntaxError"}

    env.execute_code = mock_execute_code
    return env


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
        "table": "product_template",
        "description": "Product Template",
        "rec_name": "name",
        "order": "default_code, name, id",
        "fields": {
            "id": {"type": "integer", "string": "ID", "required": False, "readonly": True, "store": True, "index": True},
            "name": {
                "type": "char",
                "string": "Name",
                "required": True,
                "readonly": False,
                "store": True,
                "translate": True,
                "index": "trigram",
            },
            "default_code": {"type": "char", "string": "Internal Reference", "required": False, "readonly": False, "store": True},
            "list_price": {
                "type": "float",
                "string": "Sales Price",
                "required": False,
                "readonly": False,
                "store": True,
                "digits": "Product Price",
                "default": 1.0,
            },
            "standard_price": {
                "type": "float",
                "string": "Cost",
                "required": False,
                "readonly": False,
                "store": True,
                "digits": "Product Price",
                "groups": "base.group_user",
            },
            "categ_id": {
                "type": "many2one",
                "string": "Product Category",
                "required": True,
                "readonly": False,
                "store": True,
                "relation": "product.category",
                "default": "lambda self: self.env['product.category'].search([], limit=1)",
                "ondelete": "cascade",
            },
            "type": {
                "type": "selection",
                "string": "Product Type",
                "required": True,
                "readonly": False,
                "store": True,
                "selection": [["consu", "Consumable"], ["service", "Service"], ["product", "Storable Product"]],
                "default": "consu",
            },
            "uom_id": {
                "type": "many2one",
                "string": "Unit of Measure",
                "required": True,
                "readonly": False,
                "store": True,
                "relation": "uom.uom",
                "ondelete": "restrict",
            },
            "uom_po_id": {
                "type": "many2one",
                "string": "Purchase UoM",
                "required": True,
                "readonly": False,
                "store": True,
                "relation": "uom.uom",
                "ondelete": "restrict",
            },
            "active": {"type": "boolean", "string": "Active", "required": False, "readonly": False, "store": True, "default": True},
            "product_variant_ids": {
                "type": "one2many",
                "string": "Products",
                "required": False,
                "readonly": True,
                "store": False,
                "relation": "product.product",
                "relation_field": "product_tmpl_id",
            },
            "product_variant_count": {
                "type": "integer",
                "string": "# Product Variants",
                "required": False,
                "readonly": True,
                "store": False,
                "compute": "_compute_product_variant_count",
            },
            "barcode": {
                "type": "char",
                "string": "Barcode",
                "required": False,
                "readonly": False,
                "store": True,
                "copy": False,
                "index": True,
            },
            "company_id": {
                "type": "many2one",
                "string": "Company",
                "required": False,
                "readonly": False,
                "store": True,
                "relation": "res.company",
                "index": True,
            },
        },
        "field_count": 14,
        "methods": [
            "create",
            "write",
            "unlink",
            "copy",
            "name_get",
            "_compute_product_variant_count",
            "_get_product_price",
            "action_open_product_template",
        ],
        "method_count": 8,
        "_inherit": ["mail.thread", "mail.activity.mixin", "image.mixin"],
        "decorators": {
            "api.depends": 5,
            "api.constrains": 3,
            "api.onchange": 2,
            "api.model": 4,
        },
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
