import json
from typing import Any, TypeVar

T = TypeVar("T")


def get_required(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if value is None:
        raise KeyError(f"Required argument '{key}' is missing")
    return str(value)


def get_optional_str(arguments: dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = arguments.get(key)
    if value is None:
        return default
    return str(value)


def get_optional_int(arguments: dict[str, Any], key: str, default: int | None = None) -> int | None:
    value = arguments.get(key)
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, (str, float)):
        return int(value)
    return default


def get_optional_bool(arguments: dict[str, Any], key: str, default: bool = False) -> bool:
    value = arguments.get(key)
    if value is None:
        return default
    return bool(value)


def get_optional_list(arguments: dict[str, Any], key: str, default: list | None = None) -> list:
    value = arguments.get(key)
    if value is None:
        return default or []
    if isinstance(value, list):
        return value
    return [value]


class PaginatedResponse[T]:
    def __init__(
        self, items: list[T], total_count: int, page: int = 1, page_size: int = 100, filter_applied: str | None = None
    ) -> None:
        self.items = items
        self.total_count = total_count
        self.page = page
        self.page_size = page_size
        self.filter_applied = filter_applied

    @property
    def total_pages(self) -> int:
        return (self.total_count + self.page_size - 1) // self.page_size

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous_page(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict[str, object]:
        return {
            "items": self.items,
            "pagination": {
                "page": self.page,
                "page_size": self.page_size,
                "total_count": self.total_count,
                "total_pages": self.total_pages,
                "has_next_page": self.has_next_page,
                "has_previous_page": self.has_previous_page,
                "filter_applied": self.filter_applied,
            },
        }


class PaginationParams:
    def __init__(
        self,
        page: int = 1,
        page_size: int = 100,
        limit: int | None = None,
        offset: int | None = None,
        filter_text: str | None = None,
    ) -> None:
        if limit is not None and offset is not None:
            self.page = (offset // (limit or 100)) + 1
            self.page_size = limit
        else:
            self.page = max(1, page)
            self.page_size = min(max(1, page_size), 1000)

        self.filter_text = filter_text

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @classmethod
    def from_arguments(cls, arguments: dict[str, Any]) -> "PaginationParams":
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 100)
        limit = arguments.get("limit")
        offset = arguments.get("offset")
        filter_text = arguments.get("filter")

        return cls(
            page=int(page) if isinstance(page, (int, str)) and page else 1,
            page_size=int(page_size) if isinstance(page_size, (int, str)) and page_size else 100,
            limit=int(limit) if limit and isinstance(limit, (int, str)) else None,
            offset=int(offset) if offset and isinstance(offset, (int, str)) else None,
            filter_text=str(filter_text) if filter_text else None,
        )


def paginate_list[T](items: list[T], pagination: PaginationParams) -> PaginatedResponse[T]:
    filtered_items = items

    if pagination.filter_text:
        filter_lower = pagination.filter_text.lower()
        filtered_items = [item for item in items if filter_lower in str(item).lower()]

    total_count = len(filtered_items)
    start_idx = pagination.offset
    end_idx = start_idx + pagination.page_size

    page_items = filtered_items[start_idx:end_idx]

    return PaginatedResponse(
        items=page_items,
        total_count=total_count,
        page=pagination.page,
        page_size=pagination.page_size,
        filter_applied=pagination.filter_text,
    )


def paginate_dict_list(
    items: list[dict[str, Any]], pagination: PaginationParams, search_fields: list[str] | None = None
) -> PaginatedResponse[dict[str, Any]]:
    filtered_items = items

    if pagination.filter_text:
        filter_lower = pagination.filter_text.lower()

        def matches_filter(item: dict[str, Any]) -> bool:
            if search_fields:
                return any(field in item and filter_lower in str(item[field]).lower() for field in search_fields)
            return filter_lower in str(item).lower()

        filtered_items = [item for item in items if matches_filter(item)]

    total_count = len(filtered_items)
    start_idx = pagination.offset
    end_idx = start_idx + pagination.page_size

    page_items = filtered_items[start_idx:end_idx]

    return PaginatedResponse(
        items=page_items,
        total_count=total_count,
        page=pagination.page,
        page_size=pagination.page_size,
        filter_applied=pagination.filter_text,
    )


class ResponseSizeError(Exception):
    def __init__(self, estimated_tokens: int, max_tokens: int = 25000) -> None:
        self.estimated_tokens = estimated_tokens
        self.max_tokens = max_tokens
        super().__init__(
            f"MCP tool response ({estimated_tokens} tokens) exceeds maximum allowed tokens ({max_tokens}). "
            f"Please use pagination, filtering, or limit parameters to reduce the response size."
        )


def check_response_size(data: dict[str, Any], max_tokens: int = 25000) -> bool:
    try:
        json_str = json.dumps(data)
        estimated_tokens = len(json_str) // 4
        return estimated_tokens <= max_tokens
    except (TypeError, ValueError):
        return True


def validate_response_size(data: dict[str, Any], max_tokens: int = 25000) -> dict[str, Any]:
    try:
        json_str = json.dumps(data, default=str)
        estimated_tokens = len(json_str) // 4

        # Add size warning for large responses
        if estimated_tokens > 15000:  # 15K token warning threshold
            if "meta" not in data:
                data["meta"] = {}
            data["meta"]["size_warning"] = {
                "estimated_tokens": estimated_tokens,
                "message": "Large response detected. Consider using pagination, filtering, or limit parameters.",
                "recommendations": [
                    "Use pagination.page_size to limit results",
                    "Apply filter_text to narrow results",
                    "Use specific limit parameters where available",
                ],
            }

        if estimated_tokens > max_tokens:
            # Instead of failing, truncate the response

            # Check for paginated responses (may be nested)
            items_path: list[str] | None = None
            if "items" in data:
                items_path = ["items"]
            elif "implementations" in data and isinstance(data["implementations"], dict) and "items" in data["implementations"]:
                items_path = ["implementations", "items"]
            elif "computed_fields" in data and isinstance(data["computed_fields"], dict) and "items" in data["computed_fields"]:
                items_path = ["computed_fields", "items"]

            if items_path:
                # Navigate to the items list
                items_container = data
                for key in items_path[:-1]:
                    items_container = items_container[key]
                items_key = items_path[-1]
                assert isinstance(items_key, str)

                # For paginated responses, reduce items
                original_count = len(items_container[items_key])
                target_ratio = max_tokens / estimated_tokens
                keep_items = max(1, int(original_count * target_ratio * 0.8))  # 80% to ensure under limit

                items_container[items_key] = items_container[items_key][:keep_items]
                data["truncated"] = True
                data["truncation_info"] = {
                    "original_items": original_count,
                    "kept_items": keep_items,
                    "reason": f"Response exceeded {max_tokens} token limit",
                }
            elif isinstance(data, dict):
                # For non-paginated responses, add truncation warning
                data["truncated"] = True
                data["truncation_info"] = {
                    "estimated_tokens": estimated_tokens,
                    "max_tokens": max_tokens,
                    "message": "Response truncated due to size. Use pagination or filtering to get complete data.",
                }

                # Try to intelligently truncate large fields
                for key, value in list(data.items()):
                    if isinstance(value, list) and len(value) > 10:
                        data[key] = value[:10]
                        if "truncated_fields" not in data:
                            data["truncated_fields"] = []
                        data["truncated_fields"].append(key)
                    elif isinstance(value, str) and len(value) > 1000:
                        data[key] = value[:1000] + "... (truncated)"
                        if "truncated_fields" not in data:
                            data["truncated_fields"] = []
                        data["truncated_fields"].append(key)

        return data
    except (TypeError, ValueError):
        return data


def add_pagination_to_schema(base_schema: dict[str, Any]) -> dict[str, Any]:
    pagination_properties = {
        "page": {"type": "integer", "default": 1, "description": "Page number for pagination"},
        "page_size": {"type": "integer", "default": 100, "maximum": 1000, "description": "Number of items per page"},
        "limit": {"type": "integer", "maximum": 1000, "description": "Maximum number of items to return"},
        "offset": {"type": "integer", "description": "Number of items to skip"},
        "filter": {"type": "string", "description": "Optional filter to apply to results"},
    }

    enhanced_schema = base_schema.copy()
    if "properties" not in enhanced_schema:
        enhanced_schema["properties"] = {}
    enhanced_schema["properties"].update(pagination_properties)

    return enhanced_schema
