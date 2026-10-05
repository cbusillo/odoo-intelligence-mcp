from typing import TYPE_CHECKING

import pytest

from odoo_intelligence_mcp.core import env as env_module

if TYPE_CHECKING:
    from pathlib import Path


def test_find_project_repo_root_should_find_sibling_odoo_ai(tmp_path: Path) -> None:
    workspace_root = tmp_path / "Developer"
    mcp_repo = workspace_root / "odoo-intelligence-mcp"
    start_dir = mcp_repo / "src"
    start_dir.mkdir(parents=True)

    target_repo = workspace_root / "odoo-ai"
    (target_repo / "platform").mkdir(parents=True)
    (target_repo / "platform" / "stack.toml").write_text("schema_version = 1\n", encoding="utf-8")

    assert env_module._find_project_repo_root(start_dir) == target_repo


def test_resolve_stack_env_file_should_prefer_platform_runtime_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "Developer"
    mcp_repo = workspace_root / "odoo-intelligence-mcp"
    mcp_repo.mkdir(parents=True)

    target_repo = workspace_root / "odoo-ai"
    (target_repo / "platform").mkdir(parents=True)
    (target_repo / "platform" / "stack.toml").write_text("schema_version = 1\n", encoding="utf-8")

    runtime_env_file = target_repo / ".platform" / "env" / "opw.local.env"
    runtime_env_file.parent.mkdir(parents=True)
    runtime_env_file.write_text("ODOO_PROJECT_NAME=odoo-opw-local\n", encoding="utf-8")

    monkeypatch.chdir(mcp_repo)
    monkeypatch.setenv("ODOO_STACK_NAME", "opw-local")
    monkeypatch.delenv("ODOO_PROJECT_NAME", raising=False)
    monkeypatch.delenv("ODOO_PROJECT_DIR", raising=False)
    monkeypatch.delenv("ODOO_ENV_FILE", raising=False)

    resolved_env_file = env_module._resolve_stack_env_file()

    assert resolved_env_file == runtime_env_file


@pytest.mark.parametrize("priority", [None, "process", "env_file"])
def test_load_env_config_respects_selected_priority(priority: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file_settings = {
        "ODOO_PROJECT_NAME": "file-project",
        "ODOO_DB_NAME": "file-db",
        "ODOO_ADDONS_PATH": "/file/addons",
        "ODOO_DB_HOST": "file-host",
        "ODOO_DB_PORT": "7001",
    }
    process_settings = {
        "ODOO_PROJECT_NAME": "process-project",
        "ODOO_DB_NAME": "process-db",
        "ODOO_ADDONS_PATH": "/process/addons",
        "ODOO_DB_HOST": "process-host",
        "ODOO_DB_PORT": "7002",
    }
    environment_file = tmp_path / "priority.env"
    environment_file.write_text("\n".join(f"{name}={value}" for name, value in file_settings.items()), encoding="utf-8")
    monkeypatch.setenv("ODOO_ENV_FILE", str(environment_file))
    for name, value in process_settings.items():
        monkeypatch.setenv(name, value)
    if priority is None:
        monkeypatch.delenv("ODOO_ENV_PRIORITY", raising=False)
    else:
        monkeypatch.setenv("ODOO_ENV_PRIORITY", priority)

    configuration = env_module.load_env_config()
    expected_settings = file_settings if priority == "env_file" else process_settings
    actual_settings = {
        "ODOO_PROJECT_NAME": configuration.container_prefix,
        "ODOO_DB_NAME": configuration.database,
        "ODOO_ADDONS_PATH": configuration.addons_path,
        "ODOO_DB_HOST": configuration.db_host,
        "ODOO_DB_PORT": configuration.db_port,
    }
    assert actual_settings == expected_settings
    assert configuration.__dict__["_env_file"] == environment_file


def test_load_env_config_reports_missing_container_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from odoo_intelligence_mcp.utils.error_utils import EnvironmentResolutionError

    environment_file = tmp_path / "empty.env"
    environment_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("ODOO_ENV_FILE", str(environment_file))
    monkeypatch.delenv("ODOO_PROJECT_NAME")

    with pytest.raises(EnvironmentResolutionError):
        env_module.load_env_config()


def test_load_env_config_accepts_directory_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_name = "fixture-project"
    database_name = "fixture-database"
    environment_file = tmp_path / ".env"
    environment_file.write_text(f"ODOO_PROJECT_NAME={project_name}\nODOO_DB_NAME={database_name}\n", encoding="utf-8")
    monkeypatch.setenv("ODOO_ENV_FILE", str(tmp_path))
    monkeypatch.delenv("ODOO_PROJECT_NAME")

    configuration = env_module.load_env_config()

    assert configuration.container_prefix == project_name
    assert configuration.database == database_name
    assert configuration.__dict__["_env_file"] == environment_file


@pytest.mark.parametrize("has_target", [True, False])
def test_load_env_config_without_file_requires_explicit_target(
    has_target: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from odoo_intelligence_mcp.utils.error_utils import EnvironmentResolutionError

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ODOO_ENV_FILE")
    monkeypatch.setattr(env_module, "_resolve_stack_env_file", lambda: None)
    monkeypatch.setattr(env_module, "_resolve_local_env_file", lambda: None)
    project_name = "fixture-project"
    if has_target:
        monkeypatch.setenv("ODOO_PROJECT_NAME", project_name)
        configuration = env_module.load_env_config()
        assert configuration.container_prefix == project_name
    else:
        monkeypatch.delenv("ODOO_PROJECT_NAME")
        with pytest.raises(EnvironmentResolutionError):
            env_module.load_env_config()


@pytest.mark.parametrize("has_working_directory_file", [True, False])
def test_local_env_resolution_uses_fixture_roots(
    has_working_directory_file: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = tmp_path / "project"
    source_directory = project_root / "src"
    source_directory.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text('[project]\nname = "fixture"\n', encoding="utf-8")
    project_environment = project_root / ".env"
    project_environment.write_text("ODOO_PROJECT_NAME=fixture-project\n", encoding="utf-8")
    working_directory = tmp_path / "working"
    working_directory.mkdir()
    working_environment = working_directory / ".env"
    if has_working_directory_file:
        working_environment.write_text("ODOO_PROJECT_NAME=fixture-working\n", encoding="utf-8")
    monkeypatch.chdir(working_directory)
    monkeypatch.setattr(env_module, "__file__", str(source_directory / "env.py"))

    resolved_file = env_module._resolve_local_env_file()

    assert resolved_file == (working_environment if has_working_directory_file else project_environment)
