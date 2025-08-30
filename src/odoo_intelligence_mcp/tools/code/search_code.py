import re
from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size


async def search_code(pattern: str, file_type: str = "py", pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    try:
        # Validate regex pattern
        re.compile(pattern)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e!s}"}

    # Use Python script execution in container for more reliable search
    from ...core.env import HostOdooEnvironmentManager

    env_manager = HostOdooEnvironmentManager()
    env = await env_manager.get_environment()

    search_code_script = f"""
import os
import re
import glob

pattern = {pattern!r}
file_type = {file_type!r}
results = []

# Get addon paths from Odoo configuration
addon_paths = []
try:
    import odoo.tools.config as odoo_config
    for path in odoo_config.get('addons_path', '').split(','):
        path = path.strip()
        if os.path.exists(path):
            addon_paths.append(path)
except:
    pass

# If no addon paths from config, use default locations
if not addon_paths:
    default_paths = ['/opt/project/addons', '/odoo/addons', '/volumes/enterprise']
    addon_paths = [p for p in default_paths if os.path.exists(p)]

# Search for files and patterns
for addon_path in addon_paths:
    try:
        # Find all files with the specified extension
        for file_path in glob.glob(os.path.join(addon_path, '**', f'*.{{file_type}}'), recursive=True):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line):
                            results.append({{
                                'file': file_path,
                                'line': line_num,
                                'match': line.strip(),
                                'context': line.strip()
                            }})
                            if len(results) >= 100:  # Limit results
                                break
            except Exception:
                continue
            if len(results) >= 100:
                break
    except Exception:
        continue
    if len(results) >= 100:
        break

result = results[:100]  # Ensure we don't exceed limits
"""

    try:
        output = await env.execute_code(search_code_script)

        if isinstance(output, dict) and "error" in output:
            return output

        results = output if isinstance(output, list) else []

        # Apply pagination
        paginated_results = paginate_dict_list(results, pagination, search_fields=["file", "match", "context"])

        return validate_response_size(paginated_results.to_dict())

    except Exception as e:
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "pattern": pattern, "file_type": file_type}
