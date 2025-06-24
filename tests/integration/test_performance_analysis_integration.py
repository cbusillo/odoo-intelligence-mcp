import pytest

from odoo_intelligence_mcp.core.env import HostOdooEnvironment, HostOdooEnvironmentManager
from odoo_intelligence_mcp.tools.analysis.performance_analysis import analyze_performance


class TestPerformanceAnalysisIntegration:
    @pytest.fixture
    async def odoo_env(self) -> HostOdooEnvironment:
        manager = HostOdooEnvironmentManager()
        return await manager.get_environment()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_res_partner(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_performance(odoo_env, "res.partner")

        assert "error" not in result
        assert result["model"] == "res.partner"
        assert "performance_issues" in result
        assert "issue_count" in result
        assert "recommendations" in result

        # Check recommendations are present
        assert len(result["recommendations"]) > 0
        assert any("index" in rec.lower() for rec in result["recommendations"])
        assert any("prefetch" in rec.lower() for rec in result["recommendations"])

        # Issue count should match length of issues
        assert result["issue_count"] == len(result["performance_issues"])

        # Check issue structure if any exist
        for issue in result["performance_issues"]:
            assert "type" in issue
            assert "description" in issue
            assert "severity" in issue
            assert issue["severity"] in ["high", "medium", "low"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_product_template(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_performance(odoo_env, "product.template")

        assert "error" not in result
        assert result["model"] == "product.template"
        assert isinstance(result["performance_issues"], list)

        # Product template might have relational field issues
        n_plus_1_issues = [issue for issue in result["performance_issues"] if issue["type"] == "potential_n_plus_1"]

        # Check structure of N+1 issues if present
        for issue in n_plus_1_issues:
            assert "field" in issue
            assert "field_type" in issue
            assert issue["field_type"] in ["many2one", "one2many", "many2many"]
            assert "recommendation" in issue

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_sale_order(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_performance(odoo_env, "sale.order")

        assert "error" not in result
        assert result["model"] == "sale.order"

        # Sale order commonly has computed fields
        compute_issues = [issue for issue in result["performance_issues"] if issue["type"] == "expensive_compute"]

        # Check structure of compute issues if present
        for issue in compute_issues:
            assert "field" in issue
            assert "depends_on" in issue
            assert isinstance(issue["depends_on"], list)
            assert len(issue["depends_on"]) > 3  # Should have heavy dependencies

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_motor_product_template(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_performance(odoo_env, "motor.product.template")

        assert "error" not in result
        assert result["model"] == "motor.product.template"
        assert isinstance(result["performance_issues"], list)

        # Custom models might have various issues
        if result["performance_issues"]:
            # Issues should be sorted by severity
            severities = [issue["severity"] for issue in result["performance_issues"]]
            severity_order = {"high": 0, "medium": 1, "low": 2}
            sorted_severities = sorted(severities, key=lambda x: severity_order.get(x, 3))
            assert severities == sorted_severities

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_missing_index_detection(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a model that commonly has unindexed fields
        result = await analyze_performance(odoo_env, "stock.picking")

        assert "error" not in result

        missing_index_issues = [issue for issue in result["performance_issues"] if issue["type"] == "missing_index"]

        # Check structure of missing index issues
        for issue in missing_index_issues:
            assert "field" in issue
            assert "field_type" in issue
            assert issue["field_type"] in ["char", "integer", "many2one", "date", "datetime"]
            assert "commonly used in searches" in issue["description"]
            assert "index=True" in issue["recommendation"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_method_analysis(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with a model that likely has compute methods
        result = await analyze_performance(odoo_env, "account.move")

        assert "error" not in result

        method_issues = [issue for issue in result["performance_issues"] if issue["type"] == "potential_heavy_method"]

        # Check structure of method issues if present
        for issue in method_issues:
            assert "method" in issue
            assert issue["method"].startswith("_")  # Should be private methods
            assert "heavy computations" in issue["description"]
            assert issue["severity"] == "low"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_comprehensive_analysis(self, odoo_env: HostOdooEnvironment) -> None:
        # Test with multiple models to ensure comprehensive coverage
        models_to_test = ["res.partner", "product.template", "sale.order", "account.move"]

        for model_name in models_to_test:
            result = await analyze_performance(odoo_env, model_name)

            assert "error" not in result
            assert result["model"] == model_name
            assert isinstance(result["performance_issues"], list)
            assert isinstance(result["issue_count"], int)
            assert result["issue_count"] == len(result["performance_issues"])

            # All issue types should have required fields
            for issue in result["performance_issues"]:
                assert "type" in issue
                assert "description" in issue
                assert "severity" in issue
                assert "recommendation" in issue
                assert issue["type"] in ["potential_n_plus_1", "expensive_compute", "missing_index", "potential_heavy_method"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_nonexistent_model(self, odoo_env: HostOdooEnvironment) -> None:
        result = await analyze_performance(odoo_env, "nonexistent.model")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_all_issue_types(self, odoo_env: HostOdooEnvironment) -> None:
        # Try to find models that exhibit all types of issues
        models_with_complex_structure = ["sale.order", "account.move", "mrp.production", "stock.picking"]

        all_issue_types = set()

        for model_name in models_with_complex_structure:
            result = await analyze_performance(odoo_env, model_name)

            # Skip if model doesn't exist in this Odoo instance
            if "error" in result:
                continue

            for issue in result["performance_issues"]:
                all_issue_types.add(issue["type"])

        # We should find at least some of the issue types
        expected_types = {"potential_n_plus_1", "expensive_compute", "missing_index", "potential_heavy_method"}

        # At least some issue types should be found
        assert len(all_issue_types.intersection(expected_types)) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_performance_field_type_coverage(self, odoo_env: HostOdooEnvironment) -> None:
        # Test that we properly detect issues across different field types
        result = await analyze_performance(odoo_env, "product.template")

        if "error" not in result:
            field_types_with_issues = set()

            for issue in result["performance_issues"]:
                if "field_type" in issue:
                    field_types_with_issues.add(issue["field_type"])

            # Should detect issues with various field types
            relational_types = {"many2one", "one2many", "many2many"}
            indexable_types = {"char", "integer", "date", "datetime"}

            # Check that we can detect issues across different field types
            if field_types_with_issues:
                detected_relational = field_types_with_issues.intersection(relational_types)
                detected_indexable = field_types_with_issues.intersection(indexable_types)

                # At least one type should be detected (or no issues at all)
                assert len(detected_relational) > 0 or len(detected_indexable) > 0 or len(field_types_with_issues) == 0
