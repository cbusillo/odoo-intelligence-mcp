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


def _enhance_registry_failure(env: CompatibleEnvironment, tool_name: str, result: object) -> object:
    """Add a structured, LLM-friendly error contract when Odoo can't boot.

    We only transform dict-like error payloads that look like container/registry
    problems, leaving successful and unrelated errors unchanged.
    """
    # noinspection PyBroadException
    try:
        if not isinstance(result, dict):
            return result

        # Already success or no error: leave as-is
        if result.get("success") is True or "error" not in result:
            return result

        error_type = str(result.get("error_type", ""))
        error_msg = str(result.get("error", ""))
        indicative = (
            error_type in {"DockerConnectionError", "ExecutionError", "CodeExecutionError"}
            or "odoo" in error_msg.lower()
            or "database" in error_msg.lower()
            or "docker" in error_msg.lower()
        )
        if not indicative:
            return result

        # Check feature flag before enhancing
        # noinspection PyBroadException
        try:
            from .core.env import load_env_config  # local import to avoid cycles

            cfg = load_env_config()
            if not getattr(cfg, "enhanced_errors", False):
                return result
        except Exception:
            return result

        # Build structured guidance
        container = getattr(env, "container_name", None)
        web_container = getattr(cfg, "web_container", None)  # safe access without try/except

        import re as _re

        text_to_scan = error_msg + "\n" + _re.sub(r"\\s+", " ", str(result.get("stderr", "")))
        culprit_files = [
            {"path": m.group(1), "line": (m.group(2) or "")}
            for m in _re.finditer(r"(/[^:\s]+\.py)(?::(\d+))?", text_to_scan)
        ]

        guidance = {
            "success": False,
            "category": "odoo_registry_error",
            "summary": f"{tool_name} failed because Odoo could not start or connect.",
            "error": error_msg,
            "error_type": error_type or "OdooRegistryError",
            "tool": tool_name,
            "next_tools": [
                "read_odoo_file",
                "find_files",
                "addon_dependencies",
                "module_structure",
                "odoo_status",
                "odoo_restart",
            ],
            "suggestions": [
                "Inspect the failing file via read_odoo_file using an absolute container path.",
                "Search occurrences with search_code (fs) or find_files if paths are unknown.",
                "Check container health with odoo_status; if needed use odoo_restart.",
                "Temporarily disable module auto-updates (ODOO_UPDATE) while debugging.",
            ],
            "telemetry": {
                "container": container,
                "web_container": web_container,
            },
            "culprit_files": culprit_files[:5],
        }
        # Keep original fields for compatibility/context
        guidance["original"] = {k: v for k, v in result.items() if k not in guidance}
        return guidance
    except Exception:
        # On any enhancement error, return original result
        return result


async def _handle_model_info(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    # Use smaller default page size to prevent huge responses
    if pagination.page_size == 100 and "page_size" not in arguments:
        pagination.page_size = 25
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    if mode == "fs":
        from .tools.model.model_info_fs import get_model_info_fs

        return await get_model_info_fs(get_required(arguments, "model_name"), pagination)
    return await get_model_info(env, get_required(arguments, "model_name"), pagination)


async def _handle_search_models(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    # Use smaller default page size to prevent huge responses
    if pagination.page_size == 100 and "page_size" not in arguments:
        pagination.page_size = 25
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    if mode == "fs":
        from .tools.model.search_models_fs import search_models_fs

        return await search_models_fs(get_required(arguments, "pattern"), pagination)
    return await search_models(env, get_required(arguments, "pattern"), pagination)


async def _handle_model_relationships(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    if mode == "fs":
        from .tools.model.model_relationships_fs import get_model_relationships_fs

        return await get_model_relationships_fs(get_required(arguments, "model_name"), pagination)
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
    # Use smaller default page size to prevent huge responses
    if pagination.page_size == 100 and "page_size" not in arguments:
        pagination.page_size = 25
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    if mode == "fs":
        from .tools.analysis.pattern_analysis_fs import analyze_patterns_fs

        return await analyze_patterns_fs(pattern_type, pagination)
    return await analyze_patterns(env, pattern_type, pagination)


async def _handle_inheritance_chain(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    if mode == "fs":
        from .tools.model.inheritance_chain_fs import analyze_inheritance_chain_fs

        return await analyze_inheritance_chain_fs(get_required(arguments, "model_name"), pagination)
    return await analyze_inheritance_chain(env, get_required(arguments, "model_name"), pagination)


async def _handle_addon_dependencies(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_addon_dependencies(get_required(arguments, "addon_name"), pagination)


async def _handle_search_code(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pattern = get_required(arguments, "pattern")
    file_type = get_optional_str(arguments, "file_type", "py")
    roots = get_optional_list(arguments, "roots")
    pagination = PaginationParams.from_arguments(arguments)
    return await search_code(pattern, file_type, pagination, roots)


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
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    return await find_method_implementations(env, get_required(arguments, "method_name"), pagination, mode)


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
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    return await search_decorators(env, get_required(arguments, "decorator"), pagination, mode)


async def _handle_field_dependencies(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await get_field_dependencies(
        env, get_required(arguments, "model_name"), get_required(arguments, "field_name"), pagination
    )


async def _handle_workflow_states(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    mode = get_optional_str(arguments, "mode", "auto") or "auto"
    if mode == "fs":
        from .tools.analysis.workflow_states_fs import analyze_workflow_states_fs

        return await analyze_workflow_states_fs(get_required(arguments, "model_name"), pagination)
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
    elif operation == "search" or operation == "list":
        # alias: list -> search (default to pattern ".*" if missing)
        if operation == "list" and "pattern" not in arguments:
            arguments = {**arguments, "pattern": ".*"}
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
    mode = get_optional_str(arguments, "mode", "auto") or "auto"

    if operation == "usages":
        return await _handle_field_usages(env, arguments)
    elif operation == "analyze_values":
        return await _handle_field_value_analyzer(env, arguments)
    elif operation == "resolve_dynamic":
        return await _handle_resolve_dynamic_fields(env, arguments)
    elif operation == "dependencies":
        return await _handle_field_dependencies(env, arguments)
    elif operation == "search_properties":
        if mode == "fs":
            from .tools.field.search_field_properties_fs import search_field_properties_fs

            pagination = PaginationParams.from_arguments(arguments)
            return await search_field_properties_fs(get_required(arguments, "property"), pagination)
        return await _handle_search_field_properties(env, arguments)
    elif operation == "search_type":
        if mode == "fs":
            from .tools.field.search_field_type_fs import search_field_type_fs

            pagination = PaginationParams.from_arguments(arguments)
            return await search_field_type_fs(get_required(arguments, "field_type"), pagination)
        return await _handle_search_field_type(env, arguments)
    elif operation == "list":
        # alias: list -> flatten fields of model_name
        model_name = get_required(arguments, "model_name")
        info = await _handle_model_info(env, {**arguments, "model_name": model_name})
        if isinstance(info, dict) and "error" in info:
            return info
        fields_dict = info.get("fields", {}) if isinstance(info, dict) else {}
        items = []
        if isinstance(fields_dict, dict):
            for fname, fdata in fields_dict.items():
                entry = {"name": fname}
                if isinstance(fdata, dict):
                    for k in ("type", "string", "required", "store", "relation"):
                        if k in fdata:
                            entry[k] = fdata[k]
                items.append(entry)
        pagination = PaginationParams.from_arguments(arguments)
        from .core.utils import paginate_dict_list

        return {"model": model_name, "fields": paginate_dict_list(items, pagination, ["name", "type", "string"]).to_dict()}
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
    elif analysis_type == "inheritance":
        # alias to model_query inheritance
        return await _handle_inheritance_chain(env, arguments)
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
                    "properties": {"addon_name": {"type": "string", "description": "Name of the addon to get dependencies for"}},
                    "required": ["addon_name"],
                }
            ),
        ),
        Tool(
            name="search_code",
            description="Regex search in addons (fs)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern",
                        },
                        "file_type": {"type": "string", "description": "File extension filter"},
                        "roots": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of container directories to search; defaults to ODOO_ADDONS_PATH",
                        },
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
                    "properties": {"module_name": {"type": "string", "description": "Name of the module to analyze"}},
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
                    "properties": {
                        "method_name": {"type": "string", "description": "Name of the method to find"},
                        "mode": {
                            "type": "string",
                            "description": "Execution mode",
                            "enum": ["auto", "fs", "registry"],
                        },
                    },
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
                            "description": "Type of decorator to search for",
                            "enum": ["depends", "constrains", "onchange", "create_multi"],
                        },
                        "mode": {
                            "type": "string",
                            "description": "Execution mode",
                            "enum": ["auto", "fs", "registry"],
                        },
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
                "properties": {"code": {"type": "string", "description": "Python code to execute in Odoo environment"}},
                "required": ["code"],
            },
        ),
        Tool(
            name="permission_checker",
            description="Check permissions",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "Username to check permissions for"},
                    "model": {"type": "string", "description": "Model name to check permissions on"},
                    "operation": {
                        "type": "string",
                        "description": "Operation to check permission for",
                        "enum": ["read", "write", "create", "unlink"],
                    },
                    "record_id": {"type": "integer", "description": "Optional record ID to check specific record permissions"},
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
            description="Models: search|info|relationships|inheritance|view_usage (alias: list→search)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Type of query operation to perform",
                            "enum": ["info", "search", "relationships", "inheritance", "view_usage", "list"],
                        },
                        "model_name": {"type": "string", "description": "Name of the model to query"},
                        "pattern": {"type": "string", "description": "Search pattern for model search"},
                        "mode": {"type": "string", "description": "Execution mode", "enum": ["auto", "fs", "registry"]},
                    },
                    "required": ["operation"],
                }
            ),
        ),
        Tool(
            name="field_query",
            description="Fields: usages|analyze_values|resolve_dynamic|dependencies|search_properties|search_type (alias: list→fields of model)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Type of field query operation to perform",
                            "enum": [
                                "usages",
                                "analyze_values",
                                "resolve_dynamic",
                                "dependencies",
                                "search_properties",
                                "search_type",
                                "list",
                            ],
                        },
                        "model": {"type": "string", "description": "Model name (deprecated, use model_name)"},
                        "model_name": {"type": "string", "description": "Name of the model containing the field"},
                        "field": {"type": "string", "description": "Field name (deprecated, use field_name)"},
                        "field_name": {"type": "string", "description": "Name of the field to query"},
                        "property": {"type": "string", "description": "Field property to search for"},
                        "field_type": {"type": "string", "description": "Type of field to search for"},
                        "domain": {"type": "array", "description": "Domain filter for field search"},
                        "sample_size": {"type": "integer", "description": "Number of sample values to analyze"},
                        "mode": {"type": "string", "description": "Execution mode", "enum": ["auto", "fs", "registry", "db"]},
                    },
                    "required": ["operation"],
                }
            ),
        ),
        Tool(
            name="analysis_query",
            description="Analysis: performance|patterns|workflow (alias: inheritance→model_query)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "analysis_type": {
                            "type": "string",
                            "description": "Type of analysis to perform",
                            "enum": ["performance", "patterns", "workflow", "inheritance"],
                        },
                        "model_name": {"type": "string", "description": "Name of the model to analyze"},
                        "pattern_type": {"type": "string", "description": "Type of pattern to analyze"},
                        "mode": {"type": "string", "description": "Execution mode", "enum": ["auto", "fs", "registry"]},
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

    # noinspection PyBroadException
    try:
        env = await odoo_env_manager.get_environment()

        try:
            result = await handler(env, arguments)
            # Enhance registry-related failures into a structured, actionable contract
            result = _enhance_registry_failure(env, name, result)
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
