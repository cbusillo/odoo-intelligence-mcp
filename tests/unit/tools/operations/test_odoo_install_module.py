from unittest.mock import MagicMock, patch

import pytest
from docker.errors import NotFound

from odoo_intelligence_mcp.tools.operations.module_update import odoo_install_module


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_install_module_success() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.module_update.docker") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()

        # Mock exec_run to return proper output structure
        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"Module 'sale' installed successfully", b"")
        mock_container.exec_run.return_value = mock_exec_result

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        result = await odoo_install_module("sale")

        assert result["success"] is True
        assert result["modules"] == ["sale"]
        assert result["operation"] == "install"
        assert "Module 'sale' installed successfully" in result["stdout"]
        assert result["exit_code"] == 0
        mock_container.exec_run.assert_called_once()


@pytest.mark.asyncio
async def test_odoo_install_multiple_modules() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.module_update.docker") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"3 modules installed", b"")
        mock_container.exec_run.return_value = mock_exec_result

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        result = await odoo_install_module("sale,purchase,stock")

        assert result["success"] is True
        assert result["modules"] == ["sale", "purchase", "stock"]
        assert len(result["modules"]) == 3


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_install_module_failure() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.module_update.docker") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 1
        mock_exec_result.output = (b"", b"Error: Module 'fake_module' not found")
        mock_container.exec_run.return_value = mock_exec_result

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        result = await odoo_install_module("fake_module")

        assert result["success"] is False
        assert "Error: Module 'fake_module' not found" in result["stderr"]
        assert result["exit_code"] == 1


@pytest.mark.asyncio
async def test_odoo_install_module_container_not_found() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.module_update.docker") as mock_docker:
        mock_client = MagicMock()
        mock_client.containers.get.side_effect = NotFound("Container not found")
        mock_docker.from_env.return_value = mock_client

        result = await odoo_install_module("sale")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_odoo_install_module_sanitization() -> None:
    with patch("odoo_intelligence_mcp.tools.operations.module_update.docker") as mock_docker:
        mock_client = MagicMock()
        mock_container = MagicMock()

        mock_exec_result = MagicMock()
        mock_exec_result.exit_code = 0
        mock_exec_result.output = (b"Module installed", b"")
        mock_container.exec_run.return_value = mock_exec_result

        mock_client.containers.get.return_value = mock_container
        mock_docker.from_env.return_value = mock_client

        # Test that module names are properly sanitized
        result = await odoo_install_module("sale, purchase , stock ")

        assert result["modules"] == ["sale", "purchase", "stock"]
        # Check the exec command was called with sanitized names
        call_args = mock_container.exec_run.call_args[0][0]
        assert "sale,purchase,stock" in " ".join(call_args)
