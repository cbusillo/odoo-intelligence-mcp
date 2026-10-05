import json
from typing import Any

import pytest

from odoo_intelligence_mcp.core.utils import (
    DEFAULT_PAGE_SIZE,
    PaginatedResponse,
    PaginationParams,
    check_response_size,
    get_optional_bool,
    get_optional_int,
    get_optional_list,
    get_optional_str,
    get_required,
    paginate_dict_list,
    paginate_list,
    validate_response_size,
)


def test_get_required_with_value() -> None:
    arguments = {"key": "value", "other": "data"}
    result = get_required(arguments, "key")
    assert result == "value"


def test_get_required_missing_key() -> None:
    arguments = {"other": "data"}
    with pytest.raises(KeyError) as exc_info:
        get_required(arguments, "key")
    assert "Required argument 'key' is missing" in str(exc_info.value)


def test_get_required_none_value() -> None:
    arguments = {"key": None}
    with pytest.raises(KeyError) as exc_info:
        get_required(arguments, "key")
    assert "Required argument 'key' is missing" in str(exc_info.value)


def test_get_optional_str_with_value() -> None:
    arguments = {"key": "value"}
    result = get_optional_str(arguments, "key")
    assert result == "value"


def test_get_optional_str_with_default() -> None:
    arguments = {}
    result = get_optional_str(arguments, "key", "default")
    assert result == "default"


def test_get_optional_str_none_value() -> None:
    arguments = {"key": None}
    result = get_optional_str(arguments, "key", "default")
    assert result == "default"


def test_get_optional_int_with_int() -> None:
    arguments = {"key": 42}
    result = get_optional_int(arguments, "key")
    assert result == 42


def test_get_optional_int_with_string() -> None:
    arguments = {"key": "42"}
    result = get_optional_int(arguments, "key")
    assert result == 42


def test_get_optional_int_with_float() -> None:
    arguments = {"key": 42.7}
    result = get_optional_int(arguments, "key")
    assert result == 42


def test_get_optional_int_with_default() -> None:
    arguments = {}
    result = get_optional_int(arguments, "key", 10)
    assert result == 10


def test_get_optional_int_invalid_value() -> None:
    arguments = {"key": [1, 2, 3]}
    result = get_optional_int(arguments, "key", 10)
    assert result == 10


def test_get_optional_bool_true() -> None:
    arguments = {"key": True}
    result = get_optional_bool(arguments, "key")
    assert result is True


def test_get_optional_bool_false() -> None:
    arguments = {"key": False}
    result = get_optional_bool(arguments, "key")
    assert result is False


def test_get_optional_bool_with_default() -> None:
    arguments = {}
    result = get_optional_bool(arguments, "key", True)
    assert result is True


def test_get_optional_bool_truthy_value() -> None:
    arguments = {"key": "yes"}
    result = get_optional_bool(arguments, "key")
    assert result is True


def test_get_optional_list_with_list() -> None:
    arguments = {"key": [1, 2, 3]}
    result = get_optional_list(arguments, "key")
    assert result == [1, 2, 3]


def test_get_optional_list_with_single_value() -> None:
    arguments = {"key": "value"}
    result = get_optional_list(arguments, "key")
    assert result == ["value"]


def test_get_optional_list_with_default() -> None:
    arguments = {}
    result = get_optional_list(arguments, "key", ["default"])
    assert result == ["default"]


def test_get_optional_list_none_default() -> None:
    arguments = {}
    result = get_optional_list(arguments, "key")
    assert result == []


class TestPaginatedResponse:
    def test_init_basic(self) -> None:
        items = ["a", "b", "c"]
        response = PaginatedResponse(items, total_count=10)
        assert response.items == items
        assert response.total_count == 10
        assert response.page == 1
        assert response.page_size == DEFAULT_PAGE_SIZE
        assert response.filter_applied is None

    def test_init_with_all_params(self) -> None:
        items = ["a", "b", "c"]
        response = PaginatedResponse(items, total_count=10, page=2, page_size=5, filter_applied="test filter")
        assert response.items == items
        assert response.total_count == 10
        assert response.page == 2
        assert response.page_size == 5
        assert response.filter_applied == "test filter"

    def test_to_dict(self) -> None:
        items = ["a", "b", "c"]
        response = PaginatedResponse(items, total_count=10, page=2, page_size=5)
        result = response.to_dict()

        assert result == {
            "items": ["a", "b", "c"],
            "pagination": {
                "page": 2,
                "page_size": 5,
                "total_count": 10,
                "total_pages": 2,
                "has_next_page": False,
                "has_previous_page": True,
                "filter_applied": None,
            },
        }

    def test_to_dict_with_filter(self) -> None:
        items = ["a"]
        response = PaginatedResponse(items, total_count=1, filter_applied="test")
        result: dict[str, Any] = response.to_dict()

        assert result["pagination"]["filter_applied"] == "test"

    def test_total_pages_calculation(self) -> None:
        response = PaginatedResponse([], total_count=25, page_size=10)
        assert response.total_pages == 3

        response = PaginatedResponse([], total_count=20, page_size=10)
        assert response.total_pages == 2

        response = PaginatedResponse([], total_count=0, page_size=10)
        assert response.total_pages == 0

    def test_has_next_and_previous(self) -> None:
        # First page
        response = PaginatedResponse([], total_count=30, page_size=10)
        assert response.has_next_page is True
        assert response.has_previous_page is False

        # Middle page
        response = PaginatedResponse([], total_count=30, page=2, page_size=10)
        assert response.has_next_page is True
        assert response.has_previous_page is True

        # Last page
        response = PaginatedResponse([], total_count=30, page=3, page_size=10)
        assert response.has_next_page is False
        assert response.has_previous_page is True

        # Single page
        response = PaginatedResponse([], total_count=5, page_size=10)
        assert response.has_next_page is False
        assert response.has_previous_page is False


class TestPaginationParams:
    def test_from_arguments_defaults(self) -> None:
        arguments: dict[str, Any] = {}
        params = PaginationParams.from_arguments(arguments)
        assert params.page == 1
        assert params.page_size == DEFAULT_PAGE_SIZE
        assert params.filter_text is None

    def test_from_arguments_with_page_size(self) -> None:
        arguments = {"page": 2, "page_size": 50, "filter": "test"}
        params = PaginationParams.from_arguments(arguments)
        assert params.page == 2
        assert params.page_size == 50
        assert params.filter_text == "test"

    def test_from_arguments_with_limit_offset(self) -> None:
        # limit=50, offset=100 should be page 3 with size 50
        arguments = {"limit": 50, "offset": 100}
        params = PaginationParams.from_arguments(arguments)
        assert params.page == 3
        assert params.page_size == 50

    def test_from_arguments_page_precedence(self) -> None:
        # When both are provided, limit/offset takes precedence in constructor
        arguments = {"page": 2, "page_size": 25, "limit": 50, "offset": 100}
        params = PaginationParams.from_arguments(arguments)
        # offset=100, limit=50 means page 3 (100/50 + 1)
        assert params.page == 3
        assert params.page_size == 50

    @pytest.mark.parametrize("offset", [0, "0"])
    def test_from_arguments_offset_zero_honors_limit(self, offset: int | str) -> None:
        items = list(range(9))
        arguments = {"limit": 3, "offset": offset}
        params = PaginationParams.from_arguments(arguments)
        result = paginate_list(items, params)

        assert result.items == items[: arguments["limit"]]
        assert result.page_size == arguments["limit"]
        assert result.has_next_page is True

    def test_get_offset(self) -> None:
        params = PaginationParams(page_size=10)
        assert params.offset == 0

        params = PaginationParams(page=2, page_size=10)
        assert params.offset == 10

        params = PaginationParams(page=5, page_size=20)
        assert params.offset == 80


def test_paginate_list() -> None:
    items = list(range(1, 26))  # 1-25

    # First page
    params = PaginationParams(page_size=10)
    result = paginate_list(items, params)
    assert result.items == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert result.total_count == 25
    assert result.has_next_page is True
    assert result.has_previous_page is False

    # Second page
    params = PaginationParams(page=2, page_size=10)
    result = paginate_list(items, params)
    assert result.items == [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    assert result.has_next_page is True
    assert result.has_previous_page is True

    # Last page
    params = PaginationParams(page=3, page_size=10)
    result = paginate_list(items, params)
    assert result.items == [21, 22, 23, 24, 25]
    assert result.has_next_page is False
    assert result.has_previous_page is True

    # Page beyond data
    params = PaginationParams(page=5, page_size=10)
    result = paginate_list(items, params)
    assert result.items == []
    assert result.total_count == 25


def test_paginate_list_with_filter() -> None:
    items = list(range(1, 11))
    params = PaginationParams(page_size=5, filter_text="numbers")
    result = paginate_list(items, params)
    assert result.filter_applied == "numbers"


def test_paginate_dict_list() -> None:
    items = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
        {"id": 4, "name": "David"},
        {"id": 5, "name": "Eve"},
    ]

    params = PaginationParams(page_size=2)
    result = paginate_dict_list(items, params)

    assert result.items == [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    assert result.total_count == 5
    assert result.page == 1
    assert result.page_size == 2
    assert result.has_next_page is True


def test_paginate_dict_list_with_filter() -> None:
    items = [{"id": i, "name": f"test{i}"} for i in range(1, 6)]
    params = PaginationParams(page_size=10, filter_text="test")
    result = paginate_dict_list(items, params)

    # All items should match because they all contain "test"
    assert len(result.items) == 5
    assert result.filter_applied == "test"


def test_validate_response_size_small() -> None:
    # Small response should pass through unchanged
    response = {"data": "small"}
    result = validate_response_size(response)
    assert result == response


def test_validate_response_size_warns_at_configured_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    from odoo_intelligence_mcp.core import utils

    monkeypatch.setattr(utils, "RESPONSE_SIZE_WARNING_TOKENS", 12)
    text = "x" * 80
    response = {"data": text}
    result = validate_response_size(response, max_tokens=100)
    assert result["meta"]["size_warning"]["estimated_tokens"] > utils.RESPONSE_SIZE_WARNING_TOKENS
    assert result["data"] == text
    assert "truncated" not in result


@pytest.mark.parametrize("container_key", [None, "implementations", "computed_fields"])
def test_validate_response_size_truncates_list(container_key: str | None) -> None:
    items = [{"name": f"item-{number}"} for number in range(8)]
    container = {"items": items}
    response = {container_key: container} if container_key else container
    result = validate_response_size(response, max_tokens=8)
    remaining_items = result[container_key]["items"] if container_key else result["items"]

    assert result["truncated"] is True
    assert 0 < len(remaining_items) < len(items)
    assert remaining_items == items[: len(remaining_items)]
    assert result["truncation_info"]["original_items"] == len(items)
    assert result["truncation_info"]["kept_items"] == len(remaining_items)


def test_validate_response_size_truncates_fields_at_configured_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    from odoo_intelligence_mcp.core import utils

    monkeypatch.setattr(utils, "TRUNCATED_STRING_LENGTH", 6)
    monkeypatch.setattr(utils, "TRUNCATED_LIST_LENGTH", 2)
    text = "fixture-text"
    values = list(range(5))
    response = {"data": text, "values": values}
    result = validate_response_size(response, max_tokens=1)

    assert result["truncated"] is True
    assert result["data"].startswith(text[: utils.TRUNCATED_STRING_LENGTH])
    assert text not in result["data"]
    assert result["values"] == values[: utils.TRUNCATED_LIST_LENGTH]
    assert set(result["truncated_fields"]) == {"data", "values"}


@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_check_response_size_obeys_requested_limit(difference: int) -> None:
    response = {"data": "fixture-text"}
    estimated_tokens = len(json.dumps(response)) // 4
    limit = estimated_tokens + difference
    assert check_response_size(response, max_tokens=limit) is (difference >= 0)
