# AGENTS.md

Development guidelines for agents (Codex or Claude Code) working on the Odoo Intelligence MCP server.

Target the live Odoo workspace, such as an `odoo-devkit` checkout with `platform/stack.toml`. The `odoo-ai`
repository is archived; do not use it as a target unless the user explicitly asks for archival investigation.
Discovery code still has `odoo-ai` leftovers; #15 tracks removing them.

## Project Snapshot

- **Stack**: Python 3.14+, MCP SDK 2.0+, asyncio

## Workflow Metadata

- Use [`.github/github.json`](.github/github.json)
  for setup, run, format, test, coverage, inspection, and cleanup routing.

## Code Standards

- Avoid docstrings/comments; code must be self-documenting (pyproject comments allowed)
- Use descriptive, unabbreviated identifiers; avoid short or ambiguous locals (especially 1–3 character abbreviations like
  `idx`, `cfg`, `tmp`, `obj`, `val`, `res`, `ctx`). Allow only explicit tokens (`id`, `db`, `api`, `orm`, `env`,
  `io`, `url`, `ui`, `ux`, `ip`, `http`, `json`, `xml`, `sql`) and math-only contexts.
- Functions as verbs; objects as nouns. Keep one responsibility per function.
- Type all function signatures and public data shapes. Prefer implicit local typing
  when the type is obvious; avoid redundant local annotations. Leverage
  `type_defs.odoo_types`.
- Line length 133 characters max
- Use f-strings for formatting/logging
- Do not run Python directly; use `uv run` for scripts/tests.
- Prefer early returns (ignore TRY300) and shallow nesting
- Maintain ≥75 % coverage before shipping

## Test Rules

- A test must fail when the product is broken and pass when someone makes an intended change.
- Do not assert literals defined elsewhere (versions, timeouts, command lines, glob lists, hashes); compare against the
  single source of truth or assert behavior instead. The package version lives only in `pyproject.toml`.
- Do not assert workflow or config text; enforce the rule where it executes.
- Verification and loading code must not depend on working-tree or host state, and must not branch on whether pytest is
  running. No-live-stack tests never reach the host Docker daemon or sleep for real (`tests/conftest.py` enforces this).

## Workflow Expectations

1. Exercise the relevant MCP tool against the Docker stack before restarting the server.
2. Reserve raw `docker exec` / SQL for emergencies (schema corruption, ORM boot failures).

### Standard Loop

1. Baseline the existing tool behavior.
2. Follow patterns in `src/odoo_intelligence_mcp/server.py` when modifying handlers.
3. Paginate responses likely to exceed ~25 K tokens (`core/utils.py`: `add_pagination_to_schema`, `PaginationParams`).
4. Always close cursors/contexts via `try/finally`.
5. Run `uv run mcp-test`—all no-live-stack tests must pass.
6. Format with `uv run mcp-format`.
7. Run JetBrains inspections on changed files with the `jetbrains-inspection` skill (scope order in `.github/github.json`).
8. Verify coverage (`uv run mcp-test-cov` ≥ 75 %; CI runs `uv run mcp-test-cov-ci`).

## MCP Tool Development

When adding a tool:

1. Implement `async def tool_name(env, ...) -> dict[str, Any]` in the matching `tools/<domain>/` package.
2. Add its `Tool` schema to `handle_list_tools` in `server.py` (wrap list results with `add_pagination_to_schema`).
3. Add a `_handle_<tool_name>` adapter in `server.py` and register it in `TOOL_HANDLERS`.
4. Smoke-test with an MCP client before restart.
5. Validate payload size with `core/utils.py` (`validate_response_size`) or the pagination helpers.

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

- `ODOO_PROJECT_NAME`: Docker compose prefix (required unless container overrides are set)
- `ODOO_DB_NAME`: active database (default `odoo`)
- `ODOO_ADDONS_PATH`: comma-separated paths (`/odoo/addons,/odoo/odoo/addons,/opt/project/addons,/opt/extra_addons,/opt/enterprise` by default)

The server loads environment variables or the nearest `.env`; process variables win unless `ODOO_ENV_PRIORITY=env_file`. Use
`ODOO_ENV_FILE` to point at a target project's env file when running elsewhere.
Optional overrides: `ODOO_CONTAINER_NAME`, `ODOO_SCRIPT_RUNNER_CONTAINER`,
`ODOO_WEB_CONTAINER`, `ODOO_PROJECT_DIR`, `ODOO_COMPOSE_FILES`,
`ODOO_STACK_NAME`, `ODOO_ENV_PRIORITY`. When `platform/stack.toml` exists, MCP
prefers `.platform/env/<context>.<instance>.env` and falls back to
`uv run platform info --context <ctx> --instance <instance> --json-output` (an `odoo-ai` command that
`odoo-devkit` does not provide). README.md has the full resolution order.

## Architecture Overview

- Host process: `odoo_intelligence_mcp.server` (async MCP server)
- Key modules
  - `core/env.py`: Docker exec orchestration
  - `utils/`: pagination, responses, Docker helpers
  - `tools/`: MCP tool implementations (grouped by domain)
  - `services/`: higher-level orchestration (analyzers, inspectors)
- Each request spins up a fresh `docker exec` for isolation—handle timeouts carefully.

## Docker Integration

- Default containers: `{prefix}-web-1`, `{prefix}-script-runner-1`, `{prefix}-database-1`
- Commands run through `docker exec ...`
- When autostart is allowed (`should_allow_autostart` in `core/env.py`), missing containers trigger
  `docker compose up -d <service>` with a 10-minute timeout (see `utils/docker_utils.py`).

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

Run with `uv run python smoke.py`. Ensure outputs are JSON-serializable; paginate anything large. Inline `# noqa` suppressions require justification.

## Pre-Commit Checklist

- [ ] `uv run mcp-format`
- [ ] JetBrains inspections on changed files via `jetbrains-inspection` (no new actionable findings)
- [ ] `uv run mcp-test`
- [ ] `uv run mcp-test-cov` ≥ 75 %

Tip: keep tool responses short and structured; default to conservative paging to help downstream agent consumers.
