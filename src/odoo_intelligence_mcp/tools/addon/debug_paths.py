from pathlib import Path
from typing import Any

from .get_addon_paths import get_addon_paths_from_container, map_container_path_to_host


async def debug_addon_paths() -> dict[str, Any]:
    """Debug tool to check addon paths and mappings"""
    from ...core.env import load_env_config

    config = load_env_config()
    container_paths = await get_addon_paths_from_container()

    result: dict[str, Any] = {"config": config, "container_paths": container_paths, "mappings": {}, "exists_check": {}}

    for container_path in container_paths:
        host_path = map_container_path_to_host(container_path)
        result["mappings"][container_path] = str(host_path) if host_path else None

        if host_path:
            result["exists_check"][str(host_path)] = {
                "exists": host_path.exists(),
                "is_dir": host_path.is_dir() if host_path.exists() else False,
                "contents": [str(p) for p in list(host_path.iterdir())[:5]] if host_path.exists() and host_path.is_dir() else [],
            }

    # Also check project root
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    result["project_root"] = str(project_root)
    result["project_addons"] = str(project_root / "addons")
    result["project_addons_exists"] = (project_root / "addons").exists()

    return result
