from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.code.search_code import search_code


@pytest.mark.asyncio
async def test_search_code_basic_pattern() -> None:
    mock_files = [
        Path("/addons/test_module/models/test_model.py"),
        Path("/addons/test_module/models/other_model.py"),
        Path("/addons/test_module/views/test_view.xml"),
    ]

    file_contents = {
        "/addons/test_module/models/test_model.py": """
class TestModel(models.Model):
    _name = 'test.model'

    def test_method(self):
        return True
""",
        "/addons/test_module/models/other_model.py": """
class OtherModel(models.Model):
    _name = 'other.model'

    def other_method(self):
        return False
""",
    }

    def mock_open_file(filename, *args, **kwargs):
        return mock_open(read_data=file_contents.get(str(filename), ""))()

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", side_effect=mock_open_file):
        result = await search_code("test_method", "py")

    assert result["total_count"] == 1
    assert result["items"][0]["file"] == "test_module/models/test_model.py"
    assert result["items"][0]["matches"][0]["line"] == 4
    assert "test_method" in result["items"][0]["matches"][0]["content"]


@pytest.mark.asyncio
async def test_search_code_multiple_matches() -> None:
    mock_files = [Path("/addons/module/models/model.py")]

    file_content = """
def compute_total(self):
    total = 0
    for line in self.lines:
        total += line.price
    self.total = total
"""

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=file_content)):
        result = await search_code("total", "py")

    assert result["total_count"] == 1
    assert len(result["items"][0]["matches"]) == 3  # 3 lines contain "total"


@pytest.mark.asyncio
async def test_search_code_xml_files() -> None:
    mock_files = [Path("/addons/module/views/view.xml")]

    xml_content = """<?xml version="1.0"?>
<odoo>
    <record id="view_test" model="ir.ui.view">
        <field name="name">test.view</field>
        <field name="model">test.model</field>
        <field name="arch" type="xml">
            <form string="Test Form">
                <field name="name"/>
            </form>
        </field>
    </record>
</odoo>"""

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=xml_content)):
        result = await search_code("test\\.model", "xml")

    assert result["total_count"] == 1
    assert "test.model" in result["items"][0]["matches"][0]["content"]


@pytest.mark.asyncio
async def test_search_code_with_pagination() -> None:
    # Create many mock files
    mock_files = [Path(f"/addons/module/models/model_{i}.py") for i in range(30)]

    file_content = "def test_method(self):\n    pass"

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=file_content)):
        pagination = PaginationParams(limit=10, offset=0)
        result = await search_code("test_method", "py", pagination)

    assert len(result["items"]) == 10
    assert result["total_count"] == 30
    assert result["page_info"]["has_next_page"] is True
    assert result["page_info"]["has_previous_page"] is False


@pytest.mark.asyncio
async def test_search_code_no_matches() -> None:
    mock_files = [Path("/addons/module/models/model.py")]

    file_content = "class MyModel(models.Model):\n    _name = 'my.model'"

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=file_content)):
        result = await search_code("nonexistent_pattern", "py")

    assert result["total_count"] == 0
    assert result["items"] == []


@pytest.mark.asyncio
async def test_search_code_case_sensitive_regex() -> None:
    mock_files = [Path("/addons/module/models/model.py")]

    file_content = """
class TestModel(models.Model):
    test_field = fields.Char()
    TEST_CONSTANT = 'value'
"""

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=file_content)):
        # Search for uppercase TEST
        result = await search_code("TEST", "py")

    assert result["total_count"] == 1
    assert len(result["items"][0]["matches"]) == 1
    assert "TEST_CONSTANT" in result["items"][0]["matches"][0]["content"]


@pytest.mark.asyncio
async def test_search_code_complex_regex() -> None:
    mock_files = [Path("/addons/module/models/model.py")]

    file_content = """
@api.depends('line_ids.price')
def _compute_total(self):
    pass

@api.onchange('partner_id')
def _onchange_partner(self):
    pass
"""

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=file_content)):
        # Search for @api decorators
        result = await search_code(r"@api\.\w+", "py")

    assert result["total_count"] == 1
    assert len(result["items"][0]["matches"]) == 2


@pytest.mark.asyncio
async def test_search_code_file_read_error() -> None:
    mock_files = [
        Path("/addons/module/models/readable.py"),
        Path("/addons/module/models/unreadable.py"),
    ]

    def mock_open_file(filename, *args, **kwargs):
        if "unreadable" in str(filename):
            raise PermissionError("Access denied")
        return mock_open(read_data="def test(): pass")()

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", side_effect=mock_open_file):
        result = await search_code("test", "py")

    # Should still return results from readable files
    assert result["total_count"] == 1
    assert "readable.py" in result["items"][0]["file"]


@pytest.mark.asyncio
async def test_search_code_javascript_files() -> None:
    mock_files = [Path("/addons/module/static/src/js/widget.js")]

    js_content = """
odoo.define('module.widget', function (require) {
    'use strict';

    const Widget = require('web.Widget');

    return Widget.extend({
        start: function () {
            console.log('Widget started');
        }
    });
});"""

    with patch("pathlib.Path.rglob", return_value=mock_files), patch("builtins.open", mock_open(read_data=js_content)):
        result = await search_code("Widget", "js")

    assert result["total_count"] == 1
    assert len(result["items"][0]["matches"]) == 3  # 3 occurrences of "Widget"
