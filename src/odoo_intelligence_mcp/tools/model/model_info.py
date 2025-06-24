from typing import Any

from ...type_defs.odoo_types import CompatibleEnvironment
from ...utils.error_utils import handle_tool_error, validate_model_name


@handle_tool_error
async def get_model_info(env: CompatibleEnvironment, model_name: str) -> dict[str, Any]:
    validate_model_name(model_name)
    code = f"""
model_name = {model_name!r}
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
    }}

    fields_info = {{}}
    for field_name, field in model._fields.items():
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
    basic_info["field_count"] = len(fields_info)

    model_class = type(model)
    methods = []
    for name in dir(model_class):
        if not name.startswith('_') or name in ['_compute_display_name', '_search']:
            if hasattr(model_class, name) and callable(getattr(model_class, name, None)):
                methods.append(name)

    basic_info["methods"] = methods
    basic_info["method_count"] = len(methods)

    result = basic_info
"""

    return await env.execute_code(code)
