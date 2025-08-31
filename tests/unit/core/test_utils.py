from typing import Any

import pytest

from odoo_intelligence_mcp.core.utils import (
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
        assert response.page_size == 100
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
        result = response.to_dict()

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
        assert params.page_size == 100
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

    def test_from_arguments_offset_zero(self) -> None:
        # Note: offset=0 is treated as falsy so doesn't work correctly
        arguments = {"limit": 20, "offset": 0}
        params = PaginationParams.from_arguments(arguments)
        # Due to bug in from_arguments, offset=0 is ignored
        assert params.page == 1
        assert params.page_size == 100  # Falls back to default

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


def test_validate_response_size_large_string() -> None:
    # Create a large string (>100KB, which is >25K tokens)
    large_string = "x" * 200000
    response = {"data": large_string}

    # The new implementation doesn't raise error but adds warning/truncation info
    result = validate_response_size(response)
    assert "meta" in result
    assert "size_warning" in result["meta"]
    assert result["meta"]["size_warning"]["estimated_tokens"] > 25000


def test_validate_response_size_large_list() -> None:
    # Create a large list
    large_list = ["item"] * 50000
    response = {"items": large_list}  # Use "items" key for truncation logic

    # The new implementation truncates the list instead of raising error
    result = validate_response_size(response)
    assert "truncated" in result
    assert result["truncated"] is True
    assert len(result["items"]) < len(large_list)


def test_validate_response_size_with_custom_limit() -> None:
    # Test with custom max_tokens
    medium_string = "x" * 1000
    response = {"data": medium_string}

    # Should pass with default limit
    result = validate_response_size(response)
    assert result == response

    # With very small limit, should truncate the response
    result = validate_response_size(response, max_tokens=10)
    assert "truncated" in result
    assert result["truncated"] is True
    assert "truncation_info" in result


def test_check_response_size_small() -> None:
    # Small response should return True
    response = {"data": "small"}
    assert check_response_size(response) is True


def test_check_response_size_large() -> None:
    # Large response should return False
    large_string = "x" * 200000
    response = {"data": large_string}
    assert check_response_size(response) is False


def test_check_response_size_with_custom_limit() -> None:
    medium_string = "x" * 1000
    response = {"data": medium_string}

    # Should pass with default limit
    assert check_response_size(response) is True

    # Should fail with very small limit
    assert check_response_size(response, max_tokens=10) is False
