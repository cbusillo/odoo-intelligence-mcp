from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ..common.fs_utils import ensure_pagination, get_models_index, not_found


async def get_model_relationships_fs(model_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    pagination = ensure_pagination(pagination)

    models = await get_models_index()
    meta = models.get(model_name)
    if not meta:
        return not_found(model_name)

    many2one_fields = []
    one2many_fields = []
    many2many_fields = []

    for field_name, field in meta.get("fields", {}).items():
        field_type = field.get("type")
        if field_type == "many2one":
            many2one_fields.append(
                {
                    "field_name": field_name,
                    "target_model": field.get("relation"),
                    "string": field.get("string"),
                    "required": bool(field.get("required")),
                }
            )
        elif field_type == "one2many":
            one2many_fields.append(
                {
                    "field_name": field_name,
                    "target_model": field.get("relation"),
                    "inverse_field": field.get("inverse_name"),
                    "string": field.get("string"),
                }
            )
        elif field_type == "many2many":
            many2many_fields.append(
                {
                    "field_name": field_name,
                    "target_model": field.get("relation"),
                    "relation_table": None,
                    "string": field.get("string"),
                }
            )

    all_relationships: list[dict[str, Any]] = []
    for rel in many2one_fields:
        r = rel.copy()
        r["relationship_type"] = "many2one"
        r["direction"] = "outgoing"
        all_relationships.append(r)
    for rel in one2many_fields:
        r = rel.copy()
        r["relationship_type"] = "one2many"
        r["direction"] = "outgoing"
        all_relationships.append(r)
    for rel in many2many_fields:
        r = rel.copy()
        r["relationship_type"] = "many2many"
        r["direction"] = "outgoing"
        all_relationships.append(r)

    paginated = paginate_dict_list(all_relationships, pagination, ["field_name", "string", "target_model"])
    return {
        "model": model_name,
        "relationship_summary": {
            "many2one_count": len(many2one_fields),
            "one2many_count": len(one2many_fields),
            "many2many_count": len(many2many_fields),
            "reverse_many2one_count": 0,
            "reverse_one2many_count": 0,
            "reverse_many2many_count": 0,
        },
        "relationships": paginated.to_dict(),
        "many2one_fields": many2one_fields,
        "one2many_fields": one2many_fields,
        "many2many_fields": many2many_fields,
        "reverse_many2one": [],
        "reverse_one2many": [],
        "reverse_many2many": [],
        "mode_used": "fs",
        "data_quality": "approximate",
    }
