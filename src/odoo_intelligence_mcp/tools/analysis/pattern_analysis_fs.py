from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ..ast import build_ast_index
from .pattern_analysis import VALID_PATTERN_TYPES


async def analyze_patterns_fs(pattern_type: str = "all", pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    pattern_type = (pattern_type or "all").strip()
    if pattern_type not in VALID_PATTERN_TYPES:
        return {
            "success": False,
            "error": f"Invalid pattern_type '{pattern_type}'.",
            "valid_pattern_types": VALID_PATTERN_TYPES,
            "example": {"pattern_type": "computed_fields"},
            "mode_used": "fs",
            "data_quality": "approximate",
        }

    idx = await build_ast_index()
    models = idx.get("models", {}) if isinstance(idx, dict) else {}

    computed_fields: list[dict[str, Any]] = []
    related_fields: list[dict[str, Any]] = []
    api_decorators: list[dict[str, Any]] = []
    custom_methods: list[dict[str, Any]] = []
    state_machines: list[dict[str, Any]] = []

    for model_name, meta in models.items():
        modules = meta.get("module") or ""
        file_path = meta.get("file") or ""
        # fields
        for fname, f in meta.get("fields", {}).items():
            if f.get("compute"):
                computed_fields.append(
                    {
                        "model": model_name,
                        "modules": modules,
                        "file": file_path,
                        "field": fname,
                        "compute_method": f.get("compute"),
                        "store": bool(f.get("store")),
                        "depends": [],
                    }
                )
            if f.get("related"):
                related_fields.append(
                    {
                        "model": model_name,
                        "modules": modules,
                        "file": file_path,
                        "field": fname,
                        "related_path": f.get("related"),
                        "store": bool(f.get("store", True)),
                    }
                )
            if fname == "state" and f.get("type") == "selection" and isinstance(f.get("selection"), list):
                state_machines.append(
                    {
                        "model": model_name,
                        "modules": modules,
                        "file": file_path,
                        "states": f.get("selection"),
                        "field_type": "selection",
                    }
                )

        # decorators and methods
        decs = meta.get("decorators", {})
        for method, lst in decs.items():
            for d in lst:
                api_decorators.append(
                    {
                        "model": model_name,
                        "modules": modules,
                        "file": file_path,
                        "method": method,
                        "decorator_type": d.get("type"),
                        "decorator_fields": d.get("args", []),
                    }
                )

        for method in meta.get("methods", []):
            if method not in {"create", "write", "unlink", "search", "browse", "read", "exists"}:
                custom_methods.append(
                    {
                        "model": model_name,
                        "modules": modules,
                        "file": file_path,
                        "method": method,
                        "signature": f"{method}(self, *args, **kwargs)",
                        "has_decorators": method in decs,
                    }
                )

    all_data = {
        "computed_fields": computed_fields,
        "related_fields": related_fields,
        "api_decorators": api_decorators,
        "custom_methods": custom_methods,
        "state_machines": state_machines,
    }

    if pattern_type != "all":
        items = all_data.get(pattern_type, [])
        paginated = paginate_dict_list(items, pagination, ["model", "modules", "file"]) if items else None
        return validate_response_size(
            {
                pattern_type: paginated.to_dict() if paginated else {"items": [], "pagination": {"total_count": 0}},
                "mode_used": "fs",
                "data_quality": "approximate",
            }
        )

    result: dict[str, Any] = {}
    for key, items in all_data.items():
        paginated = paginate_dict_list(items, pagination, ["model", "modules", "file"]) if items else None
        result[key] = paginated.to_dict() if paginated else {"items": [], "pagination": {"total_count": 0}}
    result["mode_used"] = "fs"
    result["data_quality"] = "approximate"
    return validate_response_size(result)
