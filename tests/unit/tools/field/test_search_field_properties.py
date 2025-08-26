from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, MockRegistry
from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.field.search_field_properties import search_field_properties
from tests.mock_types import ConcreteModelMock as MockModel


class TestSearchFieldPropertiesRegistryIssue:
    """Test search_field_properties tool with focus on registry iteration issue."""

    @pytest.fixture
    def mock_env_with_registry(self) -> HostOdooEnvironment:
        """Create a mock environment with a properly configured registry."""
        env = HostOdooEnvironment("test-container", "test-db", "/test/path")

        # Set up registry with test models
        env._registry = MockRegistry()
        env._registry._models = {
            "sale.order": MockModel,
            "sale.order.line": MockModel,
            "product.template": MockModel,
            "res.partner": MockModel,
            "account.move": MockModel,
            "account.move.line": MockModel,
        }

        return env

    @pytest.mark.asyncio
    async def test_search_computed_fields_with_iterable_registry(self, mock_env_with_registry) -> None:
        """Test that search_field_properties works for computed fields when registry is properly iterable."""
        env = mock_env_with_registry
        property_type = "computed"

        # Mock execute_code to return models with fields
        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Set up models with computed and non-computed fields
            sale_order_fields = {
                "name": MagicMock(type="char", compute=None, string="Order Reference"),
                "amount_total": MagicMock(type="float", compute="_compute_amounts", store=True, string="Total"),
                "amount_untaxed": MagicMock(type="float", compute="_compute_amounts", store=True, string="Untaxed Amount"),
                "partner_id": MagicMock(type="many2one", compute=None, string="Customer"),
            }

            sale_line_fields = {
                "price_subtotal": MagicMock(type="float", compute="_compute_amount", store=True, string="Subtotal"),
                "price_tax": MagicMock(type="float", compute="_compute_amount", store=True, string="Tax"),
                "price_total": MagicMock(type="float", compute="_compute_amount", store=True, string="Total"),
                "product_id": MagicMock(type="many2one", compute=None, string="Product"),
            }

            product_fields = {
                "display_name": MagicMock(type="char", compute="_compute_display_name", store=False, string="Display Name"),
                "lst_price": MagicMock(type="float", compute="_compute_lst_price", string="Public Price"),
                "name": MagicMock(type="char", compute=None, string="Product Name"),
            }

            partner_fields = {
                "display_name": MagicMock(type="char", compute="_compute_display_name", store=False, string="Display Name"),
                "email": MagicMock(type="char", compute=None, string="Email"),
            }

            account_move_fields = {
                "amount_total": MagicMock(type="float", compute="_compute_amount", store=True, string="Total"),
                "state": MagicMock(type="selection", compute=None, string="Status"),
            }

            account_line_fields = {
                "balance": MagicMock(type="float", compute="_compute_balance", store=True, string="Balance"),
                "debit": MagicMock(type="float", compute=None, string="Debit"),
            }

            mock_models = [
                MagicMock(_name="sale.order", _fields=sale_order_fields),
                MagicMock(_name="sale.order.line", _fields=sale_line_fields),
                MagicMock(_name="product.template", _fields=product_fields),
                MagicMock(_name="res.partner", _fields=partner_fields),
                MagicMock(_name="account.move", _fields=account_move_fields),
                MagicMock(_name="account.move.line", _fields=account_line_fields),
            ]

            mock_exec.side_effect = mock_models

            # Call search_field_properties
            result = await search_field_properties(env, property_type, PaginationParams())

            # Should successfully complete without TypeError
            assert "error" not in result
            assert result["property"] == property_type

            # Count computed fields found
            computed_count = len(result["fields"])
            assert computed_count == 10  # Total computed fields across all models

            # Verify some specific computed fields
            field_tuples = [(f["model_name"], f["field_name"]) for f in result["fields"]]
            assert ("sale.order", "amount_total") in field_tuples
            assert ("sale.order.line", "price_subtotal") in field_tuples
            assert ("product.template", "display_name") in field_tuples
            assert ("res.partner", "display_name") in field_tuples

            # Check compute method names are captured
            sale_total = next(f for f in result["fields"] if f["model_name"] == "sale.order" and f["field_name"] == "amount_total")
            assert sale_total["field_info"]["compute"] == "_compute_amounts"

    @pytest.mark.asyncio
    async def test_search_related_fields_with_iterable_registry(self, mock_env_with_registry) -> None:
        """Test searching for related fields."""
        env = mock_env_with_registry
        property_type = "related"

        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Models with related fields
            sale_order_fields = {
                "partner_shipping_id": MagicMock(type="many2one", related="partner_id.child_ids", string="Delivery Address"),
                "user_id": MagicMock(type="many2one", related=None, string="Salesperson"),
                "currency_id": MagicMock(type="many2one", related="company_id.currency_id", string="Currency"),
            }

            sale_line_fields = {
                "order_partner_id": MagicMock(type="many2one", related="order_id.partner_id", string="Customer"),
                "currency_id": MagicMock(type="many2one", related="order_id.currency_id", string="Currency"),
                "name": MagicMock(type="char", related=None, string="Description"),
            }

            product_fields = {
                "categ_name": MagicMock(type="char", related="categ_id.name", string="Category Name"),
                "company_id": MagicMock(type="many2one", related="product_tmpl_id.company_id", string="Company"),
            }

            mock_models = [
                MagicMock(_name="sale.order", _fields=sale_order_fields),
                MagicMock(_name="sale.order.line", _fields=sale_line_fields),
                MagicMock(_name="product.template", _fields=product_fields),
                MagicMock(_name="res.partner", _fields={}),
                MagicMock(_name="account.move", _fields={}),
                MagicMock(_name="account.move.line", _fields={}),
            ]

            mock_exec.side_effect = mock_models

            result = await search_field_properties(env, property_type, PaginationParams())

            assert "error" not in result
            assert len(result["fields"]) == 6  # Total related fields

            # Check related paths
            partner_shipping = next(
                f for f in result["fields"] if f["model_name"] == "sale.order" and f["field_name"] == "partner_shipping_id"
            )
            assert partner_shipping["field_info"]["related"] == "partner_id.child_ids"

            order_partner = next(
                f for f in result["fields"] if f["model_name"] == "sale.order.line" and f["field_name"] == "order_partner_id"
            )
            assert order_partner["field_info"]["related"] == "order_id.partner_id"

    @pytest.mark.asyncio
    async def test_search_stored_fields_with_iterable_registry(self, mock_env_with_registry) -> None:
        """Test searching for stored fields."""
        env = mock_env_with_registry
        property_type = "stored"

        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Mix of stored and non-stored fields
            sale_fields = {
                "name": MagicMock(type="char", store=True, string="Reference"),
                "amount_total": MagicMock(type="float", compute="_compute_amounts", store=True, string="Total"),
                "amount_display": MagicMock(type="char", compute="_compute_display", store=False, string="Display"),
                "partner_id": MagicMock(type="many2one", store=True, string="Customer"),
            }

            product_fields = {
                "name": MagicMock(type="char", store=True, string="Name"),
                "list_price": MagicMock(type="float", store=True, string="Price"),
                "display_name": MagicMock(type="char", compute="_compute_display_name", store=False, string="Display"),
            }

            mock_models = [
                MagicMock(_name="sale.order", _fields=sale_fields),
                MagicMock(_name="product.template", _fields=product_fields),
                MagicMock(_name="sale.order.line", _fields={}),
                MagicMock(_name="res.partner", _fields={}),
                MagicMock(_name="account.move", _fields={}),
                MagicMock(_name="account.move.line", _fields={}),
            ]

            mock_exec.side_effect = mock_models

            result = await search_field_properties(env, property_type, PaginationParams())

            assert "error" not in result
            # Should find all stored fields (including computed stored fields)
            assert len(result["fields"]) == 5  # name, amount_total, partner_id from sale + name, list_price from product

            # Verify no non-stored fields are included
            field_names = [f["field_name"] for f in result["fields"]]
            assert "amount_display" not in field_names
            assert "display_name" not in field_names

    @pytest.mark.asyncio
    async def test_search_required_fields_with_iterable_registry(self, mock_env_with_registry) -> None:
        """Test searching for required fields."""
        env = mock_env_with_registry
        property_type = "required"

        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Models with required and optional fields
            partner_fields = {
                "name": MagicMock(type="char", required=True, string="Name"),
                "email": MagicMock(type="char", required=False, string="Email"),
                "is_company": MagicMock(type="boolean", required=True, string="Is a Company"),
            }

            product_fields = {
                "name": MagicMock(type="char", required=True, string="Product Name"),
                "type": MagicMock(type="selection", required=True, string="Product Type"),
                "list_price": MagicMock(type="float", required=False, string="Price"),
            }

            sale_fields = {
                "partner_id": MagicMock(type="many2one", required=True, string="Customer"),
                "date_order": MagicMock(type="datetime", required=True, string="Order Date"),
                "note": MagicMock(type="text", required=False, string="Note"),
            }

            mock_models = [
                MagicMock(_name="res.partner", _fields=partner_fields),
                MagicMock(_name="product.template", _fields=product_fields),
                MagicMock(_name="sale.order", _fields=sale_fields),
                MagicMock(_name="sale.order.line", _fields={}),
                MagicMock(_name="account.move", _fields={}),
                MagicMock(_name="account.move.line", _fields={}),
            ]

            mock_exec.side_effect = mock_models

            result = await search_field_properties(env, property_type, PaginationParams())

            assert "error" not in result
            assert len(result["fields"]) == 6  # All required fields

            # Verify field types diversity
            field_types = {f["field_info"]["type"] for f in result["fields"]}
            assert "char" in field_types
            assert "boolean" in field_types
            assert "selection" in field_types
            assert "many2one" in field_types
            assert "datetime" in field_types

    @pytest.mark.asyncio
    async def test_search_readonly_fields_with_iterable_registry(self, mock_env_with_registry) -> None:
        """Test searching for readonly fields."""
        env = mock_env_with_registry
        property_type = "readonly"

        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Models with readonly fields
            account_move_fields = {
                "name": MagicMock(type="char", readonly=True, string="Number"),
                "state": MagicMock(type="selection", readonly=False, string="Status"),
                "posted_before": MagicMock(type="boolean", readonly=True, string="Posted Before"),
            }

            sale_order_fields = {
                "name": MagicMock(type="char", readonly=True, string="Order Reference"),
                "create_date": MagicMock(type="datetime", readonly=True, string="Creation Date"),
                "partner_id": MagicMock(type="many2one", readonly=False, string="Customer"),
            }

            mock_models = [
                MagicMock(_name="account.move", _fields=account_move_fields),
                MagicMock(_name="sale.order", _fields=sale_order_fields),
                MagicMock(_name="sale.order.line", _fields={}),
                MagicMock(_name="product.template", _fields={}),
                MagicMock(_name="res.partner", _fields={}),
                MagicMock(_name="account.move.line", _fields={}),
            ]

            mock_exec.side_effect = mock_models

            result = await search_field_properties(env, property_type, PaginationParams())

            assert "error" not in result
            assert len(result["fields"]) == 4  # All readonly fields

            # Check field names
            readonly_fields = [(f["model_name"], f["field_name"]) for f in result["fields"]]
            assert ("account.move", "name") in readonly_fields
            assert ("account.move", "posted_before") in readonly_fields
            assert ("sale.order", "name") in readonly_fields
            assert ("sale.order", "create_date") in readonly_fields

    def test_registry_dict_interface(self) -> None:
        """Test that registry supports dict-like interface while being iterable."""
        registry = MockRegistry()
        registry._models = {  # type: ignore[assignment]
            "res.users": MagicMock(_name="res.users"),
            "res.groups": MagicMock(_name="res.groups"),
            "ir.model": MagicMock(_name="ir.model"),
        }

        # Test iteration yields keys
        keys = list(registry)
        assert keys == ["res.users", "res.groups", "ir.model"]

        # Test dict-like access still works
        assert registry["res.users"]._name == "res.users"
        assert "res.users" in registry
        assert "non.existent" not in registry
        assert len(registry) == 3

    @pytest.mark.asyncio
    async def test_search_properties_with_pagination_and_filter(self, mock_env_with_registry) -> None:
        """Test search with both pagination and text filter."""
        env = mock_env_with_registry
        property_type = "computed"

        # Add more models to test pagination
        if hasattr(env._registry, "_models"):
            for i in range(10):
                env._registry._models[f"test.model.{i}"] = MockModel

        with patch.object(env, "execute_code", new_callable=AsyncMock) as mock_exec:
            # Create models with computed fields, some matching filter
            mock_models = []
            for i in range(16):  # 6 original + 10 new models
                if i < 6:
                    # Original models with some amount fields
                    fields = {
                        "amount_total": MagicMock(type="float", compute="_compute_amount", string="Total Amount"),
                        "other_field": MagicMock(type="char", compute="_compute_other", string="Other"),
                    }
                else:
                    # Test models without amount fields
                    fields = {"computed_field": MagicMock(type="char", compute="_compute_field", string="Computed Field")}
                mock_models.append(MagicMock(_fields=fields))

            mock_exec.side_effect = mock_models

            # Search with filter for "amount"
            pagination = PaginationParams(page_size=5, filter_text="amount")
            result = await search_field_properties(env, property_type, pagination)

            assert "error" not in result
            # Should only find fields with "amount" in name or string
            assert all(
                "amount" in f["field_name"].lower() or "amount" in f["field_info"]["string"].lower() for f in result["fields"]
            )
            assert len(result["fields"]) <= 5  # Limited by page_size
