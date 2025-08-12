from typing import Any

from ...core.utils import PaginationParams
from ...type_defs.odoo_types import CompatibleEnvironment
from ._common import execute_and_paginate_results


async def search_field_type(
    env: CompatibleEnvironment, field_type: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    valid_types = [
        "many2one",
        "one2many",
        "many2many",
        "char",
        "text",
        "integer",
        "float",
        "boolean",
        "date",
        "datetime",
        "binary",
        "selection",
        "json",
    ]
    if field_type not in valid_types:
        return {"error": f"Invalid field type. Valid types: {', '.join(valid_types)}"}

    code = f"""
field_type = {field_type!r}

# Get all model names from the registry
model_names = list(env.registry.models.keys())

results = []

for model_name in model_names:
    try:
        model = env[model_name]

        # Get all fields using fields_get() which includes inherited fields
        fields_info = model.fields_get()
        matching_fields = []

        for field_name, field_data in fields_info.items():
            if field_data.get("type") == field_type:
                field_info = {{
                    "field": field_name,
                    "string": field_data.get("string", ""),
                    "required": field_data.get("required", False),
                }}

                # Add relational field information
                if field_type in ["many2one", "one2many", "many2many"]:
                    field_info["comodel_name"] = field_data.get("relation")
                    if field_type == "one2many":
                        field_info["inverse_name"] = field_data.get("inverse_name")

                matching_fields.append(field_info)

        if matching_fields:
            results.append({{
                "model": model_name,
                "description": getattr(model, "_description", ""),
                "fields": matching_fields
            }})
    except Exception:
        continue

result = {{"results": results}}
"""

    result = await execute_and_paginate_results(env, code, pagination)
    if "error" in result:
        result["field_type"] = field_type
    return result
