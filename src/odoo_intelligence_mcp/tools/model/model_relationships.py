from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ...type_defs.odoo_types import CompatibleEnvironment


async def get_model_relationships(
    env: CompatibleEnvironment, model_name: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    code = f"""
model_name = {model_name!r}
if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    model = env[model_name]

    many2one_fields = []
    one2many_fields = []
    many2many_fields = []

    # Direct relationships
    for field_name, field in model._fields.items():
        if field.type == "many2one":
            many2one_fields.append({{
                "field_name": field_name,
                "target_model": field.comodel_name,
                "string": field.string,
                "required": field.required,
                "ondelete": getattr(field, "ondelete", "set null"),
            }})
        elif field.type == "one2many":
            one2many_fields.append({{
                "field_name": field_name,
                "target_model": field.comodel_name,
                "inverse_field": field.inverse_name,
                "string": field.string,
            }})
        elif field.type == "many2many":
            many2many_fields.append({{
                "field_name": field_name,
                "target_model": field.comodel_name,
                "relation_table": getattr(field, "relation", None),
                "string": field.string,
            }})

    # Reverse relationships (where this model is referenced)
    reverse_many2one = []
    reverse_one2many = []
    reverse_many2many = []

    for other_model_name in list(env):
        try:
            other_model = env[other_model_name]
            for field_name, field in other_model._fields.items():
                if field.type == "many2one" and field.comodel_name == model_name:
                    reverse_many2one.append({{
                        "source_model": other_model_name,
                        "field_name": field_name,
                        "string": field.string,
                    }})
                elif field.type == "one2many" and field.comodel_name == model_name:
                    reverse_one2many.append({{
                        "source_model": other_model_name,
                        "field_name": field_name,
                        "string": field.string,
                        "inverse_field": field.inverse_name,
                    }})
                elif field.type == "many2many" and field.comodel_name == model_name:
                    reverse_many2many.append({{
                        "source_model": other_model_name,
                        "field_name": field_name,
                        "string": field.string,
                        "relation_table": getattr(field, "relation", None),
                    }})
        except Exception:
            # Skip models that can't be accessed
            pass

    result = {{
        "model": model_name,
        "many2one_fields": many2one_fields,
        "one2many_fields": one2many_fields,
        "many2many_fields": many2many_fields,
        "reverse_many2one": reverse_many2one,
        "reverse_one2many": reverse_one2many,
        "reverse_many2many": reverse_many2many,
        "relationship_summary": {{
            "many2one_count": len(many2one_fields),
            "one2many_count": len(one2many_fields),
            "many2many_count": len(many2many_fields),
            "reverse_many2one_count": len(reverse_many2one),
            "reverse_one2many_count": len(reverse_one2many),
            "reverse_many2many_count": len(reverse_many2many),
        }}
    }}
"""

    result = await env.execute_code(code)

    if "error" in result:
        return result

    # Combine all relationships for pagination
    all_relationships = []

    # Add direct relationships
    many2one_fields = result.get("many2one_fields", [])
    assert isinstance(many2one_fields, list)  # Type assertion for PyCharm
    for rel in many2one_fields:
        rel["relationship_type"] = "many2one"
        rel["direction"] = "outgoing"
        all_relationships.append(rel)

    one2many_fields = result.get("one2many_fields", [])
    assert isinstance(one2many_fields, list)  # Type assertion for PyCharm
    for rel in one2many_fields:
        rel["relationship_type"] = "one2many"
        rel["direction"] = "outgoing"
        all_relationships.append(rel)

    many2many_fields = result.get("many2many_fields", [])
    assert isinstance(many2many_fields, list)  # Type assertion for PyCharm
    for rel in many2many_fields:
        rel["relationship_type"] = "many2many"
        rel["direction"] = "outgoing"
        all_relationships.append(rel)

    # Add reverse relationships
    reverse_many2one = result.get("reverse_many2one", [])
    assert isinstance(reverse_many2one, list)  # Type assertion for PyCharm
    for rel in reverse_many2one:
        rel["relationship_type"] = "many2one"
        rel["direction"] = "incoming"
        all_relationships.append(rel)

    reverse_one2many = result.get("reverse_one2many", [])
    assert isinstance(reverse_one2many, list)  # Type assertion for PyCharm
    for rel in reverse_one2many:
        rel["relationship_type"] = "one2many"
        rel["direction"] = "incoming"
        all_relationships.append(rel)

    reverse_many2many = result.get("reverse_many2many", [])
    assert isinstance(reverse_many2many, list)  # Type assertion for PyCharm
    for rel in reverse_many2many:
        rel["relationship_type"] = "many2many"
        rel["direction"] = "incoming"
        all_relationships.append(rel)

    # Apply pagination
    paginated_result = paginate_dict_list(all_relationships, pagination, ["field_name", "string", "target_model", "source_model"])

    return {
        "model": result["model"],
        "relationship_summary": result["relationship_summary"],
        "relationships": paginated_result.to_dict(),
    }
