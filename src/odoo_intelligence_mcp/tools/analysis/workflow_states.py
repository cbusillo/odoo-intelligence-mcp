from typing import TYPE_CHECKING, Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size

if TYPE_CHECKING:
    from ...type_defs.odoo_types import CompatibleEnvironment


async def analyze_workflow_states(
    env: "CompatibleEnvironment", model_name: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    code = f"""
import inspect
import re

model_name = {model_name!r}

if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    model = env[model_name]
    model_class = type(model)

    workflow_analysis = {{
        "model": model_name,
        "state_fields": {{}},
        "state_transitions": [],
        "button_actions": [],
        "automated_transitions": [],
        "state_dependencies": {{}},
    }}

    # Get all fields using fields_get() which includes inherited fields
    fields_info = model.fields_get()

    # Find state fields
    for field_name, field_data in fields_info.items():
        if ((field_name in ["state", "status"] or
             "state" in field_name or
             "status" in field_name) and
            field_data.get("type") == "selection"):

            selection_values = field_data.get("selection", [])

            # Handle dynamic selections
            if not isinstance(selection_values, list):
                try:
                    # Try to get field from model to access selection
                    field_obj = model._fields.get(field_name)
                    if field_obj and hasattr(field_obj, "selection") and callable(field_obj.selection):
                        selection_values = field_obj.selection(model)
                    else:
                        selection_values = "dynamic"
                except Exception:
                    selection_values = "dynamic"

            default_value = field_data.get("default")

            workflow_analysis["state_fields"][field_name] = {{
                "type": field_data.get("type"),
                "string": field_data.get("string"),
                "selection": selection_values if isinstance(selection_values, list) else str(selection_values),
                "default": default_value,
                "readonly": field_data.get("readonly", False),
                "required": field_data.get("required", False),
            }}

    # Find methods that modify state fields
    state_field_names = list(workflow_analysis["state_fields"].keys())

    if state_field_names:  # Only analyze if we found state fields
        for method_name, method in inspect.getmembers(model_class, inspect.isfunction):
            if method_name.startswith("_"):
                continue

            try:
                source = inspect.getsource(method)

                # Check if method modifies any state field
                for state_field in state_field_names:
                    if "'" + state_field + "'" in source or '"' + state_field + '"' in source:
                        decorators = []

                        # Check for common Odoo decorators
                        if hasattr(method, "_depends"):
                            decorators.append("@api.depends(" + ', '.join(repr(d) for d in method._depends) + ")")
                        if hasattr(method, "_constrains"):
                            decorators.append("@api.constrains(" + ', '.join(repr(c) for c in method._constrains) + ")")
                        if hasattr(method, "_onchange"):
                            decorators.append("@api.onchange(" + ', '.join(repr(o) for o in method._onchange) + ")")

                        transition_info = {{
                            "method": method_name,
                            "affects_field": state_field,
                            "signature": str(inspect.signature(method)),
                            "decorators": decorators,
                        }}

                        # Check if it's a button action
                        if "button_" in method_name or any("@api.onchange" in d for d in decorators):
                            workflow_analysis["button_actions"].append(transition_info)
                        # Check if it's automated (depends/constrains)
                        elif any("@api.depends" in d or "@api.constrains" in d for d in decorators):
                            workflow_analysis["automated_transitions"].append(transition_info)
                        else:
                            workflow_analysis["state_transitions"].append(transition_info)

                        # Extract state transitions from source
                        # Build pattern to match state assignments like: state = 'draft' or self.state = "done"
                        # Use simpler pattern to avoid escaping issues - escape field name for regex
                        import re as regex_module
                        escaped_field = regex_module.escape(state_field)
                        state_pattern = escaped_field + r'''\\\\s*[:=]\\\\s*["']([^"']+)["']'''
                        try:
                            transitions = re.findall(state_pattern, source)
                        except re.error:
                            transitions = []
                        if transitions:
                            transition_info["transitions_to"] = list(set(transitions))
            except Exception:
                continue

        # Find computed fields that depend on state
        for field_name, field_data in fields_info.items():
            if field_data.get("compute"):
                try:
                    field_obj = model._fields.get(field_name)
                    if field_obj and hasattr(field_obj, "compute"):
                        compute_method_name = field_obj.compute
                        compute_method = getattr(model, compute_method_name, None) if isinstance(compute_method_name, str) else None

                        if compute_method and hasattr(compute_method, "_depends"):
                            dependencies = list(compute_method._depends)
                            for state_field in state_field_names:
                                if state_field in dependencies or any(state_field in dep for dep in dependencies):
                                    if state_field not in workflow_analysis["state_dependencies"]:
                                        workflow_analysis["state_dependencies"][state_field] = []
                                    workflow_analysis["state_dependencies"][state_field].append({{
                                        "field": field_name,
                                        "type": field_data.get("type"),
                                        "compute_method": compute_method_name,
                                    }})
                except Exception:
                    continue

    # Add summary
    workflow_analysis["summary"] = {{
        "has_workflow": bool(workflow_analysis["state_fields"]),
        "state_field_count": len(workflow_analysis["state_fields"]),
        "transition_method_count": len(workflow_analysis["state_transitions"]),
        "button_action_count": len(workflow_analysis["button_actions"]),
        "automated_transition_count": len(workflow_analysis["automated_transitions"]),
        "fields_depending_on_state": sum(len(deps) for deps in workflow_analysis["state_dependencies"].values()),
    }}

    result = workflow_analysis
"""

    try:
        raw_result = await env.execute_code(code)

        if isinstance(raw_result, dict) and "error" in raw_result:
            return raw_result

        # Apply pagination to various lists in the result
        paginated_result = raw_result.copy()

        # Paginate state_transitions
        if "state_transitions" in raw_result and isinstance(raw_result["state_transitions"], list):
            paginated_transitions = paginate_dict_list(raw_result["state_transitions"], pagination, ["method", "affects_field"])
            paginated_result["state_transitions"] = paginated_transitions.to_dict()

        # Paginate button_actions
        if "button_actions" in raw_result and isinstance(raw_result["button_actions"], list):
            paginated_actions = paginate_dict_list(raw_result["button_actions"], pagination, ["method", "affects_field"])
            paginated_result["button_actions"] = paginated_actions.to_dict()

        # Paginate automated_transitions
        if "automated_transitions" in raw_result and isinstance(raw_result["automated_transitions"], list):
            paginated_automated = paginate_dict_list(raw_result["automated_transitions"], pagination, ["method", "affects_field"])
            paginated_result["automated_transitions"] = paginated_automated.to_dict()

        return validate_response_size(paginated_result)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "model": model_name,
        }
