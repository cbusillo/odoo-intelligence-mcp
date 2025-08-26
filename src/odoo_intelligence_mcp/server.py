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
from .tools.code.execute_code import odoo_shell
from .tools.code.read_odoo_file import read_odoo_file
from .tools.code.search_code import search_code
from .tools.development import run_tests
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
from .tools.operations import odoo_install_module, odoo_logs, odoo_restart, odoo_status, odoo_update_module
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


async def _handle_test_runner(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    pagination = PaginationParams.from_arguments(arguments)
    return await run_tests(
        get_required(arguments, "module"),
        get_optional_str(arguments, "test_class"),
        get_optional_str(arguments, "test_method"),
        get_optional_str(arguments, "test_tags"),
        pagination,
    )


async def _handle_field_value_analyzer(env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await analyze_field_values(
        env,
        get_required(arguments, "model"),
        get_required(arguments, "field"),
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


async def _handle_odoo_shell(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return odoo_shell(get_required(arguments, "code"), get_optional_int(arguments, "timeout", 30) or 30)


async def _handle_odoo_status(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    verbose = get_optional_bool(arguments, "verbose")
    return await odoo_status(verbose)


async def _handle_odoo_restart(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    services = get_optional_str(arguments, "services")
    return await odoo_restart(**({"services": services} if services else {}))


async def _handle_odoo_install_module(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    return await odoo_install_module(get_required(arguments, "modules"))


async def _handle_odoo_logs(_env: CompatibleEnvironment, arguments: dict[str, object]) -> object:
    kwargs = {}
    container = get_optional_str(arguments, "container")
    if container:
        kwargs["container"] = container
    lines = get_optional_int(arguments, "lines")
    if lines:
        kwargs["lines"] = lines
    return await odoo_logs(**kwargs)


TOOL_HANDLERS = {
    "model_info": _handle_model_info,
    "search_models": _handle_search_models,
    "model_relationships": _handle_model_relationships,
    "field_usages": _handle_field_usages,
    "performance_analysis": _handle_performance_analysis,
    "pattern_analysis": _handle_pattern_analysis,
    "inheritance_chain": _handle_inheritance_chain,
    "addon_dependencies": _handle_addon_dependencies,
    "search_code": _handle_search_code,
    "find_files": _handle_find_files,
    "read_odoo_file": _handle_read_odoo_file,
    "find_method": _handle_find_method,
    "module_structure": _handle_module_structure,
    "view_model_usage": _handle_view_model_usage,
    "resolve_dynamic_fields": _handle_resolve_dynamic_fields,
    "search_field_properties": _handle_search_field_properties,
    "search_field_type": _handle_search_field_type,
    "search_decorators": _handle_search_decorators,
    "field_dependencies": _handle_field_dependencies,
    "workflow_states": _handle_workflow_states,
    "execute_code": _handle_execute_code,
    "test_runner": _handle_test_runner,
    "field_value_analyzer": _handle_field_value_analyzer,
    "permission_checker": _handle_permission_checker,
    "odoo_update_module": _handle_odoo_update_module,
    "odoo_shell": _handle_odoo_shell,
    "odoo_status": _handle_odoo_status,
    "odoo_restart": _handle_odoo_restart,
    "odoo_install_module": _handle_odoo_install_module,
    "odoo_logs": _handle_odoo_logs,
}


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    # noinspection PyDataclass,Annotator
    return [
        Tool(
            name="model_info",
            description="Get comprehensive information about an Odoo model including fields, methods, and inheritance",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the Odoo model (e.g., 'product.template', 'res.partner')",
                    }
                },
                "required": ["model_name"],
            },
        ),
        Tool(
            name="search_models",
            description="Search for Odoo models by name pattern with exact, partial, and description matches",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern to match against model names and descriptions",
                        }
                    },
                    "required": ["pattern"],
                }
            ),
        ),
        Tool(
            name="model_relationships",
            description="Analyze all relationships (M2O, O2M, M2M) for an Odoo model",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model to analyze relationships for",
                        }
                    },
                    "required": ["model_name"],
                }
            ),
        ),
        Tool(
            name="field_usages",
            description="Find where a specific field is used across views, methods, and domains",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model",
                        },
                        "field_name": {
                            "type": "string",
                            "description": "Name of the field to analyze usage for",
                        },
                    },
                    "required": ["model_name", "field_name"],
                }
            ),
        ),
        Tool(
            name="performance_analysis",
            description="Identify potential performance issues like N+1 queries and missing indexes",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model to analyze for performance issues",
                        }
                    },
                    "required": ["model_name"],
                }
            ),
        ),
        Tool(
            name="pattern_analysis",
            description="Analyze common Odoo patterns across the codebase "
            "(computed_fields, related_fields, api_decorators, custom_methods, state_machines)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern_type": {
                            "type": "string",
                            "description": "Type of pattern to analyze. Options: computed_fields, related_fields, "
                            "api_decorators, custom_methods, state_machines, all (default: all)",
                            "enum": [
                                "computed_fields",
                                "related_fields",
                                "api_decorators",
                                "custom_methods",
                                "state_machines",
                                "all",
                            ],
                            "default": "all",
                        }
                    },
                    "required": [],
                }
            ),
        ),
        Tool(
            name="inheritance_chain",
            description="Analyze the complete inheritance chain of a model including MRO, "
            "inherits relationships, and inherited fields",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model to analyze inheritance for",
                        }
                    },
                    "required": ["model_name"],
                }
            ),
        ),
        Tool(
            name="addon_dependencies",
            description="Get addon manifest information and dependencies, including which addons depend on this one",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "addon_name": {
                            "type": "string",
                            "description": "Name of the Odoo addon to analyze dependencies for",
                        }
                    },
                    "required": ["addon_name"],
                }
            ),
        ),
        Tool(
            name="search_code",
            description="Search for regex patterns in code files across addon directories",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regular expression pattern to search for in file contents",
                        },
                        "file_type": {
                            "type": "string",
                            "description": "File extension to search in (e.g., 'py', 'xml', 'js'). Defaults to 'py'",
                            "default": "py",
                        },
                    },
                    "required": ["pattern"],
                }
            ),
        ),
        Tool(
            name="find_files",
            description="Find files by name pattern in Odoo addon directories",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "File name pattern (supports wildcards like *.py, test_*.xml, *invoice*)",
                        },
                        "file_type": {
                            "type": "string",
                            "description": "Optional file extension filter (e.g., 'py', 'xml', 'js')",
                        },
                    },
                    "required": ["pattern"],
                }
            ),
        ),
        Tool(
            name="read_odoo_file",
            description="Read a file from Odoo source (core, enterprise, or custom addons) with flexible options",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Path to file. Examples: 'sale/views/sale_views.xml', "
                            "'/odoo/addons/sale/views/sale_views.xml', 'addons/product_connect/models/motor.py'"
                        ),
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Line number to start reading from (1-based)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Line number to stop reading at (inclusive)",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for and show context around",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines to show before/after pattern matches (default 5)",
                        "default": 5,
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="module_structure",
            description="Analyze module directory structure including models, views, controllers, "
            "wizards, reports, and static files",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "module_name": {
                            "type": "string",
                            "description": "Name of the Odoo module to analyze structure for",
                        }
                    },
                    "required": ["module_name"],
                }
            ),
        ),
        Tool(
            name="find_method",
            description="Find all models that implement a specific method",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "method_name": {
                            "type": "string",
                            "description": "Name of the method to search for across all models",
                        }
                    },
                    "required": ["method_name"],
                }
            ),
        ),
        Tool(
            name="search_decorators",
            description="Find methods by decorator type (depends, constrains, onchange, model_create_multi)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "decorator": {
                            "type": "string",
                            "description": "Decorator type to search for",
                            "enum": ["depends", "constrains", "onchange", "model_create_multi"],
                        }
                    },
                    "required": ["decorator"],
                }
            ),
        ),
        Tool(
            name="view_model_usage",
            description="Show which views use a model, field coverage statistics, buttons, actions, and unexposed fields",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model to analyze view usage for",
                        }
                    },
                    "required": ["model_name"],
                }
            ),
        ),
        Tool(
            name="workflow_states",
            description="Analyze state fields, transitions, button actions, and automated state changes in a model",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model to analyze workflow states for",
                        }
                    },
                    "required": ["model_name"],
                }
            ),
        ),
        Tool(
            name="execute_code",
            description="Execute arbitrary Python code in the Odoo environment context for testing and exploration",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. Has access to 'env' variable.",
                    }
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="test_runner",
            description="Run specific Odoo tests with granular control over module, class, and method selection",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "module": {
                            "type": "string",
                            "description": "Module name to test (e.g., 'product_connect')",
                        },
                        "test_class": {
                            "type": "string",
                            "description": "Specific test class to run (optional)",
                        },
                        "test_method": {
                            "type": "string",
                            "description": "Specific test method to run (optional)",
                        },
                        "test_tags": {
                            "type": "string",
                            "description": "Comma-separated test tags to filter by (optional)",
                        },
                    },
                    "required": ["module"],
                }
            ),
        ),
        Tool(
            name="field_value_analyzer",
            description="Analyze actual field values in the database to understand data patterns, distributions, and quality",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., 'product.template')",
                    },
                    "field": {
                        "type": "string",
                        "description": "Field name to analyze",
                    },
                    "domain": {
                        "type": "array",
                        "description": "Optional domain to filter records (default: [])",
                        "items": {"type": "array"},
                    },
                    "sample_size": {
                        "type": "integer",
                        "description": "Maximum number of records to analyze (default: 1000)",
                    },
                },
                "required": ["model", "field"],
            },
        ),
        Tool(
            name="permission_checker",
            description="Debug access rights and record rules to understand why a user can or cannot access specific records",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "string",
                        "description": "User login or ID to check permissions for",
                    },
                    "model": {
                        "type": "string",
                        "description": "Model name to check access on",
                    },
                    "operation": {
                        "type": "string",
                        "description": "Operation to check",
                        "enum": ["read", "write", "create", "unlink"],
                    },
                    "record_id": {
                        "type": "integer",
                        "description": "Specific record ID to check (optional)",
                    },
                },
                "required": ["user", "model", "operation"],
            },
        ),
        Tool(
            name="resolve_dynamic_fields",
            description="Analyze computed and related fields with cross-model dependencies and runtime field resolution patterns",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model to analyze dynamic fields for",
                        }
                    },
                    "required": ["model_name"],
                }
            ),
        ),
        Tool(
            name="field_dependencies",
            description="Show dependency graph for a specific field - what it depends on and what depends on it",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "model_name": {
                            "type": "string",
                            "description": "Name of the Odoo model",
                        },
                        "field_name": {
                            "type": "string",
                            "description": "Name of the field to analyze dependencies for",
                        },
                    },
                    "required": ["model_name", "field_name"],
                }
            ),
        ),
        Tool(
            name="search_field_properties",
            description="Search for fields by specific properties (computed, related, stored, required, readonly)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "property": {
                            "type": "string",
                            "description": "Field property to search for. Options: computed, related, stored, required, readonly",
                            "enum": ["computed", "related", "stored", "required", "readonly"],
                        }
                    },
                    "required": ["property"],
                }
            ),
        ),
        Tool(
            name="search_field_type",
            description="Find all models with fields of a specific type (e.g., many2one, char, selection, date, boolean)",
            inputSchema=add_pagination_to_schema(
                {
                    "type": "object",
                    "properties": {
                        "field_type": {
                            "type": "string",
                            "description": "Field type to search for",
                            "enum": [
                                "many2one",
                                "one2many",
                                "many2many",
                                "char",
                                "text",
                                "integer",
                                "float",
                                "boolean",
                                "date",
                                "datetime",
                                "binary",
                                "selection",
                                "json",
                            ],
                        }
                    },
                    "required": ["field_type"],
                }
            ),
        ),
        Tool(
            name="odoo_update_module",
            description="Update Odoo module(s) using the script-runner container",
            inputSchema={
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "string",
                        "description": "Module name or comma-separated list of modules to update",
                    },
                    "force_install": {
                        "type": "boolean",
                        "description": "Force install if module is not installed (default: false)",
                        "default": False,
                    },
                },
                "required": ["modules"],
            },
        ),
        Tool(
            name="odoo_shell",
            description="Execute Python code in Odoo shell environment",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute in Odoo shell",
                    },
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)", "default": 30},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="odoo_status",
            description="Check Odoo container status and health",
            inputSchema={
                "type": "object",
                "properties": {
                    "verbose": {
                        "type": "boolean",
                        "description": "Show detailed container information (optional)",
                        "default": False,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="odoo_restart",
            description="Restart Odoo containers (useful after code changes)",
            inputSchema={
                "type": "object",
                "properties": {
                    "services": {
                        "type": "string",
                        "description": "Specific services to restart (default: web-1,shell-1,script-runner-1)",
                        "default": "web-1,shell-1,script-runner-1",
                    }
                },
            },
        ),
        Tool(
            name="odoo_install_module",
            description="Install new Odoo module(s)",
            inputSchema={
                "type": "object",
                "properties": {
                    "modules": {
                        "type": "string",
                        "description": "Module name or comma-separated list of modules to install",
                    }
                },
                "required": ["modules"],
            },
        ),
        Tool(
            name="odoo_logs",
            description="Get recent Odoo container logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "container": {
                        "type": "string",
                        "description": "Container name (defaults to web container from env)",
                    },
                    "lines": {"type": "integer", "description": "Number of lines to retrieve (default: 100)", "default": 100},
                },
            },
        ),
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, object] | None) -> list[TextContent]:
    if not arguments:
        # noinspection Annotator
        return [TextContent(type="text", text=json.dumps({"error": "No arguments provided"}))]

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
