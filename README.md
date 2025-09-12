# Odoo Intelligence MCP Server

Comprehensive Model Context Protocol (MCP) server providing deep code analysis and development tools for Odoo projects.

## Features

**30 Tools Available:**
- **Code Intelligence**: Analyze models, fields, relationships, inheritance chains, and patterns
- **Development Tools**: Execute code, run tests, analyze field values, debug permissions  
- **Shell Integration**: Direct access to Odoo shell environment

**Key Capabilities:**
- Auto-pagination for large responses (25K token limit)
- Persistent Odoo environment connection
- Comprehensive error handling and JSON serialization
- Works with Dockerized Odoo setups

## Installation

1. Ensure Python 3.12+ and `uv` are installed
2. From the project directory: `uv sync`

## Configuration

### Claude Code Integration

To add this MCP server to any project:

```bash
# Add the MCP server (use --project flag to ensure uv finds the correct environment)
claude mcp add-json odoo-intelligence '{"command": "uv", "args": ["run", "--project", "/path/to/odoo-intelligence-mcp", "odoo-intelligence-mcp"]}'
```

**Note**: The `--project` flag is required when running from a different directory to ensure `uv` finds the correct virtual environment.

Restart Claude Code after configuration changes.

### Environment

The MCP server loads configuration from `.env` files in this order:
1. **Current working directory** - Where Claude Code was launched from (your project directory)
2. **MCP server directory** - Fallback if no .env found in working directory

Default configuration (can be customized via environment variables or `.env` file):
- **Database**: `odoo` (env: `ODOO_DB_NAME`)
- **Addons Path**: `/opt/project/addons,/odoo/addons,/volumes/enterprise` (env: `ODOO_ADDONS_PATH`)
- **Container Prefix**: `odoo` (env: `ODOO_PROJECT_NAME`)

Containers are automatically derived from the prefix:
- Primary: `{prefix}-script-runner-1` (used for most operations)
- Web: `{prefix}-web-1` (file operations, logs)
- Shell: `{prefix}-shell-1` (available for shell access)

### Modes and fallbacks

Many tools accept an optional `mode` parameter:
- `auto` (default): normal behavior, may fall back to FS mode when available
- `fs`: Odoo-less static analysis using AST over `ODOO_ADDONS_PATH`
- `registry`: force runtime via Odoo shell/registry
- `db`: reserved for future DB-only fallbacks (field_query)

Enable structured error payloads when the registry fails by setting `ODOO_MCP_ENHANCED_ERRORS=true`.

### Using with Different Projects

**Important**: Launch Claude Code from your Odoo project directory so the MCP server can find your `.env` file.

To use with a different Odoo project, you can either:
1. Launch Claude Code from your project directory (recommended)
2. Or set environment variables before running:

```bash
# Example for a project with containers named "odoo-dev-*" and database "mydb"
export ODOO_PROJECT_NAME="odoo-dev"
export ODOO_DB_NAME="mydb"
export ODOO_ADDONS_PATH="/custom/addons,/odoo/addons"

# Then add to Claude Code
claude mcp add-json odoo-intelligence '...'
```

### Manual Testing

```bash
# Test individual functions
docker exec -i ${ODOO_PROJECT_NAME}-web-1 bash -c "cd /mcp_servers/odoo_intelligence_mcp && /venv/bin/python -c '
import sys
sys.path.insert(0, \"/mcp_servers/odoo_intelligence_mcp/src\")
from odoo_intelligence_mcp.server import model_info
# Test implementation
'"
```

## Available Tools (30 total)

**Code Intelligence:**
- `model_info` - Comprehensive model analysis (fields, methods, inheritance)
- `search_models` - Pattern-based model search with fuzzy matching
- `model_relationships` - M2O/O2M/M2M relationship mapping
- `field_usages` - Track field usage across views/methods/domains
- `performance_analysis` - Identify N+1 queries and optimization opportunities
- `pattern_analysis` - Analyze Odoo coding patterns across codebase (paginated)
- `inheritance_chain` - Complete inheritance chain with MRO analysis
- `addon_dependencies` - Manifest analysis and dependency tracking
- `search_code` - Regex-based code search across addons (paginated)
- `find_files` - Find files by name pattern in Odoo addon directories (paginated)
- `read_odoo_file` - Read any Odoo source file with line range and pattern matching support
- `module_structure` - Module directory structure analysis
- `find_method` - Find all models implementing a specific method (paginated)
- `search_decorators` - Find methods by decorator type
- `view_model_usage` - View usage statistics and field coverage analysis
- `workflow_states` - Analyze state fields, transitions, and workflow patterns
- `search_field_type` - Find models with fields of specific type (paginated)
- `search_field_properties` - Search fields by properties (paginated)
- `resolve_dynamic_fields` - Analyze computed/related fields with cross-model dependencies
- `field_dependencies` - Show dependency graph for specific field

**Development & Analysis:**
- `execute_code` - Run arbitrary Python code in Odoo environment context
- `test_runner` - Run Odoo tests with granular control (placeholder implementation)
- `field_value_analyzer` - Analyze actual field values for data patterns and quality
- `permission_checker` - Debug access rights and record rules

**Odoo Shell Integration:**
- `odoo_shell` - Execute Python code in dedicated Odoo shell container (with security validation)

**Container Management:**
- `odoo_update_module` - Update Odoo modules with optional force install
- `odoo_install_module` - Install new Odoo modules
- `odoo_status` - Check Odoo container health and status
- `odoo_restart` - Restart Odoo containers
- `odoo_logs` - Retrieve recent Odoo container logs

## Pagination

Many tools that return lists support pagination to handle large result sets efficiently. Tools with pagination support are marked with "(paginated)" in the tool list above.

### Pagination Parameters

All paginated tools support **two pagination styles** - you can use either one:

**Style 1: Page-based (Recommended)**
- `page` - Page number (1-based, default: 1)
- `page_size` - Number of items per page (default: 100, max: 1000)

**Style 2: Offset-based (Alternative)**
- `limit` - Maximum number of items to return (max: 1000)
- `offset` - Number of items to skip

**Additional Parameter:**
- `filter` - Text filter to search within results (optional)

### Examples

```python
from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager

async def example_usage() -> None:
    env = await HostOdooEnvironmentManager().get_environment()
    
    # Page-based pagination (recommended)
    computed_fields = await pattern_analysis(env, "computed_fields", page=2, page_size=50)
    print(f"Found {len(computed_fields['data'])} computed fields")
    
    # Offset-based pagination (alternative)
    product_models = await search_models(env, "product", limit=20, offset=40)
    print(f"Found {len(product_models['data'])} product models")
    
    # With filtering
    create_methods = await find_method(env, "create", page=1, page_size=100, filter="sale")
    print(f"Found {len(create_methods['data'])} create methods in sale")
```

### Response Structure

Paginated responses include metadata:
```json
{
  "success": true,
  "data": [],
  "pagination": {
    "page": 2,
    "page_size": 50,
    "total_count": 245,
    "total_pages": 5,
    "has_next": true,
    "has_previous": true,
    "filter_applied": "sale"
  }
}
```

## Limitations

- **Docker Management Tools**: `odoo_status`, `odoo_restart`, `odoo_logs` require Docker access and won't work from inside containers due to permission restrictions. These are functional but designed for host-based MCP deployments.
- **Large Responses**: Tools automatically paginate responses >25K tokens to prevent overwhelming the LLM context window.

## Development

### Testing Requirements

**IMPORTANT**: Before committing any changes, ALL tests must pass with proper coverage:

```bash
# Run the FULL test suite - ALL tests must pass
uv run mcp-test

# Alternative test commands:
uv run mcp-test-unit      # Unit tests only
uv run mcp-test-integration  # Integration tests only
uv run mcp-test-cov       # Run with coverage report

# Required: 80% minimum code coverage
# All tests must pass - no failures, no errors
```

### Code Quality

```bash
# Format and lint (run before committing)
uv run mcp-format  # Format code with ruff
uv run mcp-lint    # Fix linting issues

# Or manually:
ruff format . && ruff check . --fix
```

See CLAUDE.md for detailed development guidelines and patterns.
