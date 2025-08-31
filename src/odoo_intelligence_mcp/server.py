import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, TextContent, Tool, ToolsCapability

from .core.env import HostOdooEnvironmentManager
from .core.utils import (
    PaginationParams,
    add_pagination_to_schema,
    get_optional_bool,
    get_optional_int,
    get_optional_list,
    get_optional_str,
    get_required,
)
from .tools.addon import get_addon_dependencies, get_module_structure
from .tools.analysis import analyze_patterns, analyze_performance, analyze_workflow_states
from .tools.code.execute_code import execute_code as execute_code_tool
from .tools.code.read_odoo_file import read_odoo_file
from .tools.code.search_code import search_code
from .tools.field import (
    analyze_field_values,
    get_field_dependencies,
    get_field_usages,
    resolve_dynamic_fields,
    search_field_properties,
    search_field_type,
)
from .tools.filesystem.find_files import find_files
from .tools.model import (
    analyze_inheritance_chain,
    find_method_implementations,
    get_model_info,
    get_model_relationships,
    get_view_model_usage,
    search_decorators,
    search_models,
)
from .tools.operations import odoo_restart, odoo_status, odoo_update_module
from .tools.security import check_permissions
from .type_defs.odoo_types import CompatibleEnvironment
from .utils.error_utils import OdooMCPError, create_error_response

logger = logging.getLogger(__name__)

app = Server("odoo-intelligence")

odoo_env_manager = HostOdooEnvironmentManager()


async def _handle_model_info(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await get_model_info(env, get_required(arguments, "model_name"))


async def _handle_search_models(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await search_models(env, get_required(arguments, "pattern"), pagination)


async def _handle_model_relationships(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_model_relationships(env, get_required(arguments, "model_name"), pagination)


async def _handle_field_usages(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_field_usages(env, get_required(arguments, "model_name"), get_required(arguments, "field_name"), pagination)


async def _handle_performance_analysis(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await analyze_performance(env, get_required(arguments, "model_name"), pagination)


async def _handle_pattern_analysis(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pattern_type = get_optional_str(arguments, "pattern_type", "all")
    pagination = PaginationParams.from_arguments(arguments)
    return await analyze_patterns(env, pattern_type, pagination)


async def _handle_inheritance_chain(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await analyze_inheritance_chain(env, get_required(arguments, "model_name"), pagination)


async def _handle_addon_dependencies(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_addon_dependencies(get_required(arguments, "addon_name"), pagination)


async def _handle_search_code(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pattern = get_required(arguments, "pattern")
    file_type = get_optional_str(arguments, "file_type", "py")
    pagination = PaginationParams.from_arguments(arguments)
    return await search_code(pattern, file_type, pagination)


async def _handle_find_files(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pattern = get_required(arguments, "pattern")
    file_type = get_optional_str(arguments, "file_type")
    pagination = PaginationParams.from_arguments(arguments)
    return await find_files(pattern, file_type, pagination)


async def _handle_read_odoo_file(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    file_path = get_required(arguments, "file_path")
    start_line = get_optional_int(arguments, "start_line")
    end_line = get_optional_int(arguments, "end_line")
    pattern = get_optional_str(arguments, "pattern")
    context_lines = get_optional_int(arguments, "context_lines", 5)
    return await read_odoo_file(file_path, start_line, end_line, pattern, context_lines)


async def _handle_find_method(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await find_method_implementations(env, get_required(arguments, "method_name"), pagination)


async def _handle_module_structure(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_module_structure(get_required(arguments, "module_name"), pagination)


async def _handle_view_model_usage(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_view_model_usage(env, get_required(arguments, "model_name"), pagination)


async def _handle_resolve_dynamic_fields(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await resolve_dynamic_fields(env, get_required(arguments, "model_name"), pagination)


async def _handle_search_field_properties(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await search_field_properties(env, get_required(arguments, "property"), pagination)


async def _handle_search_field_type(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await search_field_type(env, get_required(arguments, "field_type"), pagination)


async def _handle_search_decorators(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await search_decorators(env, get_required(arguments, "decorator"), pagination)


async def _handle_field_dependencies(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_field_dependencies(
        env, get_required(arguments, "model_name"), get_required(arguments, "field_name"), pagination
    )


async def _handle_workflow_states(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await analyze_workflow_states(env, get_required(arguments, "model_name"), pagination)


async def _handle_execute_code(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await execute_code_tool(env, get_required(arguments, "code"))


async def _handle_field_value_analyzer(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await analyze_field_values(
        env,
        get_required(arguments, "model_name"),
        get_required(arguments, "field_name"),
        get_optional_list(arguments, "domain", []),
        get_optional_int(arguments, "sample_size", 1000),
    )


async def _handle_permission_checker(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await check_permissions(
        env,
        get_required(arguments, "user"),
        get_required(arguments, "model"),
        get_required(arguments, "operation"),
        get_optional_int(arguments, "record_id"),
    )


async def _handle_odoo_update_module(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await odoo_update_module(get_required(arguments, "modules"), get_optional_bool(arguments, "force_install"))


async def _handle_odoo_status(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    verbose = get_optional_bool(arguments, "verbose")
    return await odoo_status(verbose)


async def _handle_odoo_restart(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    services = get_optional_str(arguments, "services")
    return await odoo_restart(**({"services": services} if services else {}))


async def _handle_model_query(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    operation = get_required(arguments, "operation")

    if operation == "info":
        return await _handle_model_info(env, arguments)
    elif operation == "search":
        return await _handle_search_models(env, arguments)
    elif operation == "relationships":
        return await _handle_model_relationships(env, arguments)
    elif operation == "inheritance":
        return await _handle_inheritance_chain(env, arguments)
    elif operation == "view_usage":
        return await _handle_view_model_usage(env, arguments)
    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}


async def _handle_field_query(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    operation = get_required(arguments, "operation")

    if operation == "usages":
        return await _handle_field_usages(env, arguments)
    elif operation == "analyze_values":
        return await _handle_field_value_analyzer(env, arguments)
    elif operation == "resolve_dynamic":
        return await _handle_resolve_dynamic_fields(env, arguments)
    elif operation == "dependencies":
        return await _handle_field_dependencies(env, arguments)
    elif operation == "search_properties":
        return await _handle_search_field_properties(env, arguments)
    elif operation == "search_type":
        return await _handle_search_field_type(env, arguments)
    else:
        return {"success": False, "error": f"Unknown operation: {operation}"}


async def _handle_analysis_query(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    analysis_type = get_required(arguments, "analysis_type")

    if analysis_type == "performance":
        return await _handle_performance_analysis(env, arguments)
    elif analysis_type == "patterns":
        return await _handle_pattern_analysis(env, arguments)
    elif analysis_type == "workflow":
        return await _handle_workflow_states(env, arguments)
    else:
        return {"success": False, "error": f"Unknown analysis_type: {analysis_type}"}


TOOL_HANDLERS = {
    "addon_dependencies": _handle_addon_dependencies,
    "search_code": _handle_search_code,
    "find_files": _handle_find_files,
    "read_odoo_file": _handle_read_odoo_file,
    "find_method": _handle_find_method,
    "module_structure": _handle_module_structure,
    "search_decorators": _handle_search_decorators,
    "execute_code": _handle_execute_code,
    "permission_checker": _handle_permission_checker,
    "odoo_update_module": _handle_odoo_update_module,
    "odoo_status": _handle_odoo_status,
    "odoo_restart": _handle_odoo_restart,
    "model_query": _handle_model_query,
    "field_query": _handle_field_query,
    "analysis_query": _handle_analysis_query,
}


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    # noinspection PyDataclass,Annotator
    return [
        Tool(
            name="addon_dependencies",
            description="Get addon dependencies",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {"addon_name": {"type": "string"}},
                    "required": ["addon_name"],
                }
            ),
        ),
        Tool(
            name="search_code",
            description="Search code",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern",
                        },
                        "file_type": {"type": "string"},
                    },
                    "required": ["pattern"],
                }
            ),
        ),
        Tool(
            name="find_files",
            description="Find files",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "File pattern",
                        },
                        "file_type": {
                            "type": "string",
                            "description": "File extension filter",
                        },
                    },
                    "required": ["pattern"],
                }
            ),
        ),
        Tool(
            name="read_odoo_file",
            description="Read files",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Start line",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "End line",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Context lines",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="module_structure",
            description="Get module structure",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {"module_name": {"type": "string"}},
                    "required": ["module_name"],
                }
            ),
        ),
        Tool(
            name="find_method",
            description="Find method",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {"method_name": {"type": "string"}},
                    "required": ["method_name"],
                }
            ),
        ),
        Tool(
            name="search_decorators",
            description="Search decorators",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "decorator": {
                            "type": "string",
                            "enum": ["depends", "constrains", "onchange", "create_multi"],
                        }
                    },
                    "required": ["decorator"],
                }
            ),
        ),
        Tool(
            name="execute_code",
            description="Execute code",
            inputSchema={
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
            },
        ),
        Tool(
            name="permission_checker",
            description="Check permissions",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {"type": "string"},
                    "model": {"type": "string"},
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "create", "unlink"],
                    },
                    "record_id": {"type": "integer"},
                },
                "required": ["user", "model", "operation"],
            },
        ),
        Tool(
            name="odoo_update_module",
            description="Update modules",
            inputSchema={
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "string",
                        "description": "Module names",
                    },
                    "force_install": {
                        "type": "boolean",
                        "description": "Force install",
                    },
                },
                "required": ["modules"],
            },
        ),
        Tool(
            name="odoo_status",
            description="Get status",
            inputSchema={
                "type": "object",
                "properties": {
                    "verbose": {
                        "type": "boolean",
                        "description": "Show details",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="odoo_restart",
            description="Restart containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "services": {
                        "type": "string",
                        "description": "Services",
                    }
                },
            },
        ),
        Tool(
            name="model_query",
            description="Query model operations",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["info", "search", "relationships", "inheritance", "view_usage"],
                        },
                        "model_name": {"type": "string"},
                        "pattern": {"type": "string"},
                    },
                    "required": ["operation"],
                }
            ),
        ),
        Tool(
            name="field_query",
            description="Query field operations",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": [
                                "usages",
                                "analyze_values",
                                "resolve_dynamic",
                                "dependencies",
                                "search_properties",
                                "search_type",
                            ],
                        },
                        "model": {"type": "string"},
                        "model_name": {"type": "string"},
                        "field": {"type": "string"},
                        "field_name": {"type": "string"},
                        "property": {"type": "string"},
                        "field_type": {"type": "string"},
                        "domain": {"type": "array"},
                        "sample_size": {"type": "integer"},
                    },
                    "required": ["operation"],
                }
            ),
        ),
        Tool(
            name="analysis_query",
            description="Query analysis operations",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "enum": ["performance", "patterns", "workflow"],
                        },
                        "model_name": {"type": "string"},
                        "pattern_type": {"type": "string"},
                    },
                    "required": ["analysis_type"],
                }
            ),
        ),
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, object] | None) -> list[TextContent]:
    if arguments is None:
        arguments = {}  # Default to empty dict for tools with all optional parameters

    handler = TOOL_HANDLERS.get(name)
    if not handler:
        # noinspection Annotator
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    try:
        env = await odoo_env_manager.get_environment()

        try:
            result = await handler(env, arguments)
            response_text = json.dumps(result, indent=2, default=str)
            # noinspection Annotator
            return [TextContent(type="text", text=response_text)]
        finally:
            if hasattr(env, "cr") and env.cr and hasattr(env.cr, "close"):
                env.cr.close()

    except OdooMCPError as e:
        logger.exception(f"Error in tool {name}")
        error_response = create_error_response(e)
        response_text = json.dumps(error_response, indent=2)
        # noinspection Annotator
        return [TextContent(type="text", text=response_text)]
    except Exception as e:
        logger.exception(f"Unexpected error in tool {name}")
        error_response = create_error_response(e)
        response_text = json.dumps(error_response, indent=2)
        # noinspection Annotator
        return [TextContent(type="text", text=response_text)]


# noinspection Annotator
async def run_server() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="odoo-intelligence",
                server_version="0.1.0",
                capabilities=ServerCapabilities(tools=ToolsCapability()),
            ),
        )


def main() -> None:
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
