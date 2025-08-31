from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.services.base_service import ServiceExecutionError, ServiceValidationError
from odoo_intelligence_mcp.services.model_inspector import ModelInspector
from odoo_intelligence_mcp.type_defs.odoo_types import Environment


class TestModelInspector:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        env = MagicMock()
        env.__contains__ = MagicMock(return_value=True)
        env.__getitem__ = MagicMock()
        return env

    @pytest.fixture
    def model_inspector(self, mock_env: MagicMock) -> ModelInspector:
        return ModelInspector(cast("Environment", mock_env))

    def test_get_service_name(self, model_inspector: ModelInspector) -> None:
        assert model_inspector.get_service_name() == "ModelInspector"

    @pytest.mark.asyncio
    async def test_get_comprehensive_model_analysis_success(self, model_inspector: ModelInspector, mock_env: MagicMock) -> None:
        mock_env.__contains__.return_value = True
        mock_model = MagicMock()
        mock_model._module = "sale"
        mock_env.__getitem__.return_value = mock_model

        with (
            patch("odoo_intelligence_mcp.services.model_inspector.model_info.get_model_info", new_callable=AsyncMock) as mock_info,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.model_relationships.get_model_relationships",
                new_callable=AsyncMock,
            ) as mock_relationships,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.inheritance_chain.analyze_inheritance_chain",
                new_callable=AsyncMock,
            ) as mock_inheritance,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.view_model_usage.get_view_model_usage", new_callable=AsyncMock
            ) as mock_view_usage,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.performance_analysis.analyze_performance", new_callable=AsyncMock
            ) as mock_performance,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.workflow_states.analyze_workflow_states", new_callable=AsyncMock
            ) as mock_workflow,
        ):
            mock_info.return_value = {"name": "sale.order", "fields": {}}
            mock_relationships.return_value = {"many2one": [], "one2many": []}
            mock_inheritance.return_value = {"inherits": [], "inherit": []}
            mock_view_usage.return_value = {"views": []}
            mock_performance.return_value = {"n_plus_1_queries": []}
            mock_workflow.return_value = {"states": []}

            result = await model_inspector.get_comprehensive_model_analysis("sale.order")

            assert result["model_name"] == "sale.order"
            assert "basic_info" in result
            assert "relationships" in result
            assert "inheritance" in result
            assert "view_usage" in result
            assert "performance_issues" in result
            assert "workflow_states" in result

            mock_info.assert_called_once_with(mock_env, "sale.order")
            mock_relationships.assert_called_once_with(mock_env, "sale.order")

    @pytest.mark.asyncio
    async def test_get_comprehensive_model_analysis_cached(self, model_inspector: ModelInspector, mock_env: MagicMock) -> None:
        cached_data = {"model_name": "sale.order", "cached": True}
        model_inspector._set_cached("comprehensive_analysis:sale.order", cached_data)

        result = await model_inspector.get_comprehensive_model_analysis("sale.order")

        assert result == cached_data
        mock_env.__getitem__.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_comprehensive_model_analysis_model_not_found(
        self, model_inspector: ModelInspector, mock_env: MagicMock
    ) -> None:
        mock_env.__contains__.return_value = False

        with pytest.raises(ServiceValidationError, match="Model 'invalid.model' not found"):
            await model_inspector.get_comprehensive_model_analysis("invalid.model")

    @pytest.mark.asyncio
    async def test_find_models_by_pattern(self, model_inspector: ModelInspector, mock_env: MagicMock) -> None:
        with patch("odoo_intelligence_mcp.services.model_inspector.search_models", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"models": ["sale.order", "sale.order.line"]}

            result = await model_inspector.find_models_by_pattern("sale")

            assert result == {"models": ["sale.order", "sale.order.line"]}
            mock_search.assert_called_once_with(mock_env, "sale")

    @pytest.mark.asyncio
    async def test_analyze_model_dependencies(self, model_inspector: ModelInspector, mock_env: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model._module = "sale"
        mock_env.__getitem__.return_value = mock_model

        with (
            patch(
                "odoo_intelligence_mcp.services.model_inspector.inheritance_chain.analyze_inheritance_chain", new_callable=AsyncMock
            ) as mock_inheritance,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.model_relationships.get_model_relationships",
                new_callable=AsyncMock,
            ) as mock_relationships,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.addon_dependencies.get_addon_dependencies", new_callable=AsyncMock
            ) as mock_addon_deps,
        ):
            mock_inheritance.return_value = {"inherits": []}
            mock_relationships.return_value = {"many2one": []}
            mock_addon_deps.return_value = {"depends": ["base"]}

            result = await model_inspector.analyze_model_dependencies("sale.order")

            assert result["model_name"] == "sale.order"
            assert result["module"] == "sale"
            assert "inheritance_chain" in result
            assert "relationships" in result
            assert "module_dependencies" in result

    @pytest.mark.asyncio
    async def test_get_model_patterns(self, model_inspector: ModelInspector, mock_env: MagicMock) -> None:
        with patch(
            "odoo_intelligence_mcp.services.model_inspector.pattern_analysis.analyze_patterns", new_callable=AsyncMock
        ) as mock_patterns:
            mock_patterns.return_value = {
                "computed_fields": [{"model": "sale.order", "field": "total"}, {"model": "other.model", "field": "value"}],
                "related_fields": [{"model": "sale.order", "field": "partner_name"}],
                "api_decorators": [],
                "custom_methods": [{"model": "sale.order", "method": "action_confirm"}],
                "state_machines": [],
                "summary": {"total": 3},
            }

            result = await model_inspector.get_model_patterns("sale.order")

            assert result["model_name"] == "sale.order"
            assert len(result["computed_fields"]) == 1
            assert result["computed_fields"][0]["field"] == "total"
            assert len(result["related_fields"]) == 1
            assert len(result["custom_methods"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_model_quality(self, model_inspector: ModelInspector, mock_env: MagicMock) -> None:
        with (
            patch(
                "odoo_intelligence_mcp.services.model_inspector.performance_analysis.analyze_performance", new_callable=AsyncMock
            ) as mock_performance,
            patch.object(model_inspector, "get_model_patterns", new_callable=AsyncMock) as mock_patterns,
            patch(
                "odoo_intelligence_mcp.services.model_inspector.view_model_usage.get_view_model_usage", new_callable=AsyncMock
            ) as mock_view_usage,
        ):
            mock_performance.return_value = {
                "n_plus_1_queries": [{"location": "method1"}, {"location": "method2"}],
                "missing_indexes": ["field1", "field2"],
            }
            mock_patterns.return_value = {
                "computed_fields": [],
                "related_fields": [],
                "api_decorators": [],
                "custom_methods": [],
                "state_machines": [],
            }
            mock_view_usage.return_value = {"unexposed_fields": ["field1", "field2", "field3", "field4", "field5", "field6"]}

            result = await model_inspector.analyze_model_quality("sale.order")

            assert result["model_name"] == "sale.order"
            assert "quality_score" in result
            assert "recommendations" in result
            assert result["quality_score"]["score"] < 100
            assert len(result["quality_score"]["penalties"]) > 0
            assert len(result["recommendations"]) > 0

    def test_calculate_quality_score_perfect(self, model_inspector: ModelInspector) -> None:
        analysis = {"performance_issues": {}, "view_coverage": {}}

        score = model_inspector._calculate_quality_score(analysis)

        assert score["score"] == 100
        assert len(score["penalties"]) == 0

    def test_calculate_quality_score_with_issues(self, model_inspector: ModelInspector) -> None:
        analysis = {
            "performance_issues": {
                "n_plus_1_queries": [{"location": "method1"}, {"location": "method2"}],
                "missing_indexes": ["field1"],
            },
            "view_coverage": {"unexposed_fields": ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]},
        }

        score = model_inspector._calculate_quality_score(analysis)

        assert score["score"] < 100
        assert score["score"] >= 0
        assert "N+1 queries" in str(score["penalties"])
        assert "Missing indexes" in str(score["penalties"])
        assert "unexposed fields" in str(score["penalties"])

    def test_generate_recommendations(self, model_inspector: ModelInspector) -> None:
        analysis = {
            "performance_issues": {
                "n_plus_1_queries": [{"location": "method1"}, {"location": "method2"}],
                "missing_indexes": ["field1", "field2"],
            },
            "view_coverage": {"unexposed_fields": ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]},
            "patterns": {"computed_fields": [], "related_fields": []},
        }

        recommendations = model_inspector._generate_recommendations(analysis)

        assert len(recommendations) > 0
        assert any("N+1 queries" in r for r in recommendations)
        assert any("indexes" in r for r in recommendations)
        assert any("unexposed fields" in r for r in recommendations)
        assert any("computed or related fields" in r for r in recommendations)

    @pytest.mark.asyncio
    async def test_safe_execute_success(self, model_inspector: ModelInspector) -> None:
        async def test_func(arg: str) -> str:
            return f"result_{arg}"

        result = await model_inspector._safe_execute("test operation", test_func, "input")
        assert result == "result_input"

    @pytest.mark.asyncio
    async def test_safe_execute_service_error(self, model_inspector: ModelInspector) -> None:
        async def test_func() -> None:
            raise ServiceValidationError("Test validation error")

        with pytest.raises(ServiceValidationError, match="Test validation error"):
            await model_inspector._safe_execute("test operation", test_func)

    @pytest.mark.asyncio
    async def test_safe_execute_general_error(self, model_inspector: ModelInspector) -> None:
        async def test_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ServiceExecutionError, match="Failed to execute test operation in ModelInspector"):
            await model_inspector._safe_execute("test operation", test_func)

    def test_cache_operations(self, model_inspector: ModelInspector) -> None:
        assert model_inspector._get_cached("test_key") is None

        model_inspector._set_cached("test_key", {"data": "value"})
        assert model_inspector._get_cached("test_key") == {"data": "value"}

        model_inspector.clear_cache()
        assert model_inspector._get_cached("test_key") is None
