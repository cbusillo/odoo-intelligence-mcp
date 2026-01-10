from typing import Any

VALID_FIELD_TYPES = [
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

from ...core.utils import PaginationParams
from ...type_defs.odoo_types import CompatibleEnvironment
from ._common import execute_and_paginate_results


async def search_field_type(
    env: CompatibleEnvironment,
    field_type: str,
    pagination: PaginationParams | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    field_type = field_type.lower().strip()
    if field_type not in VALID_FIELD_TYPES:
        return {
            "success": False,
            "error": f"Invalid field_type '{field_type}'.",
            "valid_types": VALID_FIELD_TYPES,
            "example": {"field_type": "char"},
        }

    code = f"""
import gc

field_type = {field_type!r}

# Get all model names from the registry
model_names = list(env.registry.models.keys())
if {bool(model_name)!r}:
    if {model_name!r} in model_names:
        model_names = [{model_name!r}]
    else:
        model_names = []

results = []
max_results = 100  # Limit results to prevent memory issues

# Process in batches
batch_size = 25
for batch_start in range(0, len(model_names), batch_size):
    if len(results) >= max_results:
        break
        
    batch_end = min(batch_start + batch_size, len(model_names))
    batch_models = model_names[batch_start:batch_end]
    
    for model_name in batch_models:
        if len(results) >= max_results:
            break
            
        try:
            model = env[model_name]

            # Get all fields using fields_get() which includes inherited fields
            fields_info = model.fields_get()
            matching_fields = []

            for field_name, field_data in fields_info.items():
                if field_data.get("type") == field_type:
                    field_info = {{
                        "field": field_name,
                        "string": (field_data.get("string", ""))[:100],  # Limit string length
                        "required": field_data.get("required", False),
                    }}

                    # Add relational field information
                    if field_type in ["many2one", "one2many", "many2many"]:
                        field_info["comodel_name"] = field_data.get("relation", "")[:100]
                        if field_type == "one2many":
                            field_info["inverse_name"] = field_data.get("inverse_name", "")[:100]

                    matching_fields.append(field_info)
                    
                    # Limit fields per model to avoid huge results
                    if len(matching_fields) >= 20:
                        break

            if matching_fields:
                results.append({{
                    "model": model_name,
                    "description": (getattr(model, "_description", ""))[:200],  # Limit description length
                    "fields": matching_fields
                }})
        except Exception:
            continue
    
    # Garbage collect after each batch
    if batch_start % 50 == 0:
        gc.collect()

result = {{"results": results[:max_results]}}
"""

    result = await execute_and_paginate_results(env, code, pagination)
    if "error" in result:
        result["field_type"] = field_type
    return result
