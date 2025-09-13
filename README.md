# Odoo Intelligence MCP Server

Comprehensive Model Context Protocol (MCP) server providing deep code analysis and development tools for Odoo projects.

## Features

- 15 registered tools exposing 30+ capabilities
- Model/field/analysis queries with pagination and filtering
- Persistent Odoo environment connection (Docker exec + Odoo shell)
- Structured errors with optional enhanced diagnostics
- Safe JSON serialization and automatic large-response protection

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
- `auto` (default): normal behavior (falls back to FS when possible)
- `fs`: static AST analysis over `ODOO_ADDONS_PATH` (no running Odoo)
- `registry`: force runtime via Odoo registry
- `db`: reserved (for future DB-only fallbacks)

Enable enhanced error payloads: `ODOO_MCP_ENHANCED_ERRORS=true`.

### Using with Different Projects

Launch Claude from your Odoo project directory so `.env` is discovered. Or set env vars:

```bash
export ODOO_PROJECT_NAME="odoo-dev"
export ODOO_DB_NAME="mydb"
export ODOO_ADDONS_PATH="/custom/addons,/odoo/addons"
```

## Registered Tools

The server exposes these MCP tools (names and input schemas match the implementation):

- `addon_dependencies` – Get addon dependencies
- `search_code` – Regex search in addons (fs; optional `file_type`, `roots`)
- `find_files` – Find files by pattern (optional `file_type`)
- `read_odoo_file` – Read source file ranges with optional pattern/context
- `module_structure` – Analyze module directory structure
- `find_method` – Find method implementations (`mode`: auto|fs|registry)
- `search_decorators` – Find decorated methods (`depends|constrains|onchange|create_multi`; `mode` supported)
- `execute_code` – Run Python in Odoo shell context (Docker exec)
- `permission_checker` – Check access rights and record rules
- `odoo_update_module` – Update modules (`force_install` optional)
- `odoo_status` – Container health/status (`verbose` optional)
- `odoo_restart` – Restart containers (optional `services`)
- `model_query` – Models: `info|search|relationships|inheritance|view_usage` (alias: `list→search`)
- `field_query` – Fields: `usages|analyze_values|resolve_dynamic|dependencies|search_properties|search_type` (alias: `list`)
- `analysis_query` – Analysis: `performance|patterns|workflow|inheritance`

Notes:
- Former standalone tools like `model_info`, `search_models`, `workflow_states`, etc. are now accessed via the consolidated `model_query`, `field_query`, and `analysis_query` tools.
- There is no separate `odoo_shell` or `odoo_logs` tool registered; use `execute_code` and `odoo_status/odoo_restart` respectively.

### Example Calls (conceptual)

- Model info: `model_query { operation: "info", model_name: "sale.order" }`
- Search models: `model_query { operation: "search", pattern: "product", page: 1, page_size: 25 }`
- Field usages: `field_query { operation: "usages", model_name: "sale.order", field_name: "partner_id" }`
- Patterns: `analysis_query { analysis_type: "patterns", pattern_type: "computed_fields", page_size: 50 }`

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
