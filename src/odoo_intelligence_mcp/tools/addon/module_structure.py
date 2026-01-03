import json
from typing import Any

from ...core.env import load_env_config
from ...core.utils import PaginationParams, paginate_dict_list
from ...utils.docker_utils import DockerClientManager
from .get_addon_paths import get_addon_paths_from_container


async def get_module_structure(module_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    # Get Docker client and container
    docker_manager = DockerClientManager()
    config = load_env_config()
    container_name = config.script_runner_container

    container_result = docker_manager.get_container(container_name)
    if not container_result.get("success"):
        return {"success": False, "error": f"Container error: {container_result.get('error', 'Unknown error')}"}

    # Get addon paths from the container
    container_paths = await get_addon_paths_from_container(container_name)

    # Check if module exists in any addon path
    check_cmd = [
        "sh",
        "-c",
        f"for path in {' '.join(container_paths)}; do "
        f'  if [ -d "$path/{module_name}" ]; then '
        f'    echo "$path/{module_name}"; '
        "    exit 0; "
        "  fi; "
        "done; "
        "exit 1",
    ]

    exec_result = docker_manager.exec_run(container_name, check_cmd)
    if not exec_result.get("success") or exec_result.get("exit_code") != 0:
        return {"error": f"Module {module_name} not found in addon paths: {container_paths}"}

    module_path = exec_result.get("stdout", "").strip()

    # Analyze module structure in container
    analyze_cmd = [
        "python3",
        "-c",
        f"""
import os
import json
import ast
from pathlib import Path

module_path = Path('{module_path}')
structure = {{
    "path": str(module_path),
    "models": [],
    "views": [],
    "controllers": [],
    "wizards": [],
    "reports": [],
    "static": {{"js": [], "css": [], "xml": []}},
    "manifest": {{}},
}}

# Read manifest file
manifest_path = module_path / "__manifest__.py"
if manifest_path.exists():
    try:
        with manifest_path.open() as manifest_file:
            content = manifest_file.read()
            structure["manifest"] = ast.literal_eval(content)
    except Exception:
        pass

# Scan Python files
for python_file in module_path.rglob("*.py"):
    relative_path = python_file.relative_to(module_path)
    category = relative_path.parts[0] if relative_path.parts else ""
    
    if category == "models":
        structure["models"].append(str(relative_path))
    elif category == "controllers":
        structure["controllers"].append(str(relative_path))
    elif category in ["wizard", "wizards"]:
        structure["wizards"].append(str(relative_path))
    elif category in ["report", "reports"]:
        structure["reports"].append(str(relative_path))

# Scan XML files
for xml_file in module_path.rglob("*.xml"):
    relative_path = xml_file.relative_to(module_path)
    if relative_path.parts and relative_path.parts[0] in ["views", "data", "security"]:
        structure["views"].append(str(relative_path))

# Scan static files
static_path = module_path / "static" / "src"
if static_path.exists():
    for js_file in static_path.rglob("*.js"):
        structure["static"]["js"].append(str(js_file.relative_to(static_path)))
    for css_file in static_path.rglob("*.css"):
        structure["static"]["css"].append(str(css_file.relative_to(static_path)))
    for xml_file in static_path.rglob("*.xml"):
        structure["static"]["xml"].append(str(xml_file.relative_to(static_path)))

# Output as JSON
print(json.dumps(structure))
""",
    ]

    exec_result = docker_manager.exec_run(container_name, analyze_cmd)
    if not exec_result.get("success") or exec_result.get("exit_code") != 0:
        error_msg = exec_result.get("stdout", "") or exec_result.get("stderr", "") or "Failed to analyze module structure"
        return {"error": f"Failed to analyze module {module_name}: {error_msg}"}

    try:
        structure = json.loads(exec_result.get("stdout", ""))
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse module structure: {e}"}

    # Combine all files for pagination
    all_files = []

    # Add models
    all_files.extend([{"path": file_path, "category": "models", "type": "python"} for file_path in structure.get("models", [])])

    # Add views
    all_files.extend([{"path": file_path, "category": "views", "type": "xml"} for file_path in structure.get("views", [])])

    # Add controllers
    all_files.extend(
        [{"path": file_path, "category": "controllers", "type": "python"} for file_path in structure.get("controllers", [])]
    )

    # Add wizards
    all_files.extend([{"path": file_path, "category": "wizards", "type": "python"} for file_path in structure.get("wizards", [])])

    # Add reports
    all_files.extend([{"path": file_path, "category": "reports", "type": "python"} for file_path in structure.get("reports", [])])

    # Add static files
    static = structure.get("static", {})
    all_files.extend([{"path": file_path, "category": "static/js", "type": "javascript"} for file_path in static.get("js", [])])
    all_files.extend([{"path": file_path, "category": "static/css", "type": "css"} for file_path in static.get("css", [])])
    all_files.extend([{"path": file_path, "category": "static/xml", "type": "xml"} for file_path in static.get("xml", [])])

    # Apply pagination to files
    paginated_files = paginate_dict_list(all_files, pagination, search_fields=["path", "category"])

    # Build result
    result = {
        "module": module_name,
        "path": structure.get("path", ""),
        "manifest": structure.get("manifest", {}),
        "files": paginated_files.to_dict(),
        "summary": {
            "models_count": len(structure.get("models", [])),
            "views_count": len(structure.get("views", [])),
            "controllers_count": len(structure.get("controllers", [])),
            "wizards_count": len(structure.get("wizards", [])),
            "reports_count": len(structure.get("reports", [])),
            "js_count": len(static.get("js", [])),
            "css_count": len(static.get("css", [])),
        },
    }

    return result
