from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment


async def analyze_inheritance_chain(
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
    model_class = type(model)

    # Get MRO (Method Resolution Order)
    mro_entries = []
    for cls in model_class.__mro__:
        if hasattr(cls, "_name") and cls._name:
            mro_entries.append({{
                "class": cls.__name__,
                "model": cls._name,
                "module": cls.__module__
            }})

    # Get _inherit list (models this model inherits from)
    inherits_list = getattr(model_class, "_inherit", [])
    if isinstance(inherits_list, str):
        inherits_list = [inherits_list]

    # Get _inherits dict (delegation inheritance)
    inherits_from_dict = getattr(model_class, "_inherits", {{}})

    # Get inherited fields information
    inherited_fields_info = {{}}
    for field_name, field in model._fields.items():
        if field.inherited:
            inherited_fields_info[field_name] = {{
                "from_model": field.model_name,
                "type": field.type,
                "string": field.string,
                "original_field": field.related[0] if field.related else None,
            }}

    # Find models that inherit from this model
    inheriting_models = []
    for other_model_name in env.registry.models:
        if other_model_name == model_name:
            continue
        other_model = env[other_model_name]
        other_class = type(other_model)

        # Check if it inherits from our model
        inherit_list = getattr(other_class, "_inherit", [])
        if isinstance(inherit_list, str):
            inherit_list = [inherit_list]

        if model_name in inherit_list:
            inheriting_models.append({{
                "model": other_model_name,
                "description": other_model._description,
                "module": other_class.__module__
            }})

    # Analyze inherited and overridden methods
    overridden_methods = []
    inherited_methods = {{}}

    # Get methods from the model class
    model_methods = set()
    for attr_name in dir(model_class):
        try:
            attr = getattr(model_class, attr_name)
            if callable(attr) and hasattr(attr, "__self__") and attr.__self__ == model_class:
                model_methods.add(attr_name)
        except:
            pass

    # Check parent classes for overridden methods
    for parent_cls in model_class.__mro__[1:]:
        if hasattr(parent_cls, "_name") and parent_cls._name:
            parent_methods = set()
            for attr_name in dir(parent_cls):
                try:
                    attr = getattr(parent_cls, attr_name)
                    if callable(attr):
                        parent_methods.add(attr_name)
                except:
                    pass

            # Methods that exist in both child and parent are overridden
            for method_name in model_methods.intersection(parent_methods):
                if not method_name.startswith("__"):
                    overridden_methods.append({{
                        "method": method_name,
                        "overridden_from": parent_cls._name
                    }})

            # Store inherited methods by source
            for method_name in parent_methods - model_methods:
                if not method_name.startswith("__") and method_name not in inherited_methods:
                    inherited_methods[method_name] = parent_cls._name

    # Summary statistics
    summary = {{
        "total_inherited_fields": len(inherited_fields_info),
        "total_models_inheriting": len(inheriting_models),
        "total_overridden_methods": len(overridden_methods),
        "inheritance_depth": len(mro_entries) - 1,  # Exclude object class
        "uses_delegation": bool(inherits_from_dict),
        "uses_prototype": bool(inherits_list),
    }}

    result = {{
        "model": model_name,
        "mro": mro_entries,
        "inherits": inherits_list,
        "inherits_from": inherits_from_dict,
        "inherited_fields": inherited_fields_info,
        "inheriting_models": inheriting_models,
        "overridden_methods": overridden_methods,
        "inherited_methods": inherited_methods,
        "summary": summary
    }}
"""

    result = await env.execute_code(code)

    # Check for errors first
    if isinstance(result, dict) and "error" in result:
        return result

    # Extract the actual result data from execute_code response
    if "result" in result and isinstance(result["result"], dict):
        data = result["result"]
    else:
        data = result

    # Apply pagination to large lists if provided
    if isinstance(data, dict) and pagination:
        # Paginate inheriting_models if needed
        if "inheriting_models" in data and isinstance(data["inheriting_models"], list):
            inheriting_models = data["inheriting_models"]
            assert isinstance(inheriting_models, list)  # Type assertion for PyCharm
            paginated = paginate_dict_list(inheriting_models, pagination, ["model", "description"])
            data["inheriting_models"] = paginated.to_dict()

        # Paginate inherited_fields if needed
        if "inherited_fields" in data and isinstance(data["inherited_fields"], dict):
            # Convert dict to list for pagination
            inherited_fields_dict = data["inherited_fields"]
            assert isinstance(inherited_fields_dict, dict)  # Type assertion for PyCharm
            fields_list = [{"field_name": k, **v} for k, v in inherited_fields_dict.items()]
            if len(fields_list) > pagination.page_size:
                paginated = paginate_dict_list(fields_list, pagination, ["field_name", "from_model"])
                data["inherited_fields"] = paginated.to_dict()

        # Paginate overridden_methods if needed
        if "overridden_methods" in data and isinstance(data["overridden_methods"], list):
            overridden_methods = data["overridden_methods"]
            assert isinstance(overridden_methods, list)  # Type assertion for PyCharm
            if len(overridden_methods) > pagination.page_size:
                paginated = paginate_dict_list(overridden_methods, pagination, ["method"])
                data["overridden_methods"] = paginated.to_dict()

        # Paginate inherited_methods if needed
        if "inherited_methods" in data and isinstance(data["inherited_methods"], dict):
            # Convert dict to list for pagination
            inherited_methods_dict = data["inherited_methods"]
            assert isinstance(inherited_methods_dict, dict)  # Type assertion for PyCharm
            methods_list = [{"method_name": k, "from_model": v} for k, v in inherited_methods_dict.items()]
            if len(methods_list) > pagination.page_size:
                paginated = paginate_dict_list(methods_list, pagination, ["method_name"])
                data["inherited_methods"] = paginated.to_dict()

    # Validate response size
    return validate_response_size(data)
