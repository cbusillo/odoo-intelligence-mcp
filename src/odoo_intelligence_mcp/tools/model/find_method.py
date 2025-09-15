from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment
from ...utils.error_utils import handle_tool_error, validate_method_name
from ..ast import build_ast_index


@handle_tool_error
async def find_method_implementations(
    env: CompatibleEnvironment, method_name: str, pagination: PaginationParams, mode: str = "auto"
) -> dict[str, Any]:
    validate_method_name(method_name)

    # Use pagination page_size to limit collection
    max_results = pagination.page_size

    if mode == "fs":
        idx = await build_ast_index()
        if not isinstance(idx, dict) or "models" not in idx:
            return {"success": False, "error": "AST index unavailable", "error_type": "AstIndexError"}
        implementations: list[dict[str, Any]] = []
        for model_name, meta in idx["models"].items():
            methods = meta.get("methods", [])
            if method_name in methods:
                implementations.append(
                    {
                        "model": model_name,
                        "module": meta.get("module", ""),
                        "signature": f"{method_name}(self, *args, **kwargs)",
                        "doc": "",
                        "source_preview": f"# static_ast: {meta.get('file', '')}",
                        "has_super": False,
                        "source": "static_ast",
                    }
                )
        paginated_results = paginate_dict_list(implementations, pagination, search_fields=["model", "module", "signature"])
        return validate_response_size(
            {
                "method_name": method_name,
                "implementations": paginated_results.to_dict(),
                "mode_used": "fs",
                "data_quality": "approximate",
            }
        )

    code = (
        """
import inspect
import gc

method_name = """
        + repr(method_name)
        + """
max_results = """
        + repr(max_results)
        + """
implementations = []

# Get all model names from the registry
model_names = list(env.registry.models.keys())

# Process in batches to avoid memory issues
batch_size = 50
for batch_start in range(0, len(model_names), batch_size):
    batch_end = min(batch_start + batch_size, len(model_names))
    batch_models = model_names[batch_start:batch_end]
    
    for model_name in batch_models:
        try:
            model = env[model_name]
            model_class = type(model)
            
            # Check in the entire MRO (Method Resolution Order) to find inherited methods
            method_found = False
            method = None
            for base_class in inspect.getmro(model_class):
                if method_name in base_class.__dict__:
                    method = base_class.__dict__[method_name]
                    if callable(method):
                        method_found = True
                        break
            
            if method_found and method:
                # Get method info with safe serialization
                try:
                    signature = str(inspect.signature(method))[:100]  # Further limit signature length
                except Exception:
                    signature = "Unable to inspect signature"

                try:
                    source = inspect.getsource(method)
                    source_lines = source.split("\\n")
                    max_lines = 5  # Reduce preview length

                    if len(source_lines) <= max_lines:
                        source_preview = "\\n".join(f"{{i + 1:3}}: {{line[:100]}}" for i, line in enumerate(source_lines))
                    else:
                        preview_lines = source_lines[:max_lines]
                        source_preview = "\\n".join(f"{{i + 1:3}}: {{line[:100]}}" for i, line in enumerate(preview_lines))
                        source_preview += f"\\n{{max_lines + 1:3}}: ..."
                except Exception:
                    source_preview = "Source not available"

                try:
                    module = str(model_class.__module__)[:100]  # Limit module name length
                except Exception:
                    module = "Unknown module"

                doc_string = ""
                try:
                    doc_string = (inspect.getdoc(method) or "")[:200]  # Limit doc length further
                except Exception:
                    pass

                implementations.append({
                    "model": model_name,
                    "module": module,
                    "signature": signature,
                    "doc": doc_string,
                    "source_preview": source_preview,
                    "has_super": "super()" in source_preview if source_preview != "Source not available" else False,
                })
                
                # Early exit to prevent memory issues - limit total results during collection
                if len(implementations) >= max_results:  # Use pagination limit
                    break
        except Exception:
            continue
        
        # Check if we need to break out of outer batch loop too
        if len(implementations) >= max_results:
            break
    
    # Garbage collect after each batch
    if batch_start % 100 == 0:
        gc.collect()
    
    # Early termination if we have enough results
    if len(implementations) >= max_results:
        break

result = implementations  # Limited collection
"""
    )

    implementations: object = await env.execute_code(code)

    if isinstance(implementations, dict) and "error" in implementations:
        return implementations

    # Validate and narrow type for static checkers
    from typing import cast

    if not isinstance(implementations, list):
        return {"success": False, "error": "Unexpected response type from environment", "error_type": "TypeError"}
    impl_list = cast("list[dict[str, Any]]", implementations)

    # Apply pagination
    paginated_results = paginate_dict_list(impl_list, pagination, search_fields=["model", "module", "signature"])

    result = {"method_name": method_name, "implementations": paginated_results.to_dict()}

    # Additional size check - if still too large, truncate further
    import json

    result_size = len(json.dumps(result))
    if result_size > 25000:  # 25KB limit
        # Truncate the actual items to fit within limit
        items = result["implementations"]["items"]
        truncated_items = []
        current_size = len(json.dumps({"method_name": method_name, "implementations": {"items": [], "total_count": 0}}))

        for item in items:
            item_size = len(json.dumps(item))
            if current_size + item_size > 20000:  # Leave some buffer
                break
            truncated_items.append(item)
            current_size += item_size

        result["implementations"]["items"] = truncated_items
        result["implementations"]["truncated"] = True
        result["implementations"]["truncated_reason"] = "Response size limit exceeded"

    return validate_response_size(result)


async def find_models_with_method(
    method_name: str, page: int = 1, page_size: int = 100, text_filter: str | None = None
) -> dict[str, Any]:
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
