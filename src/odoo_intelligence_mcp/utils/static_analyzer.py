import ast
import re
from pathlib import Path
from typing import Any

from ..core.env import load_env_config


class OdooStaticAnalyzer:
    def __init__(self, addon_paths: list[str] | None = None) -> None:
        if addon_paths is None:
            config = load_env_config()
            self.addon_paths = config.addons_path.split(",")
        else:
            self.addon_paths = addon_paths
        self._model_cache: dict[str, dict[str, Any]] = {}

    def find_model_file(self, model_name: str) -> Path | None:
        for addon_path in self.addon_paths:
            base_path = Path(addon_path)
            if not base_path.exists():
                continue

            for addon_dir in base_path.iterdir():
                if not addon_dir.is_dir():
                    continue

                models_dir = addon_dir / "models"
                if not models_dir.exists():
                    continue

                for py_file in models_dir.glob("*.py"):
                    if py_file.name == "__init__.py":
                        continue

                    try:
                        content = py_file.read_text()
                        if f'_name = "{model_name}"' in content or f"_name = '{model_name}'" in content:
                            return py_file
                    except (OSError, UnicodeDecodeError, PermissionError):
                        continue

        return None

    def analyze_model_file(self, file_path: Path) -> dict[str, Any]:
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            return self._extract_model_info(tree, content)
        except Exception as e:
            return {"error": f"Failed to analyze {file_path}: {e}"}

    def _extract_model_info(self, tree: ast.AST, source: str) -> dict[str, Any]:
        info: dict[str, Any] = {
            "fields": {},
            "methods": {},
            "decorators": {"depends": [], "constrains": [], "onchange": [], "model_create_multi": []},
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                info["class_name"] = node.name

                for item in node.body:
                    if isinstance(item, ast.Assign):
                        self._analyze_field_assignment(item, source, info)
                    elif isinstance(item, ast.FunctionDef):
                        self._analyze_method(item, source, info)

        return info

    def _analyze_field_assignment(self, node: ast.Assign, source: str, info: dict[str, Any]) -> None:
        if not node.targets or not isinstance(node.targets[0], ast.Name):
            return

        target = node.targets[0]
        assert isinstance(target, ast.Name)  # Type narrowing for PyCharm
        field_name = target.id

        if isinstance(node.value, ast.Call):
            field_info = self._extract_field_info(node.value, source)
            if field_info:
                info["fields"][field_name] = field_info

    def _extract_field_info(self, call_node: ast.Call, source: str) -> dict[str, Any] | None:
        if not isinstance(call_node.func, ast.Attribute) or not hasattr(call_node.func, "attr"):
            return None

        field_type = call_node.func.attr
        field_info = {"type": field_type, "parameters": {}}

        for keyword in call_node.keywords:
            if keyword.arg:
                param_value = self._extract_keyword_value(keyword.value, source)
                field_info["parameters"][keyword.arg] = param_value

        return field_info

    # noinspection PyTypeHints
    def _extract_keyword_value(self, node: ast.expr, source: str) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return [self._extract_keyword_value(elt, source) for elt in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(self._extract_keyword_value(elt, source) for elt in node.elts)
        else:
            start_pos = node.col_offset if hasattr(node, "col_offset") else 0
            end_pos = node.end_col_offset if hasattr(node, "end_col_offset") else start_pos + 10
            lines = source.splitlines()
            if hasattr(node, "lineno") and node.lineno <= len(lines):
                line = lines[node.lineno - 1]
                return line[start_pos:end_pos].strip()
            return str(type(node).__name__)

    def _analyze_method(self, node: ast.FunctionDef, source: str, info: dict[str, Any]) -> None:
        method_info = {
            "name": node.name,
            "decorators": [],
            "signature": self._get_method_signature(node),
        }

        for decorator in node.decorator_list:
            # noinspection PyTypeChecker
            decorator_info = self._analyze_decorator(decorator, source)
            if decorator_info:
                method_info["decorators"].append(decorator_info)

                if "api.depends" in decorator_info["name"]:
                    info["decorators"]["depends"].append(
                        {
                            "method": node.name,
                            "depends_on": decorator_info.get("args", []),
                        }
                    )
                elif "api.constrains" in decorator_info["name"]:
                    info["decorators"]["constrains"].append(
                        {
                            "method": node.name,
                            "constrains": decorator_info.get("args", []),
                        }
                    )
                elif "api.onchange" in decorator_info["name"]:
                    info["decorators"]["onchange"].append(
                        {
                            "method": node.name,
                            "onchange": decorator_info.get("args", []),
                        }
                    )
                elif "api.model_create_multi" in decorator_info["name"]:
                    info["decorators"]["model_create_multi"].append(
                        {
                            "method": node.name,
                        }
                    )

        info["methods"][node.name] = method_info

    def _analyze_decorator(self, node: ast.AST, source: str) -> dict[str, Any] | None:
        if isinstance(node, ast.Name):
            return {"name": node.id}
        elif isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            return {"name": ".".join(parts)}
        elif isinstance(node, ast.Call):
            # noinspection PyTypeChecker
            base_info = self._analyze_decorator(node.func, source)
            if base_info:
                args = []
                for arg in node.args:
                    if isinstance(arg, ast.Constant):
                        args.append(arg.value)
                base_info["args"] = args
                return base_info
        return None

    @staticmethod
    def _get_method_signature(node: ast.FunctionDef) -> str:
        args = [arg.arg for arg in node.args.args]
        # noinspection PyTypeChecker
        return f"({', '.join(args)})"

    def find_state_fields(self, model_name: str) -> dict[str, Any]:
        file_path = self.find_model_file(model_name)
        if not file_path:
            return {}

        model_info = self.analyze_model_file(file_path)
        state_fields = {}

        for field_name, field_info in model_info.get("fields", {}).items():
            if field_info["type"] == "Selection" and ("state" in field_name.lower() or "status" in field_name.lower()):
                state_fields[field_name] = field_info

        return state_fields

    def find_computed_fields(self, model_name: str) -> dict[str, Any]:
        file_path = self.find_model_file(model_name)
        if not file_path:
            return {}

        model_info = self.analyze_model_file(file_path)

        return {
            field_name: {
                "type": field_info["type"],
                "compute_method": field_info["parameters"]["compute"],
                "store": field_info["parameters"].get("store", False),
                "depends": self._find_compute_dependencies(model_info, field_info["parameters"]["compute"]),
            }
            for field_name, field_info in model_info.get("fields", {}).items()
            if "compute" in field_info.get("parameters", {})
        }

    @staticmethod
    def _find_compute_dependencies(model_info: dict[str, Any], compute_method: str) -> list[str]:
        for decorator_info in model_info.get("decorators", {}).get("depends", []):
            if decorator_info["method"] == compute_method:
                return decorator_info["depends_on"]
        return []

    def find_related_fields(self, model_name: str) -> dict[str, Any]:
        file_path = self.find_model_file(model_name)
        if not file_path:
            return {}

        model_info = self.analyze_model_file(file_path)
        related_fields = {}

        for field_name, field_info in model_info.get("fields", {}).items():
            if "related" in field_info.get("parameters", {}):
                related_fields[field_name] = {
                    "type": field_info["type"],
                    "related_path": field_info["parameters"]["related"],
                }

        return related_fields

    # noinspection PyTooManyBranches
    def search_decorators_in_files(self, decorator_type: str) -> list[dict[str, Any]]:
        results = []
        decorator_patterns = {
            "depends": r"@api\.depends\s*\((.*?)\)",
            "constrains": r"@api\.constrains\s*\((.*?)\)",
            "onchange": r"@api\.onchange\s*\((.*?)\)",
            "model_create_multi": r"@api\.model_create_multi",
        }

        pattern = decorator_patterns.get(decorator_type)
        if not pattern:
            return results

        for addon_path in self.addon_paths:
            base_path = Path(addon_path)
            if not base_path.exists():
                continue

            for py_file in base_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue

                try:
                    content = py_file.read_text()
                    model_name = self._extract_model_name(content)
                    if not model_name:
                        continue

                    matches = re.finditer(pattern, content, re.DOTALL | re.MULTILINE)
                    for match in matches:
                        method_name = self._find_method_name_after_decorator(content, match.start())
                        if method_name:
                            result: dict[str, Any] = {
                                "model": model_name,
                                "method": method_name,
                                "file": str(py_file),
                            }

                            if decorator_type in ["depends", "constrains", "onchange"]:
                                args_str = match.group(1)
                                args = self._parse_decorator_args(args_str)
                                result[decorator_type] = args

                            results.append(result)

                except (SyntaxError, UnicodeDecodeError, OSError):
                    continue

        return results

    @staticmethod
    def _extract_model_name(content: str) -> str | None:
        match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', content)
        return match.group(1) if match else None

    @staticmethod
    def _find_method_name_after_decorator(content: str, decorator_pos: int) -> str | None:
        after_decorator = content[decorator_pos:]
        match = re.search(r"def\s+(\w+)\s*\(", after_decorator)
        return match.group(1) if match else None

    @staticmethod
    def _parse_decorator_args(args_str: str) -> list[str]:
        args_str = args_str.strip()
        if not args_str:
            return []

        args = []
        for arg in re.findall(r'["\']([^"\']+)["\']', args_str):
            args.append(arg)
        return args
