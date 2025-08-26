from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...type_defs.odoo_types import CompatibleEnvironment


async def execute_and_paginate_results(env: CompatibleEnvironment, code: str, pagination: PaginationParams) -> dict[str, Any]:
    try:
        # noinspection PyUnresolvedReferences
        data = await env.execute_code(code)
        if isinstance(data, dict) and "error" in data:
            return data
        if "results" in data:
            results = data["results"]
            assert isinstance(results, list)  # Type assertion for PyCharm
            paginated_results = paginate_dict_list(results, pagination, search_fields=["model", "description"])
            return validate_response_size({"fields": paginated_results.to_dict()})
        else:
            return {"error": "Failed to get results from execute_code", "data": data}
    except Exception as e:
        return {"error": f"Failed to execute code: {e}", "error_type": type(e).__name__}
