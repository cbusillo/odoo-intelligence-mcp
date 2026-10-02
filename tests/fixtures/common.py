from typing import Any


def assert_model_info_response(response: dict[str, Any], model_name: str) -> None:
    assert response.get("name") == model_name or response.get("model") == model_name
    assert "table" in response
    assert "description" in response
    assert "fields" in response
    assert isinstance(response["fields"], dict)
    assert "displayed_field_count" in response
    assert response["displayed_field_count"] == len(response["fields"])
    assert "total_field_count" in response
    assert "methods_sample" in response
    assert isinstance(response["methods_sample"], list)
    assert "total_method_count" in response
    assert response["total_method_count"] >= len(response["methods_sample"])
    assert "pagination" in response
