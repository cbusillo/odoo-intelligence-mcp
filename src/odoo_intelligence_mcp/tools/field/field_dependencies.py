from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment


async def get_field_dependencies(
    env: CompatibleEnvironment, model_name: str, field_name: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    code = f"""
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
        field_info = fields_info[field_name]

        dependencies = {{
            "field": field_name,
            "model": model_name,
            "type": field_info.get("type", "unknown"),
            "direct_dependencies": [],
            "indirect_dependencies": [],
            "dependent_fields": [],
            "dependency_chain": [],
        }}

        # Direct dependencies (what this field depends on)
        # Try to get from _fields for compute dependencies
        try:
            field_obj = model._fields.get(field_name)
            if field_obj:
                if hasattr(field_obj, "compute") and field_obj.compute:
                    # Handle case where compute is a method name (string) or method object
                    compute_method = getattr(model, field_obj.compute, None) if isinstance(field_obj.compute, str) else field_obj.compute
                    if compute_method and hasattr(compute_method, "_depends"):
                        dependencies["direct_dependencies"] = list(getattr(compute_method, "_depends", []))
                elif hasattr(field_obj, "related") and field_obj.related:
                    dependencies["direct_dependencies"] = [".".join(field_obj.related)]
        except Exception:
            pass

        # Try to extract dependency info from fields_get() if available
        if not dependencies["direct_dependencies"]:
            if field_info.get("related"):
                dependencies["direct_dependencies"] = [field_info["related"]]
            elif field_info.get("depends"):
                dependencies["direct_dependencies"] = field_info["depends"] if isinstance(field_info["depends"], list) else [field_info["depends"]]

        # Find fields that depend on this field (reverse lookup)
        try:
            for fname, other_field_info in fields_info.items():
                if fname != field_name:
                    field_deps = []

                    # Check if this field is in depends
                    if other_field_info.get("depends"):
                        depends_list = other_field_info["depends"] if isinstance(other_field_info["depends"], list) else [other_field_info["depends"]]
                        if field_name in depends_list or any(field_name in dep for dep in depends_list):
                            field_deps.extend(depends_list)

                    # Check if this field is in related path
                    if other_field_info.get("related"):
                        related_path = other_field_info["related"]
                        if field_name in related_path:
                            field_deps.append(related_path)

                    # Try to get compute dependencies from _fields
                    try:
                        other_field_obj = model._fields.get(fname)
                        if other_field_obj and hasattr(other_field_obj, "compute") and other_field_obj.compute:
                            compute_method = getattr(model, other_field_obj.compute, None) if isinstance(other_field_obj.compute, str) else None
                            if compute_method and hasattr(compute_method, "_depends"):
                                compute_deps = list(compute_method._depends)
                                if field_name in compute_deps or any(field_name in dep for dep in compute_deps):
                                    field_deps.extend(compute_deps)
                    except Exception:
                        pass

                    if field_deps:
                        dependencies["dependent_fields"].append({{
                            "field": fname,
                            "type": other_field_info.get("type", "unknown"),
                            "dependencies": list(set(field_deps)),
                            "compute_method": other_field_info.get("compute"),
                            "related": other_field_info.get("related"),
                        }})
        except Exception:
            pass

        # Build dependency chain for related fields
        if dependencies["direct_dependencies"]:
            for dep in dependencies["direct_dependencies"]:
                if "." in dep:  # It's a path like "partner_id.name"
                    chain_parts = dep.split(".")
                    chain_info = {{
                        "path": dep,
                        "steps": [],
                    }}

                    current_model = model_name
                    for i, part in enumerate(chain_parts):
                        try:
                            current_fields = env[current_model].fields_get()
                            if part in current_fields:
                                field_data = current_fields[part]
                                step = {{
                                    "model": current_model,
                                    "field": part,
                                    "type": field_data.get("type"),
                                    "relation": field_data.get("relation"),
                                }}
                                chain_info["steps"].append(step)

                                # Update current model for next iteration
                                if field_data.get("relation") and i < len(chain_parts) - 1:
                                    current_model = field_data["relation"]
                                else:
                                    break
                            else:
                                break
                        except Exception:
                            break

                    if chain_info["steps"]:
                        dependencies["dependency_chain"].append(chain_info)

        result = dependencies
"""

    try:
        raw_result = await env.execute_code(code)

        if isinstance(raw_result, dict) and "error" in raw_result:
            return raw_result

        # Apply pagination to lists in the result
        paginated_result = raw_result.copy()

        # Paginate dependent_fields
        if "dependent_fields" in raw_result and isinstance(raw_result["dependent_fields"], list):
            paginated_fields = paginate_dict_list(raw_result["dependent_fields"], pagination, ["field", "type"])
            paginated_result["dependent_fields"] = paginated_fields.to_dict()

        # Paginate dependency_chain
        if "dependency_chain" in raw_result and isinstance(raw_result["dependency_chain"], list):
            paginated_chain = paginate_dict_list(raw_result["dependency_chain"], pagination, ["path"])
            paginated_result["dependency_chain"] = paginated_chain.to_dict()

        return validate_response_size(paginated_result)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "model": model_name,
            "field": field_name,
        }
