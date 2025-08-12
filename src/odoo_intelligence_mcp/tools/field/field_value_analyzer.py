from typing import Any

from ...type_defs.odoo_types import CompatibleEnvironment


async def analyze_field_values(
    env: CompatibleEnvironment, model: str, field: str, domain: list | None = None, sample_size: int = 1000
) -> dict[str, Any]:
    if domain is None:
        domain = []

    code = f"""
from collections import Counter

model_name = {model!r}
field_name = {field!r}
domain = {domain!r}
sample_size = {sample_size}

# Check if model exists
if model_name not in env:
    result = {{"error": f"Model {{model_name}} not found"}}
else:
    model_obj = env[model_name]

    # Get field info using fields_get() which includes inherited fields
    fields_info = model_obj.fields_get()
    if field_name not in fields_info:
        result = {{"error": f"Field {{field_name}} not found in model {{model_name}}"}}
    else:
        field_info = fields_info[field_name]

        # Search for records
        records = model_obj.search(domain, limit=sample_size)
        total_records = model_obj.search_count(domain)

        if not records:
            result = {{
                "model": model_name,
                "field": field_name,
                "field_type": field_info.get("type", ""),
                "total_records": total_records,
                "sample_size": 0,
                "message": "No records found matching the domain",
            }}
        else:
            field_values = []
            null_count = 0
            empty_count = 0

            # Analyze field values
            for record in records:
                try:
                    value = getattr(record, field_name, None)
                    if value is None or value is False:
                        null_count += 1
                        field_values.append(None)
                    elif isinstance(value, str) and value.strip() == "":
                        empty_count += 1
                        field_values.append("")
                    elif hasattr(value, "id"):
                        # Relational field
                        field_values.append(f"{{value.display_name}} (ID: {{value.id}})")
                    elif hasattr(value, "mapped"):
                        # Many2many field
                        field_values.append([f"{{v.display_name}} (ID: {{v.id}})" for v in value])
                    else:
                        # Regular field
                        field_values.append(str(value)[:100])
                except Exception:
                    null_count += 1
                    field_values.append(None)

            # Statistical analysis
            non_null_values = [v for v in field_values if v is not None]
            unique_values = list(set(str(v) for v in non_null_values))

            # Numeric statistics
            numeric_stats = {{}}
            if field_info.get("type") in ["integer", "float", "monetary"]:
                numeric_values = []
                for v in non_null_values:
                    try:
                        if isinstance(v, str) and v.strip():
                            numeric_values.append(float(v))
                        elif isinstance(v, (int, float)):
                            numeric_values.append(float(v))
                    except (ValueError, TypeError):
                        continue

                if numeric_values:
                    numeric_stats = {{
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "avg": sum(numeric_values) / len(numeric_values),
                        "median": sorted(numeric_values)[len(numeric_values) // 2],
                    }}

            # Text statistics
            text_stats = {{}}
            if field_info.get("type") in ["char", "text"]:
                text_lengths = [len(str(v)) for v in non_null_values if v]
                if text_lengths:
                    text_stats = {{
                        "min_length": min(text_lengths),
                        "max_length": max(text_lengths),
                        "avg_length": sum(text_lengths) / len(text_lengths),
                    }}

            # Value distribution
            value_counts = Counter(str(v) for v in non_null_values)
            most_common = value_counts.most_common(10)

            result = {{
                "model": model_name,
                "field": field_name,
                "field_info": {{
                    "type": field_info.get("type", ""),
                    "string": field_info.get("string", ""),
                    "required": field_info.get("required", False),
                    "readonly": field_info.get("readonly", False),
                    "store": field_info.get("store", True),
                    "compute": field_info.get("compute"),
                    "relation": field_info.get("relation"),
                }},
                "statistics": {{
                    "total_records": total_records,
                    "sample_size": len(field_values),
                    "null_count": null_count,
                    "empty_count": empty_count,
                    "unique_count": len(unique_values),
                    "null_percentage": round((null_count / len(field_values)) * 100, 2) if field_values else 0,
                    "unique_percentage": round((len(unique_values) / len(non_null_values)) * 100, 2) if non_null_values else 0,
                }},
                "value_distribution": most_common,
                "sample_values": field_values[:20],
            }}

            if numeric_stats:
                result["numeric_stats"] = numeric_stats
            if text_stats:
                result["text_stats"] = text_stats
"""

    try:
        return await env.execute_code(code)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "model": model,
            "field": field,
        }
