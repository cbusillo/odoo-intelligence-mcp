from unittest.mock import MagicMock, Mock

import pytest

from odoo_intelligence_mcp.tools.field.field_value_analyzer import analyze_field_values


@pytest.fixture
def field_test_env():
    """Custom env fixture that properly handles model access and containment checks."""

    class MockEnv:
        def __init__(self) -> None:
            self.models = {}

        def __contains__(self, model_name: str) -> bool:
            return model_name in self.models

        def __getitem__(self, model_name: str) -> MagicMock:
            if model_name not in self.models:
                raise KeyError(f"Model {model_name} not found")
            return self.models[model_name]

        def add_model(self, model_name: str, model: MagicMock) -> None:
            self.models[model_name] = model

    return MockEnv()


@pytest.mark.asyncio
async def test_field_value_analyzer_finds_standard_fields(field_test_env) -> None:
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
            "searchable": True,
        },
        "create_date": {
            "type": "datetime",
            "string": "Created on",
            "readonly": True,
            "store": True,
        },
    }

    # Mock search and search_count
    mock_records = []
    for i in range(5):
        record = Mock()
        record.name = f"Product {i}"
        record.display_name = f"Product {i}"
        record.create_date = f"2024-01-{i + 1:02d} 10:00:00"
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = 5

    # Set up environment
    field_test_env.add_model(model_name, mock_model)

    # Test standard char field
    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["model"] == model_name
    assert result["field"] == field_name
    assert result["field_info"]["type"] == "char"
    assert result["field_info"]["required"] is True
    assert result["field_info"]["store"] is True
    assert "sample_statistics" in result
    assert result["sample_statistics"]["sample_size"] == 5
    assert result["sample_statistics"]["non_empty_count"] == 5


@pytest.mark.asyncio
async def test_field_value_analyzer_finds_inherited_fields(field_test_env) -> None:
    model_name = "product.template"
    field_name = "create_date"

    # Mock the model
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
        "create_uid": {
            "type": "many2one",
            "string": "Created by",
            "relation": "res.users",
            "readonly": True,
        },
    }

    # Mock search results
    mock_records = []
    for i in range(3):
        record = Mock()
        record.create_date = f"2024-01-{i + 1:02d} 10:00:00"
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = 3

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field"] == field_name
    assert result["field_info"]["type"] == "datetime"
    assert result["field_info"]["readonly"] is True
    assert result["sample_statistics"]["sample_size"] == 3


@pytest.mark.asyncio
async def test_field_value_analyzer_with_computed_fields(field_test_env) -> None:
    model_name = "sale.order"
    field_name = "amount_total"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() with computed field info
    mock_model.fields_get.return_value = {
        "amount_total": {
            "type": "monetary",
            "string": "Total",
            "compute": "_compute_amounts",
            "store": True,
            "currency_field": "currency_id",
            "depends": ["order_line.price_total"],
        },
        "currency_id": {
            "type": "many2one",
            "string": "Currency",
            "relation": "res.currency",
        },
    }

    # Mock records with monetary values
    mock_records = []
    for i in range(5):
        record = Mock()
        record.amount_total = 100.0 * (i + 1)
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = 5

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field_info"]["type"] == "monetary"
    assert result["field_info"]["compute"] is True
    assert result["field_info"]["store"] is True
    assert "numeric_analysis" in result
    assert result["numeric_analysis"]["min_value"] == 100.0
    assert result["numeric_analysis"]["max_value"] == 500.0


@pytest.mark.asyncio
async def test_field_value_analyzer_with_selection_field(field_test_env) -> None:
    model_name = "sale.order"
    field_name = "state"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() with selection field
    mock_model.fields_get.return_value = {
        "state": {
            "type": "selection",
            "string": "Status",
            "selection": [
                ["draft", "Quotation"],
                ["sent", "Quotation Sent"],
                ["sale", "Sales Order"],
                ["done", "Locked"],
                ["cancel", "Cancelled"],
            ],
            "default": "draft",
            "required": True,
        }
    }

    # Mock records with various states
    mock_records = []
    states = ["draft", "draft", "sale", "done", "sale", "cancel"]
    for state in states:
        record = Mock()
        record.state = state
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = len(mock_records)

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field_info"]["type"] == "selection"
    assert "selection_analysis" in result
    assert "available_options" in result["selection_analysis"]
    assert len(result["selection_analysis"]["available_options"]) == 5
    assert "value_distribution" in result["selection_analysis"]


@pytest.mark.asyncio
async def test_field_value_analyzer_with_many2one_field(field_test_env) -> None:
    model_name = "sale.order"
    field_name = "partner_id"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Mock fields_get() with relational field
    mock_model.fields_get.return_value = {
        "partner_id": {
            "type": "many2one",
            "string": "Customer",
            "relation": "res.partner",
            "required": True,
            "domain": [],
            "context": {},
        }
    }

    # Mock records with partner references
    mock_records = []
    for i in range(4):
        record = Mock()
        partner = Mock()
        partner.id = i + 1
        partner.display_name = f"Partner {i + 1}"
        record.partner_id = partner
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = 4

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field_info"]["type"] == "many2one"
    assert "relational_analysis" in result
    assert result["relational_analysis"]["target_model"] == "res.partner"
    assert result["relational_analysis"]["relationship_type"] == "many2one"


@pytest.mark.asyncio
async def test_field_value_analyzer_handles_missing_field_gracefully(field_test_env) -> None:
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

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert field_name in result["error"]


@pytest.mark.asyncio
async def test_field_value_analyzer_with_empty_records(field_test_env) -> None:
    model_name = "product.template"
    field_name = "name"

    mock_model = MagicMock()
    mock_model._name = model_name

    mock_model.fields_get.return_value = {"name": {"type": "char", "string": "Name", "required": True}}

    # No records found
    mock_model.search.return_value = []
    mock_model.search_count.return_value = 0

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["sample_size"] == 0
    assert result["message"] == "No records found matching the domain"
    assert result["field_type"] == "char"
    assert result["total_records"] == 0


@pytest.mark.asyncio
async def test_field_value_analyzer_with_domain_filter(field_test_env) -> None:
    model_name = "res.partner"
    field_name = "name"
    domain = [["is_company", "=", True]]

    mock_model = MagicMock()
    mock_model._name = model_name

    mock_model.fields_get.return_value = {
        "name": {"type": "char", "string": "Name"},
        "is_company": {"type": "boolean", "string": "Is a Company"},
    }

    # Mock filtered records
    mock_records = []
    for i in range(2):
        record = Mock()
        record.name = f"Company {i}"
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = 2

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name, domain=domain)

    assert "error" not in result
    assert result["domain_applied"] == domain
    assert result["sample_statistics"]["sample_size"] == 2


@pytest.mark.asyncio
async def test_field_value_analyzer_data_quality_analysis(field_test_env) -> None:
    model_name = "res.partner"
    field_name = "email"

    mock_model = MagicMock()
    mock_model._name = model_name

    mock_model.fields_get.return_value = {"email": {"type": "char", "string": "Email", "required": False}}

    # Mock records with mixed data quality
    mock_records = []

    # Good emails
    for i in range(3):
        record = Mock()
        record.email = f"user{i}@example.com"
        mock_records.append(record)

    # Null/empty values
    for _ in range(2):
        record = Mock()
        record.email = None
        mock_records.append(record)

    # Empty string
    record = Mock()
    record.email = ""
    mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = len(mock_records)

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert "data_quality" in result
    assert result["sample_statistics"]["null_count"] == 2
    assert result["sample_statistics"]["empty_string_count"] == 1
    assert result["sample_statistics"]["non_empty_count"] == 3
    assert result["sample_statistics"]["data_completeness_percentage"] == 50.0


@pytest.mark.asyncio
async def test_field_value_analyzer_handles_all_field_info_from_fields_get(field_test_env) -> None:
    model_name = "product.template"
    field_name = "list_price"

    mock_model = MagicMock()
    mock_model._name = model_name

    # Complete field info from fields_get()
    mock_model.fields_get.return_value = {
        "list_price": {
            "type": "float",
            "string": "Sales Price",
            "required": False,
            "readonly": False,
            "store": True,
            "help": "Base price to compute the customer price",
            "digits": [16, 2],
            "groups": "base.group_user",
        }
    }

    # Mock records
    mock_records = []
    for i in range(5):
        record = Mock()
        record.list_price = 10.0 + (i * 5.0)
        mock_records.append(record)

    mock_model.search.return_value = mock_records
    mock_model.search_count.return_value = 5

    field_test_env.add_model(model_name, mock_model)

    result = await analyze_field_values(field_test_env, model_name, field_name)

    assert "error" not in result
    assert result["field_info"]["type"] == "float"
    assert result["field_info"]["string"] == "Sales Price"
    assert result["field_info"]["required"] is False
    assert result["field_info"]["readonly"] is False
    assert result["field_info"]["store"] is True
    assert "numeric_analysis" in result
    assert result["numeric_analysis"]["min_value"] == 10.0
    assert result["numeric_analysis"]["max_value"] == 30.0
