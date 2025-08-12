from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment


async def resolve_dynamic_fields(
    env: CompatibleEnvironment, model_name: str, pagination: PaginationParams | None = None
) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    code = f"""
import inspect

model_name = {model_name!r}

if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    model = env[model_name]
    model_class = type(model)

    dynamic_analysis = {{
        "model": model_name,
        "computed_fields": {{}},
        "related_fields": {{}},
        "field_dependencies": {{}},
        "runtime_fields": [],
        "reverse_dependencies": {{}},
    }}

    # Get field objects from model._fields to access compute/related info
    model_fields = model._fields

    # Also get fields_get for additional info
    fields_info = model.fields_get()

    # Analyze computed and related fields
    for field_name, field_obj in model_fields.items():
        # Get additional info from fields_get if available
        field_data = fields_info.get(field_name, {{}})

        field_info = {{
            "type": field_obj.type,
            "string": field_obj.string or field_data.get("string", ""),
            "dependencies": [],
            "affects": []
        }}

        # Check if it's a computed field
        compute_method = getattr(field_obj, 'compute', None)
        if compute_method:
            try:
                # Try to get compute method from model class
                compute_func = getattr(model_class, compute_method, None) if isinstance(compute_method, str) else None
                if compute_func and hasattr(compute_func, "_depends"):
                    dependencies = list(compute_func._depends)
                    field_info["compute_method"] = compute_method
                    field_info["dependencies"] = dependencies
                    field_info["stored"] = getattr(field_obj, 'store', False)

                    # Analyze cross-model dependencies
                    cross_model_deps = []
                    for dependency in dependencies:
                        if "." in dependency:
                            dependency_parts = dependency.split(".", 1)
                            related_field_name = dependency_parts[0]
                            related_path = dependency_parts[1]

                            # Check if related field has relation
                            if related_field_name in fields_info:
                                related_field_data = fields_info[related_field_name]
                                if related_field_data.get("relation"):
                                    cross_model_deps.append({{
                                        "through_field": related_field_name,
                                        "target_model": related_field_data["relation"],
                                        "target_field": related_path,
                                    }})

                    if cross_model_deps:
                        field_info["cross_model_deps"] = cross_model_deps

                    dynamic_analysis["computed_fields"][field_name] = field_info
            except Exception:
                pass

        # Check if it's a related field
        related_path = getattr(field_obj, 'related', None)
        if related_path:
            field_info["related_path"] = related_path
            if "." in related_path:
                field_info["dependencies"] = [related_path.split(".")[0]]

            # Analyze chain resolution
            chain_info = []
            chain_valid = True

            try:
                current_model = model
                related_parts = related_path.split(".")

                for i, part in enumerate(related_parts):
                    current_fields = current_model.fields_get()
                    if part in current_fields:
                        part_data = current_fields[part]
                        chain_step = {{
                            "model": current_model._name,
                            "field": part,
                            "type": part_data.get("type"),
                            "comodel": part_data.get("relation"),
                        }}
                        chain_info.append(chain_step)

                        # Move to next model if there's a relation
                        if i < len(related_parts) - 1 and part_data.get("relation"):
                            if part_data["relation"] in env:
                                current_model = env[part_data["relation"]]
                            else:
                                chain_valid = False
                                break
                    else:
                        chain_valid = False
                        break
            except Exception:
                chain_valid = False

            field_info["chain_resolution"] = chain_info
            field_info["chain_valid"] = chain_valid
            dynamic_analysis["related_fields"][field_name] = field_info

        # Track field dependencies
        if field_info["dependencies"]:
            dynamic_analysis["field_dependencies"][field_name] = field_info["dependencies"]

    # Calculate reverse dependencies
    for dependent_field, dependencies in dynamic_analysis["field_dependencies"].items():
        for dependency in dependencies:
            base_dependency = dependency.split(".")[0]
            if base_dependency not in dynamic_analysis["reverse_dependencies"]:
                dynamic_analysis["reverse_dependencies"][base_dependency] = []
            dynamic_analysis["reverse_dependencies"][base_dependency].append(dependent_field)

    # Check for runtime fields (selection fields with callable selection)
    try:
        for field_name, field_obj in model_fields.items():
            try:
                if field_obj and field_obj.type == "selection" and callable(field_obj.selection):
                    runtime_field_info = {{
                        "field": field_name,
                        "type": "dynamic_selection",
                        "selection_method": field_obj.selection.__name__ if hasattr(field_obj.selection, "__name__") else str(field_obj.selection),
                    }}

                    try:
                        runtime_selection = field_obj.selection(model)
                        if isinstance(runtime_selection, list):
                            runtime_field_info["current_options"] = runtime_selection
                            runtime_field_info["option_count"] = len(runtime_selection)
                        else:
                            runtime_field_info["error"] = "Selection returned non-list value"
                    except Exception as e:
                        runtime_field_info["error"] = f"Could not evaluate selection: {{str(e)}}"

                    dynamic_analysis["runtime_fields"].append(runtime_field_info)
            except Exception:
                continue
    except Exception:
        pass

    # Add summary statistics
    dynamic_analysis["summary"] = {{
        "computed_field_count": len(dynamic_analysis["computed_fields"]),
        "related_field_count": len(dynamic_analysis["related_fields"]),
        "runtime_field_count": len(dynamic_analysis["runtime_fields"]),
        "fields_with_dependencies": len(dynamic_analysis["field_dependencies"]),
        "fields_affecting_others": len(dynamic_analysis["reverse_dependencies"]),
    }}

    result = dynamic_analysis
"""

    try:
        raw_result = await env.execute_code(code)

        if isinstance(raw_result, dict) and "error" in raw_result:
            return raw_result

        # Apply pagination to runtime_fields list
        paginated_result = raw_result.copy()

        if "runtime_fields" in raw_result and isinstance(raw_result["runtime_fields"], list):
            paginated_runtime = paginate_dict_list(raw_result["runtime_fields"], pagination, ["field", "type"])
            paginated_result["runtime_fields"] = paginated_runtime.to_dict()
            # Update summary count to reflect total, not paginated
            if "summary" in paginated_result:
                paginated_result["summary"]["runtime_field_count"] = paginated_runtime.total_count

        return validate_response_size(paginated_result)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "model": model_name,
        }
