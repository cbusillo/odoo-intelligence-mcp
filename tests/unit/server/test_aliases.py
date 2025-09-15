import json
from unittest.mock import AsyncMock, patch

import pytest

from odoo_intelligence_mcp.server import handle_call_tool


@pytest.mark.asyncio
async def test_model_query_list_alias_routes_to_search() -> None:
    with (
        patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock) as mock_env,
        patch("odoo_intelligence_mcp.server._handle_search_models", new_callable=AsyncMock) as mock_search,
    ):
        mock_env.return_value = AsyncMock()
        mock_search.return_value = {"items": [], "pagination": {"page": 1, "page_size": 25, "total_count": 0}}

        out = await handle_call_tool("model_query", {"operation": "list", "limit": 10})
        content = json.loads(out[0].text)
        assert "items" in content or "error" not in content
        mock_search.assert_awaited()


@pytest.mark.asyncio
async def test_field_query_list_alias_lists_fields() -> None:
    with (
        patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock) as mock_env,
        patch("odoo_intelligence_mcp.server._handle_model_info", new_callable=AsyncMock) as mock_info,
    ):
        mock_env.return_value = AsyncMock()
        mock_info.return_value = {
            "model": "res.partner",
            "fields": {
                "name": {"type": "char", "string": "Name", "required": False, "store": True},
                "email": {"type": "char", "string": "Email", "required": False, "store": True},
            },
        }

        out = await handle_call_tool("field_query", {"operation": "list", "model_name": "res.partner", "page": 1, "page_size": 1})
        content = json.loads(out[0].text)
        assert content.get("model") == "res.partner"
        assert "fields" in content and "items" in content["fields"]


@pytest.mark.asyncio
async def test_analysis_query_inheritance_alias_routes() -> None:
    with (
        patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment", new_callable=AsyncMock) as mock_env,
        patch("odoo_intelligence_mcp.server._handle_inheritance_chain", new_callable=AsyncMock) as mock_inh,
    ):
        mock_env.return_value = AsyncMock()
        mock_inh.return_value = {"model": "res.partner", "summary": {}}

        out = await handle_call_tool("analysis_query", {"analysis_type": "inheritance", "model_name": "res.partner"})
        content = json.loads(out[0].text)
        assert content.get("model") == "res.partner"
        mock_inh.assert_awaited()
