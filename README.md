# Odoo Intelligence MCP Server

Comprehensive Model Context Protocol (MCP) server providing deep code analysis and development tools for Odoo projects.

## Features

**25 Tools Available:**
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
claude mcp add-json odoo-intelligence '{"command": "uv", "args": ["run", "--project", "/Users/cbusillo/Developer/odoo-intelligence-mcp", "odoo-intelligence-mcp"]}'
```

**Note**: The `--project` flag is required when running from a different directory to ensure `uv` finds the correct virtual environment.

Restart Claude Code after configuration changes.

### Environment

- **Database**: `opw`
- **Addons Path**: `/volumes/addons,/odoo/addons,/volumes/enterprise` 
- **Container**: `odoo-opw-web-1` (main), `odoo-opw-shell-1` (shell), `odoo-opw-script-runner-1` (updates)

### Manual Testing

```bash
# Test individual functions
docker exec -i odoo-opw-web-1 bash -c "cd /mcp_servers/odoo_intelligence_mcp && /venv/bin/python -c '
import sys
sys.path.insert(0, \"/mcp_servers/odoo_intelligence_mcp/src\")
from odoo_intelligence_mcp.server import model_info
# Test implementation
'"
```

## Available Tools (28 total)

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
# Page-based pagination (recommended)
result = await pattern_analysis(env, "computed_fields", page=2, page_size=50)

# Offset-based pagination (alternative)
result = await search_models(env, "product", limit=20, offset=40)

# With filtering
result = await find_method(env, "create", page=1, page_size=100, filter="sale")
```

### Response Structure

Paginated responses include metadata:
```json
{
  "success": true,
  "data": [...],  // The actual results
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

```bash
# Format and lint
ruff format . && ruff check . --fix

# Run tests
uv run pytest

# Test changes directly in container before MCP restart
docker exec -i odoo-opw-web-1 bash -c "cd /mcp_servers/odoo_intelligence_mcp && /venv/bin/python -c 'test_code_here'"
```

See CLAUDE.md for detailed development guidelines and patterns.