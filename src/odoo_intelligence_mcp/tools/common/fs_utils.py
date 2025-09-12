from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ..ast import build_ast_index


async def get_models_index() -> dict[str, Any]:
    idx = await build_ast_index()
    return idx.get("models", {}) if isinstance(idx, dict) else {}


def ensure_pagination(pagination: PaginationParams | None, default_page_size: int | None = None) -> PaginationParams:
    if pagination is None:
        return PaginationParams(page_size=default_page_size) if default_page_size else PaginationParams()
    return pagination


def not_found(model_name: str) -> dict[str, Any]:
    return {"error": f"Model {model_name} not found (fs)", "mode_used": "fs", "data_quality": "approximate"}


def fs_enrich(payload: dict[str, Any]) -> dict[str, Any]:
    if "mode_used" not in payload:
        payload["mode_used"] = "fs"
    if "data_quality" not in payload:
        payload["data_quality"] = "approximate"
    return payload


def paginate_items(items: list[dict[str, Any]], pagination: PaginationParams, search_fields: list[str]) -> dict[str, Any]:
    return paginate_dict_list(items, pagination, search_fields).to_dict()

