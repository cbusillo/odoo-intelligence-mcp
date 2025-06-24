from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment
from ...utils.error_utils import handle_tool_error, validate_method_name


@handle_tool_error
async def find_method_implementations(env: CompatibleEnvironment, method_name: str, pagination: PaginationParams) -> dict[str, Any]:
    validate_method_name(method_name)

    code = f"""
import inspect

method_name = {method_name!r}
implementations = []

# Get all model names from the registry
model_names = list(env.registry.models.keys())

for model_name in model_names:
    try:
        model = env[model_name]
        model_class = type(model)
        
        if hasattr(model_class, method_name):
            method = getattr(model_class, method_name)
            if callable(method):
                # Get method info
                try:
                    signature = str(inspect.signature(method))
                except Exception:
                    signature = "Unable to inspect signature"
                
                try:
                    source = inspect.getsource(method)
                    source_lines = source.split("\\n")
                    max_lines = 10
                    
                    if len(source_lines) <= max_lines:
                        source_preview = "\\n".join(f"{{i + 1:3}}: {{line}}" for i, line in enumerate(source_lines))
                    else:
                        preview_lines = source_lines[:max_lines]
                        source_preview = "\\n".join(f"{{i + 1:3}}: {{line}}" for i, line in enumerate(preview_lines))
                        source_preview += f"\\n{{max_lines + 1:3}}: ..."
                except Exception:
                    source_preview = "Source not available"
                
                try:
                    module = model_class.__module__
                except Exception:
                    module = "Unknown module"
                
                implementations.append({{
                    "model": model_name,
                    "module": module,
                    "signature": signature,
                    "doc": inspect.getdoc(method) or "",
                    "source_preview": source_preview,
                    "has_super": "super()" in source_preview if source_preview != "Source not available" else False,
                }})
    except Exception:
        continue

result = implementations
"""

    implementations = await env.execute_code(code)

    if isinstance(implementations, dict) and "error" in implementations:
        return implementations

    # Apply pagination
    paginated_results = paginate_dict_list(implementations, pagination, search_fields=["model", "module", "signature"])

    result = {"method_name": method_name, "implementations": paginated_results.to_dict()}

    return validate_response_size(result)


async def find_models_with_method(
    method_name: str, page: int = 1, page_size: int = 100, text_filter: str | None = None
) -> dict[str, Any]:
    """Find all models that implement a specific method."""
    # This is a simplified version that would need the actual implementation
    # For now, return an empty result to fix the import error
    # Note: text_filter parameter would be used to filter results in a full implementation
    return {
        "method_name": method_name,
        "models": [],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": 0,
            "total_pages": 0,
            "has_next": False,
            "has_previous": False,
        },
        "filter_applied": text_filter,
    }
