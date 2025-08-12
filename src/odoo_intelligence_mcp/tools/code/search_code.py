import re
from pathlib import Path
from typing import Any

from ...core.utils import PaginationParams, paginate_dict_list, validate_response_size
from ..addon.get_addon_paths import get_addon_paths_from_container


async def search_code(pattern: str, file_type: str = "py", pagination: PaginationParams | None = None) -> dict[str, Any]:
    if pagination is None:
        pagination = PaginationParams()

    results = []
    # Get addon paths from the container
    container_paths = await get_addon_paths_from_container()

    # Use container paths directly - this tool searches on the host filesystem
    # which may not have the Odoo source code available
    search_paths = container_paths

    try:
        regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {e!s}"}

    for base_path in search_paths:
        base = Path(base_path)
        if not base.exists():
            continue

        for file_path in base.rglob(f"*.{file_type}"):
            try:
                content = file_path.read_text(encoding="utf-8")
                matches = list(regex.finditer(content))

                if matches:
                    lines = content.split("\n")
                    for match in matches[:5]:  # Limit to 5 matches per file
                        line_no = content[: match.start()].count("\n") + 1
                        results.append(
                            {
                                "file": str(file_path),
                                "line": line_no,
                                "match": match.group(),
                                "context": get_line_context(lines, line_no - 1),
                            }
                        )
            except (OSError, UnicodeDecodeError):
                pass

    paginated_results = paginate_dict_list(results, pagination, search_fields=["file", "match", "context"])

    return validate_response_size(paginated_results.to_dict())


def get_line_context(lines: list[str], line_idx: int, context: int = 2) -> str:
    start = max(0, line_idx - context)
    end = min(len(lines), line_idx + context + 1)
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))
