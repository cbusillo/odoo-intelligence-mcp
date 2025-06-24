from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestFieldTypeSearcherFix:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        env = MagicMock()
        return env

    @pytest.fixture
    def mock_model_files(self, tmp_path: Path) -> dict[str, Path]:
        # Create test model files with various field types
        sale_order = tmp_path / "sale_order.py"
        sale_order.write_text("""
from odoo import models, fields, api

class SaleOrder(models.Model):
    _name = 'sale.order'
    
    # Many2one fields
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, tracking=2)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True)
    
    # Char fields
    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True)
    client_order_ref = fields.Char(string='Customer Reference', copy=False)
    origin = fields.Char(string='Source Document')
    
    # Text field
    note = fields.Text('Terms and conditions')
    
    # Date/Datetime fields
    date_order = fields.Datetime(string='Order Date', required=True, index=True)
    validity_date = fields.Date(string='Expiration', readonly=True)
    
    # Float/Monetary fields
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, compute='_compute_amounts')
    amount_tax = fields.Monetary(string='Taxes', store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string='Total', store=True, compute='_compute_amounts')
    
    # Integer field
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    
    # Boolean field
    require_signature = fields.Boolean('Online signature')
    require_payment = fields.Boolean('Online payment')
    
    # Selection field
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')
    
    # One2many field
    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines', copy=True)
    
    # Binary field
    signature = fields.Binary('Signature')
""")

        product_template = tmp_path / "product_template.py"
        product_template.write_text("""
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _name = 'product.template'
    
    # Basic fields
    name = fields.Char('Name', index=True, required=True, translate=True)
    sequence = fields.Integer('Sequence', default=1)
    description = fields.Text('Description', translate=True)
    description_purchase = fields.Text('Purchase Description', translate=True)
    description_sale = fields.Text('Sales Description', translate=True)
    
    # Selection field
    type = fields.Selection([
        ('consu', 'Consumable'),
        ('service', 'Service'),
        ('product', 'Storable Product')
    ], string='Product Type', default='consu', required=True)
    
    # Many2one fields
    categ_id = fields.Many2one('product.category', 'Product Category', required=True)
    uom_id = fields.Many2one('uom.uom', 'Unit of Measure', required=True)
    uom_po_id = fields.Many2one('uom.uom', 'Purchase Unit of Measure', required=True)
    
    # Float fields
    list_price = fields.Float('Sales Price', default=1.0, digits='Product Price')
    standard_price = fields.Float('Cost', company_dependent=True, digits='Product Price')
    volume = fields.Float('Volume')
    weight = fields.Float('Weight', digits='Stock Weight')
    
    # Boolean fields
    active = fields.Boolean('Active', default=True)
    sale_ok = fields.Boolean('Can be Sold', default=True)
    purchase_ok = fields.Boolean('Can be Purchased', default=True)
    
    # Binary field
    image_1920 = fields.Binary("Image")
    
    # One2many field
    product_variant_ids = fields.One2many('product.product', 'product_tmpl_id', 'Products', required=True)
    
    # Many2many field
    route_ids = fields.Many2many('stock.route', 'stock_route_product', 'product_id', 'route_id', 'Routes')
""")

        res_partner = tmp_path / "res_partner.py"
        res_partner.write_text("""
from odoo import models, fields, api

class ResPartner(models.Model):
    _name = 'res.partner'
    
    # Char fields
    name = fields.Char(index=True, required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    ref = fields.Char(string='Reference', index=True)
    vat = fields.Char(string='Tax ID')
    website = fields.Char('Website Link')
    
    # Text fields
    comment = fields.Text(string='Notes')
    
    # Many2one fields
    parent_id = fields.Many2one('res.partner', string='Related Company', index=True)
    user_id = fields.Many2one('res.users', string='Salesperson')
    country_id = fields.Many2one('res.country', string='Country')
    state_id = fields.Many2one('res.country.state', string='State')
    
    # Date fields
    date = fields.Date(index=True)
    
    # Boolean fields
    is_company = fields.Boolean(string='Is a Company', default=False)
    active = fields.Boolean(default=True)
    customer_rank = fields.Integer(string='Customer Rank', default=0)
    supplier_rank = fields.Integer(string='Vendor Rank', default=0)
    
    # Selection field
    company_type = fields.Selection([('person', 'Individual'), ('company', 'Company')])
    
    # One2many fields
    child_ids = fields.One2many('res.partner', 'parent_id', string='Contact')
    bank_ids = fields.One2many('res.partner.bank', 'partner_id', string='Banks')
    
    # Many2many field
    category_id = fields.Many2many('res.partner.category', column1='partner_id', 
                                   column2='category_id', string='Tags')
    
    # Binary field
    image_1920 = fields.Binary("Image", max_width=1920, max_height=1920)
    
    # Json field
    partner_gid = fields.Json('Company database ID', readonly=True)
""")

        # Create a model to test less common field types
        test_model = tmp_path / "test_model.py"
        test_model.write_text("""
from odoo import models, fields

class TestModel(models.Model):
    _name = 'test.model'
    
    # Html field
    html_content = fields.Html('HTML Content', sanitize=True)
    
    # Monetary field
    amount = fields.Monetary('Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency')
    
    # Reference field
    reference = fields.Reference([
        ('res.partner', 'Partner'),
        ('res.users', 'User')
    ], string='Reference')
    
    # Json field
    json_data = fields.Json('JSON Data')
    
    # Properties field (new in recent versions)
    properties = fields.Properties('Properties')
""")

        return {"sale.order": sale_order, "product.template": product_template, "res.partner": res_partner, "test.model": test_model}

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_many2one_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("many2one")

        assert result is not None
        assert len(result["results"]) > 0

        # Extract field names by model
        many2one_fields = {}
        for r in result["results"]:
            if r["model"] not in many2one_fields:
                many2one_fields[r["model"]] = []
            many2one_fields[r["model"]].append(r["field_name"])

        # Check sale.order many2one fields
        assert "sale.order" in many2one_fields
        assert "partner_id" in many2one_fields["sale.order"]
        assert "user_id" in many2one_fields["sale.order"]
        assert "company_id" in many2one_fields["sale.order"]
        assert "pricelist_id" in many2one_fields["sale.order"]

        # Check product.template many2one fields
        assert "product.template" in many2one_fields
        assert "categ_id" in many2one_fields["product.template"]
        assert "uom_id" in many2one_fields["product.template"]

        # Check res.partner many2one fields
        assert "res.partner" in many2one_fields
        assert "parent_id" in many2one_fields["res.partner"]
        assert "country_id" in many2one_fields["res.partner"]

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_char_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("char")

        assert len(result["results"]) > 0

        char_fields = [(r["model"], r["field_name"]) for r in result["results"]]

        # Check char fields
        assert ("sale.order", "name") in char_fields
        assert ("sale.order", "client_order_ref") in char_fields
        assert ("product.template", "name") in char_fields
        assert ("res.partner", "name") in char_fields
        assert ("res.partner", "vat") in char_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_boolean_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("boolean")

        assert len(result["results"]) > 0

        boolean_fields = [(r["model"], r["field_name"]) for r in result["results"]]

        assert ("sale.order", "require_signature") in boolean_fields
        assert ("sale.order", "require_payment") in boolean_fields
        assert ("product.template", "active") in boolean_fields
        assert ("product.template", "sale_ok") in boolean_fields
        assert ("res.partner", "is_company") in boolean_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_date_and_datetime_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Test date fields
        result = searcher.search("date")
        date_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("sale.order", "validity_date") in date_fields
        assert ("res.partner", "date") in date_fields

        # Test datetime fields
        result = searcher.search("datetime")
        datetime_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("sale.order", "date_order") in datetime_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_selection_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("selection")

        assert len(result["results"]) > 0

        selection_fields = [(r["model"], r["field_name"]) for r in result["results"]]

        assert ("sale.order", "state") in selection_fields
        assert ("product.template", "type") in selection_fields
        assert ("res.partner", "company_type") in selection_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_relational_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Test one2many
        result = searcher.search("one2many")
        one2many_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("sale.order", "order_line") in one2many_fields
        assert ("product.template", "product_variant_ids") in one2many_fields
        assert ("res.partner", "child_ids") in one2many_fields

        # Test many2many
        result = searcher.search("many2many")
        many2many_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("product.template", "route_ids") in many2many_fields
        assert ("res.partner", "category_id") in many2many_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_numeric_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Test integer fields
        result = searcher.search("integer")
        integer_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("sale.order", "invoice_count") in integer_fields
        assert ("product.template", "sequence") in integer_fields
        assert ("res.partner", "customer_rank") in integer_fields

        # Test float fields
        result = searcher.search("float")
        float_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("product.template", "list_price") in float_fields
        assert ("product.template", "volume") in float_fields
        assert ("product.template", "weight") in float_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_binary_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("binary")

        assert len(result["results"]) > 0

        binary_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("sale.order", "signature") in binary_fields
        assert ("product.template", "image_1920") in binary_fields
        assert ("res.partner", "image_1920") in binary_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_text_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("text")

        assert len(result["results"]) > 0

        text_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("sale.order", "note") in text_fields
        assert ("product.template", "description") in text_fields
        assert ("res.partner", "comment") in text_fields

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_find_json_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("json")

        assert len(result["results"]) > 0

        json_fields = [(r["model"], r["field_name"]) for r in result["results"]]
        assert ("res.partner", "partner_gid") in json_fields
        assert ("test.model", "json_data") in json_fields

    def test_should_validate_field_type(self, searcher: Mock) -> None:
        # Valid field types
        valid_types = [
            "many2one",
            "one2many",
            "many2many",
            "char",
            "text",
            "integer",
            "float",
            "boolean",
            "date",
            "datetime",
            "binary",
            "selection",
            "json",
        ]

        for field_type in valid_types:
            result = searcher.search(field_type)  # Should not raise
            assert result is not None

        # Invalid field type
        with pytest.raises(ValueError) as exc_info:
            searcher.search("invalid_type")
        assert "Invalid field type" in str(exc_info.value)

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    def test_should_handle_no_files_found(self, mock_glob: Mock, searcher: Mock) -> None:
        mock_glob.glob.return_value = []

        result = searcher.search("char")

        assert result is not None
        assert result["results"] == []
        assert result["total_count"] == 0

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_extract_field_attributes(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = [mock_model_files["sale.order"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order"].read_text()

        result = searcher.search("many2one")

        # Find partner_id field
        partner_field = next((r for r in result["results"] if r["field_name"] == "partner_id"), None)
        assert partner_field is not None

        # Check attributes
        assert partner_field["relation"] == "res.partner"
        assert "string" in partner_field["attributes"]
        assert partner_field["attributes"]["string"] == "Customer"
        assert partner_field["attributes"].get("required") is True

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_handle_monetary_fields(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Monetary fields are typically stored as float but have special handling
        result = searcher.search("float")

        # Should find monetary fields as floats
        field_names = [r["field_name"] for r in result["results"] if r["model"] == "sale.order"]
        assert "amount_untaxed" in field_names
        assert "amount_tax" in field_names
        assert "amount_total" in field_names

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_paginate_results(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Get first page
        result_page1 = searcher.search("many2one", limit=5, offset=0)
        assert len(result_page1["results"]) <= 5

        # Get second page
        result_page2 = searcher.search("many2one", limit=5, offset=5)

        # Ensure no overlap between pages
        page1_fields = [(r["model"], r["field_name"]) for r in result_page1["results"]]
        page2_fields = [(r["model"], r["field_name"]) for r in result_page2["results"]]
        assert not set(page1_fields).intersection(set(page2_fields))

    @patch("odoo_intelligence_mcp.tools.field.search_field_type.glob")
    @patch("odoo_intelligence_mcp.tools.field.search_field_type.Path")
    def test_should_handle_special_field_types(self, mock_path: Mock, mock_glob: Mock, searcher: Mock, tmp_path: Path) -> None:
        # Create model with special field types
        special_model = tmp_path / "special_model.py"
        special_model.write_text("""
from odoo import models, fields

class SpecialModel(models.Model):
    _name = 'special.model'
    
    # Html field (stored as text in DB but has special widget)
    html_field = fields.Html('Rich Text Content')
    
    # Reference field
    reference_field = fields.Reference([
        ('res.partner', 'Partner'),
        ('res.users', 'User'),
    ], string='Document Reference')
    
    # Monetary field (technically float but with currency handling)
    price = fields.Monetary('Price', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Currency')
    
    # Properties field (new JSON-based dynamic fields)
    properties = fields.Properties('Dynamic Properties')
""")

        mock_glob.glob.return_value = [special_model]
        mock_path.return_value.read_text.return_value = special_model.read_text()

        # HTML fields should be detected as text
        result = searcher.search("text")
        html_fields = [r["field_name"] for r in result["results"] if "html" in r["field_name"].lower()]
        assert "html_field" in html_fields
