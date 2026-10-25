# AGENTS.md

Development guidelines for agents (Codex or Claude Code) working on the Odoo Intelligence MCP server.

## What Odoo Intelligence MCP does

Odoo Intelligence MCP gives coding agents tools to query and analyze Odoo models, fields, code, and development environments.
It connects to a target Docker-backed Odoo workspace; live qualification and legacy discovery cleanup remain held, as documented.
Evidence: [README.md](README.md) and the safety-selection guidance below.

## Direction and Execution

Read the Director's overall [DIRECTION.md](https://github.com/cbusillo/direction/blob/HEAD/DIRECTION.md) first.
This repository has no separate DIRECTION.md; overall direction applies. AGENTS.md is the only agent-instruction filename.

Use the maintained [executing loop](https://github.com/cbusillo/codex-skills/blob/HEAD/skills/references/executing-loop.md)
and [task scope and authorization](https://github.com/cbusillo/codex-skills/blob/HEAD/skills/references/execution-scope.md).
Load each step's owning skill before acting: `github-plan` for issue selection and claims, `github` for bot commits,
pushes and PRs, `python-uv-workflow` for Python commands, `jetbrains-inspection` for IDE checks, `babysit-pr` for CI/review
follow-through, and `work-closeout` for issue reconciliation and worktree retirement.
Execution-guidance changes, including AGENTS.md, use `model-review` and the maintained
[review reference](https://github.com/cbusillo/codex-skills/blob/HEAD/skills/references/model-review.md).

For issue-backed work, claim the issue before creating its linked task worktree; implement there instead of the primary checkout.
Hand authorised changes to Launchplane's merge train with `gh-pr.py ready` after green current-head CI and a weighed review.
Active policy owns enrollment and routing; metadata is only a hint.
Merging is separate from deploying or changing a target Odoo runtime; apply overall direction and the task's scope to each action.

Target the current Odoo workspace, such as an `odoo-devkit` checkout with `platform/stack.toml`. The `odoo-ai`
repository is archived; do not use it as a target unless the user explicitly asks for archival investigation.
Discovery code still has `odoo-ai` leftovers; [the deferred cleanup](https://github.com/cbusillo/odoo-intelligence-mcp/issues/15)
tracks removing them.

## Project Snapshot

- **Stack**: Python 3.14+, MCP SDK 2.0+, asyncio
- This host-side service targets the Python range in `pyproject.toml`, rather
  than the shared style reference's Odoo image target.

## Workflow Metadata

- Use [`.github/github.json`](.github/github.json)
  for setup, run, format, test, coverage, inspection, and cleanup routing.

## Code Standards

- Write Python and Odoo JavaScript in the shared
  [Python and Odoo style](https://github.com/cbusillo/codex-skills/blob/HEAD/skills/references/python-odoo-style.md).
- Use descriptive, unabbreviated identifiers; avoid short or ambiguous locals (especially 1–3 character abbreviations like
  `idx`, `cfg`, `tmp`, `obj`, `val`, `res`, `ctx`). Allow only explicit tokens (`id`, `db`, `api`, `orm`, `env`,
  `io`, `url`, `ui`, `ux`, `ip`, `http`, `json`, `xml`, `sql`) and math-only contexts.
- Use `type_defs.odoo_types` for the MCP server's public data shapes.
- Do not run Python directly; use `uv run` for scripts/tests.
- Maintain ≥75 % coverage before shipping

## Test Rules

- A test must fail when the product is broken and pass when someone makes an intended change.
- Do not assert literals defined elsewhere (versions, timeouts, command lines, glob lists, hashes); compare against the
  single source of truth or assert behavior instead. The package version lives only in `pyproject.toml`.
- Do not assert workflow or config text; enforce the rule where it executes.
- Verification and loading code must not depend on working-tree or host state, and must not branch on whether pytest is
  running. No-live-stack tests never reach the host Docker daemon or sleep for real (`tests/conftest.py` enforces this).

## Safety Test Selection

Select complete modules through the changed code and its callers. Security
validation uses `tests/unit/utils/test_security_utils.py`, permission checks use
`tests/unit/tools/security/test_permission_checker.py`, and execution boundaries
use `tests/integration/test_security_boundaries.py` plus the affected
`tests/unit/tools/operations/test_odoo_restart.py`, `test_odoo_update_module.py`,
`tests/unit/tools/code/test_execute_code.py`, `test_read_odoo_file.py`,
`tests/unit/tools/common/test_fs_utils.py`, and
`tests/unit/utils/test_execution_utils.py` modules. Environment/autostart changes
also use the affected `tests/unit/core/test_env_resolution.py`,
`test_env_registry.py`, `test_docker_registry.py`, and
`tests/unit/utils/test_docker_utils.py` modules plus
`tests/integration/test_docker_failure_modes.py`. Keep the no-live marker filter;
record missing evidence when affected safety coverage requires a held live lane.
Live qualification and target-discovery cleanup remain held under #13 and #15.

## Workflow Expectations

1. Exercise the relevant MCP tool against the Docker stack before restarting the server.
2. Reserve raw `docker exec` / SQL for emergencies (schema corruption, ORM boot failures).

### Standard Loop

1. Baseline the existing tool behavior.
2. Follow patterns in `src/odoo_intelligence_mcp/server.py` when modifying handlers.
3. Paginate responses likely to exceed ~25 K tokens (`core/utils.py`: `add_pagination_to_schema`, `PaginationParams`).
4. Always close cursors/contexts via `try/finally`.
5. Run `qualityGate.test.local`, replacing `{test_paths}` with affected test files or directories. The no-live markers stay selected.
6. Format with `uv run mcp-format`.
7. Run JetBrains inspections on changed files with the `jetbrains-inspection` skill (scope order in `.github/github.json`).
8. CI runs `qualityGate.test.ci`, the complete no-live-stack suite with the coverage gate. Check current-head CI before ready; do not rerun the full suite locally.

Follow the [inspection skill](https://github.com/cbusillo/codex-skills/blob/HEAD/skills/jetbrains-inspection/SKILL.md)
for recovery: actionable findings, stale results, `capture_incomplete`, timeouts, and wrong-worktree routing are not clean.
Record the verdict, reason, and next action. For Markdown-only changes affecting no code paths, the skill permits an explicit
not-run reason.

## MCP Tool Development

When adding a tool:

1. Implement `async def tool_name(env, ...) -> dict[str, Any]` in the matching `tools/<domain>/` package.
2. Add its `Tool` schema to `handle_list_tools` in `server.py` (wrap list results with `add_pagination_to_schema`).
3. Add a `_handle_<tool_name>` adapter in `server.py` and register it in `TOOL_HANDLERS`.
4. Smoke-test with an MCP client before restart.
5. Validate payload size with `core/utils.py` (`validate_response_size`) or the pagination helpers.

### Canonical Pattern

```python
import logging
from typing import Any

from odoo_intelligence_mcp.core.env import HostOdooEnvironment

_logger = logging.getLogger(__name__)


async def get_model_fields(env: HostOdooEnvironment, model: str) -> dict[str, Any]:
    try:
        data = await env.execute_code(f"result = env['{model}'].fields_get()")
        return {"success": True, "model": model, "fields": data}
    except Exception as exc:
        _logger.exception("Failed to retrieve fields for model %s", model)
        return {"success": False, "error": str(exc), "error_type": type(exc).__name__}
```

## Configuration Cheatsheet

- `ODOO_PROJECT_NAME`: Docker compose prefix (required unless container overrides are set)
- `ODOO_DB_NAME`: active database (default `odoo`)
- `ODOO_ADDONS_PATH`: comma-separated paths
  (`/odoo/addons,/odoo/odoo/addons,/opt/project/addons,/opt/extra_addons,/opt/enterprise` by default)

The server resolves an env file in the order documented in [README.md](README.md#environment);
process variables win unless `ODOO_ENV_PRIORITY=env_file`. Use
`ODOO_ENV_FILE` to point at a target project's env file when running elsewhere.
Optional overrides: `ODOO_CONTAINER_NAME`, `ODOO_SCRIPT_RUNNER_CONTAINER`,
`ODOO_WEB_CONTAINER`, `ODOO_PROJECT_DIR`, `ODOO_COMPOSE_FILES`,
`ODOO_STACK_NAME`, `ODOO_ENV_PRIORITY`. When `platform/stack.toml` exists, MCP
prefers `.platform/env/<context>.<instance>.env` and falls back to
`uv run platform info --context <ctx> --instance <instance> --json-output` (an `odoo-ai` command that
`odoo-devkit` does not provide). README.md has the full resolution order.

## Architecture Overview

- Host process: `odoo_intelligence_mcp.server` (async MCP server)
- `core/env.py`: environment discovery and Docker exec orchestration
- `core/utils.py`: tool argument parsing, pagination, and response-size validation
- `utils/`: Docker, execution, model, error, security, response, and static-analysis helpers
- `tools/`: MCP tool implementations (grouped by domain)
- `services/`: higher-level orchestration (analyzers, inspectors)
- Registry queries execute Odoo code in containers; static queries build filesystem indexes in containers using `docker exec`.
  Handle execution timeouts carefully.

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

Run with `uv run python smoke.py`. Ensure outputs are JSON-serializable; paginate anything large.

## Pre-Commit Checklist

- [ ] `uv run mcp-format`
- [ ] JetBrains inspections on changed files via `jetbrains-inspection` (no new actionable findings)
- [ ] Focused `qualityGate.test.local` tests and the complete affected safety modules
- [ ] Green current-head `qualityGate.test.ci` with required coverage before ready

Tip: keep tool responses short and structured; default to conservative paging to help downstream agent consumers.
