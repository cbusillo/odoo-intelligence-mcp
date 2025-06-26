import ast
from pathlib import Path
from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from .get_addon_paths import get_addon_paths_from_container, map_container_path_to_host


async def _get_addon_paths() -> list[Path]:
    container_paths = await get_addon_paths_from_container()
    addon_paths = []
    for container_path in container_paths:
        host_base = map_container_path_to_host(container_path)
        if host_base:
            addon_paths.append(host_base)
        else:
            addon_paths.append(Path(container_path))
    return addon_paths


def _read_manifest(manifest_path: Path) -> dict[str, Any] | None:
    try:
        with manifest_path.open() as manifest_file:
            manifest_content = manifest_file.read()
            return ast.literal_eval(manifest_content)
    except (OSError, SyntaxError, ValueError):
        return None


def _find_addon_manifest(addon_name: str, addon_paths: list[Path]) -> tuple[dict[str, Any] | None, Path | None]:
    for base_path in addon_paths:
        potential_manifest = base_path / addon_name / "__manifest__.py"
        if potential_manifest.exists():
            manifest_data = _read_manifest(potential_manifest)
            if manifest_data:
                return manifest_data, base_path / addon_name
    return None, None


def _extract_manifest_info(addon_name: str, addon_path: Path, manifest_data: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "depends_on_this": [],
    }


def _find_dependent_addons(addon_name: str, addon_paths: list[Path]) -> list[dict[str, Any]]:
    addons_depending_on_this = []

    for base_path in addon_paths:
        if not base_path.exists():
            continue

        for potential_addon in base_path.iterdir():
            if not potential_addon.is_dir() or potential_addon.name == addon_name:
                continue

            other_manifest = potential_addon / "__manifest__.py"
            if other_manifest.exists():
                other_data = _read_manifest(other_manifest)
                if other_data and addon_name in other_data.get("depends", []):
                    addons_depending_on_this.append({
                        "name": potential_addon.name,
                        "path": str(potential_addon),
                        "auto_install": other_data.get("auto_install", False),
                        "application": other_data.get("application", False),
                    })

    return addons_depending_on_this


async def get_addon_dependencies(addon_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    addon_paths = await _get_addon_paths()

    manifest_data, addon_path = _find_addon_manifest(addon_name, addon_paths)

    if not manifest_data:
        return {"error": f"Addon {addon_name} not found in any addon path"}

    result = _extract_manifest_info(addon_name, addon_path, manifest_data)

    addons_depending_on_this = _find_dependent_addons(addon_name, addon_paths)

    # Apply pagination to depends_on_this list
    paginated_depends = paginate_dict_list(addons_depending_on_this, pagination, ["name", "path"])
    result["depends_on_this"] = paginated_depends.to_dict()

    # Calculate dependency statistics
    result["statistics"] = {
        "direct_dependencies": len(result["depends"]),
        "addons_depending_on_this": len(addons_depending_on_this),
        "total_data_files": len(result["data"]),
        "has_external_dependencies": bool(result["external_dependencies"]),
        "is_auto_install": result["auto_install"],
        "is_application": result["application"],
    }

    return validate_response_size(result)
