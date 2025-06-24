from typing import Any, TypedDict

from ...core.utils import PaginationParams, paginate_dict_list
from ...type_defs.odoo_types import CompatibleEnvironment
from ...utils.error_utils import handle_tool_error, validate_field_name, validate_model_name


class FieldInfo(TypedDict):
    type: str
    string: str
    required: bool
    readonly: bool
    store: bool
    compute: str | None
    related: str | None
    relation: str | None
    inverse_name: str | None


class ViewUsage(TypedDict):
    id: int
    name: str
    type: str
    model: str
    arch: str


class DomainUsage(TypedDict):
    type: str
    name: str
    domain: str


class MethodUsage(TypedDict):
    type: str
    method: str


class UsageSummary(TypedDict):
    view_count: int
    domain_count: int
    method_count: int
    total_usages: int


class FieldUsagesResult(TypedDict, total=False):
    model: str
    field: str
    field_info: FieldInfo
    used_in_views: list[ViewUsage]
    used_in_domains: list[DomainUsage]
    used_in_methods: list[MethodUsage]
    usage_summary: UsageSummary
    error: str


@handle_tool_error
async def get_field_usages(
    env: CompatibleEnvironment, model_name: str, field_name: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    validate_model_name(model_name)
    validate_field_name(field_name)
    # noinspection SpellCheckingInspection
    code = f"""
import re
import inspect
from collections import defaultdict

model_name = {model_name!r}
field_name = {field_name!r}

if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    model = env[model_name]
    
    # Get field info using fields_get() which includes inherited fields
    fields_info = model.fields_get()
    
    if field_name not in fields_info:
        result = {{"error": f"Field {{field_name}} not found in {{model_name}}"}}
    else:
        field_data = fields_info[field_name]
        field_info = {{
            "type": field_data.get("type", ""),
            "string": field_data.get("string", ""),
            "help": field_data.get("help"),
            "required": field_data.get("required", False),
            "readonly": field_data.get("readonly", False),
            "store": field_data.get("store", True),
        }}
        
        # Add optional field attributes
        if field_data.get("compute"):
            field_info["compute"] = field_data["compute"]
        if field_data.get("related"):
            field_info["related"] = field_data["related"]
        if field_data.get("inverse"):
            field_info["inverse"] = field_data["inverse"]
        if field_data.get("type") in ["many2one", "one2many", "many2many"]:
            field_info["relation"] = field_data.get("relation")
            if field_data.get("type") == "one2many":
                field_info["inverse_name"] = field_data.get("inverse_name")
            elif field_data.get("type") == "many2many":
                field_info["relation_table"] = field_data.get("relation_table")
        
        # Find views using this field
        views_using_field = []
        View = env["ir.ui.view"]
        views = View.search([("model", "=", model_name)])
        for view in views:
            if hasattr(view, "arch_db") and view.arch_db and field_name in view.arch_db:
                views_using_field.append({{
                    "id": view.id,
                    "name": view.name,
                    "type": view.type,
                    "inherit_id": view.inherit_id.name if view.inherit_id else None,
                }})
        
        # Find domains using this field
        domains_using_field = []
        Action = env["ir.actions.act_window"]
        actions = Action.search([("res_model", "=", model_name)])
        for action in actions:
            if action.domain and field_name in action.domain:
                domains_using_field.append({{
                    "type": "action",
                    "name": action.name,
                    "domain": action.domain,
                }})
        
        Filter = env["ir.filters"]
        filters = Filter.search([("model_id", "=", model_name)])
        for filter_rec in filters:
            if filter_rec.domain and field_name in filter_rec.domain:
                domains_using_field.append({{
                    "type": "filter",
                    "name": filter_rec.name,
                    "domain": filter_rec.domain,
                    "user": filter_rec.user_id.name if filter_rec.user_id else "Public",
                }})
        
        # Find methods using this field
        methods_using_field = []
        model_class = type(model)
        
        # Check computed fields that depend on this field
        for fname, fdata in fields_info.items():
            if fdata.get("compute"):
                if isinstance(fdata["compute"], str) and hasattr(model_class, fdata["compute"]):
                    method = getattr(model_class, fdata["compute"])
                    if hasattr(method, "_depends"):
                        depends_list = (
                            list(method._depends)
                            if hasattr(method._depends, "__iter__") and not isinstance(method._depends, str)
                            else []
                        )
                        # Fix the f-string issue by using proper escaping
                        field_prefix = field_name + "."
                        if (
                            field_name in depends_list
                            or any(dep.startswith(field_prefix) for dep in depends_list)
                        ):
                            methods_using_field.append({{
                                "type": "compute",
                                "method": fdata["compute"],
                                "field": fname,
                                "depends": (
                                    list(method._depends)
                                    if hasattr(method._depends, "__iter__")
                                    else [str(method._depends)]
                                ),
                            }})
        
        # Check constraint and onchange methods
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name, None)
            if attr and hasattr(attr, "_constrains") and hasattr(attr._constrains, "__iter__"):
                if field_name in attr._constrains:
                    methods_using_field.append({{
                        "type": "constraint",
                        "method": attr_name,
                        "constrains": list(attr._constrains),
                    }})
            if attr and hasattr(attr, "_onchange") and hasattr(attr._onchange, "__iter__"):
                if field_name in attr._onchange:
                    methods_using_field.append({{
                        "type": "onchange",
                        "method": attr_name,
                        "onchange": list(attr._onchange),
                    }})
        
        # Check method source code for field references
        for method_name in dir(model_class):
            if (
                not method_name.startswith("_")
                or method_name in ["_compute_display_name", "_search"]
            ):
                method = getattr(model_class, method_name, None)
                if callable(method) and hasattr(method, "__code__"):
                    try:
                        source = inspect.getsource(method)
                        # Fix regex patterns - properly escape the field name
                        escaped_field = re.escape(field_name)
                        patterns = [
                            r'self\\\\.' + escaped_field + r'\\\\b',
                            r'record\\\\.' + escaped_field + r'\\\\b',  
                            r'rec\\\\.' + escaped_field + r'\\\\b',
                            r'["\\\']' + escaped_field + r'["\\\']',
                        ]
                        for pattern in patterns:
                            if re.search(pattern, source):
                                already_added = any(
                                    m["method"] == method_name
                                    for m in methods_using_field
                                    if m["type"] in ["compute", "constraint", "onchange"]
                                )
                                if not already_added:
                                    methods_using_field.append({{
                                        "type": "method",
                                        "method": method_name,
                                    }})
                                break
                    except Exception:
                        pass
        
        result = {{
            "model": model_name,
            "field": field_name,
            "field_info": field_info,
            "used_in_views": views_using_field,
            "used_in_domains": domains_using_field,
            "used_in_methods": methods_using_field,
            "usage_summary": {{
                "view_count": len(views_using_field),
                "domain_count": len(domains_using_field),
                "method_count": len(methods_using_field),
                "total_usages": (
                    len(views_using_field) + len(domains_using_field) + len(methods_using_field)
                ),
            }},
        }}
"""

    result = await env.execute_code(code)

    if "error" in result:
        return result

    # Combine all usages for pagination
    all_usages = []

    # Add view usages
    for usage in result.get("used_in_views", []):
        usage["usage_type"] = "view"
        all_usages.append(usage)

    # Add domain usages
    for usage in result.get("used_in_domains", []):
        usage["usage_type"] = "domain"
        all_usages.append(usage)

    # Add method usages
    for usage in result.get("used_in_methods", []):
        usage["usage_type"] = "method"
        all_usages.append(usage)

    # Apply pagination
    paginated_result = paginate_dict_list(all_usages, pagination, ["name", "type", "model", "method"])

    return {
        "model": result["model"],
        "field": result["field"],
        "field_info": result["field_info"],
        "usage_summary": result["usage_summary"],
        "usages": paginated_result.to_dict(),
    }
