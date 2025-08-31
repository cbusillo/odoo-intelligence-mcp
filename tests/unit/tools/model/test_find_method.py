from unittest.mock import AsyncMock, MagicMock

import pytest

from odoo_intelligence_mcp.tools.model.find_method import find_method_implementations


@pytest.mark.asyncio
async def test_find_method_basic(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    method_name = "create"

    # Mock the execute_code to return method implementations
    mock_odoo_env.execute_code = AsyncMock(
        return_value=[
            {
                "model": "res.partner",
                "module": "base",
                "signature": "(self, vals)",
                "doc": "Create a new record",
                "source_preview": "def create(self, vals):\n    return super().create(vals)",
                "has_super": True,
            }
        ]
    )

    result = await find_method_implementations(mock_odoo_env, method_name, PaginationParams())

    assert "method_name" in result
    assert result["method_name"] == method_name
    assert "implementations" in result
    assert isinstance(result["implementations"], dict)
    assert "items" in result["implementations"]


@pytest.mark.asyncio
async def test_find_method_with_results(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    method_name = "compute_amount"

    # Mock multiple implementations
    mock_odoo_env.execute_code = AsyncMock(
        return_value=[
            {
                "model": "account.move",
                "module": "account",
                "signature": "(self)",
                "doc": "Compute amount",
                "source_preview": "def compute_amount(self):\n    pass",
                "has_super": False,
            },
            {
                "model": "sale.order",
                "module": "sale",
                "signature": "(self)",
                "doc": "Compute order amount",
                "source_preview": "def compute_amount(self):\n    pass",
                "has_super": False,
            },
        ]
    )

    result = await find_method_implementations(mock_odoo_env, method_name, PaginationParams())

    assert "method_name" in result
    assert result["method_name"] == method_name
    assert "implementations" in result
    assert isinstance(result["implementations"], dict)


@pytest.mark.asyncio
async def test_find_method_not_found(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    method_name = "nonexistent_method"

    # Mock empty result
    mock_odoo_env.execute_code = AsyncMock(return_value=[])

    result = await find_method_implementations(mock_odoo_env, method_name, PaginationParams())

    assert "method_name" in result
    assert result["method_name"] == method_name
    assert "implementations" in result
    if isinstance(result["implementations"], dict):
        assert result["implementations"]["items"] == []


@pytest.mark.asyncio
async def test_find_method_with_pagination(mock_odoo_env: MagicMock) -> None:
    from odoo_intelligence_mcp.core.utils import PaginationParams

    method_name = "write"
    pagination = PaginationParams(page_size=5)

    # Mock many implementations for pagination
    mock_implementations = [
        {
            "model": f"model.{i}",
            "module": f"module_{i}",
            "signature": "(self, vals)",
            "doc": f"Write method {i}",
            "source_preview": f"def write(self, vals):\n    # Model {i}",
            "has_super": True,
        }
        for i in range(10)
    ]
    mock_odoo_env.execute_code = AsyncMock(return_value=mock_implementations)

    result = await find_method_implementations(mock_odoo_env, method_name, pagination)

    assert "method_name" in result
    assert "implementations" in result
    if isinstance(result["implementations"], dict):
        assert "pagination" in result["implementations"]
