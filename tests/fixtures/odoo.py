import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager


def docker_available() -> bool:
    try:
        # noinspection LSPLocalInspectionTool
        result = subprocess.run(["/usr/bin/env", "docker", "ps"], capture_output=True, timeout=5)
        return result.returncode == 0
    except subprocess.SubprocessError, FileNotFoundError:
        return False


@pytest.fixture
def mock_res_partner_data() -> dict[str, Any]:
    return {
        "model": "res.partner",
        "name": "res.partner",
        "table": "res_partner",
        "description": "Contact",
        "rec_name": "name",
        "order": "id",
        "fields": {
            "name": {"type": "char", "string": "Name", "required": True, "readonly": False, "store": True},
            "email": {"type": "char", "string": "Email", "required": False, "readonly": False, "store": True},
            "phone": {"type": "char", "string": "Phone", "required": False, "readonly": False, "store": True},
            "is_company": {"type": "boolean", "string": "Is a Company", "required": False, "readonly": False, "store": True},
            "parent_id": {"type": "many2one", "string": "Related Company", "relation": "res.partner", "store": True},
            "child_ids": {
                "type": "one2many",
                "string": "Contact",
                "relation": "res.partner",
                "inverse_name": "parent_id",
                "store": False,
            },
        },
        "field_count": 6,
        "methods": ["create", "write", "read", "unlink", "search", "name_get", "name_search"],
        "method_count": 7,
    }


@pytest_asyncio.fixture
async def real_odoo_env_if_available() -> HostOdooEnvironment | None:
    # Use the existing environment manager which loads config from env.py
    manager = HostOdooEnvironmentManager()

    # Trust the MCP server's auto-start functionality instead of pre-checking
    # The ensure_container_running() method will handle starting containers as needed

    # Add timeout to prevent hanging during auto-start
    try:
        import asyncio

        return await asyncio.wait_for(manager.get_environment(), timeout=30.0)
    except TimeoutError:
        pytest.skip(f"Timeout connecting to Odoo container {manager.container_name}")


class MockDockerRun:
    def __init__(self, scenario: str = "success", custom_response: dict[str, Any] | None = None) -> None:
        self.scenario = scenario
        self.custom_response = custom_response

    def __call__(self, *args: Any, **kwargs: Any) -> MagicMock:
        if self.scenario == "timeout":
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=30)

        result = MagicMock()

        if self.scenario == "success":
            result.returncode = 0
            result.stdout = self.custom_response.get("stdout", '{"success": true}') if self.custom_response else '{"success": true}'
            result.stderr = ""
        elif self.scenario == "container_not_found":
            from odoo_intelligence_mcp.core.env import load_env_config

            config = load_env_config()
            result.returncode = 125
            result.stdout = ""
            result.stderr = f"Error: No such container: {config.script_runner_container}"
        elif self.scenario == "docker_not_running":
            raise FileNotFoundError("docker command not found")
        else:
            result.returncode = 1
            result.stdout = ""
            result.stderr = "Unknown error"

        return result


@pytest.fixture
def mock_docker_run() -> type[MockDockerRun]:
    return MockDockerRun
