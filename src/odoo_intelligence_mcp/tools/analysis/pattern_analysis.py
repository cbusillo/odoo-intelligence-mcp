from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment


async def analyze_patterns(
    env: CompatibleEnvironment, pattern_type: str = "all", pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    # Execute pattern collection in Odoo environment
    collection_code = f"""
import inspect

pattern_type = {pattern_type!r}

patterns = {{
    "computed_fields": [],
    "related_fields": [],
    "api_decorators": [],
    "custom_methods": [],
    "state_machines": []
}}

def safe_serialize(obj):
    \"\"\"Ensure all objects are JSON serializable\"\"\"
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {{k: safe_serialize(v) for k, v in obj.items()}}
    else:
        return str(obj)

def get_decorators(func):
    decorators = []
    if hasattr(func, "_constrains"):
        decorators.append({{
            "type": "constrains",
            "fields": list(func._constrains) if func._constrains else []
        }})
    if hasattr(func, "_depends"):
        decorators.append({{
            "type": "depends", 
            "fields": list(func._depends) if func._depends else []
        }})
    if hasattr(func, "_onchange"):
        decorators.append({{
            "type": "onchange",
            "fields": list(func._onchange) if func._onchange else []
        }})
    if hasattr(func, "__name__") and func.__name__ in ["create", "write", "unlink"]:
        decorators.append({{
            "type": "model_create_multi" if func.__name__ == "create" else func.__name__,
            "fields": []
        }})
    return decorators

# Get all model names from the registry
model_names = list(env.registry.models.keys())

for model_name in model_names:
    try:
        model = env[model_name]
        model_class = type(model)

        # Get fields using fields_get() which includes inherited fields
        fields_info = model.fields_get()

        # Collect computed fields
        for field_name, field_data in fields_info.items():
            if field_data.get("compute"):
                patterns["computed_fields"].append({{
                    "model": model_name,
                    "field": field_name,
                    "compute_method": safe_serialize(field_data.get("compute")),
                    "store": field_data.get("store", False),
                    "depends": safe_serialize(field_data.get("depends", [])),
                }})

            # Collect related fields
            if field_data.get("related"):
                patterns["related_fields"].append({{
                    "model": model_name,
                    "field": field_name,
                    "related_path": safe_serialize(field_data.get("related")),
                    "store": field_data.get("store", True),
                }})

            # Collect state machines (selection fields named state)
            if field_name == "state" and field_data.get("type") == "selection":
                selection = field_data.get("selection", [])
                if selection:
                    patterns["state_machines"].append({{
                        "model": model_name,
                        "states": safe_serialize(selection),
                        "field_type": field_data.get("type"),
                    }})

        # Collect decorated and custom methods
        for method_name, method in inspect.getmembers(model_class, inspect.isfunction):
            if not method_name.startswith("_"):
                decorators = get_decorators(method)
                
                # Add to api_decorators
                for decorator in decorators:
                    patterns["api_decorators"].append({{
                        "model": model_name,
                        "method": method_name,
                        "decorator_type": safe_serialize(decorator["type"]),
                        "decorator_fields": safe_serialize(decorator["fields"]),
                    }})

                # Add to custom_methods if not standard method
                if method_name not in ["create", "write", "unlink", "search", "browse", "read", "exists"]:
                    try:
                        signature = str(inspect.signature(method))
                    except Exception:
                        signature = "unable_to_inspect"
                    
                    patterns["custom_methods"].append({{
                        "model": model_name,
                        "method": method_name,
                        "signature": safe_serialize(signature),
                        "has_decorators": bool(decorators),
                    }})
    except Exception:
        continue

result = patterns
"""

    try:
        raw_patterns = await env.execute_code(collection_code)

        if isinstance(raw_patterns, dict) and "error" in raw_patterns:
            return raw_patterns

        # Define search fields based on pattern type
        search_fields_map = {
            "computed_fields": ["model", "field", "compute_method"],
            "related_fields": ["model", "field", "related_path"],
            "api_decorators": ["model", "method", "decorator_type"],
            "custom_methods": ["model", "method"],
            "state_machines": ["model"],
        }

        # Apply filtering and pagination based on pattern type
        if pattern_type != "all":
            pattern_data = raw_patterns.get(pattern_type, [])
            if not isinstance(pattern_data, list):
                return {"error": f"Invalid pattern type: {pattern_type}"}

            search_fields = search_fields_map.get(pattern_type, ["model"])
            paginated_result = paginate_dict_list(pattern_data, pagination, search_fields)

            return validate_response_size({pattern_type: paginated_result.to_dict()})

        else:
            # Return all patterns with pagination for each type
            result = {}
            for key, data in raw_patterns.items():
                if isinstance(data, list):
                    search_fields = search_fields_map.get(key, ["model"])
                    paginated_data = paginate_dict_list(data, pagination, search_fields)
                    result[key] = paginated_data.to_dict()

            return validate_response_size(result)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "pattern_type": pattern_type,
        }
