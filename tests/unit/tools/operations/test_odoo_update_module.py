from unittest.mock import Mock, patch

import pytest

from odoo_intelligence_mcp.tools.operations.module_update import odoo_update_module


# noinspection DuplicatedCode
@pytest.mark.asyncio
async def test_odoo_update_module_success() -> None:
    with patch("subprocess.run") as mock_run:
        # First call: docker inspect succeeds (container is running)
        # Second call: docker exec with odoo-bin command succeeds
        mock_run.side_effect = [
            Mock(returncode=0, stdout="running", stderr=""),  # docker inspect
            Mock(returncode=0, stdout="Module 'sale' updated successfully", stderr=""),  # docker exec
        ]

        result = await odoo_update_module("sale")

        assert result["success"] is True
        assert result["modules"] == "sale"
        assert result["operation"] == "updated"
        assert "Module 'sale' updated successfully" in result["stdout"]
        assert result["exit_code"] == 0

        # Check that subprocess.run was called twice
        assert mock_run.call_count == 2

        # Check the docker inspect call
        inspect_call = mock_run.call_args_list[0][0][0]
        assert inspect_call[0] == "docker"
        assert inspect_call[1] == "inspect"
        assert "--format" in " ".join(inspect_call)

        # Check the docker exec call
        exec_call = mock_run.call_args_list[1][0][0]
        assert exec_call[0] == "docker"
        assert exec_call[1] == "exec"
        assert "-u sale" in " ".join(exec_call)


@pytest.mark.asyncio
async def test_odoo_update_multiple_modules() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout="running", stderr=""),  # docker inspect
            Mock(returncode=0, stdout="3 modules updated", stderr=""),  # docker exec
        ]

        result = await odoo_update_module("sale,purchase,stock")

        assert result["success"] is True
        assert result["modules"] == "sale,purchase,stock"
        assert "3 modules updated" in result["stdout"]


@pytest.mark.asyncio
async def test_odoo_update_module_with_force_install() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout="running", stderr=""),  # docker inspect
            Mock(returncode=0, stdout="Module installed", stderr=""),  # docker exec
        ]

        result = await odoo_update_module("new_module", force_install=True)

        assert result["success"] is True
        assert result["operation"] == "installed"

        # Check that -i flag was used instead of -u
        exec_call = mock_run.call_args_list[1][0][0]
        exec_command = " ".join(exec_call)
        assert "-i new_module" in exec_command
        assert "-u new_module" not in exec_command


@pytest.mark.asyncio
async def test_odoo_update_module_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout="running", stderr=""),  # docker inspect
            Mock(returncode=1, stdout="", stderr="ERROR: Module 'invalid_module' not found"),  # docker exec fails
        ]

        result = await odoo_update_module("invalid_module")

        assert result["success"] is False
        assert "ERROR: Module 'invalid_module' not found" in result["stderr"]
        assert result["exit_code"] == 1


@pytest.mark.asyncio
async def test_odoo_update_module_container_not_found() -> None:
    with patch("subprocess.run") as mock_run:
        # Container not found
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: No such container: odoo-script-runner-1")

        result = await odoo_update_module("sale")

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "docker compose up -d" in result["hint"]


@pytest.mark.asyncio
async def test_odoo_update_module_sanitization() -> None:
    result = await odoo_update_module("sale; rm -rf /")

    assert result["success"] is False
    assert "Invalid module name" in result["error"]
    assert "Only alphanumeric, underscore, dash, and dot are allowed" in result["error"]


@pytest.mark.asyncio
async def test_odoo_update_module_container_not_running() -> None:
    with patch("subprocess.run") as mock_run:
        # Container exists but is stopped
        mock_run.return_value = Mock(returncode=0, stdout="exited", stderr="")

        result = await odoo_update_module("sale")

        assert result["success"] is False
        assert "not running" in result["error"]
        assert "odoo_restart" in result["hint"]


@pytest.mark.asyncio
async def test_odoo_update_module_timeout() -> None:
    with patch("subprocess.run") as mock_run:
        import subprocess

        mock_run.side_effect = [
            Mock(returncode=0, stdout="running", stderr=""),  # docker inspect
            subprocess.TimeoutExpired("docker exec", 300),  # docker exec times out
        ]

        result = await odoo_update_module("large_module")

        assert result["success"] is False
        assert "timed out" in result["error"]
