from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment


async def analyze_performance(
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
    issues = []

    # Analyze fields for potential performance issues
    for field_name, field in model._fields.items():
        # Check for non-stored relational fields
        if field.type in ["many2one", "one2many", "many2many"]:
            if not getattr(field, "store", True):
                issues.append({{
                    "type": "potential_n_plus_1",
                    "field": field_name,
                    "field_type": field.type,
                    "description": f"Non-stored relational field '{{field_name}}' might cause N+1 queries when accessed in loops",
                    "severity": "high" if field.type in ["one2many", "many2many"] else "medium",
                    "recommendation": "Consider storing this field or using batch prefetching"
                }})

        # Check for computed fields without store
        if hasattr(field, "compute") and field.compute:
            if not getattr(field, "store", False):
                # Check if it has heavy dependencies
                depends = getattr(field, "depends", [])
                if depends and len(depends) > 3:
                    issues.append({{
                        "type": "expensive_compute",
                        "field": field_name,
                        "description": f"Computed field '{{field_name}}' with {{len(depends)}} dependencies is not stored",
                        "severity": "medium",
                        "depends_on": depends,
                        "recommendation": "Consider storing this computed field if frequently accessed"
                    }})

        # Check for missing indexes on commonly filtered fields
        if field.type in ["char", "integer", "many2one", "date", "datetime"]:
            if getattr(field, "store", True) and not getattr(field, "index", False):
                # These field names commonly need indexes
                index_candidates = ["name", "code", "reference", "state", "company_id",
                                  "partner_id", "user_id", "create_date", "date"]
                if field_name in index_candidates:
                    issues.append({{
                        "type": "missing_index",
                        "field": field_name,
                        "field_type": field.type,
                        "description": f"Field '{{field_name}}' is commonly used in searches but lacks an index",
                        "severity": "medium",
                        "recommendation": "Add index=True to this field definition"
                    }})

    # Check for methods that might have performance issues
    model_class = type(model)
    method_issues = []

    for method_name in dir(model_class):
        if method_name.startswith('_') and not method_name.startswith('__'):
            method = getattr(model_class, method_name, None)
            if callable(method) and hasattr(method, '__func__'):
                # Check for methods that might do heavy computation
                if any(keyword in method_name for keyword in ['compute', 'calculate', 'get']):
                    method_issues.append({{
                        "type": "potential_heavy_method",
                        "method": method_name,
                        "description": f"Method '{{method_name}}' might perform heavy computations",
                        "severity": "low",
                        "recommendation": "Profile this method and consider caching results if expensive"
                    }})

    # Add method issues to main issues list
    issues.extend(method_issues[:5])  # Limit to top 5 method issues

    # Sort issues by severity
    severity_order = {{"high": 0, "medium": 1, "low": 2}}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

    result = {{
        "model": model_name,
        "performance_issues": issues,
        "issue_count": len(issues),
        "recommendations": [
            "Consider adding database indexes on frequently queried fields",
            "Use prefetch_fields parameter for related fields in loops",
            "Batch operations instead of individual record processing",
            "Store computed fields that are frequently accessed",
            "Use SQL queries for complex aggregations instead of ORM",
            "Implement proper caching for expensive computations"
        ]
    }}
"""

    try:
        raw_result = await env.execute_code(code)

        if isinstance(raw_result, dict) and "error" in raw_result:
            return raw_result

        # Apply pagination to performance_issues list
        paginated_result = raw_result.copy()

        if "performance_issues" in raw_result and isinstance(raw_result["performance_issues"], list):
            paginated_issues = paginate_dict_list(raw_result["performance_issues"], pagination, ["field", "type", "description"])
            paginated_result["performance_issues"] = paginated_issues.to_dict()
            # Update issue count to reflect paginated results
            paginated_result["issue_count"] = paginated_issues.total_count

        return validate_response_size(paginated_result)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "model": model_name,
        }
