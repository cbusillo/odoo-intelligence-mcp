from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ...type_defs.odoo_types import CompatibleEnvironment
from ..ast import build_ast_index


async def search_decorators(
    env: CompatibleEnvironment, decorator: str, pagination: PaginationParams | None = None, mode: str = "auto"
) -> dict[str, Any]:
    filter_text = pagination.filter_text if pagination else None
    original_pagination = pagination

    def _filter_results(items: list[dict[str, Any]], needle: str) -> list[dict[str, Any]]:
        lowered = needle.lower()
        filtered: list[dict[str, Any]] = []
        for item in items:
            methods = item.get("methods", [])
            matched_methods = []
            for method_entry in methods:
                haystacks = [
                    method_entry.get("module"),
                    method_entry.get("file"),
                    method_entry.get("method"),
                    method_entry.get("signature"),
                ]
                if any(lowered in str(value).lower() for value in haystacks if value):
                    matched_methods.append(method_entry)

            item_haystacks = [
                item.get("model"),
                item.get("description"),
                item.get("module"),
                item.get("file"),
                item.get("source_module"),
                item.get("class_module"),
                item.get("class_file"),
                item.get("module_sources"),
                item.get("file_sources"),
            ]
            item_match = any(lowered in str(value).lower() for value in item_haystacks if value)

            if matched_methods:
                updated = dict(item)
                updated["methods"] = matched_methods
                filtered.append(updated)
                continue

            if item_match:
                filtered.append(item)
        return filtered

    code = f"""
import inspect

decorator = {decorator!r}

# Get all model names from the registry
model_names = list(env.registry.models.keys())
module_map = {{}}
try:
    for rec in env["ir.model"].search([]):
        if rec.model:
            module_map[rec.model] = rec.modules or ""
except Exception:
    module_map = {{}}

results = []

for model_name in model_names:
    try:
        model = env[model_name]
        model_class = type(model)
        matching_methods = []
        source_module = getattr(model, "_module", "") or ""

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
                    try:
                        method_info["module"] = str(getattr(method, "__module__", ""))[:200]
                    except Exception:
                        method_info["module"] = ""
                    try:
                        method_info["file"] = str(inspect.getsourcefile(method) or "")
                    except Exception:
                        method_info["file"] = ""
                    matching_methods.append(method_info)

        if matching_methods:
            module_sources = []
            file_sources = []
            for info in matching_methods:
                mod = info.get("module") or ""
                if mod and mod not in module_sources:
                    module_sources.append(mod)
                path = info.get("file") or ""
                if path and path not in file_sources:
                    file_sources.append(path)

            class_module = ""
            class_file = ""
            try:
                class_module = str(getattr(model_class, "__module__", ""))[:200]
            except Exception:
                class_module = ""
            try:
                class_file = str(inspect.getsourcefile(model_class) or "")
            except Exception:
                class_file = ""

            module_path = module_sources[0] if module_sources else class_module
            results.append({{
                "model": model_name,
                "description": getattr(model, "_description", ""),
                "module": module_path,
                "modules": module_map.get(model_name, ""),
                "source_module": source_module,
                "class_module": class_module,
                "class_file": class_file,
                "module_sources": module_sources,
                "file_sources": file_sources,
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
            for method_name, lst in decs.items():
                for d in lst:
                    if d.get("type") == decorator:
                        matches.append(
                            {
                                "method": method_name,
                                "signature": f"{method_name}(self, *args, **kwargs)",
                                "module": meta.get("module") or "",
                                "file": meta.get("file") or "",
                            }
                        )
                        break
            if matches:
                results.append(
                    {
                        "model": model_name,
                        "description": meta.get("description") or "",
                        "module": meta.get("module") or "",
                        "modules": meta.get("module") or "",
                        "file": meta.get("file") or "",
                        "methods": matches,
                    }
                )

        if filter_text:
            results = _filter_results(results, filter_text)
            pagination = PaginationParams(page=pagination.page, page_size=pagination.page_size)

        if pagination:
            paginated_result = paginate_dict_list(
                results,
                pagination,
                ["model", "description", "module", "modules", "file", "module_sources", "file_sources"],
            )
            return {"decorator": decorator, "results": paginated_result.to_dict(), "mode_used": "fs", "data_quality": "approximate"}
        return {"decorator": decorator, "results": results, "mode_used": "fs", "data_quality": "approximate"}

    try:
        result_payload = await env.execute_code(code)

        if not isinstance(result_payload, dict):
            return {
                "success": False,
                "error": "Unexpected execute_code response type.",
                "error_type": "ExecuteCodeResponseError",
                "decorator": decorator,
            }

        # Extract the actual result data from execute_code response
        raw_result = result_payload.get("result")
        if isinstance(raw_result, dict):
            data: dict[str, Any] = {str(key): value for key, value in raw_result.items()}
        else:
            data = result_payload

        raw_results = data.get("results")
        if filter_text and isinstance(raw_results, list) and all(isinstance(item, dict) for item in raw_results):
            typed_results: list[dict[str, Any]] = raw_results
            data["results"] = _filter_results(typed_results, filter_text)
            pagination = PaginationParams(page=pagination.page, page_size=pagination.page_size)

        if (
            mode != "fs"
            and filter_text
            and isinstance(data.get("results"), list)
            and not data.get("results")
            and original_pagination is not None
        ):
            return await search_decorators(env, decorator, original_pagination, mode="fs")

        if pagination and "results" in data:
            # Apply pagination to the results
            results_list = data["results"]
            assert isinstance(results_list, list)  # Type assertion for PyCharm
            paginated_result = paginate_dict_list(
                results_list,
                pagination,
                ["model", "description", "module", "modules", "module_sources", "file_sources"],
            )

            return {"decorator": decorator, "results": paginated_result.to_dict()}

        return data
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "decorator": decorator,
        }
