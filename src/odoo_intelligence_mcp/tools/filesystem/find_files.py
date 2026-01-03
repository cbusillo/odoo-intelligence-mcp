from typing import Any

from ...core.env import load_env_config
from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...utils.docker_utils import DockerClientManager
from ..addon.get_addon_paths import get_addon_paths_from_container


async def find_files(pattern: str, file_type: str | None = None, pagination: PaginationParams | None = None) -> dict[str, Any]:
    """
    Find files by name pattern in Odoo addon directories.

    Args:
        pattern: File name pattern (supports wildcards like *.py, test_*.xml, *invoice*)
        file_type: Optional file extension filter (e.g., 'py', 'xml', 'js')
        pagination: Pagination parameters

    Returns:
        Dict with list of matching file paths
    """
    if pagination is None:
        pagination = PaginationParams()

    docker_manager = DockerClientManager()
    config = load_env_config()
    container_result = docker_manager.get_container(config.web_container)
    if not container_result.get("success"):
        return {"success": False, "error": f"Container error: {container_result.get('error', 'Unknown error')}"}

    addon_paths = await get_addon_paths_from_container(config.web_container)
    results = []

    # Add file extension to pattern if file_type is specified
    if file_type and not pattern.endswith(f".{file_type}"):
        pattern = pattern.replace("*", f"*.{file_type}") if "*" in pattern else f"*{pattern}*.{file_type}"

    for addon_path in addon_paths:
        # Use find command to search for files
        find_cmd = ["find", addon_path, "-type", "f", "-name", pattern]
        exec_result = docker_manager.exec_run(config.web_container, find_cmd)

        if exec_result.get("success") and exec_result.get("exit_code") == 0 and exec_result.get("stdout"):
            file_paths = exec_result.get("stdout", "").strip().split("\n")
            for file_path in file_paths:
                if file_path:  # Skip empty lines
                    # Get relative path from addon base
                    relative_path = file_path.replace(addon_path + "/", "")
                    module_name = relative_path.split("/")[0] if "/" in relative_path else ""

                    results.append(
                        {
                            "path": file_path,
                            "relative_path": relative_path,
                            "module": module_name,
                            "addon_base": addon_path,
                            "filename": file_path.split("/")[-1],
                        }
                    )

    # Sort by filename for consistency
    results.sort(key=lambda x: x["filename"])

    # Apply pagination
    paginated_results = paginate_dict_list(results, pagination, ["path", "filename", "module"])

    response = {"success": True, "pattern": pattern, "file_type": file_type, "results": paginated_results.to_dict()}

    # Validate response size
    try:
        validate_response_size(response)
    except Exception as e:
        return {
            "success": False,
            "error": f"Response too large: {e!s}",
            "total_results": len(results),
            "suggestion": "Use pagination parameters (page, page_size) to retrieve results in smaller chunks",
        }

    return response
