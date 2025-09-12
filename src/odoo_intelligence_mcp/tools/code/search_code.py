import re
from typing import Any

from ...core.env import load_env_config
from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ...utils.docker_utils import DockerClientManager


async def search_code(
    pattern: str,
    file_type: str = "py",
    pagination: PaginationParams | None = None,
    roots: list[str] | None = None,
) -> dict[str, Any]:
    """
    FS-first code search that does NOT boot Odoo.

    - Scans the filesystem inside the web container across provided roots or
      ODOO_ADDONS_PATH directories.
    - Returns up to 100 matches with file, line, match, and a short context.
    """

    if pagination is None:
        pagination = PaginationParams()

    try:
        re.compile(pattern)
    except re.error as e:
        return {"success": False, "error": f"Invalid regex pattern: {e!s}", "error_type": "RegexError"}

    # Pick search roots
    config = load_env_config()
    if roots:
        search_roots = [p for p in roots if isinstance(p, str) and p.strip()]
    else:
        search_roots = [p.strip() for p in config.addons_path.split(",") if p.strip()]

    if not search_roots:
        return {
            "success": False,
            "error": "No search roots provided and ODOO_ADDONS_PATH is empty",
            "error_type": "NoSearchRoots",
        }

    # Build a container-side Python script to perform the search
    # We prefer Python over grep to keep consistent context formatting and avoid shell escaping issues.

    # noinspection SpellCheckingInspection
    py = f"""
import os, re, json
pattern = re.compile({pattern!r})
file_ext = {file_type!r}.lstrip('.')
roots = {search_roots!r}
results = []

def scan_file(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                if pattern.search(line):
                    # Build a short inline context (trimmed line)
                    results.append({{
                        'file': path,
                        'line': i,
                        'match': line.strip()[:400]
                    }})
                    if len(results) >= 100:
                        return True
    except Exception:
        pass
    return False

for root in roots:
    if not os.path.exists(root):
        continue
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if file_ext and not fn.lower().endswith('.' + file_ext.lower()):
                continue
            if scan_file(os.path.join(dirpath, fn)):
                break
        if len(results) >= 100:
            break
    if len(results) >= 100:
        break

print(json.dumps(results))
"""

    docker = DockerClientManager()
    container = config.web_container

    # Execute the search inside the web container
    exec_result = docker.exec_run(container, ["python3", "-c", py], timeout=60)
    if not exec_result.get("success"):
        return {
            "success": False,
            "error": exec_result.get("stderr") or exec_result.get("output", "Search failed"),
            "error_type": exec_result.get("error", "SearchError"),
            "container": container,
        }

    try:
        raw = exec_result.get("stdout", "[]").strip() or "[]"
        results = __import__("json").loads(raw)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse results: {e!s}",
            "error_type": type(e).__name__,
            "container": container,
        }

    # Apply pagination
    paginated = paginate_dict_list(results, pagination, search_fields=["file", "match"])
    return validate_response_size(
        {
            "success": True,
            "pattern": pattern,
            "file_type": file_type,
            "roots": search_roots,
            "results": paginated.to_dict(),
            "mode_used": "fs",
            "data_quality": "approximate",
        }
    )
