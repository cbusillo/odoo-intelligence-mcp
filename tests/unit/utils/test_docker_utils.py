import json
from unittest.mock import Mock, patch

from odoo_intelligence_mcp.utils.docker_utils import DockerClientManager


def test_docker_client_manager_init_success() -> None:
    """Test successful DockerClientManager initialization."""
    manager = DockerClientManager()
    # Since we removed docker SDK, initialization should always succeed
    assert manager is not None


def test_get_container_success() -> None:
    """Test successful container retrieval."""
    with patch("subprocess.run") as mock_run:
        # Mock successful docker inspect
        container_info = {"State": {"Status": "running", "Running": True}}
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(container_info), stderr="")

        manager = DockerClientManager()
        result = manager.get_container("test-container")

        assert result["success"] is True
        assert result["container"] == "test-container"
        assert result["state"]["Status"] == "running"

        # Verify docker inspect was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "docker"
        assert call_args[1] == "inspect"
        assert call_args[2] == "test-container"


def test_get_container_not_found() -> None:
    """Test container not found scenario."""
    with patch("subprocess.run") as mock_run:
        # Mock container not found
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: No such container: test-container")

        manager = DockerClientManager()
        result = manager.get_container("test-container")

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["error_type"] == "NotFound"
        assert result["container"] == "test-container"


def test_get_container_with_auto_start() -> None:
    """Test container auto-start when not found."""
    with patch("subprocess.run") as mock_run:
        # First call: container not found
        # Second call: docker start succeeds
        # Third call: docker inspect succeeds
        container_info = {"State": {"Status": "running", "Running": True}}
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="No such container"),  # inspect fails
            Mock(returncode=0, stdout="test-container", stderr=""),  # start succeeds
            Mock(returncode=0, stdout=json.dumps(container_info), stderr=""),  # inspect succeeds
        ]

        manager = DockerClientManager()
        result = manager.get_container("test-container", auto_start=True)

        assert result["success"] is True
        assert result["container"] == "test-container"
        assert mock_run.call_count == 3


def test_restart_container_success() -> None:
    """Test successful container restart."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="test-container", stderr="")

        manager = DockerClientManager()
        result = manager.restart_container("test-container")

        assert result["success"] is True
        assert result["operation"] == "restart"
        assert result["container"] == "test-container"

        # Verify docker restart was called
        call_args = mock_run.call_args[0][0]
        assert call_args == ["docker", "restart", "test-container"]


def test_restart_container_failure() -> None:
    """Test failed container restart."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="restart conflict")

        manager = DockerClientManager()
        result = manager.restart_container("test-container")

        assert result["success"] is False
        assert "Failed to restart" in result["error"]
        assert result["error_type"] == "RestartError"


def test_restart_container_autostart_success() -> None:
    with patch("subprocess.run") as mock_run:
        container_state = {"State": {"Status": "running"}}
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr="Error: No such container"),
            Mock(returncode=1, stdout="", stderr="Error: No such container"),
            Mock(returncode=0, stdout="started", stderr=""),
            Mock(returncode=0, stdout="restarted", stderr=""),
            Mock(returncode=0, stdout=json.dumps(container_state), stderr=""),
        ]

        manager = DockerClientManager()
        result = manager.restart_container("odoo-web-1")

        assert result["success"] is True
        assert result["operation"] == "restart"


def test_get_container_logs_success() -> None:
    """Test successful log retrieval."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="Application started successfully", stderr="Warning: deprecated config")

        manager = DockerClientManager()
        result = manager.get_container_logs("test-container", tail=50)

        assert result["success"] is True
        assert result["operation"] == "logs"
        assert result["data"]["stdout"] == "Application started successfully"
        assert result["data"]["stderr"] == "Warning: deprecated config"

        # Verify docker logs was called with correct parameters
        call_args = mock_run.call_args[0][0]
        assert call_args == ["docker", "logs", "test-container", "--tail", "50"]


def test_exec_run_success() -> None:
    """Test successful command execution in container."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="Command output", stderr="")

        manager = DockerClientManager()
        result = manager.exec_run("test-container", "ls -la")

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert result["stdout"] == "Command output"
        assert result["stderr"] == ""

        # Verify docker exec was called
        call_args = mock_run.call_args[0][0]
        assert call_args == ["docker", "exec", "test-container", "sh", "-c", "ls -la"]


def test_exec_run_with_list_command() -> None:
    """Test command execution with list of arguments."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="Output", stderr="")

        manager = DockerClientManager()
        result = manager.exec_run("test-container", ["python", "script.py"])

        assert result["success"] is True

        # Verify docker exec was called with list command
        call_args = mock_run.call_args[0][0]
        assert call_args == ["docker", "exec", "test-container", "python", "script.py"]


def test_exec_run_failure() -> None:
    """Test failed command execution."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Command not found")

        manager = DockerClientManager()
        result = manager.exec_run("test-container", "invalid-command")

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "Command not found" in result["output"]


def test_handle_container_operation_success() -> None:
    """Test successful container operation handling."""
    with patch("subprocess.run") as mock_run:
        # Mock successful container inspection
        container_info = {"State": {"Status": "running", "Running": True}}
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(container_info), stderr="")

        manager = DockerClientManager()

        def mock_operation(container_name: str) -> str:
            return f"Operation completed on {container_name}"

        result = manager.handle_container_operation("test-container", "test_operation", mock_operation)

        assert result["success"] is True
        assert result["operation"] == "test_operation"
        assert result["data"] == "Operation completed on test-container"


def test_handle_container_operation_container_not_found() -> None:
    """Test container operation when container doesn't exist."""
    with patch("subprocess.run") as mock_run:
        # Mock container not found
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="No such container")

        manager = DockerClientManager()

        def mock_operation(container_name: str) -> str:
            return f"Operation on {container_name}"

        result = manager.handle_container_operation("missing-container", "test_operation", mock_operation)

        assert result["success"] is False
        assert "not found" in result["error"].lower()
