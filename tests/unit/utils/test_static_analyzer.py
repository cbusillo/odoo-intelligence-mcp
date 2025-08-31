import ast
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from odoo_intelligence_mcp.utils.static_analyzer import OdooStaticAnalyzer


class TestOdooStaticAnalyzer:
    @pytest.fixture
    def analyzer(self) -> OdooStaticAnalyzer:
        return OdooStaticAnalyzer(addon_paths=["/test/addons", "/test/enterprise"])

    @pytest.fixture
    def mock_file_content(self) -> str:
        return """
from odoo import models, fields, api

class SaleOrder(models.Model):
    _name = "sale.order"
    _description = "Sales Order"
    
    name = fields.Char("Name", required=True)
    partner_id = fields.Many2one("res.partner", string="Customer")
    total = fields.Float(compute="_compute_total", store=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Done")
    ], default="draft")
    
    @api.depends("line_ids.subtotal")
    def _compute_total(self):
        for order in self:
            order.total = sum(order.line_ids.mapped("subtotal"))
    
    @api.constrains("partner_id")
    def _check_partner(self):
        if not self.partner_id:
            raise ValidationError("Partner is required")
    
    @api.onchange("partner_id")
    def _onchange_partner(self):
        if self.partner_id:
            self.payment_term_id = self.partner_id.property_payment_term_id
    
    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)
"""

    def test_init_with_custom_paths(self, analyzer: OdooStaticAnalyzer) -> None:
        assert analyzer.addon_paths == ["/test/addons", "/test/enterprise"]
        assert analyzer._model_cache == {}

    @patch("odoo_intelligence_mcp.utils.static_analyzer.load_env_config")
    def test_init_with_env_config(self, mock_load_env: Mock) -> None:
        from unittest.mock import MagicMock

        mock_config = MagicMock()
        mock_config.addons_path = "/env/addons,/env/enterprise"
        mock_load_env.return_value = mock_config
        analyzer = OdooStaticAnalyzer()
        assert analyzer.addon_paths == ["/env/addons", "/env/enterprise"]

    @patch("odoo_intelligence_mcp.utils.static_analyzer.Path")
    def test_find_model_file_success(
        self,
        mock_path_class: Mock,
        analyzer: OdooStaticAnalyzer,
        mock_file_content: str,
    ) -> None:
        # Create mock file that will be returned
        mock_py_file = MagicMock(spec=Path)
        mock_py_file.name = "sale.py"
        mock_py_file.read_text.return_value = mock_file_content

        # Create mock models directory
        mock_models_dir = MagicMock()
        mock_models_dir.exists.return_value = True
        mock_models_dir.glob.return_value = [mock_py_file]

        # Create mock addon directory
        mock_addon_dir = MagicMock()
        mock_addon_dir.is_dir.return_value = True
        mock_addon_dir.__truediv__.return_value = mock_models_dir

        # Create mock base path
        mock_base_path = MagicMock()
        mock_base_path.exists.return_value = True
        mock_base_path.iterdir.return_value = [mock_addon_dir]

        # Configure Path to return our mock base path
        mock_path_class.return_value = mock_base_path

        result = analyzer.find_model_file("sale.order")
        assert result == mock_py_file

    @patch("pathlib.Path.exists")
    def test_find_model_file_path_not_exists(self, mock_exists: Mock, analyzer: OdooStaticAnalyzer) -> None:
        mock_exists.return_value = False
        result = analyzer.find_model_file("sale.order")
        assert result is None

    @patch("pathlib.Path.read_text")
    def test_analyze_model_file_success(self, mock_read_text: Mock, analyzer: OdooStaticAnalyzer, mock_file_content: str) -> None:
        mock_read_text.return_value = mock_file_content
        file_path = Path("/test/sale.py")

        result = analyzer.analyze_model_file(file_path)

        assert "fields" in result
        assert "methods" in result
        assert "decorators" in result
        assert "name" in result["fields"]
        assert "partner_id" in result["fields"]
        assert "_compute_total" in result["methods"]

    @patch("pathlib.Path.read_text")
    def test_analyze_model_file_error(self, mock_read_text: Mock, analyzer: OdooStaticAnalyzer) -> None:
        mock_read_text.side_effect = Exception("Read error")
        file_path = Path("/test/sale.py")

        result = analyzer.analyze_model_file(file_path)
        assert "error" in result
        assert "Read error" in result["error"]

    def test_extract_model_info(self, analyzer: OdooStaticAnalyzer, mock_file_content: str) -> None:
        tree = ast.parse(mock_file_content)
        result = analyzer._extract_model_info(tree, mock_file_content)

        assert result["class_name"] == "SaleOrder"
        assert "name" in result["fields"]
        assert "partner_id" in result["fields"]
        assert "_compute_total" in result["methods"]
        assert len(result["decorators"]["depends"]) == 1
        assert len(result["decorators"]["constrains"]) == 1
        assert len(result["decorators"]["onchange"]) == 1
        assert len(result["decorators"]["model_create_multi"]) == 1

    def test_analyze_field_assignment(self, analyzer: OdooStaticAnalyzer) -> None:
        code = 'name = fields.Char("Name", required=True)'
        tree = ast.parse(code)
        assign_node = tree.body[0]
        info: dict[str, Any] = {"fields": {}}

        analyzer._analyze_field_assignment(cast(ast.Assign, assign_node), code, info)
        assert "name" in info["fields"]
        assert info["fields"]["name"]["type"] == "Char"

    def test_extract_field_info(self, analyzer: OdooStaticAnalyzer) -> None:
        code = 'fields.Char("Name", required=True, help="Enter name")'
        tree = ast.parse(code)
        call_node = tree.body[0].value

        result = analyzer._extract_field_info(call_node, code)
        assert result is not None
        assert result["type"] == "Char"
        assert result["parameters"]["required"] is True

    def test_extract_keyword_value_constant(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse("True")
        node = tree.body[0].value
        result = analyzer._extract_keyword_value(node, "True")
        assert result is True

    def test_extract_keyword_value_name(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse("variable")
        node = tree.body[0].value
        result = analyzer._extract_keyword_value(node, "variable")
        assert result == "variable"

    def test_extract_keyword_value_list(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse("[1, 2, 3]")
        node = tree.body[0].value
        result = analyzer._extract_keyword_value(node, "[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_extract_keyword_value_tuple(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse("(1, 2)")
        node = tree.body[0].value
        result = analyzer._extract_keyword_value(node, "(1, 2)")
        assert result == (1, 2)

    def test_analyze_method(self, analyzer: OdooStaticAnalyzer) -> None:
        code = """
@api.depends("field1", "field2")
def _compute_value(self):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        info: dict[str, Any] = {
            "methods": {},
            "decorators": {"depends": [], "constrains": [], "onchange": [], "model_create_multi": []},
        }

        analyzer._analyze_method(cast(ast.FunctionDef, func_node), code, info)
        assert "_compute_value" in info["methods"]
        assert len(info["methods"]["_compute_value"]["decorators"]) == 1
        assert len(info["decorators"]["depends"]) == 1

    def test_analyze_decorator_name(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse("@simple_decorator\ndef func(): pass")
        decorator_node = tree.body[0].decorator_list[0]
        result = analyzer._analyze_decorator(decorator_node, "")
        assert result == {"name": "simple_decorator"}

    def test_analyze_decorator_attribute(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse("@api.depends\ndef func(): pass")
        decorator_node = tree.body[0].decorator_list[0]
        result = analyzer._analyze_decorator(decorator_node, "")
        assert result == {"name": "api.depends"}

    def test_analyze_decorator_call(self, analyzer: OdooStaticAnalyzer) -> None:
        tree = ast.parse('@api.depends("field1", "field2")\ndef func(): pass')
        decorator_node = tree.body[0].decorator_list[0]
        result = analyzer._analyze_decorator(decorator_node, "")
        assert result == {"name": "api.depends", "args": ["field1", "field2"]}

    def test_get_method_signature(self, analyzer: OdooStaticAnalyzer) -> None:
        code = "def method(self, arg1, arg2): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        result = analyzer._get_method_signature(cast(ast.FunctionDef, func_node))
        assert result == "(self, arg1, arg2)"

    @patch.object(OdooStaticAnalyzer, "find_model_file")
    @patch.object(OdooStaticAnalyzer, "analyze_model_file")
    def test_find_state_fields(self, mock_analyze: Mock, mock_find: Mock, analyzer: OdooStaticAnalyzer) -> None:
        mock_find.return_value = Path("/test/sale.py")
        mock_analyze.return_value = {
            "fields": {
                "state": {"type": "Selection", "parameters": {}},
                "status": {"type": "Selection", "parameters": {}},
                "other_field": {"type": "Char", "parameters": {}},
            }
        }

        result = analyzer.find_state_fields("sale.order")
        assert "state" in result
        assert "status" in result
        assert "other_field" not in result

    @patch.object(OdooStaticAnalyzer, "find_model_file")
    def test_find_state_fields_no_file(self, mock_find: Mock, analyzer: OdooStaticAnalyzer) -> None:
        mock_find.return_value = None
        result = analyzer.find_state_fields("sale.order")
        assert result == {}

    @patch.object(OdooStaticAnalyzer, "find_model_file")
    @patch.object(OdooStaticAnalyzer, "analyze_model_file")
    def test_find_computed_fields(self, mock_analyze: Mock, mock_find: Mock, analyzer: OdooStaticAnalyzer) -> None:
        mock_find.return_value = Path("/test/sale.py")
        mock_analyze.return_value = {
            "fields": {
                "total": {"type": "Float", "parameters": {"compute": "_compute_total", "store": True}},
                "subtotal": {"type": "Float", "parameters": {"compute": "_compute_subtotal"}},
            },
            "decorators": {
                "depends": [
                    {"method": "_compute_total", "depends_on": ["line_ids"]},
                ]
            },
        }

        result = analyzer.find_computed_fields("sale.order")
        assert "total" in result
        assert result["total"]["compute_method"] == "_compute_total"
        assert result["total"]["store"] is True
        assert result["total"]["depends"] == ["line_ids"]

    @patch.object(OdooStaticAnalyzer, "find_model_file")
    @patch.object(OdooStaticAnalyzer, "analyze_model_file")
    def test_find_related_fields(self, mock_analyze: Mock, mock_find: Mock, analyzer: OdooStaticAnalyzer) -> None:
        mock_find.return_value = Path("/test/sale.py")
        mock_analyze.return_value = {
            "fields": {
                "partner_name": {"type": "Char", "parameters": {"related": "partner_id.name"}},
                "regular_field": {"type": "Char", "parameters": {}},
            }
        }

        result = analyzer.find_related_fields("sale.order")
        assert "partner_name" in result
        assert result["partner_name"]["related_path"] == "partner_id.name"
        assert "regular_field" not in result

    def test_find_compute_dependencies(self, analyzer: OdooStaticAnalyzer) -> None:
        model_info = {
            "decorators": {
                "depends": [
                    {"method": "_compute_total", "depends_on": ["line_ids", "tax_ids"]},
                    {"method": "_compute_subtotal", "depends_on": ["price", "quantity"]},
                ]
            }
        }

        result = analyzer._find_compute_dependencies(model_info, "_compute_total")
        assert result == ["line_ids", "tax_ids"]

        result = analyzer._find_compute_dependencies(model_info, "_compute_unknown")
        assert result == []

    def test_extract_model_name(self, analyzer: OdooStaticAnalyzer) -> None:
        content = '_name = "sale.order"'
        result = analyzer._extract_model_name(content)
        assert result == "sale.order"

        content = "_name = 'res.partner'"
        result = analyzer._extract_model_name(content)
        assert result == "res.partner"

        content = "no model name here"
        result = analyzer._extract_model_name(content)
        assert result is None

    def test_find_method_name_after_decorator(self, analyzer: OdooStaticAnalyzer) -> None:
        content = "@api.depends\ndef _compute_total(self):\n    pass"
        result = analyzer._find_method_name_after_decorator(content, 0)
        assert result == "_compute_total"

        content = "no method here"
        result = analyzer._find_method_name_after_decorator(content, 0)
        assert result is None

    def test_parse_decorator_args(self, analyzer: OdooStaticAnalyzer) -> None:
        result = analyzer._parse_decorator_args('"field1", "field2", "field3"')
        assert result == ["field1", "field2", "field3"]

        result = analyzer._parse_decorator_args("'single_field'")
        assert result == ["single_field"]

        result = analyzer._parse_decorator_args("")
        assert result == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.rglob")
    def test_search_decorators_in_files(self, mock_rglob: Mock, mock_exists: Mock) -> None:
        # Create analyzer with single addon path to avoid duplicates
        analyzer = OdooStaticAnalyzer(addon_paths=["/test/addons"])
        mock_exists.return_value = True

        mock_file = MagicMock(spec=Path)
        mock_file.__str__.return_value = "/test/sale.py"
        mock_file.read_text.return_value = """
_name = "sale.order"

@api.depends("line_ids")
def _compute_total(self):
    pass
"""
        mock_rglob.return_value = [mock_file]

        results = analyzer.search_decorators_in_files("depends")
        assert len(results) == 1
        assert results[0]["model"] == "sale.order"
        assert results[0]["method"] == "_compute_total"
        assert results[0]["depends"] == ["line_ids"]

    def test_search_decorators_invalid_type(self, analyzer: OdooStaticAnalyzer) -> None:
        results = analyzer.search_decorators_in_files("invalid_decorator")
        assert results == []
