from typing import TYPE_CHECKING, Any

from ...core.utils import PaginationParams, paginate_dict_list

if TYPE_CHECKING:
    from ...type_defs.odoo_types import CompatibleEnvironment


async def search_decorators(
    env: "CompatibleEnvironment", decorator: str, pagination: PaginationParams | None = None
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

    try:
        result = await env.execute_code(code)

        if pagination and "results" in result:
            # Apply pagination to the results
            paginated_result = paginate_dict_list(result["results"], pagination, ["model", "description"])

            return {"decorator": decorator, "results": paginated_result.to_dict()}

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "decorator": decorator,
        }
