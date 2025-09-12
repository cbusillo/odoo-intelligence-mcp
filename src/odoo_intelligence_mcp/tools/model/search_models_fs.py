from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ..ast import build_ast_index


async def search_models_fs(pattern: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    idx = await build_ast_index()
    models = idx.get("models", {}) if isinstance(idx, dict) else {}
    pattern_lower = pattern.lower()

    exact_matches: list[dict[str, Any]] = []
    partial_matches: list[dict[str, Any]] = []
    description_matches: list[dict[str, Any]] = []

    for model_name, meta in models.items():
        info = {
            "name": model_name,
            "description": meta.get("description") or model_name,
            "table": None,
            "transient": False,
            "abstract": False,
        }
        if model_name == pattern:
            exact_matches.append(info)
        elif pattern_lower in model_name.lower():
            partial_matches.append(info)
        elif meta.get("description") and pattern_lower in str(meta.get("description")).lower():
            description_matches.append(info)

    all_matches = []
    for m in exact_matches:
        m["match_type"] = "exact"
        m["priority"] = 1
        all_matches.append(m)
    for m in partial_matches:
        m["match_type"] = "partial"
        m["priority"] = 2
        all_matches.append(m)
    for m in description_matches:
        m["match_type"] = "description"
        m["priority"] = 3
        all_matches.append(m)

    all_matches.sort(key=lambda x: (x["priority"], x["name"]))

    paginated = paginate_dict_list(all_matches, pagination, ["name", "description"]) if all_matches else None

    return {
        "pattern": pattern,
        "total_models": len(models),
        "matches": paginated.to_dict()
        if paginated
        else {"items": [], "pagination": {"total_count": 0, "page": 1, "page_size": pagination.page_size}},
        "mode_used": "fs",
        "data_quality": "approximate",
    }
