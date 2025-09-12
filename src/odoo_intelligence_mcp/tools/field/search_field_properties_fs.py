from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ..common.fs_utils import ensure_pagination, get_models_index


async def search_field_properties_fs(property_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    pagination = ensure_pagination(pagination)

    models = await get_models_index()
    results: list[dict[str, Any]] = []
    prop = property_name.lower()

    for model_name, meta in models.items():
        for fname, f in meta.get("fields", {}).items():
            hit = False
            if (
                (prop == "computed" and f.get("compute"))
                or (prop == "related" and f.get("related"))
                or (prop == "stored" and f.get("store"))
            ):
                hit = True
            if hit:
                results.append(
                    {
                        "model": model_name,
                        "field_name": fname,
                        "field_type": f.get("type"),
                        "field_string": f.get("string"),
                    }
                )

    paginated = paginate_dict_list(results, pagination, ["model", "field_name"]) if results else None
    return {
        "results": paginated.to_dict() if paginated else {"items": [], "pagination": {"total_count": 0}},
        "mode_used": "fs",
        "data_quality": "approximate",
    }
