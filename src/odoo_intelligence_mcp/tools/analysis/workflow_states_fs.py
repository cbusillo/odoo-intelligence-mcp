from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ..common.fs_utils import ensure_pagination, get_models_index, not_found


async def analyze_workflow_states_fs(model_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    pagination = ensure_pagination(pagination)

    models = await get_models_index()
    meta = models.get(model_name)
    if not meta:
        return not_found(model_name)

    fields = meta.get("fields", {})
    state_fields: dict[str, Any] = {}
    for fname, f in fields.items():
        if fname == "state" and f.get("type") == "selection":
            state_fields[fname] = {
                "type": "selection",
                "string": f.get("string"),
                "selection": f.get("selection") if isinstance(f.get("selection"), list) else "dynamic",
                "default": None,
                "readonly": False,
                "required": bool(f.get("required")),
            }

    transitions = []
    button_actions = []
    automated_transitions = []

    decs = meta.get("decorators", {})
    for method, lst in decs.items():
        for d in lst:
            if d.get("type") == "onchange":
                button_actions.append({"method": method, "affects_field": "state", "signature": f"{method}(...)", "decorators": ["@api.onchange"]})
            if d.get("type") in ("depends", "constrains"):
                automated_transitions.append({"method": method, "affects_field": "state", "signature": f"{method}(...)", "decorators": [f"@api.{d.get('type')}"]})

    paginated_transitions = paginate_dict_list(transitions, pagination, ["method"]) if transitions else None
    paginated_buttons = paginate_dict_list(button_actions, pagination, ["method"]) if button_actions else None
    paginated_automated = paginate_dict_list(automated_transitions, pagination, ["method"]) if automated_transitions else None

    result = {
        "model": model_name,
        "state_fields": state_fields,
        "state_transitions": (paginated_transitions.to_dict() if paginated_transitions else []),
        "button_actions": (paginated_buttons.to_dict() if paginated_buttons else []),
        "automated_transitions": (paginated_automated.to_dict() if paginated_automated else []),
        "state_dependencies": {},
        "summary": {
            "has_workflow": bool(state_fields),
            "state_field_count": len(state_fields),
            "transition_method_count": len(transitions),
            "button_action_count": len(button_actions),
            "automated_transition_count": len(automated_transitions),
            "fields_depending_on_state": 0,
        },
        "mode_used": "fs",
        "data_quality": "approximate",
    }
    return validate_response_size(result)
