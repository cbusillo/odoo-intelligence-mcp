import ast
from pathlib import Path
from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from .get_addon_paths import get_addon_paths_from_container, map_container_path_to_host


async def get_addon_dependencies(addon_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    # Get addon paths from the container
    container_paths = await get_addon_paths_from_container()

    addon_paths = []
    for container_path in container_paths:
        # Try host mapping first
        host_base = map_container_path_to_host(container_path)
        if host_base:
            addon_paths.append(host_base)
        else:
            # Fallback to container path
            addon_paths.append(Path(container_path))

    manifest_data = None
    addon_path = None

    # Find the addon and read its manifest
    for base_path in addon_paths:
        potential_manifest = base_path / addon_name / "__manifest__.py"
        if potential_manifest.exists():
            addon_path = base_path / addon_name
            try:
                with open(potential_manifest) as manifest_file:
                    manifest_content = manifest_file.read()
                    manifest_data = ast.literal_eval(manifest_content)
                break
            except Exception as e:
                return {"error": f"Failed to parse manifest for {addon_name}: {e!s}"}

    if not manifest_data:
        return {"error": f"Addon {addon_name} not found in any addon path"}

    # Extract relevant manifest information
    result = {
        "addon": addon_name,
        "path": str(addon_path),
        "depends": manifest_data.get("depends", []),
        "auto_install": manifest_data.get("auto_install", False),
        "application": manifest_data.get("application", False),
        "installable": manifest_data.get("installable", True),
        "version": manifest_data.get("version", ""),
        "category": manifest_data.get("category", ""),
        "summary": manifest_data.get("summary", ""),
        "description": manifest_data.get("description", ""),
        "author": manifest_data.get("author", ""),
        "website": manifest_data.get("website", ""),
        "license": manifest_data.get("license", "LGPL-3"),
        "external_dependencies": manifest_data.get("external_dependencies", {}),
        "data": manifest_data.get("data", []),
        "demo": manifest_data.get("demo", []),
        "qweb": manifest_data.get("qweb", []),
        "depends_on_this": [],  # Will be populated below
    }

    # Find which addons depend on this one
    addons_depending_on_this = []

    for base_path in addon_paths:
        if not base_path.exists():
            continue

        for potential_addon in base_path.iterdir():
            if not potential_addon.is_dir():
                continue

            if potential_addon.name == addon_name:
                continue

            other_manifest = potential_addon / "__manifest__.py"
            if other_manifest.exists():
                try:
                    with open(other_manifest) as other_file:
                        other_data = ast.literal_eval(other_file.read())
                        if addon_name in other_data.get("depends", []):
                            addons_depending_on_this.append(
                                {
                                    "name": potential_addon.name,
                                    "path": str(potential_addon),
                                    "auto_install": other_data.get("auto_install", False),
                                    "application": other_data.get("application", False),
                                }
                            )
                except (OSError, SyntaxError, ValueError):
                    # Skip addons with unparseable manifests
                    continue

    # Apply pagination to depends_on_this list
    paginated_depends = paginate_dict_list(addons_depending_on_this, pagination, ["name", "path"])
    result["depends_on_this"] = paginated_depends.to_dict()

    # Calculate dependency statistics (use original count, not paginated)
    result["statistics"] = {
        "direct_dependencies": len(result["depends"]),
        "addons_depending_on_this": len(addons_depending_on_this),
        "total_data_files": len(result["data"]),
        "has_external_dependencies": bool(result["external_dependencies"]),
        "is_auto_install": result["auto_install"],
        "is_application": result["application"],
    }

    return validate_response_size(result)
