from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment

VALID_PATTERN_TYPES = [
    "computed_fields",
    "related_fields",
    "api_decorators",
    "custom_methods",
    "state_machines",
    "all",
]


async def analyze_patterns(
    env: CompatibleEnvironment, pattern_type: str = "all", pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    pattern_type = (pattern_type or "all").strip()
    if pattern_type not in VALID_PATTERN_TYPES:
        return {
            "success": False,
            "error": f"Invalid pattern_type '{pattern_type}'.",
            "valid_pattern_types": VALID_PATTERN_TYPES,
            "example": {"pattern_type": "computed_fields"},
        }

    # Execute pattern collection in Odoo environment with batching for memory efficiency
    collection_code = (
        """
import inspect
import gc  # For garbage collection

pattern_type = """
        + repr(pattern_type)
        + """

patterns = {
    "computed_fields": [],
    "related_fields": [],
    "api_decorators": [],
    "custom_methods": [],
    "state_machines": []
}

def safe_serialize(obj):
    \"\"\"Ensure all objects are JSON serializable\"\"\"
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj[:10]]  # Limit list size
    elif isinstance(obj, dict):
        return {k: safe_serialize(v) for k, v in list(obj.items())[:10]}  # Limit dict size
    else:
        return str(obj)[:100]  # Limit string representation

def get_decorators(func):
    decorators = []
    if hasattr(func, "_constrains"):
        decorators.append({
            "type": "constrains",
            "fields": list(func._constrains) if func._constrains else []
        })
    if hasattr(func, "_depends"):
        decorators.append({
            "type": "depends",
            "fields": list(func._depends) if func._depends else []
        })
    if hasattr(func, "_onchange"):
        decorators.append({
            "type": "onchange",
            "fields": list(func._onchange) if func._onchange else []
        })
    if hasattr(func, "__name__") and func.__name__ in ["create", "write", "unlink"]:
        decorators.append({
            "type": "model_create_multi" if func.__name__ == "create" else func.__name__,
            "fields": []
        })
    return decorators

# Get all model names from the registry and process in batches
model_names = list(env.registry.models.keys())
module_map = {}
try:
    for rec in env["ir.model"].search([]):
        if rec.model:
            module_map[rec.model] = rec.modules or ""
except Exception:
    module_map = {}
batch_size = 50  # Process 50 models at a time to avoid memory issues
processed_count = 0

for batch_start in range(0, len(model_names), batch_size):
    batch_end = min(batch_start + batch_size, len(model_names))
    batch_models = model_names[batch_start:batch_end]
    
    for model_name in batch_models:
        try:
            model = env[model_name]
            model_class = type(model)
            modules = module_map.get(model_name, "")

            # Use model._fields to access field objects directly
            # This gives us access to the actual field attributes
            
            # Collect computed fields
            for field_name, field in model._fields.items():
                if hasattr(field, 'compute') and field.compute:
                    compute_module = ""
                    compute_file = ""
                    try:
                        compute_method = None
                        if isinstance(field.compute, str):
                            compute_method = getattr(model, field.compute, None)
                        else:
                            compute_method = field.compute
                        if compute_method:
                            compute_module = getattr(compute_method, "__module__", "") or ""
                            try:
                                compute_file = inspect.getsourcefile(compute_method) or ""
                            except Exception:
                                compute_file = ""
                    except Exception:
                        compute_module = ""
                        compute_file = ""
                    patterns["computed_fields"].append({
                        "model": model_name,
                        "modules": modules,
                        "field": field_name,
                        "compute_method": safe_serialize(field.compute),
                        "compute_module": safe_serialize(compute_module),
                        "compute_file": safe_serialize(compute_file),
                        "store": getattr(field, 'store', False),
                        "depends": safe_serialize(getattr(field, 'depends', [])),
                    })

                # Collect related fields
                if hasattr(field, 'related') and field.related:
                    patterns["related_fields"].append({
                        "model": model_name,
                        "modules": modules,
                        "field": field_name,
                        "related_path": safe_serialize(field.related),
                        "store": getattr(field, 'store', True),
                    })

                # Collect state machines (selection fields named state)
                if field_name == "state" and getattr(field, 'type', '') == "selection":
                    selection = getattr(field, 'selection', [])
                    if selection:
                        patterns["state_machines"].append({
                            "model": model_name,
                            "modules": modules,
                            "states": safe_serialize(selection),
                            "field_type": getattr(field, 'type', ''),
                        })

            # Collect decorated and custom methods
            for method_name, method in inspect.getmembers(model_class, inspect.isfunction):
                if not method_name.startswith("_"):
                    decorators = get_decorators(method)
                    method_module = ""
                    method_file = ""
                    try:
                        method_module = getattr(method, "__module__", "") or ""
                    except Exception:
                        method_module = ""
                    try:
                        method_file = inspect.getsourcefile(method) or ""
                    except Exception:
                        method_file = ""

                    # Add to api_decorators
                    for decorator in decorators:
                        patterns["api_decorators"].append({
                            "model": model_name,
                            "modules": modules,
                            "method": method_name,
                            "decorator_type": safe_serialize(decorator["type"]),
                            "decorator_fields": safe_serialize(decorator["fields"]),
                            "method_module": safe_serialize(method_module),
                            "method_file": safe_serialize(method_file),
                        })

                    # Add to custom_methods if not standard method
                    if method_name not in ["create", "write", "unlink", "search", "browse", "read", "exists"]:
                        try:
                            signature = str(inspect.signature(method))
                        except Exception:
                            signature = "unable_to_inspect"

                        patterns["custom_methods"].append({
                            "model": model_name,
                            "modules": modules,
                            "method": method_name,
                            "signature": safe_serialize(signature),
                            "has_decorators": bool(decorators),
                            "method_module": safe_serialize(method_module),
                            "method_file": safe_serialize(method_file),
                        })
        except Exception:
            continue
    
    # Garbage collect after each batch to free memory
    processed_count += len(batch_models)
    if processed_count % 100 == 0:
        gc.collect()

result = patterns
"""
    )

    try:
        raw_patterns = await env.execute_code(collection_code)

        if isinstance(raw_patterns, dict) and "error" in raw_patterns:
            return raw_patterns

        # Define search fields based on pattern type
        search_fields_map = {
            "computed_fields": ["model", "field", "compute_method", "compute_module", "compute_file"],
            "related_fields": ["model", "field", "related_path"],
            "api_decorators": ["model", "method", "decorator_type", "method_module", "method_file"],
            "custom_methods": ["model", "method", "method_module", "method_file"],
            "state_machines": ["model"],
        }

        # Apply filtering and pagination based on pattern type
        if pattern_type != "all":
            pattern_data = raw_patterns.get(pattern_type, [])
            assert isinstance(pattern_data, list)  # Type assertion for PyCharm
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
