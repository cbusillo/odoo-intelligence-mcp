from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestDecoratorSearcherFix:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        env = MagicMock()
        return env

    @pytest.fixture
    def mock_model_files(self, tmp_path: Path) -> dict[str, Path]:
        # Create test model files with various decorators
        sale_order = tmp_path / "sale_order.py"
        sale_order.write_text('''
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines')
    
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, compute='_compute_amounts')
    amount_tax = fields.Monetary(string='Taxes', store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string='Total', store=True, compute='_compute_amounts')
    
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ])
    
    @api.depends('order_line.price_total')
    def _compute_amounts(self):
        """Compute the total amounts of the SO."""
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
    
    @api.constrains('date_order', 'date_planned')
    def _check_dates(self):
        for order in self:
            if order.date_planned and order.date_order and order.date_planned < order.date_order:
                raise ValidationError(_('Scheduled Date cannot be earlier than Order Date.'))
    
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """Update the invoice and delivery addresses when the partner is changed."""
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
            })
            return
        
        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
        }
        self.update(values)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if 'company_id' in vals:
                    vals['name'] = self.env['ir.sequence'].with_company(vals['company_id']).next_by_code('sale.order') or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('sale.order') or _('New')
        return super().create(vals_list)
    
    @api.constrains('company_id', 'order_line')
    def _check_order_line_company_id(self):
        for order in self:
            companies = order.order_line.product_id.company_id
            if companies and companies != order.company_id:
                raise ValidationError(_('Your quotation contains products from company %s whereas your quotation belongs to company %s.') % (companies.mapped('display_name'), order.company_id.display_name))
''')

        product_template = tmp_path / "product_template.py"
        product_template.write_text("""
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _name = 'product.template'
    
    name = fields.Char('Name', index=True, required=True, translate=True)
    list_price = fields.Float('Sales Price', default=1.0, digits='Product Price')
    
    qty_available = fields.Float(
        'Quantity On Hand', compute='_compute_quantities',
        digits='Product Unit of Measure', compute_sudo=False)
    virtual_available = fields.Float(
        'Forecasted Quantity', compute='_compute_quantities',
        digits='Product Unit of Measure', compute_sudo=False)
    
    display_name = fields.Char(compute='_compute_display_name', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency')
    
    @api.depends('product_variant_ids.qty_available')
    def _compute_quantities(self):
        res = self._compute_quantities_dict()
        for template in self:
            template.qty_available = res[template.id]['qty_available']
            template.virtual_available = res[template.id]['virtual_available']
    
    @api.depends('name', 'default_code')
    def _compute_display_name(self):
        for template in self:
            template.display_name = template.name
            if template.default_code:
                template.display_name = f'[{template.default_code}] {template.name}'
    
    @api.onchange('list_price')
    def _onchange_list_price(self):
        if self.list_price < 0:
            raise UserError(_('Sales price cannot be negative.'))
    
    @api.constrains('list_price', 'standard_price')
    def _check_prices(self):
        for template in self:
            if template.list_price < template.standard_price:
                raise ValidationError(_('Sales price cannot be lower than cost.'))
    
    @api.model
    def create(self, vals):
        # Regular create method, not model_create_multi
        template = super().create(vals)
        return template
""")

        res_partner = tmp_path / "res_partner.py"
        res_partner.write_text("""
from odoo import models, fields, api

class ResPartner(models.Model):
    _name = 'res.partner'
    
    name = fields.Char(index=True, required=True)
    email = fields.Char('Email')
    phone = fields.Char('Phone')
    
    display_name = fields.Char(compute='_compute_display_name', store=True, index=True)
    partner_share = fields.Boolean(
        'Share Partner', compute='_compute_partner_share', store=True)
    
    @api.depends('is_company', 'name', 'parent_id.display_name', 'type', 'company_name')
    def _compute_display_name(self):
        for partner in self:
            name = partner.name or ''
            if partner.company_name or partner.parent_id:
                if not name and partner.type in ['invoice', 'delivery', 'other']:
                    name = partner.parent_id.name
                if name and partner.company_name:
                    name = f"{partner.company_name}, {name}"
            partner.display_name = name.strip()
    
    @api.depends('user_ids.share', 'user_ids.active')
    def _compute_partner_share(self):
        for partner in self:
            partner.partner_share = not partner.user_ids or all(user.share for user in partner.user_ids)
    
    @api.onchange('email')
    def onchange_email(self):
        if self.email:
            self.email = self.email.lower().strip()
    
    @api.constrains('email')
    def _check_email(self):
        for partner in self:
            if partner.email and '@' not in partner.email:
                raise ValidationError(_('Please enter a valid email address.'))
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'email' in vals and vals['email']:
                vals['email'] = vals['email'].lower().strip()
        return super().create(vals_list)
""")

        # Model with multiple decorators on same method
        account_move = tmp_path / "account_move.py"
        account_move.write_text("""
from odoo import models, fields, api

class AccountMove(models.Model):
    _name = 'account.move'
    
    partner_id = fields.Many2one('res.partner', string='Partner')
    currency_id = fields.Many2one('res.currency', string='Currency')
    
    amount_total = fields.Monetary(string='Total', store=True, compute='_compute_amount')
    amount_tax = fields.Monetary(string='Tax', store=True, compute='_compute_amount')
    
    @api.depends('line_ids.debit', 'line_ids.credit', 'line_ids.amount_currency')
    def _compute_amount(self):
        for move in self:
            total = sum(move.line_ids.mapped('debit')) - sum(move.line_ids.mapped('credit'))
            move.amount_total = abs(total)
            move.amount_tax = 0  # Simplified
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.currency_id = self.partner_id.currency_id
    
    # Multiple constrains decorators
    @api.constrains('line_ids')
    def _check_balanced(self):
        for move in self:
            if not move.line_ids:
                continue
            if sum(move.line_ids.mapped('debit')) != sum(move.line_ids.mapped('credit')):
                raise ValidationError(_('Journal Entry must be balanced.'))
    
    @api.constrains('date', 'company_id')
    def _check_date(self):
        for move in self:
            if move.date > fields.Date.today():
                raise ValidationError(_('Journal Entry date cannot be in the future.'))
""")

        # Model without decorators as control
        res_currency = tmp_path / "res_currency.py"
        res_currency.write_text("""
from odoo import models, fields

class ResCurrency(models.Model):
    _name = 'res.currency'
    
    name = fields.Char(string='Currency', size=3, required=True)
    symbol = fields.Char()
    rate = fields.Float(digits=(12, 6))
    
    def get_rate(self):
        return self.rate or 1.0
""")

        return {
            "sale.order": sale_order,
            "product.template": product_template,
            "res.partner": res_partner,
            "account.move": account_move,
            "res.currency": res_currency,
        }

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_find_depends_decorators(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("depends")

        assert result is not None
        assert len(result["results"]) > 0

        # Extract decorator info by model
        depends_by_model = {}
        for r in result["results"]:
            if r["model"] not in depends_by_model:
                depends_by_model[r["model"]] = []
            depends_by_model[r["model"]].append(r)

        # Check sale.order depends
        assert "sale.order" in depends_by_model
        sale_depends = depends_by_model["sale.order"]
        assert any(d["method"] == "_compute_amounts" for d in sale_depends)

        # Check dependencies are parsed
        compute_amounts = next(d for d in sale_depends if d["method"] == "_compute_amounts")
        assert "order_line.price_total" in compute_amounts["dependencies"]

        # Check product.template depends
        assert "product.template" in depends_by_model
        product_depends = depends_by_model["product.template"]
        assert any(d["method"] == "_compute_quantities" for d in product_depends)
        assert any(d["method"] == "_compute_display_name" for d in product_depends)

        # Check res.partner depends
        assert "res.partner" in depends_by_model
        partner_depends = depends_by_model["res.partner"]
        display_name_dep = next(d for d in partner_depends if d["method"] == "_compute_display_name")
        assert "is_company" in display_name_dep["dependencies"]
        assert "name" in display_name_dep["dependencies"]

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_find_constrains_decorators(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("constrains")

        assert len(result["results"]) > 0

        constrains_methods = [(r["model"], r["method"]) for r in result["results"]]

        # Check sale.order constraints
        assert ("sale.order", "_check_dates") in constrains_methods
        assert ("sale.order", "_check_order_line_company_id") in constrains_methods

        # Check constraint fields are parsed
        check_dates = next(r for r in result["results"] if r["model"] == "sale.order" and r["method"] == "_check_dates")
        assert "date_order" in check_dates["fields"]
        assert "date_planned" in check_dates["fields"]

        # Check product.template constraints
        assert ("product.template", "_check_prices") in constrains_methods

        # Check res.partner constraints
        assert ("res.partner", "_check_email") in constrains_methods

        # Check account.move multiple constraints
        assert ("account.move", "_check_balanced") in constrains_methods
        assert ("account.move", "_check_date") in constrains_methods

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_find_onchange_decorators(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("onchange")

        assert len(result["results"]) > 0

        onchange_methods = [(r["model"], r["method"]) for r in result["results"]]

        # Check sale.order onchange
        assert ("sale.order", "onchange_partner_id") in onchange_methods

        # Check onchange fields are parsed
        partner_onchange = next(r for r in result["results"] if r["model"] == "sale.order" and r["method"] == "onchange_partner_id")
        assert "partner_id" in partner_onchange["fields"]

        # Check product.template onchange
        assert ("product.template", "_onchange_list_price") in onchange_methods

        # Check res.partner onchange
        assert ("res.partner", "onchange_email") in onchange_methods

        # Check account.move onchange
        assert ("account.move", "_onchange_partner_id") in onchange_methods

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_find_model_create_multi_decorators(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        result = searcher.search("model_create_multi")

        assert len(result["results"]) > 0

        create_multi_methods = [(r["model"], r["method"]) for r in result["results"]]

        # Check sale.order has model_create_multi
        assert ("sale.order", "create") in create_multi_methods

        # Check res.partner has model_create_multi
        assert ("res.partner", "create") in create_multi_methods

        # Product.template should NOT appear (it has regular create)
        assert ("product.template", "create") not in create_multi_methods

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_handle_models_without_decorators(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        # Test with only res.currency which has no decorators
        mock_glob.glob.return_value = [mock_model_files["res.currency"]]
        mock_path.return_value.read_text.return_value = mock_model_files["res.currency"].read_text()

        for decorator in ["depends", "constrains", "onchange", "model_create_multi"]:
            result = searcher.search(decorator)
            assert result["results"] == []

    def test_should_validate_decorator_parameter(self, searcher: Mock) -> None:
        # Valid decorators
        valid_decorators = ["depends", "constrains", "onchange", "model_create_multi"]
        for decorator in valid_decorators:
            result = searcher.search(decorator)  # Should not raise
            assert result is not None

        # Invalid decorator
        with pytest.raises(ValueError) as exc_info:
            searcher.search("invalid_decorator")
        assert "Invalid decorator" in str(exc_info.value)

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    def test_should_handle_no_files_found(self, mock_glob: Mock, searcher: Mock) -> None:
        mock_glob.glob.return_value = []

        result = searcher.search("depends")

        assert result is not None
        assert result["results"] == []
        assert result["total_count"] == 0

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_extract_decorator_parameters(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = [mock_model_files["account.move"]]
        mock_path.return_value.read_text.return_value = mock_model_files["account.move"].read_text()

        result = searcher.search("depends")

        # Find _compute_amount method
        compute_amount = next((r for r in result["results"] if r["method"] == "_compute_amount"), None)
        assert compute_amount is not None

        # Check multiple dependencies are parsed
        expected_deps = ["line_ids.debit", "line_ids.credit", "line_ids.amount_currency"]
        for dep in expected_deps:
            assert dep in compute_amount["dependencies"]

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_handle_complex_decorator_syntax(self, mock_path: Mock, mock_glob: Mock, searcher: Mock, tmp_path: Path) -> None:
        # Create model with complex decorator syntax
        complex_model = tmp_path / "complex_model.py"
        complex_model.write_text("""
from odoo import models, fields, api

class ComplexModel(models.Model):
    _name = 'complex.model'
    
    # Multi-line depends
    @api.depends(
        'line_ids.product_id',
        'line_ids.price_unit',
        'line_ids.quantity',
        'line_ids.discount'
    )
    def _compute_totals(self):
        pass
    
    # Single line with multiple fields
    @api.constrains('start_date', 'end_date', 'active')
    def _check_date_consistency(self):
        pass
    
    # Nested quotes
    @api.onchange("partner_id")
    def _onchange_partner(self):
        pass
    
    # Multiple decorators on same method
    @api.depends('state')
    @api.depends('partner_id.active')  # Additional depends
    def _compute_active_state(self):
        pass
""")

        mock_glob.glob.return_value = [complex_model]
        mock_path.return_value.read_text.return_value = complex_model.read_text()

        # Test multi-line depends
        result = searcher.search("depends")
        compute_totals = next((r for r in result["results"] if r["method"] == "_compute_totals"), None)
        assert compute_totals is not None
        assert len(compute_totals["dependencies"]) == 4
        assert "line_ids.product_id" in compute_totals["dependencies"]

        # Test constrains with multiple fields
        result = searcher.search("constrains")
        check_dates = next((r for r in result["results"] if r["method"] == "_check_date_consistency"), None)
        assert check_dates is not None
        assert len(check_dates["fields"]) == 3
        assert "start_date" in check_dates["fields"]
        assert "end_date" in check_dates["fields"]
        assert "active" in check_dates["fields"]

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_paginate_results(
        self, mock_path: Mock, mock_glob: Mock, searcher: Mock, mock_model_files: dict[str, Path]
    ) -> None:
        mock_glob.glob.return_value = list(mock_model_files.values())

        for file_path in mock_model_files.values():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Get first page
        result_page1 = searcher.search("depends", limit=3, offset=0)
        assert len(result_page1["results"]) <= 3

        # Get second page
        result_page2 = searcher.search("depends", limit=3, offset=3)

        # Ensure no overlap between pages
        page1_methods = [(r["model"], r["method"]) for r in result_page1["results"]]
        page2_methods = [(r["model"], r["method"]) for r in result_page2["results"]]
        assert not set(page1_methods).intersection(set(page2_methods))

    @patch("odoo_intelligence_mcp.tools.model.search_decorators.glob")
    @patch("odoo_intelligence_mcp.tools.model.search_decorators.Path")
    def test_should_find_computed_fields_from_depends(self, mock_path, mock_glob, searcher, mock_model_files):
        mock_glob.glob.return_value = [mock_model_files["sale.order"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order"].read_text()

        result = searcher.search("depends")

        # Find _compute_amounts
        compute_amounts = next((r for r in result["results"] if r["method"] == "_compute_amounts"), None)
        assert compute_amounts is not None

        # Should identify which fields this method computes
        assert "computed_fields" in compute_amounts
        computed_fields = compute_amounts["computed_fields"]
        assert "amount_untaxed" in computed_fields
        assert "amount_tax" in computed_fields
        assert "amount_total" in computed_fields
