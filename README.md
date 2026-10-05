# Odoo Intelligence MCP Server

Comprehensive Model Context Protocol (MCP) server providing deep code analysis and development tools for Odoo projects.

Repository work follows the Director's overall [DIRECTION.md](https://github.com/cbusillo/direction/blob/HEAD/DIRECTION.md).
There is no repository-specific DIRECTION.md. [AGENTS.md](AGENTS.md) is the sole agent-instruction filename and describes
execution and landing; [workflow metadata](.github/github.json) owns command routing.

## Features

- 15 tools exposing 30+ capabilities
- Model/field/analysis queries with pagination and filtering
- Docker-connected Odoo environment (exec into containers)
- Structured errors with optional enhanced diagnostics
- Large-response protection with pagination and truncation

## Installation

- Prereqs: Python 3.14+ and `uv`
- From the project directory: `uv sync --locked --group dev`

## Configuration

### Claude Code Integration

Add the MCP server to Claude Code:

```bash
# Use --project to ensure uv resolves this repo's environment
claude mcp add-json odoo-intelligence '{"command": "uv", "args": ["run", "--project", "/path/to/odoo-intelligence-mcp", "odoo-intelligence-mcp"]}'
```

Restart Claude after configuration changes.

### Environment

`.env` resolution order:
1) `ODOO_ENV_FILE` (explicit)
2) Platform env resolution from a workspace that has `platform/stack.toml`, such as an `odoo-devkit` checkout. MCP looks
   for it in `ODOO_PROJECT_DIR` (or the current directory) and its parents. It runs only when `ODOO_STACK_NAME`
   (`<context>-<instance>`; aliases `ODOO_STACK`, `ODOO_ENV_NAME`) or an `ODOO_PROJECT_NAME` of the form `odoo-<context>-<instance>` is set.
   - MCP uses `.platform/env/<context>.<instance>.env` when it exists.
   - Otherwise it tries `uv run platform info --context <ctx> --instance <instance> --json-output` in that workspace.
     This and a sibling `odoo-ai` lookup are leftovers from the archived `odoo-ai` workspace; `odoo-devkit` has no
     `platform info` command. Removal is tracked in #15.
3) Current working directory of the MCP server process
4) This MCP server directory (fallback)

Override discovery by setting `ODOO_ENV_FILE` to the target project's env file path or `ODOO_PROJECT_DIR` for platform resolution. Process env vars override file values by default; set `ODOO_ENV_PRIORITY=env_file` to let the env file win.

Optional container overrides:
- `ODOO_CONTAINER_NAME` (primary exec container)
- `ODOO_SCRIPT_RUNNER_CONTAINER`
- `ODOO_WEB_CONTAINER`

If the script-runner container is missing, MCP will try `{prefix}-web-1`, `{prefix}-odoo-1`, and `{prefix}-app-1`.

Compose files can be supplied via `ODOO_COMPOSE_FILES` or inherited from `DEPLOY_COMPOSE_FILES`/`COMPOSE_FILE` in the target env.

Defaults (override via environment or `.env`):
- Database: `odoo` (`ODOO_DB_NAME`)
- Addons Path: `/odoo/addons,/odoo/odoo/addons,/opt/project/addons,/opt/extra_addons,/opt/enterprise` (`ODOO_ADDONS_PATH`)
- Container Prefix: required (`ODOO_PROJECT_NAME`) unless container overrides are set

Derived containers from prefix:
- Script Runner: `{prefix}-script-runner-1`
- Web: `{prefix}-web-1`

### Modes and Fallbacks

Many operations accept `mode`:
- `auto` (default)
- `fs` (static scan over `ODOO_ADDONS_PATH`)
- `registry` (runtime via Odoo registry)

Enable enhanced error payloads: `ODOO_MCP_ENHANCED_ERRORS=true`.

### Using with Different Projects

Start the MCP server from your Odoo project directory so `.env` is discovered, or set `ODOO_ENV_FILE` explicitly.
Alternatively, set env vars:

```bash
export ODOO_PROJECT_NAME="odoo-dev"
export ODOO_DB_NAME="mydb"
export ODOO_ADDONS_PATH="/custom/addons,/odoo/addons"
```

## Operations (Tools)

- `search_code(pattern, file_type=py, roots?[])` → hits[] (default file_type is `py`; set `xml`/`js` for other sources)
- `find_files(pattern, file_type?)` → files[]
- `read_odoo_file(file_path, start_line?, end_line?, pattern?, context_lines=5)` → content
- `find_method(method_name, mode=auto|fs|registry)` → locations[]
- `search_decorators(decorator: depends|constrains|onchange|model_create_multi, mode=auto|fs|registry)` → methods[]
- `model_query(operation: info|search|relationships|inheritance|view_usage, model_name?, pattern?, page?, page_size?, mode=auto)`
- `field_query(operation: usages|dependencies|analyze_values|resolve_dynamic|search_properties|search_type, model_name?, field_name?, field_type?, property?, sample_size=1000, page?, page_size?, mode=auto)`
- `analysis_query(analysis_type: performance|patterns|workflow|inheritance, model_name?, pattern_type?, page?, page_size?, mode=auto)`
- `addon_dependencies(addon_name)` → deps[]
- `module_structure(module_name)` → files[], manifest, meta
- `execute_code(code)` → success with result/output or structured error; assign to `result` to return a value
- `permission_checker(user, model, operation, record_id?)` → allowed: true|false, rationale (user accepts id or login/email)
- `odoo_update_module(modules, force_install=false)` → result
- `odoo_status(verbose=false)` → containers[], services[]
- `odoo_restart(services?)` → result

Parameters
- `mode` (where supported): `auto` (default), `fs`, `registry`
- Pagination: `page`, `page_size` (max 1000) or `offset`, `limit`
- Filters: `filter` (client‑side contains), `roots`

Notes
- `field_query` usages, dependencies, and analyze_values need `model_name` and `field_name`; resolve_dynamic needs `model_name`
- `field_query` search_type expects `field_type` (e.g., `char`, `many2one`, `selection`)
- `analysis_query` patterns supports `pattern_type`: `computed_fields`, `related_fields`, `api_decorators`, `custom_methods`, `state_machines`, `all`

Examples
- Search Python for a pattern:
  `search_code { "pattern": "def _compute", "file_type": "py", "roots": ["/opt/project/addons"] }`
- Model info:
  `model_query { "operation": "info", "model_name": "sale.order" }`
- Field dependencies:
  `field_query { "operation": "dependencies", "model_name": "sale.order", "field_name": "amount_total" }`
- Field type search:
  `field_query { "operation": "search_type", "field_type": "many2one" }`
- Pattern analysis:
  `analysis_query { "analysis_type": "patterns", "pattern_type": "computed_fields" }`

## Responses & Schema

Conventions
- Paginated results: `{ "items": [...], "pagination": { page, page_size, total_count, total_pages, has_next_page, has_previous_page, filter_applied } }`
- Single‑object results: plain objects with relevant fields and optional `success`/`error` keys

## Pagination

All list-style operations support pagination and filtering.

Parameters:
- Page-based (recommended): `page`, `page_size` (max 1000)
- Offset-based: `limit`, `offset`
- Filter: `filter` (applies client-side text filtering)

Response shape (typical):

```json
{
  "items": [],
  "pagination": {
    "page": 2,
    "page_size": 50,
    "total_count": 245,
    "total_pages": 5,
    "has_next_page": true,
    "has_previous_page": true,
    "filter_applied": "sale"
  }
}
```

Large responses are validated and may include warnings or truncation to respect ~25K token limits.

## Development

Read [AGENTS.md](AGENTS.md#direction-and-execution) before repository work. Use the maintained executing loop and owning
skills, claim issue-backed work before creating a linked task worktree, and use bot commits and pushes. This repository
lands authorized changes through a PR with a normal merge commit after green current-head CI and required review findings
are accounted for; execution-guidance changes receive another model's review. Runtime actions have their own scope under
overall direction.

### Testing Requirements

```bash
# Default no-live-stack gate for local/PR validation.
# Excludes tests that require a live Docker daemon or Odoo container.
uv run mcp-test

# Alternatives
uv run mcp-test-ci          # CI unit gate
uv run mcp-test-unit        # Unit tests only
uv run mcp-test-integration # Mocked/non-live integration tests
uv run mcp-test-live        # Live Docker/Odoo integration tests
uv run mcp-test-cov         # No-live-stack coverage report for odoo_intelligence_mcp
uv run mcp-test-cov-ci      # CI coverage gate with XML output
uv run mcp-test-live-cov    # Live Docker/Odoo coverage report for odoo_intelligence_mcp

# Threshold: mcp-test-cov and mcp-test-cov-ci enforce the documented 75% minimum.
```

`mcp-test-cov` measures only the `odoo_intelligence_mcp` package and emits terminal, HTML, and XML reports. `mcp-test-cov-ci`
uses the same scope and threshold but omits the local HTML report. `mcp-test-live-cov` is informational because
a live-only subset cannot represent whole-package coverage. `mcp-test-live` and `mcp-test-live-cov` require the target Docker/Odoo
workspace to be available.

### Code Quality

```bash
uv run mcp-format  # ruff format
uv run ruff check .
uv run mcp-check   # format, then lint
```

`mcp-format` returns the formatter's exit status. `mcp-check` stops if formatting fails;
otherwise it returns Ruff's lint exit status. Both commands exit successfully when their checks succeed.

Run JetBrains (PyCharm) inspections on changed files with the `jetbrains-inspection` skill; `.github/github.json` lists
the scope order.

The GitHub Actions `test` job runs `uv run ruff check .` before the no-live-stack tests and the 75% coverage gate.

See AGENTS.md for workflow, formatting, and testing conventions.
