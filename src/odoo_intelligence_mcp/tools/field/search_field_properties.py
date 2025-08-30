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

    code = (
        """
property_type = """
        + repr(property_type)
        + """

# Get all model names from the registry
model_names = list(env.registry.models.keys())

results = []

for model_name in model_names:
    try:
        model = env[model_name]

        # Use model._fields to access field objects directly
        matching_fields = []
        
        for field_name, field in model._fields.items():
            field_matches = False

            # Check property type on the field object itself
            if property_type == "computed":
                field_matches = bool(hasattr(field, 'compute') and field.compute)
            elif property_type == "related":
                field_matches = bool(hasattr(field, 'related') and field.related)
            elif property_type == "stored":
                field_matches = getattr(field, 'store', True)
            elif property_type == "required":
                field_matches = getattr(field, 'required', False)
            elif property_type == "readonly":
                field_matches = getattr(field, 'readonly', False)

            if field_matches:
                field_info = {
                    "field": field_name,
                    "type": getattr(field, 'type', ""),
                    "string": getattr(field, 'string', "")
                }

                if property_type == "computed":
                    compute_method = getattr(field, 'compute', "")
                    field_info["compute_method"] = str(compute_method) if compute_method else ""
                    field_info["stored"] = str(getattr(field, 'store', False))
                elif property_type == "related":
                    field_info["related_path"] = str(getattr(field, 'related', ""))

                matching_fields.append(field_info)

        if matching_fields:
            results.append({
                "model": model_name,
                "description": getattr(model, "_description", ""),
                "fields": matching_fields
            })
    except Exception:
        continue

result = {"results": results}
"""
    )

    result = await execute_and_paginate_results(env, code, pagination)
    result["property"] = property_type
    return result
