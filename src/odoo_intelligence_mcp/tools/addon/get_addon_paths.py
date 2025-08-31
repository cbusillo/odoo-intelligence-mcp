from ...core.env import load_env_config


async def get_addon_paths_from_container() -> list[str]:
    config = load_env_config()

    # Get paths from config which match container's ODOO_ADDONS_PATH
    addon_paths = config.addons_path
    # Convert to list and return
    return [p.strip() for p in addon_paths.split(",")]
