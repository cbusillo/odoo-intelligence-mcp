from pathlib import Path


async def get_addon_paths_from_container() -> list[str]:
    """Get the actual addon paths from the Odoo container"""
    from ...core.env import load_env_config

    config = load_env_config()

    # Get paths from config which match container's ODOO_ADDONS_PATH
    addon_paths = config.get("addons_path", "/opt/project/addons,/odoo/addons,/volumes/enterprise")
    # Convert to list and return
    return [p.strip() for p in addon_paths.split(",")]


def map_container_path_to_host(container_path: str) -> Path | None:
    """Map a container path to the corresponding host path"""
    # Get project root (7 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent.parent.parent.parent

    mappings = {
        "/volumes/addons": project_root / "addons",
        "/opt/project/addons": project_root / "addons",
        "/volumes/enterprise": project_root / "enterprise",
    }

    for container_prefix, host_path in mappings.items():
        if container_path.startswith(container_prefix):
            # Extract the relative path after the prefix
            relative = container_path[len(container_prefix) :].lstrip("/")
            if relative:
                return host_path / relative
            return host_path

    return None
