from pathlib import Path

from odoo_intelligence_mcp.core import env as env_module


def test_find_project_repo_root_should_find_sibling_odoo_ai(tmp_path: Path) -> None:
    workspace_root = tmp_path / "Developer"
    mcp_repo = workspace_root / "odoo-intelligence-mcp"
    start_dir = mcp_repo / "src"
    start_dir.mkdir(parents=True)

    target_repo = workspace_root / "odoo-ai"
    (target_repo / "platform").mkdir(parents=True)
    (target_repo / "platform" / "stack.toml").write_text("schema_version = 1\n", encoding="utf-8")

    assert env_module._find_project_repo_root(start_dir) == target_repo


def test_resolve_stack_env_file_should_prefer_platform_runtime_env(monkeypatch, tmp_path: Path) -> None:
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
    monkeypatch.delenv("ODOO_ENV_FILE", raising=False)

    resolved_env_file = env_module._resolve_stack_env_file()

    assert resolved_env_file == runtime_env_file
