from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.core.utils import PaginationParams
from odoo_intelligence_mcp.tools.code.search_code import search_code


@pytest.mark.asyncio
async def test_search_code_basic_pattern() -> None:
    # Mock container exec result
    mock_stdout = "[{'file': '/addons/test_module/models/test_model.py', 'line': 5, 'match': '    def test_method(self):'}]".replace(
        "'", '"'
    )

    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": mock_stdout, "stderr": "", "exit_code": 0}

        result = await search_code("test_method")

    assert "results" in result and "items" in result["results"]
    assert "pagination" in result["results"]
    assert len(result["results"]["items"]) == 1
    assert result["results"]["items"][0]["line"] == 5
    assert "test_method" in result["results"]["items"][0]["match"]


@pytest.mark.asyncio
async def test_search_code_xml_files() -> None:
    import json

    mock_stdout = json.dumps(
        [
            {
                "file": "/addons/module/views/view.xml",
                "line": 5,
                "match": '        <field name="model">test.model</field>',
            }
        ]
    )

    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": mock_stdout, "stderr": "", "exit_code": 0}

        result = await search_code("test\\.model", "xml")

    assert "results" in result and "items" in result["results"]
    assert "pagination" in result["results"]


@pytest.mark.asyncio
async def test_search_code_with_pagination() -> None:
    # Create many mock results
    mock_results = []
    for i in range(30):
        mock_results.append(
            {
                "file": f"/addons/module/models/model_{i}.py",
                "line": 10,
                "match": "def test_method(self):",
                "context": "def test_method(self):",
            }
        )

    mock_json = str(mock_results).replace("'", '"')
    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": mock_json, "stderr": "", "exit_code": 0}

        pagination = PaginationParams(limit=10, offset=0)
        result = await search_code("test_method", pagination=pagination)

    assert "results" in result and "items" in result["results"]
    assert "pagination" in result["results"]
    assert result["results"]["pagination"]["page_size"] == 10


@pytest.mark.asyncio
async def test_search_code_no_matches() -> None:
    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": "[]", "stderr": "", "exit_code": 0}

        result = await search_code("nonexistent_pattern")

    assert "results" in result and "items" in result["results"]
    assert len(result["results"]["items"]) == 0
    assert result["results"]["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_search_code_invalid_regex() -> None:
    # Invalid regex should be caught before execution
    result = await search_code("[invalid(regex")

    assert "error" in result
    assert "Invalid regex pattern" in result["error"]


@pytest.mark.asyncio
async def test_search_code_file_read_error() -> None:
    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Failed to read file",
            "error": "IOError",
            "exit_code": 1,
        }

        result = await search_code("test_pattern")

    assert "error" in result
    assert "Failed to read file" in result["error"]


@pytest.mark.asyncio
async def test_search_code_javascript_files() -> None:
    mock_stdout = (
        "[{'file': '/addons/module/static/src/js/widget.js', 'line': 15, 'match': '    testFunction: function() {'}]".replace(
            "'", '"'
        )
    )

    with patch("odoo_intelligence_mcp.utils.docker_utils.DockerClientManager.exec_run") as mock_exec:
        mock_exec.return_value = {"success": True, "stdout": mock_stdout, "stderr": "", "exit_code": 0}

        result = await search_code("testFunction", "js")

    assert "results" in result and "items" in result["results"]
    assert len(result["results"]["items"]) == 1
    assert result["results"]["items"][0]["file"].endswith(".js")
    assert "testFunction" in result["results"]["items"][0]["match"]
