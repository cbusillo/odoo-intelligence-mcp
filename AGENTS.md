# AGENTS.md

Development guidelines for running the Odoo Intelligence MCP server inside the Codex CLI environment.

## Project Snapshot

- **Stack**: Python 3.12+, MCP SDK 1.9+, asyncio
- **Primary agent shell**: Codex CLI (tools: `Read`, `Edit`, `MultiEdit`, `Write`, inspections, etc.)

## Quick Command Reference

- **Setup**: `uv sync` (installs dependencies in local venv)
- **Run**: `uv run odoo_intelligence_mcp` (host process that connects to Docker)
- **Format**: `uv run mcp-format`
- **Inspections**: `inspection_trigger(scope="whole_project")` then `inspection_get_problems()`
- **Tests**: `uv run mcp-test`
- **Coverage**: `uv run mcp-test-cov` (minimum 75 %)

## Code Standards

- Avoid docstrings/comments; code must be self-documenting (pyproject comments allowed)
- Use descriptive, unabbreviated identifiers
- Type everything (`list[str]` style); leverage `type_defs.odoo_types`
- Line length 133 characters max
- Use f-strings for formatting/logging
- Prefer early returns (ignore TRY300) and shallow nesting
- Maintain ≥75 % coverage before shipping

## Codex Workflow Expectations

1. Exercise the relevant MCP tool against the Docker stack before restarting the server.
2. Prefer Codex built-ins (`Read`, `Edit`, `MultiEdit`, `Write`) for file/dependency work.
3. Reserve raw `docker exec` / SQL for emergencies (schema corruption, ORM boot failures).

> ❗ Inside Codex, avoid `bash` for `find`, `grep`, `cat`, or `ls`; `rg`, `fd`, and the explorer are faster and safer.

### Standard Loop

1. Baseline the existing tool behavior.
2. Follow patterns in `src/odoo_intelligence_mcp/server.py` when modifying handlers.
3. Paginate responses likely to exceed ~25 K tokens (`pagination_utils.py`).
4. Always close cursors/contexts via `try/finally`.
5. Run `uv run mcp-test`—all tests must pass.
6. Format with `uv run mcp-format`.
7. Trigger inspections (`inspection_trigger(scope="whole_project")`; review via `inspection_get_problems`).
8. Verify coverage (`uv run mcp-test-cov` ≥ 75 %).

## MCP Tool Development

When adding a tool:

1. Register it in the `tools` list (`server.py`).
2. Add a branch in `handle_call_tool`.
3. Implement `async def tool_name(...) -> dict[str, Any]` above `run_server()`.
4. Smoke-test with the Codex MCP client before restart.
5. Validate payload size with `response_utils` or pagination helpers.

**Canonical pattern**

```python
from odoo_intelligence_mcp.core.env import HostOdooEnvironment

async def get_model_fields(env: HostOdooEnvironment, model: str) -> dict[str, Any]:
    try:
        data = await env.execute_code(f"result = env['{model}'].fields_get()")
        return {"success": True, "model": model, "fields": data}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc), "error_type": type(exc).__name__}
```

## Configuration Cheatsheet

- `ODOO_PROJECT_NAME`: Docker compose prefix (default `odoo`)
- `ODOO_DB_NAME`: active database (default `odoo`)
- `ODOO_ADDONS_PATH`: comma-separated paths (`/opt/project/addons,/odoo/addons,/volumes/enterprise` by default)

The server loads environment variables or the nearest `.env`. Codex usually starts from `odoo-intelligence-mcp`, falling back to `../odoo-ai/.env` in tests.

## Architecture Overview

- Host process: `odoo_intelligence_mcp.server` (async MCP server)
- Key modules
  - `core/env.py`: Docker exec orchestration
  - `utils/`: pagination, responses, Docker helpers
  - `tools/`: MCP tool implementations (grouped by domain)
  - `services/`: higher-level orchestration (analyzers, inspectors)
- Each request spins up a fresh `docker exec` for isolation—handle timeouts carefully.

## Docker Integration

- Default containers: `{prefix}-web-1`, `{prefix}-shell-1`, `{prefix}-script-runner-1`, `{prefix}-database-1`
- Commands run through `docker exec ...`
- Missing containers trigger `docker compose up -d <service>` with a 10-minute timeout (see `utils/docker_utils.py`).

## Quick Tool Testing

```python
import asyncio
from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.model.model_info import get_model_info


async def smoke() -> None:
    env = await HostOdooEnvironmentManager().get_environment()
    print(await get_model_info(env, "res.partner"))


asyncio.run(smoke())
```

Run with `uv run python smoke.py` inside Codex. Ensure outputs are JSON-serializable; paginate anything large. Inline `# noqa` suppressions require justification.

## Pre-Commit Checklist

- [ ] `uv run mcp-format`
- [ ] `inspection_trigger(scope="whole_project")` / `inspection_get_problems()` (no new actionable findings)
- [ ] `uv run mcp-test`
- [ ] `uv run mcp-test-cov` ≥ 75 %

Codex tip: keep responses short and structured; default to conservative paging to help downstream agent consumers.
