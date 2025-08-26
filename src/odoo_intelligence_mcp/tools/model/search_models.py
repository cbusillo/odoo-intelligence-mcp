from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from ...type_defs.odoo_types import CompatibleEnvironment
from ...utils.error_utils import handle_tool_error


@handle_tool_error
async def search_models(env: CompatibleEnvironment, pattern: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    code = f"""
import re

pattern = {pattern!r}
pattern_lower = pattern.lower()
exact_matches = []
partial_matches = []
description_matches = []
all_models = []

# Get all models
model_names = list(env)
for model_name in sorted(model_names):
    try:
        model = env[model_name]
        model_info = {{
            "name": model_name,
            "description": model._description or model_name,
            "table": model._table,
            "transient": model._transient,
            "abstract": model._abstract,
        }}

        all_models.append(model_info)

        # Check for exact match
        if model_name == pattern:
            exact_matches.append(model_info)
        # Check for partial match in name
        elif pattern_lower in model_name.lower():
            partial_matches.append(model_info)
        # Check for match in description
        elif model._description and pattern_lower in model._description.lower():
            description_matches.append(model_info)

    except Exception:
        # Skip models that can't be accessed
        continue

# Compile results
result = {{
    "exact_matches": exact_matches,
    "partial_matches": partial_matches,
    "description_matches": description_matches,
    "total_models": len(all_models),
    "pattern": pattern
}}
"""

    result = await env.execute_code(code)

    if pagination and "exact_matches" in result:
        # Combine all matches for pagination
        all_matches = []

        # Add exact matches with priority
        exact_matches = result.get("exact_matches", [])
        assert isinstance(exact_matches, list)  # Type assertion for PyCharm
        for match in exact_matches:
            match["match_type"] = "exact"
            match["priority"] = 1
            all_matches.append(match)

        # Add partial matches
        partial_matches = result.get("partial_matches", [])
        assert isinstance(partial_matches, list)  # Type assertion for PyCharm
        for match in partial_matches:
            match["match_type"] = "partial"
            match["priority"] = 2
            all_matches.append(match)

        # Add description matches
        description_matches = result.get("description_matches", [])
        assert isinstance(description_matches, list)  # Type assertion for PyCharm
        for match in description_matches:
            match["match_type"] = "description"
            match["priority"] = 3
            all_matches.append(match)

        # Sort by priority and name
        all_matches.sort(key=lambda x: (x["priority"], x["name"]))

        # Apply pagination
        paginated_result = paginate_dict_list(all_matches, pagination, ["name", "description"])

        return {"pattern": result["pattern"], "total_models": result["total_models"], "matches": paginated_result.to_dict()}

    return result
