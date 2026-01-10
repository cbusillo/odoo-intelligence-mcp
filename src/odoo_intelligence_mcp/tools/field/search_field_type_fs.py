from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ..common.fs_utils import ensure_pagination, get_models_index
from .search_field_type import VALID_FIELD_TYPES


async def search_field_type_fs(field_type: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    pagination = ensure_pagination(pagination)

    models = await get_models_index()
    results: list[dict[str, Any]] = []
    field_type = field_type.lower().strip()
    if field_type not in VALID_FIELD_TYPES:
        return {
            "success": False,
            "error": f"Invalid field_type '{field_type}'.",
            "valid_types": VALID_FIELD_TYPES,
            "example": {"field_type": "char"},
        }

    for model_name, meta in models.items():
        fields = meta.get("fields", {})
        group = []
        for fname, f in fields.items():
            if f.get("type") == field_type:
                entry = {"field": fname, "string": f.get("string")}
                if field_type in ("many2one", "one2many", "many2many"):
                    entry["comodel_name"] = f.get("relation")
                group.append(entry)
        if group:
            results.append({"model": model_name, "description": meta.get("description", ""), "fields": group})

    paginated = paginate_dict_list(results, pagination, ["model", "description"]) if results else None
    return {
        "results": paginated.to_dict() if paginated else {"items": [], "pagination": {"total_count": 0}},
        "mode_used": "fs",
        "data_quality": "approximate",
    }
