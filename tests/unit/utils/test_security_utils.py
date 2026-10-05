import ast

import pytest

from odoo_intelligence_mcp.utils.security_utils import (
    CodeSecurityValidator,
    SecurityError,
    SecurityValidator,
    validate_and_sanitize_code,
)


class TestCodeSecurityValidator:
    def test_validate_code_success(self) -> None:
        code = """
import json
import datetime

def calculate_total(items):
    total = 0
    for item in items:
        total += item['price']
    return total
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is True
        assert "passed security validation" in message

    @pytest.mark.parametrize("difference", [-1, 0, 1])
    def test_validate_code_enforces_configured_length(self, difference: int, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(CodeSecurityValidator, "MAX_CODE_LENGTH", 24)
        code = "#" + "x" * (CodeSecurityValidator.MAX_CODE_LENGTH + difference - 1)
        result = CodeSecurityValidator.validate_code(code)
        assert result["is_valid"] is (difference <= 0)

    def test_validate_code_syntax_error(self) -> None:
        code = "def invalid syntax("
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "Syntax error" in message

    def test_validate_code_dangerous_import_os(self) -> None:
        code = "import os\nprint(os.getcwd())"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous module 'os'" in message

    def test_validate_code_dangerous_import_subprocess(self) -> None:
        code = "import subprocess\nsubprocess.run(['ls'])"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous module 'subprocess'" in message

    def test_validate_code_dangerous_function_eval(self) -> None:
        code = "result = eval('1 + 1')"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous function 'eval'" in message

    def test_validate_code_dangerous_function_exec(self) -> None:
        code = "exec('print(123)')"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous function 'exec'" in message

    def test_validate_code_dangerous_attribute_access(self) -> None:
        code = "obj.__class__.__bases__"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous attribute" in message  # Check for either __class__ or __bases__

    def test_validate_code_path_traversal(self) -> None:
        code = 'path = "../../../etc/passwd"'
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "Path traversal attempt" in message

    def test_validate_code_base64_usage(self) -> None:
        # noinspection SpellCheckingInspection
        code = "import base64\nencoded = base64.b64encode(b'data')"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "base64" in message.lower()  # Check for base64 mention (case-insensitive)

    def test_validate_code_hex_characters(self) -> None:
        code = 'data = "\\x41\\x42\\x43"'
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "Hex character codes" in message

    def test_validate_code_chr_manipulation(self) -> None:
        code = "char = chr(65)"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "Character code manipulation" in message

    def test_validate_code_allowed_modules(self) -> None:
        code = """
import datetime
import json
import re
import math
from collections import defaultdict
from itertools import chain

data = json.dumps({'key': 'value'})
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        _message = result.get("error", result.get("message", ""))
        assert is_valid is True

    def test_validate_code_odoo_import_allowed(self) -> None:
        code = """
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _name = 'sale.order'
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        _message = result.get("error", result.get("message", ""))
        assert is_valid is True

    @pytest.mark.parametrize("difference", [0, 1])
    def test_validate_code_enforces_configured_loop_depth(self, difference: int, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(CodeSecurityValidator, "MAX_LOOP_DEPTH", 2)
        depth = CodeSecurityValidator.MAX_LOOP_DEPTH + difference
        loops = [f"{'    ' * level}for number_{level} in range(2):" for level in range(depth)]
        code = "\n".join([*loops, f"{'    ' * depth}pass"])
        result = CodeSecurityValidator.validate_code(code)
        assert result["is_valid"] is (difference == 0)

    def test_validate_code_while_without_break(self) -> None:
        code = """
i = 0
while True:
    i += 1
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "must have a clear termination condition" in message

    def test_validate_code_while_with_break(self) -> None:
        code = """
i = 0
while True:
    i += 1
    if i > 10:
        break
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        _message = result.get("error", result.get("message", ""))
        assert is_valid is True

    def test_validate_code_private_function(self) -> None:
        code = """
def _private_function():
    return 'private'
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "private function" in message

    def test_validate_code_private_async_function(self) -> None:
        code = """
async def _private_async():
    return 'private'
"""
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "private async function" in message

    def test_sanitize_code(self) -> None:
        code = "  \n  x = 1  \n  "
        sanitized = CodeSecurityValidator.sanitize_code(code)
        assert sanitized == "x = 1"

    def test_validate_code_import_from_dangerous(self) -> None:
        code = "from os import path"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous module 'os'" in message

    def test_validate_code_dangerous_method_call(self) -> None:
        code = "obj.eval('code')"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "dangerous method 'eval'" in message

    def test_validate_code_unknown_module(self) -> None:
        code = "import unknown_module"
        result = CodeSecurityValidator.validate_code(code)
        is_valid = result["is_valid"]
        message = result.get("error", result.get("message", ""))
        assert is_valid is False
        assert "not explicitly allowed" in message


class TestSecurityValidator:
    def test_security_validator_init(self) -> None:
        validator = SecurityValidator()
        assert validator.in_loop is False
        assert validator.loop_depth == 0

    def test_has_break_condition_true(self) -> None:
        tree = ast.parse("""
while True:
    if condition:
        break
""")
        first_stmt = tree.body[0]
        assert isinstance(first_stmt, ast.While)
        while_node = first_stmt
        assert SecurityValidator._has_break_condition(while_node) is True

    def test_has_break_condition_false(self) -> None:
        tree = ast.parse("""
while True:
    print('infinite')
""")
        first_stmt = tree.body[0]
        assert isinstance(first_stmt, ast.While)
        while_node = first_stmt
        assert SecurityValidator._has_break_condition(while_node) is False

    def test_visit_import_dangerous(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("import os")
        with pytest.raises(SecurityError) as exc_info:
            validator.visit(tree)
        assert "dangerous module 'os'" in str(exc_info.value)

    def test_visit_import_allowed(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("import json")
        validator.visit(tree)  # Should not raise

    def test_visit_import_from_dangerous(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("from subprocess import run")
        with pytest.raises(SecurityError) as exc_info:
            validator.visit(tree)
        assert "dangerous module 'subprocess'" in str(exc_info.value)

    def test_visit_call_dangerous_function(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("eval('1+1')")
        with pytest.raises(SecurityError) as exc_info:
            validator.visit(tree)
        assert "dangerous function 'eval'" in str(exc_info.value)

    def test_visit_attribute_dangerous(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("obj.__globals__")
        with pytest.raises(SecurityError) as exc_info:
            validator.visit(tree)
        assert "dangerous attribute '__globals__'" in str(exc_info.value)

    @pytest.mark.parametrize("loop_type", ["for", "while"])
    def test_visit_rejects_depth_above_configured_limit(self, loop_type: str) -> None:
        depth = CodeSecurityValidator.MAX_LOOP_DEPTH + 1
        loop = "for number in range(1):" if loop_type == "for" else "while True:"
        lines = [f"{'    ' * level}{loop}" for level in range(depth)]
        lines.append(f"{'    ' * depth}pass")
        if loop_type == "while":
            lines.extend(f"{'    ' * level}break" for level in range(depth, 0, -1))
        tree = ast.parse("\n".join(lines))
        with pytest.raises(SecurityError):
            SecurityValidator().visit(tree)

    def test_visit_function_def_private(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("def _private(): pass")
        with pytest.raises(SecurityError) as exc_info:
            validator.visit(tree)
        assert "private function '_private'" in str(exc_info.value)

    def test_visit_async_function_def_private(self) -> None:
        validator = SecurityValidator()
        tree = ast.parse("async def _async_private(): pass")
        with pytest.raises(SecurityError) as exc_info:
            validator.visit(tree)
        assert "private async function '_async_private'" in str(exc_info.value)


class TestValidateAndSanitizeCode:
    def test_validate_and_sanitize_valid_code(self) -> None:
        code = """
import json
data = {'key': 'value'}
result = json.dumps(data)
"""
        is_valid, message, sanitized = validate_and_sanitize_code(code)
        assert is_valid is True
        assert "passed security validation" in message
        assert sanitized.strip() == code.strip()

    def test_validate_and_sanitize_invalid_code(self) -> None:
        code = """
import os
os.system('ls')
"""
        is_valid, message, _sanitized = validate_and_sanitize_code(code)
        assert is_valid is False
        assert "dangerous module 'os'" in message

    def test_validate_and_sanitize_with_whitespace(self) -> None:
        code = "  \n\n  x = 1  \n\n  "
        is_valid, _message, sanitized = validate_and_sanitize_code(code)
        assert is_valid is True
        assert sanitized == "x = 1"

    def test_validate_and_sanitize_syntax_error(self) -> None:
        code = "def broken("
        is_valid, message, _sanitized = validate_and_sanitize_code(code)
        assert is_valid is False
        assert "Syntax error" in message

    def test_security_error_exception(self) -> None:
        error = SecurityError("Test security error")
        assert str(error) == "Test security error"
        assert isinstance(error, Exception)
