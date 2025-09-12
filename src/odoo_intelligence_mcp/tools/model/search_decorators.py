from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ...type_defs.odoo_types import CompatibleEnvironment
from ..ast import build_ast_index


async def search_decorators(
    env: CompatibleEnvironment, decorator: str, pagination: PaginationParams | None = None, mode: str = "auto"
) -> dict[str, Any]:
    code = f"""
import inspect

decorator = {decorator!r}

# Get all model names from the registry
model_names = list(env.registry.models.keys())

results = []

for model_name in model_names:
    try:
        model = env[model_name]
        model_class = type(model)
        matching_methods = []

        for name, method in inspect.getmembers(model_class, inspect.isfunction):
            if not name.startswith("_"):
                method_info = None

                if decorator == "depends" and hasattr(method, "_depends"):
                    method_info = {{
                        "method": name,
                        "depends_on": list(method._depends),
                        "signature": str(inspect.signature(method)),
                    }}
                elif decorator == "constrains" and hasattr(method, "_constrains"):
                    method_info = {{
                        "method": name,
                        "constrains": list(method._constrains),
                        "signature": str(inspect.signature(method)),
                    }}
                elif decorator == "onchange" and hasattr(method, "_onchange"):
                    method_info = {{
                        "method": name,
                        "onchange": list(method._onchange),
                        "signature": str(inspect.signature(method)),
                    }}
                elif decorator == "model_create_multi" and name == "create":
                    # Check if method has model_create_multi decorator
                    if hasattr(method, "_model_create_multi") or "create_multi" in str(method):
                        method_info = {{
                            "method": name,
                            "decorator": "@api.model_create_multi",
                            "signature": str(inspect.signature(method)),
                        }}

                if method_info:
                    matching_methods.append(method_info)

        if matching_methods:
            results.append({{
                "model": model_name,
                "description": getattr(model, "_description", ""),
                "methods": matching_methods
            }})
    except Exception:
        continue

result = {{"results": results}}
"""

    if mode == "fs":
        idx = await build_ast_index()
        if not isinstance(idx, dict) or "models" not in idx:
            return {"success": False, "error": "AST index unavailable", "error_type": "AstIndexError"}

        results = []
        for model_name, meta in idx["models"].items():
            decs = meta.get("decorators", {})
            matches = []
            for method, lst in decs.items():
                for d in lst:
                    if d.get("type") == decorator:
                        matches.append(
                            {
                                "method": method,
                                "signature": f"{method}(self, *args, **kwargs)",
                            }
                        )
                        break
            if matches:
                results.append({"model": model_name, "description": meta.get("description") or "", "methods": matches})

        if pagination:
            paginated_result = paginate_dict_list(results, pagination, ["model", "description"])
            return {"decorator": decorator, "results": paginated_result.to_dict(), "mode_used": "fs", "data_quality": "approximate"}
        return {"decorator": decorator, "results": results, "mode_used": "fs", "data_quality": "approximate"}

    try:
        result = await env.execute_code(code)

        # Extract the actual result data from execute_code response
        if "result" in result and isinstance(result["result"], dict):
            data = result["result"]
        else:
            data = result

        if pagination and "results" in data:
            # Apply pagination to the results
            results_list = data["results"]
            assert isinstance(results_list, list)  # Type assertion for PyCharm
            paginated_result = paginate_dict_list(results_list, pagination, ["model", "description"])

            return {"decorator": decorator, "results": paginated_result.to_dict()}

        return data
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "decorator": decorator,
        }
