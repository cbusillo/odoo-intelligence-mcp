from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ..common.fs_utils import ensure_pagination, get_models_index, not_found


async def analyze_inheritance_chain_fs(model_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    pagination = ensure_pagination(pagination)

    models = await get_models_index()
    meta = models.get(model_name)
    if not meta:
        return not_found(model_name)

    inherits = meta.get("inherits", [])
    delegates = meta.get("delegates", {})

    mro_entries = [{"class": meta.get("class", ""), "model": model_name, "module": meta.get("module", "")}]
    for inh in inherits:
        if inh in models:
            mro_entries.append({"class": models[inh].get("class", ""), "model": inh, "module": models[inh].get("module", "")})
        else:
            mro_entries.append({"class": "", "model": inh, "module": ""})

    inherited_fields = {}
    # Static approximation: mark fields with same name as inherited if defined on inherits model
    for fname in meta.get("fields", {}).keys():
        for inh in inherits:
            inh_fields = models.get(inh, {}).get("fields", {}) if inh in models else {}
            if fname in inh_fields:
                inherited_fields[fname] = {
                    "from_model": inh,
                    "type": inh_fields[fname].get("type"),
                    "string": inh_fields[fname].get("string"),
                }
                break

    overridden_methods = []
    child_methods = set(meta.get("methods", []))
    for inh in inherits:
        parent_methods = set(models.get(inh, {}).get("methods", []))
        for method in child_methods.intersection(parent_methods):
            overridden_methods.append({"method": method, "overridden_from": inh})

    inheriting_models = []
    for other, m in models.items():
        if other == model_name:
            continue
        if model_name in m.get("inherits", []):
            inheriting_models.append({"model": other, "description": m.get("description", ""), "module": m.get("module", "")})

    summary = {
        "total_inherited_fields": len(inherited_fields),
        "total_models_inheriting": len(inheriting_models),
        "total_overridden_methods": len(overridden_methods),
        "inheritance_depth": len(mro_entries) - 1,
        "uses_delegation": bool(delegates),
        "uses_prototype": bool(inherits),
    }

    # Paginate inheriting models as a representative large list
    paginated = paginate_dict_list(inheriting_models, pagination, ["model", "description"]) if inheriting_models else None

    result: dict[str, Any] = {
        "model": model_name,
        "mro": mro_entries,
        "inherits": inherits,
        "inherits_from": delegates,
        "inherited_fields": inherited_fields,
        "inheriting_models": paginated.to_dict() if paginated else inheriting_models,
        "overridden_methods": overridden_methods,
        "inherited_methods": {},
        "summary": summary,
        "mode_used": "fs",
        "data_quality": "approximate",
    }
    return result
