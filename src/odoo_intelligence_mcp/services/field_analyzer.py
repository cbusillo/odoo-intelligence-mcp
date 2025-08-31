from ..tools.code.execute_code import execute_code
from ..tools.field.field_dependencies import get_field_dependencies
from ..tools.field.field_usages import get_field_usages
from ..tools.field.field_value_analyzer import analyze_field_values
from ..tools.field.search_field_type import search_field_type
from ..tools.model.model_info import get_model_info
from ..type_defs.odoo_types import CompatibleEnvironment
from .base_service import BaseService, ServiceExecutionError


class FieldAnalyzer(BaseService):
    RISK_THRESHOLD_LOW = 5
    RISK_THRESHOLD_MEDIUM = 15
    MIN_NAME_PART_LENGTH = 3
    HIGH_NULL_PERCENTAGE = 80
    UNIQUE_PERCENTAGE_THRESHOLD = 100

    def __init__(self, env: CompatibleEnvironment) -> None:
        super().__init__(env)

    def get_service_name(self) -> str:
        return "FieldAnalyzer"

    async def get_comprehensive_field_analysis(
        self, model_name: str, field_name: str, analyze_values: bool = False
    ) -> dict[str, object]:
        self._validate_field_exists(model_name, field_name)

        cache_key = f"field_analysis:{model_name}:{field_name}:{analyze_values}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            field_info = await self._get_field_info(model_name, field_name)

            analysis = {
                "model_name": model_name,
                "field_name": field_name,
                "field_info": field_info,
                "usages": await get_field_usages(self.env, model_name, field_name),
                "dependencies": await get_field_dependencies(self.env, model_name, field_name),
            }

            if analyze_values and field_info.get("store", False):
                analysis["value_analysis"] = await analyze_field_values(self.env, model_name, field_name)

            analysis["quality_assessment"] = self._assess_field_quality(analysis)

            self._set_cached(cache_key, analysis)
            return analysis

        except Exception as e:
            error_msg = f"Failed to analyze field '{field_name}' on model '{model_name}': {e!s}"
            raise ServiceExecutionError(error_msg) from e

    async def _get_field_info(self, model_name: str, field_name: str) -> dict[str, object]:
        model_info = await get_model_info(self.env, model_name)

        for field in model_info.get("fields", []):
            if field["name"] == field_name:
                return field

        return {}

    async def analyze_field_impact(self, model_name: str, field_name: str) -> dict[str, object]:
        self._validate_field_exists(model_name, field_name)

        dependencies = await get_field_dependencies(self.env, model_name, field_name)

        usages = await get_field_usages(self.env, model_name, field_name)

        return {
            "model_name": model_name,
            "field_name": field_name,
            "direct_impact": {
                "dependent_fields": len(dependencies.get("dependents", [])),
                "view_usages": len(usages.get("view_usages", [])),
                "method_usages": len(usages.get("method_usages", [])),
                "domain_usages": len(usages.get("domain_usages", [])),
            },
            "risk_level": self._calculate_risk_level(dependencies, usages),
            "affected_components": self._get_affected_components(dependencies, usages),
        }

    @staticmethod
    def _calculate_risk_level(dependencies: dict[str, object], usages: dict[str, object]) -> str:
        risk_score = 0

        dependents = dependencies.get("dependents", [])
        view_usages = usages.get("view_usages", [])
        method_usages = usages.get("method_usages", [])
        domain_usages = usages.get("domain_usages", [])

        risk_score += len(dependents if isinstance(dependents, list) else []) * 3
        risk_score += len(view_usages if isinstance(view_usages, list) else []) * 2
        risk_score += len(method_usages if isinstance(method_usages, list) else []) * 2
        risk_score += len(domain_usages if isinstance(domain_usages, list) else [])

        if risk_score == 0:
            return "none"
        if risk_score <= FieldAnalyzer.RISK_THRESHOLD_LOW:
            return "low"
        if risk_score <= FieldAnalyzer.RISK_THRESHOLD_MEDIUM:
            return "medium"
        return "high"

    @staticmethod
    def _get_affected_components(dependencies: dict[str, object], usages: dict[str, object]) -> dict[str, list[str]]:
        dependents = dependencies.get("dependents", [])
        view_usages = usages.get("view_usages", [])
        method_usages = usages.get("method_usages", [])
        domain_usages = usages.get("domain_usages", [])

        return {
            "computed_fields": [f"{dep['model']}.{dep['field']}" for dep in (dependents if isinstance(dependents, list) else [])],
            "views": [view["view_name"] for view in (view_usages if isinstance(view_usages, list) else [])],
            "methods": [method["location"] for method in (method_usages if isinstance(method_usages, list) else [])],
            "domains": [domain["location"] for domain in (domain_usages if isinstance(domain_usages, list) else [])],
        }

    async def find_similar_fields(self, model_name: str, field_name: str) -> dict[str, object]:
        self._validate_field_exists(model_name, field_name)

        field_info = await self._get_field_info(model_name, field_name)
        field_type = str(field_info.get("type", ""))

        return {
            "by_type": self._find_fields_by_type(field_type, field_name) if field_type else [],
            "by_name": await self._find_fields_by_name_parts(field_name),
            "by_properties": [],
        }

    def _find_fields_by_type(self, field_type: str, exclude_field_name: str) -> list[dict[str, str]]:
        type_results = self._safe_execute("search by type", lambda: search_field_type(self.env, field_type))
        return [f for f in type_results.get("fields", []) if f["field_name"] != exclude_field_name][:10]

    async def _find_fields_by_name_parts(self, field_name: str) -> list[dict[str, str]]:
        similar_fields = []
        name_parts = field_name.split("_")

        for part in name_parts:
            if len(part) > FieldAnalyzer.MIN_NAME_PART_LENGTH:
                fields = await self._search_fields_by_part(part, field_name)
                similar_fields.extend(fields)

        return similar_fields[:10]

    async def _search_fields_by_part(self, part: str, exclude_field_name: str) -> list[dict[str, str]]:
        try:
            code_result = execute_code(self.env, "result = list(env.registry.models.keys())")
            all_models = code_result.get("result", []) if isinstance(code_result, dict) else []
        except (KeyError, AttributeError, TypeError):
            return []

        matching_fields = []
        for model in all_models:
            fields = self._get_model_fields_containing(model, part, exclude_field_name)
            matching_fields.extend(fields)

        return matching_fields

    def _get_model_fields_containing(self, model_name: str, part: str, exclude_field_name: str) -> list[dict[str, str]]:
        try:
            model_info = self._safe_execute("get model info", lambda: get_model_info(self.env, model_name))
            if not isinstance(model_info, dict):
                return []

            matching_fields = []
            for field_data in model_info.get("fields", []):
                if isinstance(field_data, dict):
                    field_name = field_data.get("name", "")
                    if part in field_name and field_name != exclude_field_name:
                        matching_fields.append(
                            {
                                "model": model_name,
                                "field_name": field_name,
                                "type": field_data.get("type", "unknown"),
                            }
                        )
            return matching_fields
        except (KeyError, AttributeError):
            return []

    @staticmethod
    def _assess_field_quality(analysis: dict[str, object]) -> dict[str, object]:
        issues = []
        suggestions = []

        field_info = analysis.get("field_info", {})
        if not isinstance(field_info, dict):
            field_info = {}
        usages = analysis.get("usages", {})
        if not isinstance(usages, dict):
            usages = {}
        value_analysis = analysis.get("value_analysis", {})
        if not isinstance(value_analysis, dict):
            value_analysis = {}

        if field_info.get("required", False) and field_info.get("default") is None:
            suggestions.append("Required field without default value may cause issues during record creation")

        view_usages = usages.get("view_usages", [])
        if (not view_usages or (isinstance(view_usages, list) and len(view_usages) == 0)) and field_info.get("store", False):
            suggestions.append("Stored field is not used in any views - might be an unused field")

        if value_analysis:
            null_percentage = value_analysis.get("statistics", {}).get("null_percentage", 0)
            if null_percentage > FieldAnalyzer.HIGH_NULL_PERCENTAGE and not field_info.get("required"):
                suggestions.append(f"Field has {null_percentage}% null values - consider if it's really needed")

            unique_percentage = value_analysis.get("statistics", {}).get("unique_percentage", 0)
            if unique_percentage == FieldAnalyzer.UNIQUE_PERCENTAGE_THRESHOLD and field_info.get("type") not in ["char", "text"]:
                suggestions.append("Field has all unique values - might be a candidate for a unique constraint")

        return {
            "issues": issues,
            "suggestions": suggestions,
        }

    async def get_field_migration_plan(
        self, model_name: str, field_name: str, new_field_type: str | None = None
    ) -> dict[str, object]:
        self._validate_field_exists(model_name, field_name)

        impact = await self.analyze_field_impact(model_name, field_name)
        field_info = await self._get_field_info(model_name, field_name)

        migration_plan = {
            "field": f"{model_name}.{field_name}",
            "current_type": field_info.get("type"),
            "new_type": new_field_type,
            "impact_summary": impact,
            "migration_steps": [],
            "precautions": [],
        }

        risk_level = impact.get("risk_level", "low")
        if risk_level in ["medium", "high"]:
            migration_plan["precautions"].append("Create backup before migration")
            migration_plan["precautions"].append("Test migration in staging environment first")

        migration_plan["migration_steps"].append("1. Analyze current field usage and dependencies")
        migration_plan["migration_steps"].append("2. Create migration script with data transformation")

        direct_impact = impact.get("direct_impact", {})
        if isinstance(direct_impact, dict):
            if direct_impact.get("view_usages", 0) > 0:
                migration_plan["migration_steps"].append("3. Update all view definitions")

            if direct_impact.get("dependent_fields", 0) > 0:
                migration_plan["migration_steps"].append("4. Update dependent computed fields")

            if direct_impact.get("method_usages", 0) > 0:
                migration_plan["migration_steps"].append("5. Refactor methods using the field")

        migration_plan["migration_steps"].append("6. Run tests to verify functionality")
        migration_plan["migration_steps"].append("7. Deploy and monitor for issues")

        return migration_plan
