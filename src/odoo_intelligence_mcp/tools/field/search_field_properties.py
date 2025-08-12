from typing import Any

from ...core.utils import PaginationParams
from ...type_defs.odoo_types import CompatibleEnvironment
from ._common import execute_and_paginate_results


async def search_field_properties(
    env: CompatibleEnvironment, property_type: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    valid_properties = ["computed", "related", "stored", "required", "readonly"]

    if property_type not in valid_properties:
        return {"error": f"Invalid property type. Valid properties: {', '.join(valid_properties)}"}

    code = f"""
property_type = {property_type!r}

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
            field_matches = False

            # Check property type
            if property_type == "computed":
                field_matches = bool(field_data.get("compute"))
            elif property_type == "related":
                field_matches = bool(field_data.get("related"))
            elif property_type == "stored":
                field_matches = field_data.get("store", True)
            elif property_type == "required":
                field_matches = field_data.get("required", False)
            elif property_type == "readonly":
                field_matches = field_data.get("readonly", False)

            if field_matches:
                field_info = {{
                    "field": field_name,
                    "type": field_data.get("type", ""),
                    "string": field_data.get("string", "")
                }}

                if property_type == "computed":
                    field_info["compute_method"] = field_data.get("compute", "")
                    field_info["stored"] = str(field_data.get("store", False))
                elif property_type == "related":
                    field_info["related_path"] = field_data.get("related", "")

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
        result["property_type"] = property_type
    return result
