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

    filter_text = pagination.filter_text

    # Use pagination page_size to limit collection (unless filtering)
    max_results = pagination.page_size if not filter_text else None

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
                        "source_module": meta.get("module", ""),
                        "model_module": meta.get("module", ""),
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
filter_text = """
        + repr(filter_text)
        + """
filter_text_lower = filter_text.lower() if isinstance(filter_text, str) and filter_text else None
implementations = []

def infer_source_module(module_name, source_file):
    if source_file:
        normalized = source_file.replace("\\\\", "/")
        for marker in ("/odoo/addons/", "/addons/", "/volumes/addons/", "/volumes/enterprise/"):
            if marker in normalized:
                tail = normalized.split(marker, 1)[1]
                slug = tail.split("/", 1)[0]
                if slug:
                    return slug
        if "/volumes/" in normalized:
            tail = normalized.split("/volumes/", 1)[1]
            parts = [part for part in tail.split("/") if part]
            if len(parts) >= 2 and parts[0] in ("addons", "enterprise"):
                return parts[1]
            if parts:
                return parts[0]
    if module_name:
        if ".addons." in module_name:
            tail = module_name.split(".addons.", 1)[1]
            slug = tail.split(".", 1)[0]
            if slug:
                return slug
        parts = [part for part in module_name.split(".") if part]
        if parts:
            if parts[0] == "odoo" and len(parts) > 2 and parts[1] == "addons":
                return parts[2]
            if parts[0] != "odoo":
                return parts[0]
    return ""

# Get all model names from the registry
model_names = list(env.registry.models.keys())
module_map = {}
try:
    for rec in env["ir.model"].search([]):
        if rec.model:
            module_map[rec.model] = rec.modules or ""
except Exception:
    module_map = {}

# Process in batches to avoid memory issues
batch_size = 50
for batch_start in range(0, len(model_names), batch_size):
    batch_end = min(batch_start + batch_size, len(model_names))
    batch_models = model_names[batch_start:batch_end]
    
    for model_name in batch_models:
        try:
            model = env[model_name]
            model_class = type(model)
            modules = module_map.get(model_name, "")
            model_module = getattr(model, "_module", "") or ""
            
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
                    method_module = str(getattr(method, "__module__", ""))[:200]
                except Exception:
                    method_module = ""
                try:
                    module = str(model_class.__module__)[:200]  # Limit module name length
                except Exception:
                    module = "Unknown module"
                effective_module = method_module or module
                try:
                    source_file = str(inspect.getsourcefile(method) or "")
                except Exception:
                    source_file = ""

                source_module = infer_source_module(method_module or effective_module, source_file) or model_module

                doc_string = ""
                try:
                    doc_string = (inspect.getdoc(method) or "")[:200]  # Limit doc length further
                except Exception:
                    pass

                include_match = True
                if filter_text_lower:
                    haystacks = [
                        str(model_name).lower(),
                        str(signature).lower(),
                        str(method_module).lower(),
                        str(source_file).lower(),
                        str(effective_module).lower(),
                        str(source_module).lower(),
                        str(model_module).lower(),
                    ]
                    include_match = any(filter_text_lower in value for value in haystacks if value)

                if include_match:
                    implementations.append({
                        "model": model_name,
                        "module": effective_module or module,
                        "method_module": method_module,
                        "source_file": source_file,
                        "modules": modules,
                        "source_module": source_module,
                        "model_module": model_module,
                        "signature": signature,
                        "doc": doc_string,
                        "source_preview": source_preview,
                        "has_super": "super()" in source_preview if source_preview != "Source not available" else False,
                    })
                
                # Early exit to prevent memory issues - limit total results during collection
                if max_results is not None and len(implementations) >= max_results:  # Use pagination limit
                    break
        except Exception:
            continue
        
        # Check if we need to break out of outer batch loop too
        if max_results is not None and len(implementations) >= max_results:
            break
    
    # Garbage collect after each batch
    if batch_start % 100 == 0:
        gc.collect()
    
    # Early termination if we have enough results
    if max_results is not None and len(implementations) >= max_results:
        break

result = implementations  # Limited collection
"""
    )

    implementations: object = await env.execute_code(code)

    if isinstance(implementations, dict) and "error" in implementations:
        return implementations

    if not isinstance(implementations, list):
        return {"success": False, "error": "Unexpected response type from environment", "error_type": "TypeError"}
    impl_list = implementations

    # Apply pagination (avoid re-filtering by installed modules)
    if pagination.filter_text:
        pagination = PaginationParams(page=pagination.page, page_size=pagination.page_size, filter_text=None)
    paginated_results = paginate_dict_list(
        impl_list,
        pagination,
        search_fields=["model", "module", "method_module", "source_file", "signature"],
    )

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
