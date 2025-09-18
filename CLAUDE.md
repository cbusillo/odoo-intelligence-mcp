# CLAUDE.md

Development guidelines for the Odoo Intelligence MCP Server.

## Project: Odoo Intelligence MCP Server

**Stack**: Python 3.12+, MCP SDK 1.9+, asyncio

## Quick Command Reference

**Setup**: `uv sync` (installs dependencies in local venv)
**Run**: `uv run odoo_intelligence_mcp` (runs on host, connects to Docker)
**Format**: `uv run mcp-format`
**Inspections**: JetBrains inspection profile via `inspection_trigger(scope="whole_project")`
**Tests**: `uv run mcp-test` (ALL must pass - no failures allowed)
**Coverage**: `uv run mcp-test-cov` (minimum 75% required)

## Code Standards

- **NO comments/docstrings** - Self-documenting code via:
    - Descriptive names using full words (no abbreviations)
    - Clear function/variable names that state their purpose
    - Method chains that read like sentences
    - Exception: Comments are allowed in pyproject.toml files for configuration clarity
- **Type hints required**:
    - Use precise types, never generic `Any`/`object` unless absolutely necessary
    - Prefer `list[str]` over `List[str]` (Python 3.9+ style)
    - Async functions: `async def tool_function() -> dict[str, Any]:`
    - For Odoo types, use `type_defs.odoo_types` module:
        - `Environment` for type checking compatibility
        - `CompatibleEnvironment` when accepting both real and mock environments
        - JetBrains magic strings during TYPE_CHECKING, protocols at runtime
- **Line length**: 133 chars
- **Tests**: 75% coverage minimum
- **F-strings preferred**: Use f-strings for all string formatting, including logging and exceptions
- **Early returns preferred**: No else after return (ignore TRY300 ruff rule)

## Development Workflow

**Tool preferences** (in order of efficiency):

1. **Direct container testing** - Test functions before MCP restart
2. **Built-in tools** - `Read`, `Edit`, `MultiEdit`, `Write` for development
3. **Docker exec** - For complex operations requiring Odoo environment

**NEVER use bash for**: `find`, `grep`, `cat`, `ls` - use Claude Code tools instead

**Development steps**:

1. **Test existing tools** - Ensure clean baseline with existing MCP tools
2. **Follow MCP patterns** - Study existing tool implementations in `server.py`
3. **Handle large responses** - Use `pagination_utils.py` for >25K token responses
4. **Close cursors properly** - Always use try/finally blocks in tool handlers
5. **Run ALL tests before commit** - `uv run mcp-test` must pass 100%
6. **Format before commit** - `uv run mcp-format`
7. **Run inspections** - `inspection_trigger(scope="whole_project")` then review `inspection_get_problems`
8. **Check coverage** - `uv run mcp-test-cov` must show ≥75% coverage

## MCP Tool Development

**Adding new tools**:

1. **Tool definition** - Add to `tools` list in `server.py` with proper schema
2. **Handler** - Add `elif name == "tool_name"` in `handle_call_tool`
3. **Implementation** - Create `async def tool_function()` before `run_server()`
4. **Test directly** - Use container execution to test function before MCP restart
5. **Check response size** - Use `validate_response_size()` for large responses

**Required patterns**:

```python
from odoo_intelligence_mcp.core.env import HostOdooEnvironment

async def get_model_fields(env: HostOdooEnvironment, model_name: str) -> dict[str, Any]:
    try:
        fields_data = await env.execute_code(f"result = env['{model_name}'].fields_get()")
        return {"success": True, "model": model_name, "fields": fields_data}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
```

**Large responses**: Use `pagination_utils.py`:

- Add `PaginationParams.from_arguments(arguments)`
- Use `paginate_dict_list(items, pagination)`
- Add pagination schema with `add_pagination_to_schema()`

## Configuration

**Environment Variables** (for portability to any Odoo project):
- `ODOO_PROJECT_NAME`: Container name prefix (default: "odoo")
- `ODOO_DB_NAME`: Database name (default: "odoo")
- `ODOO_ADDONS_PATH`: Addon paths (default: "/opt/project/addons,/odoo/addons,/volumes/enterprise")

## Architecture

**Host-based MCP Server** (runs on host machine, not in Docker):

- Connects to Odoo via Docker exec to containers (configurable via ODOO_PROJECT_NAME)
- Uses subprocess to execute Python code in Odoo environment
- Returns JSON-serializable results

**Structure**:

- `server.py` - MCP server with 25 tool implementations
- `core/env.py` - Docker-based Odoo environment access (HostOdooEnvironment)
- `type_defs/odoo_types.py` - Type definitions for Odoo models and environment
- `core/utils.py` - Pagination and response validation utilities
- `tools/` - Individual tool implementations organized by category
- `services/` - Business logic services (e.g., FieldAnalyzer)

**Environment Management**:

- Each request spawns fresh Docker exec subprocess
- Code wrapped to ensure JSON output
- Error handling for Docker failures and timeouts

## Docker Connection

**Primary container**: `{ODOO_PROJECT_NAME}-script-runner-1` (default prefix: odoo)
**Database**: `odoo`
**Execution**: Uses `/odoo/odoo-bin shell` with `--no-http`

## Testing

**Direct function testing**:

```python
# test_tool.py
import asyncio
from odoo_intelligence_mcp.core.env import HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.model.model_info import get_model_info


async def test() -> None:
    env = await HostOdooEnvironmentManager().get_environment()
    result = await get_model_info(env, "res.partner")
    print(result)


asyncio.run(test())
```

**Run**: `uv run python test_tool.py`

**Response validation**:

- All responses must be JSON serializable
- Complex objects simplified to basic types
- Large responses (>25K tokens) must use pagination

**Inline suppressions**: Use sparingly with explanations:

```python
# Using subprocess.run is intentional - Docker exec is fast and we need the simplicity
process = subprocess.run(docker_cmd, ...)  # noqa: ASYNC221
```
