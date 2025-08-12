import ast
from pathlib import Path
from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list
from .get_addon_paths import get_addon_paths_from_container


async def get_module_structure(module_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    module_path = Path(module_name)
    if not module_path.exists():
        # Get addon paths from the container
        container_paths = await get_addon_paths_from_container()

        # Try to find the module in container paths
        # Note: This tool currently requires the module to exist on the host filesystem
        # TODO(team): Update to read module structure from container
        for container_path in container_paths:
            # For now, just try the container path directly on host
            test_path = Path(container_path) / module_name
            if test_path.exists():
                module_path = test_path
                break
        else:
            return {"error": f"Module {module_name} not found in addon paths: {container_paths}"}

    structure = {
        "path": str(module_path),
        "models": [],
        "views": [],
        "controllers": [],
        "wizards": [],
        "reports": [],
        "static": {"js": [], "css": [], "xml": []},
        "manifest": {},
    }

    manifest_path = module_path / "__manifest__.py"
    if manifest_path.exists():
        try:
            with manifest_path.open() as manifest_file:
                content = manifest_file.read()
                structure["manifest"] = ast.literal_eval(content)
        except (FileNotFoundError, SyntaxError, ValueError):
            pass

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

    for xml_file in module_path.rglob("*.xml"):
        relative_path = xml_file.relative_to(module_path)
        if relative_path.parts[0] in ["views", "data", "security"]:
            structure["views"].append(str(relative_path))

    static_path = module_path / "static" / "src"
    if static_path.exists():
        for js_file in static_path.rglob("*.js"):
            structure["static"]["js"].append(str(js_file.relative_to(static_path)))
        for css_file in static_path.rglob("*.css"):
            structure["static"]["css"].append(str(css_file.relative_to(static_path)))
        for xml_file in static_path.rglob("*.xml"):
            structure["static"]["xml"].append(str(xml_file.relative_to(static_path)))

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
    all_files.extend(
        [
            {"path": f"static/src/{file_path}", "category": "static", "type": "javascript"}
            for file_path in structure.get("static", {}).get("js", [])
        ]
    )
    all_files.extend(
        [
            {"path": f"static/src/{file_path}", "category": "static", "type": "css"}
            for file_path in structure.get("static", {}).get("css", [])
        ]
    )
    all_files.extend(
        [
            {"path": f"static/src/{file_path}", "category": "static", "type": "xml"}
            for file_path in structure.get("static", {}).get("xml", [])
        ]
    )

    # Apply pagination
    paginated_files = paginate_dict_list(all_files, pagination, ["path", "category", "type"])

    # Return summary with paginated files
    return {
        "module": module_name,
        "path": structure["path"],
        "manifest": structure["manifest"],
        "summary": {
            "models_count": len(structure["models"]),
            "views_count": len(structure["views"]),
            "controllers_count": len(structure["controllers"]),
            "wizards_count": len(structure["wizards"]),
            "reports_count": len(structure["reports"]),
            "static_js_count": len(structure["static"]["js"]),
            "static_css_count": len(structure["static"]["css"]),
            "static_xml_count": len(structure["static"]["xml"]),
            "total_files": len(all_files),
        },
        "files": paginated_files.to_dict(),
    }
