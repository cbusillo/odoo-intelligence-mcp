from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ...type_defs.odoo_types import CompatibleEnvironment


async def get_view_model_usage(
    env: CompatibleEnvironment, model_name: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    code = f"""
import re

model_name = {model_name!r}

if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    view_usage = {{
        "model": model_name,
        "views": [],
        "exposed_fields": set(),
        "view_types": {{}},
        "field_usage_count": {{}}
    }}

    # Get model fields using fields_get()
    model = env[model_name]
    model_fields = model.fields_get()

    # Find all views for this model
    views = env["ir.ui.view"].search([("model", "=", model_name)])

    for view in views:
        view_info = {{
            "name": view.name,
            "type": view.type,
            "xml_id": getattr(view, "xml_id", ""),
            "module": view.xml_id.split(".")[0] if hasattr(view, "xml_id") and view.xml_id else "custom",
            "fields_used": [],
            "buttons": [],
            "actions": [],
        }}

        # Parse arch to find fields, buttons, actions
        if hasattr(view, "arch") and view.arch:
            arch_str = str(view.arch)

            # Find field references
            field_pattern = r'<field[^>]*name=["\\']([^"\\']+)["\\']'
            field_matches = re.findall(field_pattern, arch_str)

            for field_name in field_matches:
                if field_name in model_fields:
                    field_data = model_fields[field_name]
                    field_info = {{
                        "name": field_name,
                        "type": field_data.get("type", ""),
                        "string": field_data.get("string", ""),
                    }}
                    view_info["fields_used"].append(field_info)
                    view_usage["exposed_fields"].add(field_name)

                    # Count field usage
                    if field_name not in view_usage["field_usage_count"]:
                        view_usage["field_usage_count"][field_name] = 0
                    view_usage["field_usage_count"][field_name] += 1

            # Find button actions
            button_pattern = r'<button[^>]*(?:name=["\\']([^"\\']+)["\\']|type=["\\']([^"\\']+)["\\'])'
            button_matches = re.findall(button_pattern, arch_str)

            for name_match, type_match in button_matches:
                if name_match:
                    view_info["buttons"].append({{"name": name_match, "type": "method"}})
                elif type_match:
                    view_info["buttons"].append({{"type": type_match}})

        view_usage["views"].append(view_info)

        # Track view types
        if view.type not in view_usage["view_types"]:
            view_usage["view_types"][view.type] = []
        view_usage["view_types"][view.type].append(view.name)

    view_usage["exposed_fields"] = list(view_usage["exposed_fields"])

    # Add field coverage analysis
    total_fields = len(model_fields)
    exposed_fields = len(view_usage["exposed_fields"])
    view_usage["field_coverage"] = {{
        "total_fields": total_fields,
        "exposed_fields": exposed_fields,
        "coverage_percentage": round((exposed_fields / total_fields * 100), 2) if total_fields > 0 else 0,
        "unexposed_fields": [field_name for field_name in model_fields if field_name not in view_usage["exposed_fields"]],
    }}

    result = view_usage
"""

    try:
        result = await env.execute_code(code)

        if "error" in result:
            return result

        # Apply pagination to views
        views = result.get("views", [])
        assert isinstance(views, list)  # Type assertion for PyCharm
        paginated_views = paginate_dict_list(views, pagination, ["name", "type", "xml_id", "inherit_id"])

        return {
            "model": result.get("model"),
            "view_types": result.get("view_types", {}),
            "exposed_fields": result.get("exposed_fields", []),
            "field_usage_count": result.get("field_usage_count", {}),
            "field_coverage": result.get("field_coverage", {}),
            "views": paginated_views.to_dict(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "model": model_name,
        }
