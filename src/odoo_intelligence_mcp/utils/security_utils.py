import ast
import re
from typing import ClassVar


class CodeSecurityValidator:
    MAX_LOOP_DEPTH = 3  # Maximum allowed nested loop depth
    # noinspection SpellCheckingInspection
    DANGEROUS_IMPORTS: ClassVar[set[str]] = {
        "os",
        "subprocess",
        "sys",
        "shutil",
        "pathlib",
        "socket",
        "urllib",
        "requests",
        "ftplib",
        "smtplib",
        "tempfile",
        "__builtin__",
        "builtins",
        "importlib",
        "eval",
        "exec",
        "compile",
        "__import__",
    }

    # noinspection SpellCheckingInspection
    DANGEROUS_FUNCTIONS: ClassVar[set[str]] = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "file",
        "input",
        "raw_input",
        "execfile",
        "setuid",
        "setgid",
        "seteuid",
        "setegid",
        "setreuid",
        "setregid",
        "getenv",
        "environ",
    }

    DANGEROUS_ATTRIBUTES: ClassVar[set[str]] = {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__globals__",
        "__code__",
        "__builtins__",
        "__dict__",
        "__func__",
        "__module__",
        "__name__",
        "environ",
        "setuid",
        "setgid",
        "seteuid",
    }

    ALLOWED_MODULES: ClassVar[set[str]] = {
        "datetime",
        "json",
        "re",
        "math",
        "collections",
        "itertools",
        "functools",
        "operator",
        "decimal",
    }

    MAX_CODE_LENGTH = 10000
    MAX_LOOP_ITERATIONS = 10000

    @classmethod
    def validate_code(cls, code: str) -> dict[str, bool | str]:
        if len(code) > cls.MAX_CODE_LENGTH:
            return {"is_valid": False, "error": f"Code exceeds maximum length of {cls.MAX_CODE_LENGTH} characters"}

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"is_valid": False, "error": f"Syntax error: {e}"}

        validator = SecurityValidator()
        try:
            validator.visit(tree)
        except SecurityError as e:
            return {"is_valid": False, "error": str(e)}

        suspicious_patterns = [
            (r"__[a-zA-Z]+__", "Security violation: Access to special attributes"),
            (r"\.\.\/", "Security violation: Path traversal attempt"),
            (r"chr\s*\(\s*\d+\s*\)", "Security violation: Character code manipulation"),
            (r"\\x[0-9a-fA-F]{2}", "Security violation: Hex character codes"),
            (r"base64", "Security violation: Base64 encoding/decoding"),
            (r"\bsudo\b", "Security violation: Sudo usage detected"),
            (r"\.system\s*\(", "Security violation: System call detected"),
            (r"\.run\s*\(", "Security violation: Process execution detected"),
        ]

        for pattern, description in suspicious_patterns:
            if re.search(pattern, code):
                return {"is_valid": False, "error": f"Suspicious pattern detected: {description}"}

        return {"is_valid": True, "message": "Code passed security validation"}

    @classmethod
    def sanitize_code(cls, code: str) -> str:
        return code.strip()

        # Don't try to auto-fix dangerous code, just validate it


class SecurityError(Exception):
    pass


class SecurityValidator(ast.NodeVisitor):
    def __init__(self) -> None:
        self.in_loop = False
        self.loop_depth = 0

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in CodeSecurityValidator.DANGEROUS_IMPORTS:
                raise SecurityError(f"Security violation: Import of potentially dangerous module '{module_name}' is not allowed")
            if module_name not in CodeSecurityValidator.ALLOWED_MODULES and not module_name.startswith("odoo"):
                raise SecurityError(f"Security restriction: Import of module '{module_name}' is not explicitly allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in CodeSecurityValidator.DANGEROUS_IMPORTS:
                raise SecurityError(f"Security violation: Import from potentially dangerous module '{module_name}' is not allowed")
            if module_name not in CodeSecurityValidator.ALLOWED_MODULES and not module_name.startswith("odoo"):
                raise SecurityError(f"Security restriction: Import from module '{module_name}' is not explicitly allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in CodeSecurityValidator.DANGEROUS_FUNCTIONS:
                raise SecurityError(f"Security violation: Call to potentially dangerous function '{node.func.id}' is not allowed")
        elif isinstance(node.func, ast.Attribute) and node.func.attr in CodeSecurityValidator.DANGEROUS_FUNCTIONS:
            raise SecurityError(f"Security violation: Call to potentially dangerous method '{node.func.attr}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in CodeSecurityValidator.DANGEROUS_ATTRIBUTES:
            raise SecurityError(f"Security violation: Access to potentially dangerous attribute '{node.attr}' is not allowed")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.loop_depth += 1
        if self.loop_depth > CodeSecurityValidator.MAX_LOOP_DEPTH:
            raise SecurityError(f"Nested loops exceed maximum depth of {CodeSecurityValidator.MAX_LOOP_DEPTH}")
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        self.loop_depth += 1
        if self.loop_depth > CodeSecurityValidator.MAX_LOOP_DEPTH:
            raise SecurityError(f"Nested loops exceed maximum depth of {CodeSecurityValidator.MAX_LOOP_DEPTH}")

        if not self._has_break_condition(node):
            raise SecurityError("While loop must have a clear termination condition")

        self.generic_visit(node)
        self.loop_depth -= 1

    @staticmethod
    def _has_break_condition(node: ast.While) -> bool:
        return any(isinstance(child, ast.Break) for child in ast.walk(node))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("_"):
            raise SecurityError(f"Definition of private function '{node.name}' is not allowed")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name.startswith("_"):
            raise SecurityError(f"Definition of private async function '{node.name}' is not allowed")
        self.generic_visit(node)


def validate_and_sanitize_code(code: str) -> tuple[bool, str, str]:
    sanitized_code = CodeSecurityValidator.sanitize_code(code)

    result = CodeSecurityValidator.validate_code(sanitized_code)

    is_valid = result["is_valid"]
    message = result.get("error", result.get("message", ""))

    return is_valid, message, sanitized_code
