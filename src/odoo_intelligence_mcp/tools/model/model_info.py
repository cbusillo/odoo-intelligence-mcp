from typing import Any

from ...core.utils import PaginationParams
from ...type_defs.odoo_types import CompatibleEnvironment
from ...utils.error_utils import handle_tool_error, validate_model_name


@handle_tool_error
async def get_model_info(env: CompatibleEnvironment, model_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    validate_model_name(model_name)
    
    if pagination is None:
        pagination = PaginationParams(page_size=25)
    
    start_idx = pagination.offset
    end_idx = start_idx + pagination.page_size
    
    code = f"""
model_name = {model_name!r}
start_idx = {start_idx}
end_idx = {end_idx}

if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    model = env[model_name]

    basic_info = {{
        "name": model_name,
        "table": model._table,
        "description": model._description,
        "rec_name": getattr(model, "_rec_name", "name"),
        "order": getattr(model, "_order", "id"),
        "total_field_count": len(model._fields),
    }}

    # Get all field names sorted for consistent pagination
    all_field_names = sorted(model._fields.keys())
    
    # Apply pagination to fields
    paginated_field_names = all_field_names[start_idx:end_idx]
    
    fields_info = {{}}
    for field_name in paginated_field_names:
        field = model._fields[field_name]
        field_data = {{
            "type": field.type,
            "string": field.string,
            "required": field.required,
            "readonly": field.readonly,
            "store": field.store,
        }}

        if field.type in ["many2one", "one2many", "many2many"]:
            field_data["relation"] = field.comodel_name

        if field.type == "selection" and hasattr(field, "selection"):
            if isinstance(field.selection, list):
                field_data["selection"] = field.selection
            else:
                field_data["selection"] = "Dynamic selection"

        fields_info[field_name] = field_data

    basic_info["fields"] = fields_info
    basic_info["displayed_field_count"] = len(fields_info)
    
    # Pagination info
    basic_info["pagination"] = {{
        "page": {pagination.page},
        "page_size": {pagination.page_size},
        "total_count": len(all_field_names),
        "has_next": end_idx < len(all_field_names),
        "has_previous": start_idx > 0
    }}

    # Only include limited methods to save space
    model_class = type(model)
    methods = []
    for name in dir(model_class):
        if not name.startswith('_') or name in ['_compute_display_name', '_search']:
            if hasattr(model_class, name) and callable(getattr(model_class, name, None)):
                methods.append(name)
                if len(methods) >= 20:  # Limit methods to save tokens
                    break

    basic_info["methods_sample"] = methods
    basic_info["total_method_count"] = len([n for n in dir(model_class) if not n.startswith('_') or n in ['_compute_display_name', '_search']])

    result = basic_info
"""

    return await env.execute_code(code)
