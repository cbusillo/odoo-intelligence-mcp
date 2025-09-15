# Odoo Intelligence MCP Server

Comprehensive Model Context Protocol (MCP) server providing deep code analysis and development tools for Odoo projects.

## Features

- 15 tools exposing 30+ capabilities
- Model/field/analysis queries with pagination and filtering
- Docker-connected Odoo environment (exec into containers)
- Structured errors with optional enhanced diagnostics
- Large-response protection with pagination and truncation

## Installation

- Prereqs: Python 3.12+ and `uv`
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
1) Current working directory (where Claude was launched)
2) This MCP server directory (fallback)

Defaults (override via environment or `.env`):
- Database: `odoo` (`ODOO_DB_NAME`)
- Addons Path: `/opt/project/addons,/odoo/addons,/volumes/enterprise` (`ODOO_ADDONS_PATH`)
- Container Prefix: `odoo` (`ODOO_PROJECT_NAME`)

Derived containers from prefix:
- Script Runner: `{prefix}-script-runner-1`
- Web: `{prefix}-web-1`
- Shell: `{prefix}-shell-1`

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

- `search_code(pattern, file_type=py, roots?[])` → hits[]
- `find_method(method_name, mode=auto|fs|registry)` → locations[]
- `model_query(operation: info|search|relationships|inheritance|view_usage, model_name?, pattern?, page?, page_size?, mode=auto)`
- `field_query(operation: usages|dependencies|analyze_values|resolve_dynamic|search_properties|search_type, model_name, field_name?, field_type?, property?, sample_size=1000, page?, page_size?, mode=auto)`
- `addon_dependencies(addon_name)` → deps[]
- `module_structure(module_name)` → files[], manifest, meta
- `execute_code(code)` → stdout, stderr, exit_code
- `permission_checker(user, model, operation, record_id?)` → allowed: true|false, rationale
- `odoo_update_module(modules, force_install=false)` → result
- `odoo_status(verbose=false)` → containers[], services[]
- `odoo_restart(services?)` → result

Parameters
- `mode` (where supported): `auto` (default), `fs`, `registry`
- Pagination: `page`, `page_size` (max 1000) or `offset`, `limit`
- Filters: `filter` (client‑side contains), `roots`

Examples
- Search Python for a pattern:
  `search_code { "pattern": "def _compute", "file_type": "py", "roots": ["/volumes/addons"] }`
- Model info:
  `model_query { "operation": "info", "model_name": "sale.order" }`
- Field dependencies:
  `field_query { "operation": "dependencies", "model_name": "sale.order", "field_name": "amount_total" }`

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

# Threshold: 80% minimum coverage (enforced in pyproject)
```

### Code Quality

```bash
uv run mcp-format  # ruff format
uv run mcp-lint    # ruff check --fix

# Or manually
ruff format . && ruff check . --fix
```

See CLAUDE.md for workflow, formatting, and testing conventions.
