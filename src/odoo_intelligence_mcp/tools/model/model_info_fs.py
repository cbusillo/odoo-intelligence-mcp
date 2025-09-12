from typing import Any

from ...core.utils import PaginationParams
from ..common.fs_utils import ensure_pagination, get_models_index, not_found


async def get_model_info_fs(model_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    pagination = ensure_pagination(pagination, default_page_size=25)

    models = await get_models_index()
    meta = models.get(model_name)
    if not meta:
        return not_found(model_name)

    fields = meta.get("fields", {})
    all_field_names = sorted(fields.keys())
    start_idx = pagination.offset
    end_idx = start_idx + pagination.page_size
    page_fields = all_field_names[start_idx:end_idx]

    fields_info: dict[str, Any] = {}
    for fname in page_fields:
        f = fields.get(fname, {})
        fields_info[fname] = {
            "type": f.get("type"),
            "string": f.get("string"),
            "required": bool(f.get("required")),
            "readonly": False,
            "store": bool(f.get("store", True)),
            **({"relation": f.get("relation")} if f.get("relation") else {}),
        }

    result = {
        "name": model_name,
        "table": None,
        "description": meta.get("description") or "",
        "rec_name": "name",
        "order": "id",
        "total_field_count": len(all_field_names),
        "fields": fields_info,
        "displayed_field_count": len(fields_info),
        "pagination": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_count": len(all_field_names),
            "has_next": end_idx < len(all_field_names),
            "has_previous": start_idx > 0,
        },
        "methods_sample": meta.get("methods", [])[:20],
        "total_method_count": len(meta.get("methods", [])),
        "mode_used": "fs",
        "data_quality": "approximate",
    }
    return result
