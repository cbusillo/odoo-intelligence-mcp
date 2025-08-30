import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager


def docker_available() -> bool:
    try:
        # noinspection LSPLocalInspectionTool
        result = subprocess.run(["docker", "ps"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def container_running(container_name: str) -> bool:
    if not docker_available():
        return False

    # noinspection LSPLocalInspectionTool
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"], capture_output=True, text=True
    )
    return container_name in result.stdout


@pytest.fixture
def mock_field_data() -> dict[str, Any]:
    return {
        "name": {"type": "char", "string": "Name", "required": True, "readonly": False, "store": True},
        "email": {"type": "char", "string": "Email", "required": False, "readonly": False, "store": True},
        "partner_id": {"type": "many2one", "string": "Partner", "relation": "res.partner", "store": True},
        "active": {"type": "boolean", "string": "Active", "required": False, "readonly": False, "store": True},
        "create_date": {"type": "datetime", "string": "Created on", "required": False, "readonly": True, "store": True},
        "amount_total": {
            "type": "float",
            "string": "Total",
            "required": False,
            "readonly": True,
            "store": False,
            "compute": "_compute_amount",
        },
    }


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


@pytest.fixture
def mock_product_template_data() -> dict[str, Any]:
    return {
        "model": "product.template",
        "name": "product.template",
        "table": "product_template",
        "description": "Product",
        "rec_name": "name",
        "order": "id",
        "fields": {
            "name": {"type": "char", "string": "Name", "required": True, "readonly": False, "store": True},
            "list_price": {"type": "float", "string": "Sales Price", "required": False, "readonly": False, "store": True},
            "standard_price": {"type": "float", "string": "Cost", "required": False, "readonly": False, "store": True},
            "categ_id": {"type": "many2one", "string": "Product Category", "relation": "product.category", "store": True},
            "type": {
                "type": "selection",
                "string": "Product Type",
                "selection": [["consu", "Consumable"], ["service", "Service"], ["product", "Storable Product"]],
                "store": True,
            },
        },
        "field_count": 5,
        "methods": ["create", "write", "read", "unlink", "search"],
        "method_count": 5,
    }


@pytest.fixture
def mock_odoo_models() -> dict[str, dict[str, Any]]:
    return {
        "res.partner": {
            "name": "res.partner",
            "description": "Contact",
            "table": "res_partner",
            "transient": False,
            "abstract": False,
        },
        "product.template": {
            "name": "product.template",
            "description": "Product",
            "table": "product_template",
            "transient": False,
            "abstract": False,
        },
        "product.product": {
            "name": "product.product",
            "description": "Product Variant",
            "table": "product_product",
            "transient": False,
            "abstract": False,
        },
        "sale.order": {
            "name": "sale.order",
            "description": "Sales Order",
            "table": "sale_order",
            "transient": False,
            "abstract": False,
        },
        "base.import.wizard": {
            "name": "base.import.wizard",
            "description": "Import Wizard",
            "table": "base_import_wizard",
            "transient": True,
            "abstract": False,
        },
    }


@pytest.fixture
def enhanced_mock_odoo_env(
    mock_res_partner_data: dict[str, Any], mock_product_template_data: dict[str, Any], mock_odoo_models: dict[str, Any]
) -> MagicMock:
    env = MagicMock()

    # Mock execute_code to return different data based on the code
    async def mock_execute_code(code: str) -> dict[str, Any]:
        if "model_name not in env" in code:
            if "res.partner" in code:
                return mock_res_partner_data
            elif "product.template" in code:
                return mock_product_template_data
            elif "invalid.model" in code:
                return {"error": "Model 'invalid.model' not found"}

        elif "list(env)" in code:  # For search_models
            return {
                "exact_matches": [],
                "partial_matches": [m for m in mock_odoo_models.values() if "product" in m["name"]],
                "description_matches": [],
                "total_models": len(mock_odoo_models),
                "pattern": "product",
            }

        # Default response
        return {"success": True}

    env.execute_code = mock_execute_code
    return env


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


@pytest.fixture
def docker_error_responses() -> dict[str, dict[str, Any]]:
    from odoo_intelligence_mcp.core.env import load_env_config

    config = load_env_config()
    container_name = config.container_name  # Use primary container

    return {
        "container_not_found": {"returncode": 125, "stderr": f"Error: No such container: {container_name}"},
        "container_not_running": {"returncode": 126, "stderr": f"Error: Container {container_name} is not running"},
        "docker_not_running": {"returncode": 1, "stderr": "Cannot connect to the Docker daemon"},
        "timeout": {"timeout": True},
        "permission_denied": {"returncode": 126, "stderr": "Permission denied while trying to connect to the Docker daemon"},
    }


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
            result.stderr = f"Error: No such container: {config.shell_container}"
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
