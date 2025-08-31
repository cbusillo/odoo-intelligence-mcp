from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odoo_intelligence_mcp.services.base_service import ServiceExecutionError
from odoo_intelligence_mcp.services.odoo_analyzer import OdooAnalyzer
from odoo_intelligence_mcp.type_defs.odoo_types import Environment


class TestOdooAnalyzer:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def odoo_analyzer(self, mock_env: MagicMock) -> OdooAnalyzer:
        return OdooAnalyzer(cast("Environment", mock_env))

    def test_get_service_name(self, odoo_analyzer: OdooAnalyzer) -> None:
        assert odoo_analyzer.get_service_name() == "OdooAnalyzer"

    @pytest.mark.asyncio
    async def test_analyze_project_health_healthy(self, odoo_analyzer: OdooAnalyzer) -> None:
        with (
            patch(
                "odoo_intelligence_mcp.services.odoo_analyzer.container_status.odoo_status", new_callable=AsyncMock
            ) as mock_status,
            patch("odoo_intelligence_mcp.services.odoo_analyzer.execute_code", new_callable=AsyncMock) as mock_execute,
        ):
            mock_status.return_value = {"all_running": True, "containers": ["web", "db"]}
            mock_execute.return_value = {"success": True, "output": "health_check"}

            result = await odoo_analyzer.analyze_project_health()

            assert result["status"] == "healthy"
            assert "container_status" in result
            assert "execution_test" in result
            mock_status.assert_called_once()
            mock_execute.assert_called_once_with("print('health_check')")

    @pytest.mark.asyncio
    async def test_analyze_project_health_containers_not_running(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch(
            "odoo_intelligence_mcp.services.odoo_analyzer.container_status.odoo_status", new_callable=AsyncMock
        ) as mock_status:
            mock_status.return_value = {"all_running": False, "containers": []}

            result = await odoo_analyzer.analyze_project_health()

            assert result["status"] == "unhealthy"
            assert result["reason"] == "Odoo containers not running"
            assert "Start Odoo containers" in result["recommendations"]

    @pytest.mark.asyncio
    async def test_analyze_project_health_execution_failure(self, odoo_analyzer: OdooAnalyzer) -> None:
        with (
            patch(
                "odoo_intelligence_mcp.services.odoo_analyzer.container_status.odoo_status", new_callable=AsyncMock
            ) as mock_status,
            patch("odoo_intelligence_mcp.services.odoo_analyzer.execute_code", new_callable=AsyncMock) as mock_execute,
        ):
            mock_status.return_value = {"all_running": True}
            mock_execute.return_value = {"success": False, "error": "Database connection failed"}

            result = await odoo_analyzer.analyze_project_health()

            assert result["status"] == "unhealthy"
            assert result["reason"] == "Cannot execute code in Odoo environment"
            assert "Restart Odoo containers" in result["recommendations"]

    @pytest.mark.asyncio
    async def test_search_across_modules_with_results(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch("odoo_intelligence_mcp.services.odoo_analyzer.search_code", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "results": [
                    {"file": "addons/sale/models/sale.py", "matches": ["line1", "line2"]},
                    {"file": "addons/sale/views/sale_views.xml", "matches": ["line3"]},
                    {"file": "addons/stock/models/stock.py", "matches": ["line4"]},
                ],
                "summary": {"total_files": 3, "total_matches": 4},
            }

            result = await odoo_analyzer.search_across_modules("test_pattern")

            assert result["pattern"] == "test_pattern"
            assert result["file_type"] == "py"
            assert len(result["matches"]) == 3
            assert "organized_by_module" in result
            assert "sale" in result["organized_by_module"]
            assert "stock" in result["organized_by_module"]
            assert result["organized_by_module"]["sale"]["total_matches"] == 3

    @pytest.mark.asyncio
    async def test_search_across_modules_no_results(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch("odoo_intelligence_mcp.services.odoo_analyzer.search_code", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"results": None}

            result = await odoo_analyzer.search_across_modules("nonexistent", "xml")

            assert result["pattern"] == "nonexistent"
            assert result["matches"] == []
            assert result["summary"]["total_files"] == 0

    @pytest.mark.asyncio
    async def test_get_module_overview_success(self, odoo_analyzer: OdooAnalyzer) -> None:
        with (
            patch(
                "odoo_intelligence_mcp.services.odoo_analyzer.module_structure.get_module_structure", new_callable=AsyncMock
            ) as mock_structure,
            patch(
                "odoo_intelligence_mcp.services.odoo_analyzer.addon_dependencies.get_addon_dependencies", new_callable=AsyncMock
            ) as mock_deps,
        ):
            mock_structure.return_value = {
                "structure": {
                    "models": {"count": 5, "files": ["sale.py"]},
                    "views": {"count": 3, "files": ["sale_views.xml"]},
                    "controllers": {"count": 1, "files": ["main.py"]},
                    "wizards": {"count": 0},
                    "reports": {"count": 0},
                    "static": {},
                    "tests": {"count": 2},
                }
            }
            mock_deps.return_value = {"dependencies": ["base", "web"], "external_dependencies": {}}

            result = await odoo_analyzer.get_module_overview("sale")

            assert result["module_name"] == "sale"
            assert "structure" in result
            assert "dependencies" in result
            assert "overview" in result
            assert result["overview"]["type"] == "web_module"
            assert "data_models" in result["overview"]["features"]

    @pytest.mark.asyncio
    async def test_execute_odoo_command_success(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch("odoo_intelligence_mcp.services.odoo_analyzer.execute_code", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "output": "Result: 42", "execution_time": 0.5}

            result = await odoo_analyzer.execute_odoo_command("env['res.partner'].search_count([])")

            assert result["success"] is True
            assert result["output"] == "Result: 42"
            assert result["code"] == "env['res.partner'].search_count([])"

    @pytest.mark.asyncio
    async def test_update_module(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch(
            "odoo_intelligence_mcp.services.odoo_analyzer.module_update.odoo_update_module", new_callable=AsyncMock
        ) as mock_update:
            mock_update.return_value = {"success": True, "output": "Module updated successfully"}

            result = await odoo_analyzer.update_module("sale", force_install=True)

            assert result["module_name"] == "sale"
            assert result["force_install"] is True
            assert result["success"] is True
            mock_update.assert_called_once_with("sale", True)

    @pytest.mark.asyncio
    async def test_restart_containers(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch(
            "odoo_intelligence_mcp.services.odoo_analyzer.container_restart.odoo_restart", new_callable=AsyncMock
        ) as mock_restart:
            mock_restart.return_value = {"success": True, "output": "Containers restarted"}

            result = await odoo_analyzer.restart_containers("web,db")

            assert result["services"] == "web,db"
            assert result["success"] is True
            mock_restart.assert_called_once_with("web,db")

    @pytest.mark.asyncio
    async def test_get_container_logs(self, odoo_analyzer: OdooAnalyzer) -> None:
        with patch("odoo_intelligence_mcp.services.odoo_analyzer.container_logs.odoo_logs", new_callable=AsyncMock) as mock_logs:
            mock_logs.return_value = {"logs": "Log line 1\nLog line 2"}

            result = await odoo_analyzer.get_container_logs("web", lines=50)

            assert result["container"] == "web"
            assert result["lines"] == 50
            assert "Log line 1" in result["logs"]
            mock_logs.assert_called_once_with("web", 50)

    def test_organize_search_results(self, odoo_analyzer: OdooAnalyzer) -> None:
        results = [
            {"file": "addons/sale/models/sale.py", "matches": ["match1", "match2"]},
            {"file": "addons/sale/views/views.xml", "matches": ["match3"]},
            {"file": "enterprise/account/models/account.py", "matches": ["match4"]},
            {"file": "unknown/path/file.py", "matches": ["match5"]},
        ]

        organized = odoo_analyzer._organize_search_results(results)

        assert "sale" in organized
        assert organized["sale"]["total_matches"] == 3
        assert len(organized["sale"]["files"]) == 2
        assert "account" in organized
        assert organized["account"]["module"] == "account"
        assert "unknown" in organized

    def test_extract_module_name_from_path(self, odoo_analyzer: OdooAnalyzer) -> None:
        assert odoo_analyzer._extract_module_name_from_path("addons/sale/models/sale.py") == "sale"
        assert odoo_analyzer._extract_module_name_from_path("enterprise/account/views/views.xml") == "account"
        assert odoo_analyzer._extract_module_name_from_path("/opt/odoo/addons/web/static/src/js/file.js") == "web"
        assert odoo_analyzer._extract_module_name_from_path("unknown/path/file.py") == "unknown"

    def test_calculate_total_files(self, odoo_analyzer: OdooAnalyzer) -> None:
        structure = {
            "structure": {
                "models": {"count": 5},
                "views": {"count": 3},
                "controllers": {"count": 2},
                "static": {"count": 10},
            }
        }
        assert odoo_analyzer._calculate_total_files(structure) == 20

        empty_structure = {"structure": {}}
        assert odoo_analyzer._calculate_total_files(empty_structure) == 0

    def test_determine_complexity(self, odoo_analyzer: OdooAnalyzer) -> None:
        assert odoo_analyzer._determine_complexity(25) == "high"
        assert odoo_analyzer._determine_complexity(15) == "medium"
        assert odoo_analyzer._determine_complexity(5) == "low"

    def test_determine_module_type(self, odoo_analyzer: OdooAnalyzer) -> None:
        web_module = {"controllers": {"count": 2}, "reports": {"count": 0}, "wizards": {"count": 0}}
        assert odoo_analyzer._determine_module_type(web_module) == "web_module"

        report_module = {"controllers": {"count": 0}, "reports": {"count": 3}, "wizards": {"count": 0}}
        assert odoo_analyzer._determine_module_type(report_module) == "reporting_module"

        workflow_module = {"controllers": {"count": 0}, "reports": {"count": 0}, "wizards": {"count": 5}}
        assert odoo_analyzer._determine_module_type(workflow_module) == "workflow_module"

        simple_module = {"controllers": {"count": 0}, "reports": {"count": 0}, "wizards": {"count": 1}}
        assert odoo_analyzer._determine_module_type(simple_module) == "simple"

    def test_identify_features(self, odoo_analyzer: OdooAnalyzer) -> None:
        structure = {
            "models": {"count": 3},
            "views": {"count": 2},
            "static": {"js": ["file.js"]},
            "tests": {"count": 5},
        }
        features = odoo_analyzer._identify_features(structure)

        assert "data_models" in features
        assert "user_interface" in features
        assert "javascript_widgets" in features
        assert "automated_tests" in features

    def test_check_concerns(self, odoo_analyzer: OdooAnalyzer) -> None:
        many_deps = {"dependencies": ["base"] * 15, "external_dependencies": {}}
        concerns = odoo_analyzer._check_concerns(many_deps)
        assert "many_dependencies" in concerns

        external_deps = {"dependencies": ["base"], "external_dependencies": {"python": ["pandas"], "bin": ["wkhtmltopdf"]}}
        concerns = odoo_analyzer._check_concerns(external_deps)
        assert "external_dependencies" in concerns

        no_concerns = {"dependencies": ["base", "web"], "external_dependencies": {}}
        concerns = odoo_analyzer._check_concerns(no_concerns)
        assert len(concerns) == 0

    def test_generate_module_overview(self, odoo_analyzer: OdooAnalyzer) -> None:
        structure = {
            "structure": {
                "models": {"count": 5},
                "views": {"count": 3},
                "controllers": {"count": 1},
                "static": {"js": ["widget.js"]},
                "tests": {"count": 2},
                "wizards": {"count": 0},
                "reports": {"count": 0},
            }
        }
        dependencies = {"dependencies": ["base", "web"], "external_dependencies": {}}

        overview = odoo_analyzer._generate_module_overview(structure, dependencies)

        assert overview["complexity"] == "medium"
        assert overview["type"] == "web_module"
        assert "data_models" in overview["features"]
        assert "javascript_widgets" in overview["features"]
        assert len(overview["concerns"]) == 0

    def test_generate_module_overview_with_error(self, odoo_analyzer: OdooAnalyzer) -> None:
        structure = {"error": "Module not found"}
        dependencies = {}

        overview = odoo_analyzer._generate_module_overview(structure, dependencies)

        assert "error" in overview

    @pytest.mark.asyncio
    async def test_safe_execute_error_handling(self, odoo_analyzer: OdooAnalyzer) -> None:
        async def failing_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ServiceExecutionError, match="Failed to execute test operation in OdooAnalyzer"):
            await odoo_analyzer._safe_execute("test operation", failing_func)
