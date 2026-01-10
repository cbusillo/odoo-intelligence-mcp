# Odoo Intelligence MCP Server

Comprehensive Model Context Protocol (MCP) server providing deep code analysis and development tools for Odoo projects.

## Features

- 15 tools exposing 30+ capabilities
- Model/field/analysis queries with pagination and filtering
- Docker-connected Odoo environment (exec into containers)
- Structured errors with optional enhanced diagnostics
- Large-response protection with pagination and truncation

## Installation

- Prereqs: Python 3.14+ and `uv`
- From the project directory: `uv sync`

## Configuration

### Claude Code Integration

Add the MCP server to Claude Code/Claude Desktop:

```bash
# Use --project to ensure uv resolves this repo's environment
claude mcp add-json odoo-intelligence '{"command": "uv", "args": ["run", "--project", "/path/to/odoo-intelligence-mcp", "odoo-intelligence-mcp"]}'
```

Restart Claude after configuration changes.

### Environment

`.env` resolution order:
1) `ODOO_ENV_FILE` (explicit)
2) `ODOO_STATE_ROOT/.compose.env` or `~/odoo-ai/<stack>/.compose.env` (via `ODOO_PROJECT_NAME` or `ODOO_STACK_NAME`)
   - When `docker/config/ops.toml` exists (found via `ODOO_PROJECT_DIR` or current dir), MCP uses
     `uv run ops local info <target> --json` to resolve the correct `.compose.env`.
3) Current working directory (where Claude was launched)
4) This MCP server directory (fallback)

Override discovery by setting `ODOO_ENV_FILE` to the target project's `.env` path or `ODOO_PROJECT_DIR` for compose resolution. Use `ODOO_ENV_PRIORITY=process` to let process env vars override `.compose.env` values.

Optional container overrides:
- `ODOO_CONTAINER_NAME` (primary exec container)
- `ODOO_SCRIPT_RUNNER_CONTAINER`
- `ODOO_WEB_CONTAINER`

If the script-runner container is missing, MCP will try `{prefix}-web-1`, `{prefix}-odoo-1`, and `{prefix}-app-1`.

Compose files can be supplied via `ODOO_COMPOSE_FILES` or inherited from `DEPLOY_COMPOSE_FILES`/`COMPOSE_FILE` in the target env.

Defaults (override via environment or `.env`):
- Database: `odoo` (`ODOO_DB_NAME`)
- Addons Path: `/opt/project/addons,/odoo/addons,/volumes/enterprise` (`ODOO_ADDONS_PATH`)
- Container Prefix: required (`ODOO_PROJECT_NAME`) unless container overrides are set

Derived containers from prefix:
- Script Runner: `{prefix}-script-runner-1`
- Web: `{prefix}-web-1`

### Modes and Fallbacks

Many operations accept `mode`:
- `auto` (default)
- `fs` (static scan over `ODOO_ADDONS_PATH`)
- `registry` (runtime via Odoo registry)
- `db` (reserved)

Enable enhanced error payloads: `ODOO_MCP_ENHANCED_ERRORS=true`.

### Using with Different Projects

Launch Claude from your Odoo project directory so `.env` is discovered. Or set env vars:

```bash
export ODOO_PROJECT_NAME="odoo-dev"
export ODOO_DB_NAME="mydb"
export ODOO_ADDONS_PATH="/custom/addons,/odoo/addons"
```

## Operations (Tools)

- `search_code(pattern, file_type=py, roots?[])` → hits[] (default file_type is `py`; set `xml`/`js` for other sources)
- `find_method(method_name, mode=auto|fs|registry)` → locations[]
- `model_query(operation: info|search|relationships|inheritance|view_usage, model_name?, pattern?, page?, page_size?, mode=auto)`
- `field_query(operation: usages|dependencies|analyze_values|resolve_dynamic|search_properties|search_type, model_name, field_name?, field_type?, property?, sample_size=1000, page?, page_size?, mode=auto)`
- `analysis_query(analysis_type: performance|patterns|workflow|inheritance, model_name?, pattern_type?, page?, page_size?, mode=auto)`
- `addon_dependencies(addon_name)` → deps[]
- `module_structure(module_name)` → files[], manifest, meta
- `execute_code(code)` → stdout, stderr, exit_code
- `permission_checker(user, model, operation, record_id?)` → allowed: true|false, rationale (user accepts id or login/email)
- `odoo_update_module(modules, force_install=false)` → result
- `odoo_status(verbose=false)` → containers[], services[]
- `odoo_restart(services?)` → result

Parameters
- `mode` (where supported): `auto` (default), `fs`, `registry`
- Pagination: `page`, `page_size` (max 1000) or `offset`, `limit`
- Filters: `filter` (client‑side contains), `roots`

Notes
- `field_query` search_type expects `field_type` (e.g., `char`, `many2one`, `selection`)
- `analysis_query` patterns supports `pattern_type`: `computed_fields`, `related_fields`, `api_decorators`, `custom_methods`, `state_machines`, `all`

Examples
- Search Python for a pattern:
  `search_code { "pattern": "def _compute", "file_type": "py", "roots": ["/volumes/addons"] }`
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

<!-- Removed deprecated View Migration Helper section; use search_code/read_odoo_file/model_query for migrations. -->

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

### Testing Requirements

```bash
# Run the full suite (must pass)
uv run mcp-test

# Alternatives
uv run mcp-test-unit        # Unit tests
uv run mcp-test-integration # Integration tests
uv run mcp-test-cov         # With coverage report

# Threshold: 75% minimum coverage (current fail-under 74.5 in pyproject)
```

### Code Quality

```bash
uv run mcp-format  # ruff format

# Project inspections (PyCharm profile via Codex CLI)
inspection_trigger(scope="whole_project")
inspection_get_problems()
```

See AGENTS.md for workflow, formatting, and testing conventions.
