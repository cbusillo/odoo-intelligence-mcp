# noinspection DuplicatedCode
from unittest.mock import MagicMock, Mock

import pytest

from odoo_intelligence_mcp.tools.field.field_dependencies import get_field_dependencies
from tests.test_utils import MockEnv


@pytest.fixture
def field_test_env() -> MockEnv:
    """Custom env fixture that properly handles model access and containment checks."""
    return MockEnv()


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_field_dependencies_finds_standard_fields(field_test_env: MockEnv) -> None:
    model_name = "product.template"
    field_name = "name"

    # Mock the model
    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() to return standard field info
    mock_model.fields_get.return_value = {
        "name": {
            "type": "char",
            "string": "Name",
            "required": True,
            "searchable": True,
            "sortable": True,
            "store": True,
        },
        "display_name": {
            "type": "char",
            "string": "Display Name",
            "compute": "_compute_display_name",
            "store": False,
            "depends": ["name"],
        },
        "description": {
            "type": "text",
            "string": "Description",
        },
    }

    # Mock _fields for dependency analysis
    mock_name_field = Mock()
    mock_name_field.type = "char"
    mock_name_field.string = "Name"
    mock_name_field.required = True
    mock_name_field.compute = None
    mock_name_field.related = None

    mock_display_field = Mock()
    mock_display_field.type = "char"
    mock_display_field.string = "Display Name"
    mock_display_field.compute = "_compute_display_name"
    mock_display_field.related = None

    # Mock compute method with dependencies
    compute_method = MagicMock()
    compute_method._depends = ["name"]
    mock_model._compute_display_name = compute_method

    mock_model._fields = {
        "name": mock_name_field,
        "display_name": mock_display_field,
    }

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["model"] == model_name
    assert result["field"] == field_name
    assert result["type"] == "char"
    assert result["direct_dependencies"] == []
    assert len(result["dependent_fields"]) == 1
    assert result["dependent_fields"][0]["field"] == "display_name"


@pytest.mark.asyncio
async def test_field_dependencies_finds_inherited_fields(field_test_env: MockEnv) -> None:
    model_name = "product.template"
    field_name = "create_date"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() to include inherited fields
    mock_model.fields_get.return_value = {
        "name": {"type": "char", "string": "Name"},
        "create_date": {
            "type": "datetime",
            "string": "Created on",
            "readonly": True,
            "store": True,
            "help": "Date on which this record was created",
        },
        "write_date": {
            "type": "datetime",
            "string": "Last Updated on",
            "readonly": True,
            "store": True,
        },
        "display_name": {
            "type": "char",
            "string": "Display Name",
            "compute": "_compute_display_name",
            "depends": ["name", "create_date"],
        },
    }

    # Mock _fields
    mock_create_field = Mock()
    mock_create_field.type = "datetime"
    mock_create_field.readonly = True
    mock_create_field.compute = None
    mock_create_field.related = None

    mock_display_field = Mock()
    mock_display_field.type = "char"
    mock_display_field.compute = "_compute_display_name"

    compute_method = MagicMock()
    compute_method._depends = ["name", "create_date"]
    mock_model._compute_display_name = compute_method

    mock_model._fields = {
        "create_date": mock_create_field,
        "display_name": mock_display_field,
    }

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field"] == field_name
    assert result["type"] == "datetime"
    assert len(result["dependent_fields"]) == 1  # display_name depends on create_date


@pytest.mark.asyncio
async def test_field_dependencies_with_computed_field(field_test_env: MockEnv) -> None:
    model_name = "sale.order"
    field_name = "amount_total"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get()
    mock_model.fields_get.return_value = {
        "amount_total": {
            "type": "monetary",
            "string": "Total",
            "compute": "_compute_amounts",
            "store": True,
            "depends": ["order_line.price_total", "currency_id"],
        },
        "order_line": {
            "type": "one2many",
            "string": "Order Lines",
            "relation": "sale.order.line",
        },
        "currency_id": {
            "type": "many2one",
            "string": "Currency",
            "relation": "res.currency",
        },
    }

    # Mock _fields
    mock_amount_field = Mock()
    mock_amount_field.type = "monetary"
    mock_amount_field.compute = "_compute_amounts"
    mock_amount_field.store = True
    mock_amount_field.related = None

    compute_method = MagicMock()
    compute_method._depends = ["order_line.price_total", "currency_id"]
    mock_model._compute_amounts = compute_method

    mock_order_line_field = Mock()
    mock_order_line_field.type = "one2many"
    mock_order_line_field.comodel_name = "sale.order.line"
    mock_order_line_field.compute = None
    mock_order_line_field.related = None

    mock_model._fields = {
        "amount_total": mock_amount_field,
        "order_line": mock_order_line_field,
        "currency_id": Mock(type="many2one", comodel_name="res.currency", compute=None, related=None),
    }

    # Mock related model
    mock_line_model = MagicMock()
    mock_price_total_field = Mock()
    mock_price_total_field.type = "monetary"
    mock_price_total_field.compute = "_compute_price"

    # Add compute method for price_total
    compute_price_method = MagicMock()
    compute_price_method._depends = ["price_unit", "quantity"]
    mock_line_model._compute_price = compute_price_method

    mock_line_model._fields = {
        "price_total": mock_price_total_field,
    }

    field_test_env.add_model(model_name, mock_model)
    field_test_env.add_model("sale.order.line", mock_line_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["type"] == "monetary"
    assert len(result["direct_dependencies"]) == 2
    assert "order_line.price_total" in result["direct_dependencies"]
    assert "currency_id" in result["direct_dependencies"]
    assert len(result["dependency_chain"]) > 0


@pytest.mark.asyncio
async def test_field_dependencies_with_related_field(field_test_env: MockEnv) -> None:
    model_name = "sale.order.line"
    field_name = "partner_id"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get()
    mock_model.fields_get.return_value = {
        "partner_id": {
            "type": "many2one",
            "string": "Customer",
            "relation": "res.partner",
            "related": "order_id.partner_id",
            "store": True,
            "readonly": True,
        },
        "order_id": {
            "type": "many2one",
            "string": "Order",
            "relation": "sale.order",
        },
    }

    # Mock _fields
    mock_partner_field = Mock()
    mock_partner_field.type = "many2one"
    mock_partner_field.comodel_name = "res.partner"
    mock_partner_field.related = ["order_id", "partner_id"]
    mock_partner_field.compute = None

    mock_order_field = Mock()
    mock_order_field.type = "many2one"
    mock_order_field.comodel_name = "sale.order"
    mock_order_field.compute = None
    mock_order_field.related = None

    mock_model._fields = {
        "partner_id": mock_partner_field,
        "order_id": mock_order_field,
    }

    # Mock related model
    mock_order_model = MagicMock()
    mock_order_model._fields = {
        "partner_id": Mock(type="many2one", comodel_name="res.partner", compute=None, related=None),
    }

    field_test_env.add_model(model_name, mock_model)
    field_test_env.add_model("sale.order", mock_order_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["type"] == "many2one"
    assert len(result["direct_dependencies"]) == 1
    assert result["direct_dependencies"][0] == "order_id.partner_id"


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_field_dependencies_handles_missing_field(field_test_env: MockEnv) -> None:
    model_name = "product.template"
    field_name = "nonexistent_field"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() without the requested field
    mock_model.fields_get.return_value = {
        "name": {"type": "char", "string": "Name"},
        "display_name": {"type": "char", "string": "Display Name"},
    }

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert field_name in result["error"]
    assert model_name in result["error"]


@pytest.mark.asyncio
async def test_field_dependencies_with_no_dependencies(field_test_env: MockEnv) -> None:
    model_name = "res.partner"
    field_name = "name"

    mock_model = MagicMock()
    mock_model._name = model_name

    mock_model.fields_get.return_value = {
        "name": {
            "type": "char",
            "string": "Name",
            "required": True,
        }
    }

    # Mock _fields
    mock_name_field = Mock()
    mock_name_field.type = "char"
    mock_name_field.compute = None
    mock_name_field.related = None

    mock_model._fields = {"name": mock_name_field}

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field"] == field_name
    assert len(result["direct_dependencies"]) == 0
    assert len(result["dependent_fields"]) == 0
    assert len(result["dependency_chain"]) == 0


@pytest.mark.asyncio
async def test_field_dependencies_complex_chain(field_test_env: MockEnv) -> None:
    model_name = "project.task"
    field_name = "project_partner_email"

    mock_task_model = MagicMock()
    mock_task_model._name = model_name

    # Mock fields_get() with complex chain
    mock_task_model.fields_get.return_value = {
        "project_partner_email": {
            "type": "char",
            "string": "Project Customer Email",
            "related": "project_id.partner_id.email",
            "readonly": True,
        },
        "project_id": {
            "type": "many2one",
            "string": "Project",
            "relation": "project.project",
        },
    }

    # Mock _fields
    mock_email_field = Mock()
    mock_email_field.type = "char"
    mock_email_field.related = ["project_id", "partner_id", "email"]
    mock_email_field.compute = None

    mock_project_field = Mock()
    mock_project_field.type = "many2one"
    mock_project_field.comodel_name = "project.project"
    mock_project_field.compute = None
    mock_project_field.related = None

    mock_task_model._fields = {
        "project_partner_email": mock_email_field,
        "project_id": mock_project_field,
    }

    # Mock project model
    mock_project_model = MagicMock()
    mock_project_model._fields = {
        "partner_id": Mock(type="many2one", comodel_name="res.partner", compute=None, related=None),
    }

    # Mock partner model
    mock_partner_model = MagicMock()
    mock_partner_model._fields = {
        "email": Mock(type="char", compute=None, related=None),
    }

    field_test_env.add_model(model_name, mock_task_model)
    field_test_env.add_model("project.project", mock_project_model)
    field_test_env.add_model("res.partner", mock_partner_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["type"] == "char"
    assert len(result["direct_dependencies"]) == 1
    assert result["direct_dependencies"][0] == "project_id.partner_id.email"
    assert len(result["dependency_chain"]) >= 1


@pytest.mark.asyncio
async def test_field_dependencies_with_circular_reference(field_test_env: MockEnv) -> None:
    model_name = "test.model"
    field_name = "field_a"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() with circular dependency
    mock_model.fields_get.return_value = {
        "field_a": {
            "type": "float",
            "string": "Field A",
            "compute": "_compute_a",
            "depends": ["field_b"],
        },
        "field_b": {
            "type": "float",
            "string": "Field B",
            "compute": "_compute_b",
            "depends": ["field_a"],  # Circular!
        },
    }

    # Mock _fields
    mock_field_a = Mock()
    mock_field_a.type = "float"
    mock_field_a.compute = "_compute_a"
    mock_field_a.related = None

    mock_field_b = Mock()
    mock_field_b.type = "float"
    mock_field_b.compute = "_compute_b"
    mock_field_b.related = None

    compute_a = MagicMock()
    compute_a._depends = ["field_b"]
    mock_model._compute_a = compute_a

    compute_b = MagicMock()
    compute_b._depends = ["field_a"]
    mock_model._compute_b = compute_b

    mock_model._fields = {
        "field_a": mock_field_a,
        "field_b": mock_field_b,
    }

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    # Should handle circular dependency gracefully
    assert "error" not in result
    assert result["field"] == field_name
    assert result["type"] == "float"
    assert "field_b" in result["direct_dependencies"]


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_field_dependencies_without_fields_attribute(field_test_env: MockEnv) -> None:
    model_name = "product.template"
    field_name = "name"

    # Mock model without _fields attribute (only fields_get)
    mock_model = MagicMock()
    mock_model._name = model_name

    # Remove _fields attribute
    if hasattr(mock_model, "_fields"):
        delattr(mock_model, "_fields")

    # Mock fields_get() to return field info
    mock_model.fields_get.return_value = {
        "name": {
            "type": "char",
            "string": "Name",
            "required": True,
        },
        "display_name": {
            "type": "char",
            "string": "Display Name",
            "related": "name",  # Related field info from fields_get
        },
    }

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["model"] == model_name
    assert result["field"] == field_name
    assert result["type"] == "char"
    # Should still work with limited functionality
    assert result["direct_dependencies"] == []


@pytest.mark.asyncio
async def test_field_dependencies_multiple_dependent_fields(field_test_env: MockEnv) -> None:
    model_name = "product.product"
    field_name = "standard_price"

    mock_model = MagicMock()
    mock_model._name = model_name

    mock_model.fields_get.return_value = {
        "standard_price": {
            "type": "float",
            "string": "Cost",
            "digits": [16, 2],
        },
        "margin": {
            "type": "float",
            "string": "Margin",
            "compute": "_compute_margin",
            "depends": ["list_price", "standard_price"],
        },
        "profit_percentage": {
            "type": "float",
            "string": "Profit %",
            "compute": "_compute_profit",
            "depends": ["standard_price", "list_price"],
        },
        "list_price": {
            "type": "float",
            "string": "Sales Price",
        },
    }

    # Mock _fields
    mock_standard_field = Mock()
    mock_standard_field.type = "float"
    mock_standard_field.compute = None
    mock_standard_field.related = None

    mock_margin_field = Mock()
    mock_margin_field.type = "float"
    mock_margin_field.compute = "_compute_margin"

    mock_profit_field = Mock()
    mock_profit_field.type = "float"
    mock_profit_field.compute = "_compute_profit"

    compute_margin = MagicMock()
    compute_margin._depends = ["list_price", "standard_price"]
    mock_model._compute_margin = compute_margin

    compute_profit = MagicMock()
    compute_profit._depends = ["standard_price", "list_price"]
    mock_model._compute_profit = compute_profit

    mock_model._fields = {
        "standard_price": mock_standard_field,
        "margin": mock_margin_field,
        "profit_percentage": mock_profit_field,
        "list_price": Mock(type="float", compute=None, related=None),
    }

    field_test_env.add_model(model_name, mock_model)

    result = await get_field_dependencies(field_test_env, model_name, field_name)

    assert "error" not in result
    assert len(result["dependent_fields"]) == 2
    dependent_field_names = [dep["field"] for dep in result["dependent_fields"]]
    assert "margin" in dependent_field_names
    assert "profit_percentage" in dependent_field_names
