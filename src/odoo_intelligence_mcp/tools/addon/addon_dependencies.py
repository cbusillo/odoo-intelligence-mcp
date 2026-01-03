import ast
from typing import Any

from ...core.env import load_env_config
from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...utils.docker_utils import DockerClientManager
from .get_addon_paths import get_addon_paths_from_container


async def _get_addon_paths(container_name: str | None = None) -> list[str]:
    return await get_addon_paths_from_container(container_name)


def _read_manifest_from_container(manifest_path: str) -> dict[str, Any] | None:
    try:
        docker_manager = DockerClientManager()
        config = load_env_config()
        container_result = docker_manager.get_container(config.web_container)
        if not container_result.get("success"):
            return None

        exec_result = docker_manager.exec_run(config.web_container, ["cat", manifest_path])
        if exec_result.get("success") and exec_result.get("exit_code") == 0:
            manifest_content = exec_result.get("stdout", "")
            return ast.literal_eval(manifest_content)
    except (SyntaxError, ValueError):
        return None
    return None


def _find_addon_manifest(addon_name: str, addon_paths: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    for base_path in addon_paths:
        potential_manifest = f"{base_path}/{addon_name}/__manifest__.py"
        manifest_data = _read_manifest_from_container(potential_manifest)
        if manifest_data:
            return manifest_data, f"{base_path}/{addon_name}"
    return None, None


def _extract_manifest_info(addon_name: str, addon_path: str, manifest_data: dict[str, Any]) -> dict[str, Any]:
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


def _find_dependent_addons(addon_name: str, addon_paths: list[str]) -> list[dict[str, Any]]:
    addons_depending_on_this = []

    docker_manager = DockerClientManager()
    config = load_env_config()
    container_result = docker_manager.get_container(config.web_container)
    if not container_result.get("success"):
        return addons_depending_on_this

    for base_path in addon_paths:
        # List directories in base_path
        list_result = docker_manager.exec_run(config.web_container, ["ls", "-d", f"{base_path}/*/"])
        if not list_result.get("success") or list_result.get("exit_code") != 0:
            continue

        addon_dirs = list_result.get("stdout", "").strip().split("\n")

        for addon_dir_raw in addon_dirs:
            addon_dir = addon_dir_raw.rstrip("/")
            potential_addon_name = addon_dir.split("/")[-1]

            if potential_addon_name == addon_name:
                continue

            other_manifest = f"{addon_dir}/__manifest__.py"
            other_data = _read_manifest_from_container(other_manifest)
            if other_data and addon_name in other_data.get("depends", []):
                addons_depending_on_this.append(
                    {
                        "name": potential_addon_name,
                        "path": addon_dir,
                        "auto_install": other_data.get("auto_install", False),
                        "application": other_data.get("application", False),
                    }
                )

    return addons_depending_on_this


async def get_addon_dependencies(addon_name: str, pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()
    config = load_env_config()
    addon_paths = await _get_addon_paths(config.web_container)

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
