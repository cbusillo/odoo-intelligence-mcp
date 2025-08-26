from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from odoo_intelligence_mcp.tools.field.resolve_dynamic_fields import resolve_dynamic_fields


class TestDynamicFieldResolverFix:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_model_files(self, tmp_path) -> dict[str, Path]:
        # Create test model files with computed and related fields
        sale_order_line = tmp_path / "sale_order_line.py"
        sale_order_line.write_text('''
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)

    # Computed fields
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Total Tax', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)

    # Related fields
    order_partner_id = fields.Many2one(related='order_id.partner_id', store=True, string='Customer')
    currency_id = fields.Many2one(related='order_id.currency_id', depends=['order_id.currency_id'], store=True, string='Currency', readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', string='Company', store=True, readonly=True)

    # Computed field with complex dependencies
    margin = fields.Float(
        "Margin", compute='_compute_margin',
        digits='Product Price', store=True, groups="base.group_user", depends=['price_subtotal', 'product_id', 'purchase_price'])
    margin_percent = fields.Float(
        "Margin (%)", compute='_compute_margin', store=True, groups="base.group_user")

    @api.depends('product_uom_qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """Compute the amounts of the SO line."""
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('price_subtotal', 'product_id', 'purchase_price')
    def _compute_margin(self):
        for line in self:
            line.margin = line.price_subtotal - (line.purchase_price * line.product_uom_qty)
            line.margin_percent = line.price_subtotal and line.margin/line.price_subtotal or 0
''')

        product_template = tmp_path / "product_template.py"
        product_template.write_text("""
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _name = 'product.template'

    name = fields.Char('Name', index=True, required=True, translate=True)
    list_price = fields.Float('Sales Price', default=1.0, digits='Product Price')
    standard_price = fields.Float('Cost', company_dependent=True, digits='Product Price')

    # Computed fields
    display_name = fields.Char(compute='_compute_display_name', store=True)
    price_extra = fields.Float(compute='_compute_price_extra', digits='Product Price')

    # Related fields
    categ_id = fields.Many2one('product.category', 'Product Category', required=True)
    category_name = fields.Char(related='categ_id.name', string='Category Name')

    # Complex computed field
    qty_available = fields.Float(
        'Quantity On Hand', compute='_compute_quantities',
        digits='Product Unit of Measure', compute_sudo=False)
    virtual_available = fields.Float(
        'Forecasted Quantity', compute='_compute_quantities',
        digits='Product Unit of Measure', compute_sudo=False)

    @api.depends('name', 'default_code')
    def _compute_display_name(self):
        for template in self:
            template.display_name = template.name
            if template.default_code:
                template.display_name = f'[{template.default_code}] {template.name}'

    @api.depends('product_variant_ids', 'product_variant_ids.price_extra')
    def _compute_price_extra(self):
        for template in self:
            template.price_extra = sum(template.product_variant_ids.mapped('price_extra'))

    @api.depends('product_variant_ids.qty_available')
    def _compute_quantities(self):
        res = self._compute_quantities_dict()
        for template in self:
            template.qty_available = res[template.id]['qty_available']
            template.virtual_available = res[template.id]['virtual_available']
""")

        res_partner = tmp_path / "res_partner.py"
        res_partner.write_text("""
from odoo import models, fields, api

class ResPartner(models.Model):
    _name = 'res.partner'

    name = fields.Char(string='Name', required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True, index=True)

    # Address fields
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    country_id = fields.Many2one('res.country', string='Country')

    # Computed address
    contact_address = fields.Char(compute='_compute_contact_address', string='Complete Address')

    # Related fields
    country_code = fields.Char(related='country_id.code', string='Country Code')

    # Computed field without explicit @api.depends
    partner_share = fields.Boolean(
        'Share Partner', compute='_compute_partner_share', store=True,
        help="Either customer (not a user), either shared user. Indicated the current partner is a customer without access or with a limited access.")

    @api.depends('is_company', 'name', 'parent_id.display_name', 'type', 'company_name', 'commercial_company_name')
    def _compute_display_name(self):
        for partner in self:
            name = partner.name or ''
            if partner.company_name or partner.parent_id:
                if not name and partner.type in ['invoice', 'delivery', 'other']:
                    name = partner.commercial_company_name or partner.parent_id.name
                if name and partner.company_name:
                    name = f"{partner.company_name}, {name}"
            partner.display_name = name.strip()

    @api.depends('street', 'street2', 'city', 'country_id')
    def _compute_contact_address(self):
        for partner in self:
            address_parts = [partner.street, partner.street2, partner.city]
            if partner.country_id:
                address_parts.append(partner.country_id.name)
            partner.contact_address = ', '.join(filter(None, address_parts))

    @api.depends('user_ids.share', 'user_ids.active')
    def _compute_partner_share(self):
        for partner in self:
            partner.partner_share = not partner.user_ids or all(user.share for user in partner.user_ids)
""")

        # Model with no computed fields as control
        res_country = tmp_path / "res_country.py"
        res_country.write_text("""
from odoo import models, fields

class ResCountry(models.Model):
    _name = 'res.country'

    name = fields.Char(string='Country Name', required=True, translate=True)
    code = fields.Char(string='Country Code', size=2, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency')
""")

        return {
            "sale.order.line": sale_order_line,
            "product.template": product_template,
            "res.partner": res_partner,
            "res.country": res_country,
        }

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_find_computed_fields_with_compute_parameter(
        self, mock_path, mock_glob, mock_model_files, mock_env
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Test sale.order.line
        result = await resolve_dynamic_fields(mock_env, "sale.order.line")
        assert result is not None
        assert "computed_fields" in result
        assert len(result["computed_fields"]) > 0

        computed_names = [f["name"] for f in result["computed_fields"]]
        assert "price_subtotal" in computed_names
        assert "price_tax" in computed_names
        assert "price_total" in computed_names
        assert "margin" in computed_names
        assert "margin_percent" in computed_names

        # Check compute method is identified
        price_fields = [f for f in result["computed_fields"] if f["name"] in ["price_subtotal", "price_tax", "price_total"]]
        for field in price_fields:
            assert field["compute"] == "_compute_amount"

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_find_related_fields(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["sale.order.line"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order.line"].read_text()

        result = await resolve_dynamic_fields(mock_env, "sale.order.line")

        assert "related_fields" in result
        assert len(result["related_fields"]) > 0

        related_names = [f["name"] for f in result["related_fields"]]
        assert "order_partner_id" in related_names
        assert "currency_id" in related_names
        assert "company_id" in related_names

        # Check related paths
        order_partner = next(f for f in result["related_fields"] if f["name"] == "order_partner_id")
        assert order_partner["related"] == "order_id.partner_id"

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_detect_api_depends_decorators(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["sale.order.line"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order.line"].read_text()

        result = await resolve_dynamic_fields(mock_env, "sale.order.line")

        # Find _compute_amount in computed fields
        compute_amount_fields = [f for f in result["computed_fields"] if f["compute"] == "_compute_amount"]
        assert len(compute_amount_fields) > 0

        # Should have dependencies from @api.depends
        for field in compute_amount_fields:
            assert "dependencies" in field
            assert "product_uom_qty" in field["dependencies"]
            assert "price_unit" in field["dependencies"]
            assert "tax_id" in field["dependencies"]

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_handle_complex_dependencies(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["res.partner"]]
        mock_path.return_value.read_text.return_value = mock_model_files["res.partner"].read_text()

        result = await resolve_dynamic_fields(mock_env, "res.partner")

        # Find display_name computed field
        display_name = next((f for f in result["computed_fields"] if f["name"] == "display_name"), None)
        assert display_name is not None

        # Should have multiple dependencies
        assert "dependencies" in display_name
        expected_deps = ["is_company", "name", "parent_id.display_name", "type", "company_name", "commercial_company_name"]
        for dep in expected_deps:
            assert dep in display_name["dependencies"]

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_handle_models_without_dynamic_fields(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["res.country"]]
        mock_path.return_value.read_text.return_value = mock_model_files["res.country"].read_text()

        result = await resolve_dynamic_fields(mock_env, "res.country")

        assert result is not None
        assert result["computed_fields"] == []
        assert result["related_fields"] == []

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_identify_store_parameter(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["sale.order.line"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order.line"].read_text()

        result = await resolve_dynamic_fields(mock_env, "sale.order.line")

        # Find stored computed fields
        stored_fields = [f for f in result["computed_fields"] if f.get("store", False)]
        assert len(stored_fields) > 0

        # price_subtotal should be stored
        price_subtotal = next((f for f in stored_fields if f["name"] == "price_subtotal"), None)
        assert price_subtotal is not None
        assert price_subtotal["store"] is True

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_handle_cross_model_dependencies(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["product.template"]]
        mock_path.return_value.read_text.return_value = mock_model_files["product.template"].read_text()

        result = await resolve_dynamic_fields(mock_env, "product.template")

        # Find _compute_quantities
        qty_fields = [f for f in result["computed_fields"] if f["compute"] == "_compute_quantities"]
        assert len(qty_fields) > 0

        # Should detect cross-model dependency on product_variant_ids
        for field in qty_fields:
            assert "dependencies" in field
            assert "product_variant_ids.qty_available" in field["dependencies"]

    async def test_should_validate_model_name(self, mock_env) -> None:
        with pytest.raises(ValueError):
            await resolve_dynamic_fields(mock_env, "")

        with pytest.raises(ValueError):
            await resolve_dynamic_fields(mock_env, None)  # type: ignore[arg-type]

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    async def test_should_handle_file_not_found(self, mock_glob, mock_env) -> None:
        mock_glob.glob.return_value = []

        result = await resolve_dynamic_fields(mock_env, "non.existent.model")

        assert result is not None
        assert result["computed_fields"] == []
        assert result["related_fields"] == []

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_parse_field_types(self, mock_path, mock_glob, mock_model_files, mock_env) -> None:
        mock_glob.glob.return_value = [mock_model_files["sale.order.line"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order.line"].read_text()

        result = await resolve_dynamic_fields(mock_env, "sale.order.line")

        # Check field types are captured
        price_subtotal = next((f for f in result["computed_fields"] if f["name"] == "price_subtotal"), None)
        assert price_subtotal is not None
        assert price_subtotal["type"] == "Monetary"

        margin_percent = next((f for f in result["computed_fields"] if f["name"] == "margin_percent"), None)
        assert margin_percent is not None
        assert margin_percent["type"] == "Float"

    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.glob")
    @patch("odoo_intelligence_mcp.tools.field.resolve_dynamic_fields.Path")
    async def test_should_extract_related_field_attributes(self, mock_path, mock_glob, tmp_path, mock_env) -> None:
        # Create model with various related field configurations
        test_model = tmp_path / "test_model.py"
        test_model.write_text("""
from odoo import models, fields

class TestModel(models.Model):
    _name = 'test.model'

    partner_id = fields.Many2one('res.partner')

    # Simple related field
    partner_name = fields.Char(related='partner_id.name')

    # Related field with store
    partner_city = fields.Char(related='partner_id.city', store=True)

    # Related field with depends
    partner_country = fields.Many2one(related='partner_id.country_id', depends=['partner_id'], store=True, readonly=True)

    # Multi-level related
    partner_country_code = fields.Char(related='partner_id.country_id.code', string='Country Code')
""")

        mock_glob.glob.return_value = [test_model]
        mock_path.return_value.read_text.return_value = test_model.read_text()

        result = await resolve_dynamic_fields(mock_env, "test.model")

        related_fields = {f["name"]: f for f in result["related_fields"]}

        # Check all related fields are found
        assert "partner_name" in related_fields
        assert "partner_city" in related_fields
        assert "partner_country" in related_fields
        assert "partner_country_code" in related_fields

        # Check store attribute
        assert related_fields["partner_city"]["store"] is True
        assert related_fields["partner_country"]["store"] is True

        # Check multi-level related path
        assert related_fields["partner_country_code"]["related"] == "partner_id.country_id.code"
