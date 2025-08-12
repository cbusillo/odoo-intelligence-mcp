"""Read Odoo source files from core, enterprise, or custom addons."""

import re
from pathlib import Path
from typing import Any

from ...utils.docker_utils import DockerClientManager


async def read_odoo_file(
    file_path: str, start_line: int | None = None, end_line: int | None = None, pattern: str | None = None, context_lines: int = 5
) -> dict[str, Any]:
    """
    Read a file from Odoo source (core, enterprise, or custom addons).

    Args:
        file_path: Path to file (can be relative to addon or absolute container path)
                  Examples:
                  - "sale/views/sale_views.xml" (finds in any addon path)
                  - "/odoo/addons/sale/views/sale_views.xml" (absolute)
                  - "addons/product_connect/models/motor.py" (custom)
        start_line: Optional line number to start reading from (1-based)
        end_line: Optional line number to stop reading at (inclusive)
        pattern: Optional pattern to search for and show context around
        context_lines: Number of lines to show before/after pattern matches (default 5)

    Returns:
        Dict with content or error message
    """
    path = Path(file_path)

    def process_content(content: str, source_path: str) -> dict[str, Any]:
        """Process file content based on parameters."""
        lines = content.split("\n")
        total_lines = len(lines)

        # If pattern provided, find matches and show context
        if pattern:
            matches = []
            try:
                regex = re.compile(pattern, re.IGNORECASE)
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        start = max(1, i - context_lines)
                        end = min(total_lines, i + context_lines)
                        context = "\n".join(f"{j:4}: {lines[j - 1]}" for j in range(start, end + 1))
                        matches.append({"line": i, "match": line.strip(), "context": context})
            except re.error as e:
                return {"success": False, "error": f"Invalid regex pattern: {e}"}

            if matches:
                return {
                    "success": True,
                    "path": source_path,
                    "pattern": pattern,
                    "matches": matches[:10],  # Limit to 10 matches
                    "total_matches": len(matches),
                }
            else:
                return {
                    "success": True,
                    "path": source_path,
                    "pattern": pattern,
                    "matches": [],
                    "message": "No matches found",
                }

        # Line range extraction
        if start_line or end_line:
            start = (start_line or 1) - 1  # Convert to 0-based
            end = end_line or total_lines

            if start < 0 or start >= total_lines:
                return {"success": False, "error": f"start_line {start_line} out of range (file has {total_lines} lines)"}
            end = min(end, total_lines)

            selected_lines = lines[start:end]
            # Add line numbers
            content_with_numbers = "\n".join(f"{i + start + 1:4}: {line}" for i, line in enumerate(selected_lines))

            return {
                "success": True,
                "path": source_path,
                "content": content_with_numbers,
                "lines": f"{start + 1}-{end}",
                "total_lines": total_lines,
            }

        # Full file (with line numbers if not too large)
        if total_lines <= 500:
            content_with_numbers = "\n".join(f"{i:4}: {line}" for i, line in enumerate(lines, 1))
        else:
            # For large files, just return raw content
            content_with_numbers = content

        return {"success": True, "path": source_path, "content": content_with_numbers, "total_lines": total_lines}

    docker_manager = DockerClientManager()
    container_name = "odoo-opw-web-1"

    container_result = docker_manager.get_container(container_name)
    if isinstance(container_result, dict):  # Error
        return {"success": False, "error": f"Container error: {container_result.get('error', 'Unknown error')}"}

    # Try as absolute path first
    if path.is_absolute():
        try:
            exec_result = container_result.exec_run(["cat", str(path)], stdout=True, stderr=True, demux=True)
            stdout = exec_result.output[0].decode("utf-8") if exec_result.output[0] else ""
            stderr = exec_result.output[1].decode("utf-8") if exec_result.output[1] else ""

            if exec_result.exit_code == 0:
                return process_content(stdout, str(path))
            else:
                return {"success": False, "error": f"File not found or not readable: {stderr or path}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to read via docker: {e}"}

    # For relative paths, search in addon paths
    from ..addon.get_addon_paths import get_addon_paths_from_container

    addon_paths = await get_addon_paths_from_container()

    # Build list of paths to try
    paths_to_try = []
    path_str = str(path)

    # If path starts with "addons/" or "enterprise/", try mapping to actual addon paths
    if path_str.startswith(("addons/", "enterprise/")):
        # Extract the first part (e.g., "addons" from "addons/product_connect/...")
        parts = path_str.split("/", 1)
        if len(parts) == 2:
            addon_dir, rest = parts
            # Find matching addon paths
            for addon_base in addon_paths:
                if addon_base.endswith(f"/{addon_dir}") or Path(addon_base).name == addon_dir:
                    paths_to_try.append(f"{addon_base}/{rest}")

    # Also try appending to all addon paths (for module-relative paths)
    for addon_base in addon_paths:
        paths_to_try.append(f"{addon_base}/{path_str}")

    # Try each potential path
    for potential_path in paths_to_try:
        try:
            # First check if file exists
            test_result = container_result.exec_run(["test", "-f", potential_path], stdout=False, stderr=False)
            if test_result.exit_code == 0:
                # File exists, read it
                exec_result = container_result.exec_run(["cat", potential_path], stdout=True, stderr=True, demux=True)
                stdout = exec_result.output[0].decode("utf-8") if exec_result.output[0] else ""

                if exec_result.exit_code == 0:
                    return process_content(stdout, potential_path)
        except:
            continue

    return {
        "success": False,
        "error": f"File not found: {file_path}",
        "searched_paths": paths_to_try[:5] + (["..."] if len(paths_to_try) > 5 else []),
    }
