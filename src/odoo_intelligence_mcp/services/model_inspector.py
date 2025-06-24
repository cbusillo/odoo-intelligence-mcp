from collections.abc import Callable
from typing import Any

from ..tools.addon import addon_dependencies
from ..tools.analysis import pattern_analysis, performance_analysis, workflow_states
from ..tools.model import (
    inheritance_chain,
    model_info,
    model_relationships,
    view_model_usage,
)
from ..tools.model.search_models import search_models
from .base_service import BaseService, ServiceError, ServiceExecutionError

# Quality score thresholds
MAX_UNEXPOSED_FIELDS_THRESHOLD = 5


class ModelInspector(BaseService):
    def get_service_name(self) -> str:
        return "ModelInspector"

    async def get_comprehensive_model_analysis(self, model_name: str) -> dict[str, Any]:
        self._validate_model_exists(model_name)

        cache_key = f"comprehensive_analysis:{model_name}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            analysis = {
                "model_name": model_name,
                "basic_info": await self._safe_execute("get model info", model_info.get_model_info, self.env, model_name),
                "relationships": await self._safe_execute(
                    "get relationships", model_relationships.get_model_relationships, self.env, model_name
                ),
                "inheritance": await self._safe_execute(
                    "get inheritance chain", inheritance_chain.analyze_inheritance_chain, self.env, model_name
                ),
                "view_usage": await self._safe_execute(
                    "get view usage", view_model_usage.get_view_model_usage, self.env, model_name
                ),
                "performance_issues": await self._safe_execute(
                    "analyze performance", performance_analysis.analyze_performance, self.env, model_name
                ),
                "workflow_states": await self._safe_execute(
                    "get workflow states", workflow_states.analyze_workflow_states, self.env, model_name
                ),
            }

            self._set_cached(cache_key, analysis)
            return analysis

        except Exception as e:
            raise ServiceExecutionError(f"Failed to analyze model '{model_name}': {e!s}") from e

    async def find_models_by_pattern(self, pattern: str) -> dict[str, Any]:
        return await self._safe_execute("search models", search_models, self.env, pattern)

    async def analyze_model_dependencies(self, model_name: str) -> dict[str, Any]:
        self._validate_model_exists(model_name)

        cache_key = f"dependencies:{model_name}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            model = self.env[model_name]
            # noinspection PyProtectedMember
            module_name = model._module

            dependencies = {
                "model_name": model_name,
                "module": module_name,
                "inheritance_chain": await self._safe_execute(
                    "get inheritance", inheritance_chain.analyze_inheritance_chain, self.env, model_name
                ),
                "relationships": await self._safe_execute(
                    "get relationships", model_relationships.get_model_relationships, self.env, model_name
                ),
                "module_dependencies": await self._safe_execute(
                    "get module dependencies",
                    addon_dependencies.get_addon_dependencies,
                    self.env,
                    module_name,
                ),
            }

            self._set_cached(cache_key, dependencies)
            return dependencies

        except Exception as e:
            raise ServiceExecutionError(f"Failed to analyze dependencies for model '{model_name}': {e!s}") from e

    async def get_model_patterns(self, model_name: str) -> dict[str, Any]:
        self._validate_model_exists(model_name)

        patterns_result = await self._safe_execute("get patterns", pattern_analysis.analyze_patterns, self.env, "all", None, 1, 1000)

        model_patterns = {
            "model_name": model_name,
            "computed_fields": [],
            "related_fields": [],
            "api_decorators": [],
            "custom_methods": [],
            "state_machines": [],
        }

        for pattern_type, items in patterns_result.items():
            if pattern_type == "summary":
                continue
            if isinstance(items, list):
                for item in items:
                    if item.get("model") == model_name:
                        model_patterns[pattern_type].append(item)

        return model_patterns

    async def analyze_model_quality(self, model_name: str) -> dict[str, Any]:
        self._validate_model_exists(model_name)

        quality_analysis = {
            "model_name": model_name,
            "performance_issues": await self._safe_execute(
                "get performance issues", performance_analysis.analyze_performance, self.env, model_name
            ),
            "patterns": await self.get_model_patterns(model_name),
            "view_coverage": await self._safe_execute(
                "get view coverage", view_model_usage.get_view_model_usage, self.env, model_name
            ),
        }

        quality_analysis["quality_score"] = self._calculate_quality_score(quality_analysis)
        quality_analysis["recommendations"] = self._generate_recommendations(quality_analysis)

        return quality_analysis

    @staticmethod
    def _calculate_quality_score(analysis: dict[str, Any]) -> dict[str, Any]:
        score = 100
        penalties = []

        performance = analysis.get("performance_issues", {})
        if performance.get("n_plus_1_queries", []):
            score -= 10 * len(performance["n_plus_1_queries"])
            penalties.append(f"N+1 queries: -{10 * len(performance['n_plus_1_queries'])} points")

        if performance.get("missing_indexes", []):
            score -= 5 * len(performance["missing_indexes"])
            penalties.append(f"Missing indexes: -{5 * len(performance['missing_indexes'])} points")

        view_coverage = analysis.get("view_coverage", {})
        unexposed_fields = len(view_coverage.get("unexposed_fields", []))
        if unexposed_fields > MAX_UNEXPOSED_FIELDS_THRESHOLD:
            score -= min(20, unexposed_fields * 2)
            penalties.append(f"Many unexposed fields: -{min(20, unexposed_fields * 2)} points")

        return {
            "score": max(0, score),
            "penalties": penalties,
        }

    @staticmethod
    def _generate_recommendations(analysis: dict[str, Any]) -> list[str]:
        recommendations = []

        performance = analysis.get("performance_issues", {})
        if performance.get("n_plus_1_queries"):
            recommendations.append(
                "Consider prefetching related records to avoid N+1 queries in: "
                + ", ".join([q["location"] for q in performance["n_plus_1_queries"][:3]])
            )

        if performance.get("missing_indexes"):
            recommendations.append(
                "Add database indexes for frequently searched fields: " + ", ".join(performance["missing_indexes"][:3])
            )

        view_coverage = analysis.get("view_coverage", {})
        if len(view_coverage.get("unexposed_fields", [])) > MAX_UNEXPOSED_FIELDS_THRESHOLD:
            recommendations.append(
                f"Review {len(view_coverage['unexposed_fields'])} unexposed fields - "
                "they may be unnecessary or should be added to views"
            )

        patterns = analysis.get("patterns", {})
        if not patterns.get("computed_fields") and not patterns.get("related_fields"):
            recommendations.append("Consider using computed or related fields for derived data instead of manual calculations")

        return recommendations

    async def _safe_execute(self, operation: str, func: Callable[..., Any], *args: object, **kwargs: object) -> Any:  # noqa: ANN401
        try:
            return await func(*args, **kwargs)
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceExecutionError(f"Failed to execute {operation} in {self.get_service_name()}: {e!s}") from e
