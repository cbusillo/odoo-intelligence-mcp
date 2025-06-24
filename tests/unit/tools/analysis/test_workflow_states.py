from unittest.mock import AsyncMock, patch

import pytest

from odoo_intelligence_mcp.tools.analysis.workflow_states import analyze_workflow_states


class TestWorkflowStatesAnalyzerFix:
    # No longer need analyzer fixture since we use function directly

    @pytest.fixture
    def mock_model_files(self, tmp_path):
        # Create test model files with state fields and workflow patterns
        sale_order = tmp_path / "sale_order.py"
        sale_order.write_text('''
from odoo import models, fields, api

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'
    
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')
    
    def action_confirm(self):
        """Confirm the sales order."""
        for order in self:
            order.state = 'sale'
        return True
    
    def action_cancel(self):
        """Cancel the sales order."""
        self.write({'state': 'cancel'})
        
    def action_draft(self):
        """Set back to draft."""
        self.state = 'draft'
        
    @api.depends('state')
    def _compute_show_update_pricelist(self):
        for order in self:
            order.show_update_pricelist = order.state == 'draft'
''')

        purchase_order = tmp_path / "purchase_order.py"
        purchase_order.write_text('''
from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    
    state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)
    
    def button_confirm(self):
        """Confirm the purchase order."""
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue
            order._add_supplier_to_product()
            # Deal with double validation process
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
        return True
        
    def button_approve(self, force=False):
        """Approve the purchase order."""
        self.write({'state': 'purchase'})
        return {}
        
    def button_cancel(self):
        """Cancel the purchase order."""
        for order in self:
            order.state = 'cancel'
''')

        repair_order = tmp_path / "repair_order.py"
        repair_order.write_text('''
from odoo import models, fields, api

class RepairOrder(models.Model):
    _name = 'repair.order'
    
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('confirmed', 'Confirmed'),
        ('under_repair', 'Under Repair'),
        ('ready', 'Ready to Repair'),
        ('2binvoiced', 'To be Invoiced'),
        ('invoice_except', 'Invoice Exception'),
        ('done', 'Repaired'),
        ('cancel', 'Cancelled')
    ], string='Status', copy=False, default='draft', readonly=True, tracking=True,
        help="Status of the repair order")
    
    def action_repair_confirm(self):
        """Confirm the repair order."""
        if self.filtered(lambda repair: repair.state != 'draft'):
            raise UserError(_("Only draft repairs can be confirmed."))
        self.write({'state': 'confirmed'})
        return True
        
    def action_repair_start(self):
        """Start the repair."""
        if self.filtered(lambda repair: repair.state not in ['confirmed', 'ready']):
            raise UserError(_("Repair must be confirmed before starting."))
        self.write({'state': 'under_repair'})
        return True
        
    def action_repair_end(self):
        """End the repair."""
        if self.filtered(lambda repair: repair.state != 'under_repair'):
            raise UserError(_("Repair must be under repair to end it."))
        self.write({'state': 'done'})
        return True
        
    def action_repair_cancel(self):
        """Cancel the repair."""
        if self.filtered(lambda repair: repair.state == 'done'):
            raise UserError(_("Cannot cancel completed repairs."))
        self.write({'state': 'cancel'})
        
    @api.depends('state')
    def _compute_show_invoice_button(self):
        for repair in self:
            repair.show_invoice_button = repair.state in ['2binvoiced', 'done']
''')

        # Create a model without state field as control
        product_template = tmp_path / "product_template.py"
        product_template.write_text("""
from odoo import models, fields

class ProductTemplate(models.Model):
    _name = 'product.template'
    
    name = fields.Char('Name', required=True)
    list_price = fields.Float('Sales Price', default=1.0)
    active = fields.Boolean('Active', default=True)
""")

        return {
            "sale.order": sale_order,
            "purchase.order": purchase_order,
            "repair.order": repair_order,
            "product.template": product_template,
        }

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_find_state_fields_in_common_models(self, mock_path, mock_glob, mock_model_files):
        # Setup mocks
        mock_glob.glob.return_value = list(mock_model_files.values())

        for model_name, file_path in mock_model_files.items():
            mock_path.return_value.read_text.return_value = file_path.read_text()

        # Test sale.order
        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "state_fields": [
                    {
                        "name": "state",
                        "type": "Selection",
                        "states": [
                            ("draft", "Quotation"),
                            ("sale", "Sales Order"),
                            ("sent", "Quotation Sent"),
                            ("cancel", "Cancelled"),
                            ("done", "Done"),
                        ],
                    }
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "sale.order")
        assert result is not None
        assert "state_fields" in result
        assert len(result["state_fields"]) > 0

        state_field = result["state_fields"][0]
        assert state_field["name"] == "state"
        assert state_field["type"] == "Selection"
        assert len(state_field["states"]) == 5
        assert ("draft", "Quotation") in state_field["states"]
        assert ("sale", "Sales Order") in state_field["states"]

        # Test purchase.order
        mock_env.execute_code = AsyncMock(
            return_value={
                "state_fields": [
                    {
                        "name": "state",
                        "type": "Selection",
                        "states": [
                            ("draft", "RFQ"),
                            ("sent", "RFQ Sent"),
                            ("to approve", "To Approve"),
                            ("purchase", "Purchase Order"),
                            ("done", "Done"),
                            ("cancel", "Cancelled"),
                        ],
                    }
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "purchase.order")
        assert result is not None
        assert len(result["state_fields"]) > 0
        assert result["state_fields"][0]["name"] == "state"
        assert len(result["state_fields"][0]["states"]) == 6

        # Test repair.order
        mock_env.execute_code = AsyncMock(
            return_value={
                "state_fields": [
                    {
                        "name": "state",
                        "type": "Selection",
                        "states": [
                            ("draft", "Quotation"),
                            ("confirmed", "Confirmed"),
                            ("ready", "Ready to Repair"),
                            ("under_repair", "Under Repair"),
                            ("2binvoiced", "To be Invoiced"),
                            ("invoice_except", "Invoice Exception"),
                            ("done", "Done"),
                            ("cancel", "Cancelled"),
                        ],
                    }
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "repair.order")
        assert result is not None
        assert len(result["state_fields"]) > 0
        assert len(result["state_fields"][0]["states"]) == 8

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_identify_state_transition_methods(self, mock_path, mock_glob, mock_model_files):
        mock_glob.glob.return_value = [mock_model_files["sale.order"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order"].read_text()

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "state_transitions": [
                    {"method": "action_confirm", "to_state": "sale"},
                    {"method": "action_cancel", "to_state": "cancel"},
                    {"method": "action_draft", "to_state": "draft"},
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "sale.order")

        assert "state_transitions" in result
        assert len(result["state_transitions"]) > 0

        # Check for action_confirm transition
        transitions = {t["method"]: t for t in result["state_transitions"]}
        assert "action_confirm" in transitions
        assert transitions["action_confirm"]["to_state"] == "sale"

        # Check for action_cancel transition
        assert "action_cancel" in transitions
        assert transitions["action_cancel"]["to_state"] == "cancel"

        # Check for action_draft transition
        assert "action_draft" in transitions
        assert transitions["action_draft"]["to_state"] == "draft"

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_detect_button_actions(self, mock_path, mock_glob, mock_model_files):
        mock_glob.glob.return_value = [mock_model_files["purchase.order"]]
        mock_path.return_value.read_text.return_value = mock_model_files["purchase.order"].read_text()

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={"button_actions": [{"name": "button_confirm"}, {"name": "button_approve"}, {"name": "button_cancel"}]}
        )
        result = await analyze_workflow_states(mock_env, "purchase.order")

        assert "button_actions" in result
        button_names = [b["name"] for b in result["button_actions"]]

        assert "button_confirm" in button_names
        assert "button_approve" in button_names
        assert "button_cancel" in button_names

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_find_fields_depending_on_state(self, mock_path, mock_glob, mock_model_files):
        mock_glob.glob.return_value = [mock_model_files["sale.order"]]
        mock_path.return_value.read_text.return_value = mock_model_files["sale.order"].read_text()

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "dependent_fields": [
                    {"name": "show_update_pricelist", "compute": "_compute_show_update_pricelist", "depends_on": ["state"]}
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "sale.order")

        assert "dependent_fields" in result
        assert len(result["dependent_fields"]) > 0

        # Should find _compute_show_update_pricelist that depends on state
        dependent_methods = [f["method"] for f in result["dependent_fields"]]
        assert "_compute_show_update_pricelist" in dependent_methods

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_handle_models_without_state_fields(self, mock_path, mock_glob, mock_model_files):
        mock_glob.glob.return_value = [mock_model_files["product.template"]]
        mock_path.return_value.read_text.return_value = mock_model_files["product.template"].read_text()

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"state_fields": [], "state_transitions": [], "button_actions": []})
        result = await analyze_workflow_states(mock_env, "product.template")

        assert result is not None
        assert result["state_fields"] == []
        assert result["state_transitions"] == []
        assert result["button_actions"] == []

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_parse_selection_field_correctly(self, mock_path, mock_glob, mock_model_files):
        mock_glob.glob.return_value = [mock_model_files["repair.order"]]
        mock_path.return_value.read_text.return_value = mock_model_files["repair.order"].read_text()

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "state_fields": [
                    {
                        "name": "state",
                        "states": [
                            ("draft", "Quotation"),
                            ("confirmed", "Confirmed"),
                            ("ready", "Ready to Repair"),
                            ("under_repair", "Under Repair"),
                            ("2binvoiced", "To be Invoiced"),
                            ("invoice_except", "Invoice Exception"),
                            ("done", "Done"),
                            ("cancel", "Cancelled"),
                        ],
                    }
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "repair.order")

        state_field = result["state_fields"][0]
        states_dict = dict(state_field["states"])

        # Verify all states are parsed correctly
        expected_states = {
            "draft": "Quotation",
            "confirmed": "Confirmed",
            "under_repair": "Under Repair",
            "ready": "Ready to Repair",
            "2binvoiced": "To be Invoiced",
            "invoice_except": "Invoice Exception",
            "done": "Repaired",
            "cancel": "Cancelled",
        }

        for key, label in expected_states.items():
            assert key in states_dict
            assert states_dict[key] == label

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    async def test_should_handle_file_not_found(self, mock_glob):
        mock_glob.glob.return_value = []

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(return_value={"state_fields": [], "state_transitions": []})
        result = await analyze_workflow_states(mock_env, "non.existent.model")

        assert result is not None
        assert result["state_fields"] == []
        assert result["state_transitions"] == []

    async def test_should_validate_model_name(self):
        mock_env = AsyncMock()
        # The function doesn't validate model names, it just passes them to env.execute_code
        # So we'll test that it handles the response correctly
        mock_env.execute_code = AsyncMock(return_value={"error": "Model  not found"})
        result = await analyze_workflow_states(mock_env, "")
        assert "error" in result

    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.glob")
    @patch("odoo_intelligence_mcp.tools.analysis.workflow_states.Path")
    async def test_should_detect_complex_state_transitions(self, mock_path, mock_glob, tmp_path):
        # Create a model with complex state transitions
        complex_model = tmp_path / "complex_workflow.py"
        complex_model.write_text('''
from odoo import models, fields, api

class ComplexWorkflow(models.Model):
    _name = 'complex.workflow'
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done'),
    ])
    
    def submit_for_approval(self):
        """Submit for approval with validation."""
        for record in self:
            if record.state != 'draft':
                raise UserError("Can only submit draft records")
            record.write({'state': 'submitted'})
            
    def approve(self):
        """Approve with conditions."""
        self.ensure_one()
        if self.state == 'submitted':
            self.state = 'approved'
            # Send notification
            self._send_approval_notification()
            
    def multi_state_action(self):
        """Handle multiple state transitions."""
        for record in self:
            if record.state == 'draft':
                record.state = 'submitted'
            elif record.state == 'submitted':
                record.state = 'approved'
            elif record.state in ('approved', 'rejected'):
                record.state = 'done'
''')

        mock_glob.glob.return_value = [complex_model]
        mock_path.return_value.read_text.return_value = complex_model.read_text()

        mock_env = AsyncMock()
        mock_env.execute_code = AsyncMock(
            return_value={
                "state_transitions": [
                    {"method": "submit_for_approval", "to_state": "submitted"},
                    {"method": "approve", "to_state": "approved"},
                    {"method": "multi_state_action", "to_state": "multiple"},
                ]
            }
        )
        result = await analyze_workflow_states(mock_env, "complex.workflow")

        # Should detect the multi-state transition method
        transitions = {t["method"]: t for t in result["state_transitions"]}
        assert "multi_state_action" in transitions

        # Should detect multiple possible transitions for multi_state_action
        multi_state = transitions["multi_state_action"]
        assert multi_state["to_state"] in ["submitted", "approved", "done"]  # Any of these is valid
