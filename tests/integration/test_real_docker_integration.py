from typing import Any
from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager
from odoo_intelligence_mcp.server import handle_call_tool
from odoo_intelligence_mcp.utils.error_utils import CodeExecutionError, DockerConnectionError
from tests.fixtures import MockDockerRun, container_running


@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_odoo_connection(real_odoo_env_if_available: Any) -> None:
    # This test only runs if Docker container is available
    result = await real_odoo_env_if_available.execute_code("result = len(env)")
    assert isinstance(result, (int, dict))
    if isinstance(result, int):
        assert result > 0  # Should have some models


@pytest.mark.asyncio
@pytest.mark.integration
async def test_docker_container_not_found(mock_docker_run: type[MockDockerRun]) -> None:
    with patch("subprocess.run", mock_docker_run("container_not_found")):
        manager = HostOdooEnvironmentManager()
        env = await manager.get_environment()

        with pytest.raises(DockerConnectionError) as exc_info:
            await env.execute_code("result = 1")

        assert "No such container" in str(exc_info.value)
        assert exc_info.value.container_name == env.container_name


@pytest.mark.asyncio
@pytest.mark.integration
async def test_docker_timeout_handling(mock_docker_run: type[MockDockerRun]) -> None:
    with patch("subprocess.run", mock_docker_run("timeout")):
        manager = HostOdooEnvironmentManager()
        env = await manager.get_environment()

        with pytest.raises(DockerConnectionError) as exc_info:
            await env.execute_code("import time; time.sleep(60)")

        assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_docker_command_not_found() -> None:
    with patch("odoo_intelligence_mcp.utils.docker_utils.docker") as mock_docker:
        mock_docker.from_env.side_effect = FileNotFoundError("docker command not found")
        result = await handle_call_tool("odoo_status", {})

        # Should handle gracefully and return error
        assert len(result) == 1
        import json

        content = json.loads(result[0].text)
        assert "error" in content or content.get("success", False) is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_code_execution_with_odoo_error(mock_docker_run: type[MockDockerRun]) -> None:
    # Mock a response where Odoo returns an error
    with patch(
        "subprocess.run",
        mock_docker_run(
            custom_response={"stdout": '{"error": "NameError: name \'invalid_var\' is not defined", "error_type": "NameError"}'}
        ),
    ):
        manager = HostOdooEnvironmentManager()
        env = await manager.get_environment()

        with pytest.raises(CodeExecutionError) as exc_info:
            await env.execute_code("result = invalid_var")

        assert "NameError" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_json_response_from_odoo(mock_docker_run: type[MockDockerRun]) -> None:
    # Mock a response with invalid JSON
    with patch("subprocess.run", mock_docker_run(custom_response={"stdout": "This is not JSON"})):
        manager = HostOdooEnvironmentManager()
        env = await manager.get_environment()

        result = await env.execute_code("print('test')")
        assert isinstance(result, dict)
        assert "output" in result
        assert result.get("raw") is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_handle_tool_with_all_docker_scenarios() -> None:
    scenarios = [
        ("container_not_found", "No such container", DockerConnectionError),
        ("timeout", "timed out", DockerConnectionError),
    ]

    for scenario, expected_error_text, error_type in scenarios:
        with patch("subprocess.run", MockDockerRun(scenario)):
            with patch("odoo_intelligence_mcp.server.odoo_env_manager.get_environment") as mock_get_env:
                manager = HostOdooEnvironmentManager()
                mock_get_env.return_value = await manager.get_environment()

                result = await handle_call_tool("model_info", {"model_name": "res.partner"})

                import json

                content = json.loads(result[0].text)
                assert content["success"] is False
                assert expected_error_text in content["error"]
                assert content["error_type"] == error_type.__name__


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(not container_running("odoo-opw-shell-1"), reason="Requires running Odoo container")
async def test_real_model_info_if_available() -> None:
    # This test runs against real Odoo if available
    result = await handle_call_tool("model_info", {"model_name": "res.partner"})

    import json

    content = json.loads(result[0].text)

    # With real Odoo, we should get actual data
    assert "error" not in content or content.get("success", True)
    if "model" in content:
        assert content["model"] == "res.partner"
        assert content["table"] == "res_partner"
        assert "fields" in content
        assert "name" in content["fields"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_environment_isolation() -> None:
    # Test that each request gets a fresh environment
    results = []

    with patch("subprocess.run", MockDockerRun(custom_response={"stdout": '{"counter": 1}'})):
        for _ in range(3):
            result = await handle_call_tool("execute_code", {"code": "result = {'counter': 1}"})
            import json

            content = json.loads(result[0].text)
            results.append(content)

    # All results should be the same (no state carried between calls)
    assert all(r == results[0] for r in results)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_requests_handling() -> None:
    # Test that concurrent requests don't interfere
    import asyncio

    async def make_request(model_name: str) -> dict[str, Any]:
        with patch("subprocess.run", MockDockerRun(custom_response={"stdout": f'{{"model": "{model_name}"}}'})):
            result = await handle_call_tool("model_info", {"model_name": model_name})
            import json

            return json.loads(result[0].text)

    # Make concurrent requests
    results = await asyncio.gather(
        make_request("res.partner"),
        make_request("product.template"),
        make_request("sale.order"),
    )

    # Each should have the correct model
    assert results[0]["model"] == "res.partner"
    assert results[1]["model"] == "product.template"
    assert results[2]["model"] == "sale.order"
