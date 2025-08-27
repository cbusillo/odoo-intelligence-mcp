from odoo_intelligence_mcp.models.odoo_models import OdooField, OdooModel, OdooRelationship
from odoo_intelligence_mcp.models.responses import (
    AddonDependencyResponse,
    BaseFieldSearchResponse,
    CodeSearchResult,
    DecoratorSearchResponse,
    DynamicFieldResponse,
    ExecutionResponse,
    FieldAnalysisResponse,
    FieldDependencyResponse,
    FieldPropertySearchResponse,
    FieldTypeSearchResponse,
    FieldUsageResponse,
    FieldValueAnalysis,
    InheritanceChainResponse,
    MethodSearchResponse,
    ModelInfoResponse,
    ModuleStructureResponse,
    OdooStatusResponse,
    PatternAnalysisResponse,
    PerformanceAnalysisResponse,
    PerformanceIssue,
    PermissionCheckResponse,
    RelationshipAnalysisResponse,
    SearchModelResponse,
    TestRunnerResponse,
    ViewUsageResponse,
    WorkflowStateResponse,
)


class TestModelInfoResponse:
    def test_init_defaults(self) -> None:
        response = ModelInfoResponse()
        assert isinstance(response.model, OdooModel)
        assert response.field_count == 0
        assert response.method_count == 0
        assert response.is_abstract is False
        assert response.inherited_from == []

    def test_init_with_values(self) -> None:
        model = OdooModel(name="sale.order")
        response = ModelInfoResponse(
            model=model,
            field_count=10,
            method_count=5,
            has_workflow=True,
            inherited_from=["mail.thread"],
        )
        assert response.model.name == "sale.order"
        assert response.field_count == 10
        assert response.has_workflow is True
        assert response.inherited_from == ["mail.thread"]

    def test_to_dict(self) -> None:
        response = ModelInfoResponse(field_count=5, record_count=100)
        result = response.to_dict()
        assert result["field_count"] == 5
        assert result["record_count"] == 100


class TestFieldAnalysisResponse:
    def test_field_analysis(self) -> None:
        field = OdooField(name="partner_id", type="many2one")
        response = FieldAnalysisResponse(
            field=field,
            model_name="sale.order",
            usage_count=15,
            used_in_views=["form", "tree"],
            has_index=True,
        )
        assert response.field.name == "partner_id"
        assert response.usage_count == 15
        assert response.used_in_views == ["form", "tree"]
        assert response.has_index is True

    def test_field_dependencies(self) -> None:
        response = FieldAnalysisResponse(
            depends_on=["field1", "field2"],
            depended_by=["computed_field"],
        )
        assert response.depends_on == ["field1", "field2"]
        assert response.depended_by == ["computed_field"]


class TestPermissionCheckResponse:
    def test_permission_check(self) -> None:
        response = PermissionCheckResponse(
            user="admin",
            model="sale.order",
            operation="write",
            allowed=True,
            groups=["sales_manager", "base.group_user"],
        )
        assert response.user == "admin"
        assert response.allowed is True
        assert "sales_manager" in response.groups

    def test_permission_denied(self) -> None:
        response = PermissionCheckResponse(
            user="guest",
            model="account.move",
            operation="unlink",
            allowed=False,
            reason="Insufficient privileges",
            sudo_required=True,
        )
        assert response.allowed is False
        assert response.reason == "Insufficient privileges"
        assert response.sudo_required is True


class TestSearchModelResponse:
    def test_search_results(self) -> None:
        response = SearchModelResponse(
            pattern="sale*",
            exact_matches=[{"name": "sale.order"}],
            partial_matches=[{"name": "sale.order.line"}],
            total_matches=5,
            search_time_ms=125.5,
        )
        assert response.pattern == "sale*"
        assert len(response.exact_matches) == 1
        assert response.total_matches == 5
        assert response.search_time_ms == 125.5


class TestRelationshipAnalysisResponse:
    def test_relationship_analysis(self) -> None:
        rel1 = OdooRelationship(
            field_name="partner_id",
            source_model="sale.order",
            target_model="res.partner",
            type="many2one",
        )
        response = RelationshipAnalysisResponse(
            model_name="sale.order",
            many2one_fields=[rel1],
            total_relationships=3,
        )
        assert response.model_name == "sale.order"
        assert len(response.many2one_fields) == 1
        assert response.total_relationships == 3

    def test_circular_dependencies(self) -> None:
        response = RelationshipAnalysisResponse(
            circular_dependencies=[["model.a", "model.b", "model.a"]],
        )
        assert len(response.circular_dependencies) == 1
        assert response.circular_dependencies[0] == ["model.a", "model.b", "model.a"]


class TestFieldUsageResponse:
    def test_field_usage(self) -> None:
        response = FieldUsageResponse(
            model_name="sale.order",
            field_name="partner_id",
            views=[{"type": "form"}, {"type": "tree"}],
            methods=[{"name": "_compute_total"}],
            total_usages=10,
        )
        assert response.field_name == "partner_id"
        assert len(response.views) == 2
        assert response.total_usages == 10


class TestPerformanceAnalysisResponse:
    def test_performance_issues(self) -> None:
        issue = PerformanceIssue(
            type="n_plus_one",
            severity="high",
            description="N+1 query detected",
            suggestion="Use prefetch",
            affected_records=1000,
        )
        response = PerformanceAnalysisResponse(
            model_name="sale.order",
            issues=[issue],
            missing_indexes=["partner_id"],
            performance_score=65.0,
        )
        assert response.model_name == "sale.order"
        assert len(response.issues) == 1
        assert response.issues[0].severity == "high"
        assert response.performance_score == 65.0

    def test_performance_issue_details(self) -> None:
        issue = PerformanceIssue(
            type="missing_index",
            severity="medium",
            location="sale.order.partner_id",
            query_example="SELECT * FROM sale_order WHERE partner_id = %s",
        )
        assert issue.type == "missing_index"
        assert issue.query_example is not None


class TestPatternAnalysisResponse:
    def test_pattern_analysis(self) -> None:
        response = PatternAnalysisResponse(
            pattern_type="computed_fields",
            patterns=[{"field": "total", "method": "_compute_total"}],
            total_count=25,
            page=2,
            has_more=True,
        )
        assert response.pattern_type == "computed_fields"
        assert len(response.patterns) == 1
        assert response.page == 2
        assert response.has_more is True


class TestInheritanceChainResponse:
    def test_inheritance_chain(self) -> None:
        response = InheritanceChainResponse(
            model_name="sale.order",
            mro=["sale.order", "mail.thread", "BaseModel"],
            inherit=["mail.thread"],
            inheritance_depth=2,
            is_abstract=False,
        )
        assert response.model_name == "sale.order"
        assert len(response.mro) == 3
        assert response.inheritance_depth == 2

    def test_mixin_detection(self) -> None:
        response = InheritanceChainResponse(
            model_name="mail.thread.mixin",
            is_abstract=True,
            is_mixin=True,
        )
        assert response.is_abstract is True
        assert response.is_mixin is True


class TestAddonDependencyResponse:
    def test_addon_dependencies(self) -> None:
        response = AddonDependencyResponse(
            addon_name="sale",
            depends=["base", "mail"],
            dependents=["sale_management"],
            auto_install=False,
            application=True,
            version="16.0.1.0.0",
        )
        assert response.addon_name == "sale"
        assert "base" in response.depends
        assert "sale_management" in response.dependents
        assert response.application is True

    def test_external_dependencies(self) -> None:
        response = AddonDependencyResponse(
            addon_name="custom_module",
            external_dependencies={"python": ["pandas", "numpy"], "bin": ["wkhtmltopdf"]},
        )
        assert "python" in response.external_dependencies
        assert "pandas" in response.external_dependencies["python"]


class TestCodeSearchResult:
    def test_code_search_result(self) -> None:
        result = CodeSearchResult(
            file_path="sale/models/sale.py",
            line_number=150,
            line_content="    def action_confirm(self):",
            module="sale",
            model="sale.order",
            method="action_confirm",
        )
        assert result.file_path == "sale/models/sale.py"
        assert result.line_number == 150
        assert result.model == "sale.order"

    def test_match_context(self) -> None:
        result = CodeSearchResult(
            file_path="test.py",
            line_number=10,
            line_content="matched line",
            match_context=["line before", "matched line", "line after"],
        )
        assert len(result.match_context) == 3
        assert "matched line" in result.match_context


class TestModuleStructureResponse:
    def test_module_structure(self) -> None:
        response = ModuleStructureResponse(
            module_name="sale",
            path="/odoo/addons/sale",
            python_files=25,
            xml_files=15,
            js_files=5,
            total_lines=5000,
        )
        assert response.module_name == "sale"
        assert response.python_files == 25
        assert response.total_lines == 5000

    def test_module_components(self) -> None:
        response = ModuleStructureResponse(
            models=[{"name": "sale.order"}],
            views=[{"type": "form"}],
            controllers=[{"name": "SaleController"}],
            security={"ir_model_access": 10, "ir_rule": 5},
        )
        assert len(response.models) == 1
        assert response.security["ir_model_access"] == 10


class TestMethodSearchResponse:
    def test_method_search(self) -> None:
        response = MethodSearchResponse(
            method_name="action_confirm",
            results=[{"model": "sale.order", "line": 100}],
            total_count=3,
            page=1,
            has_more=False,
        )
        assert response.method_name == "action_confirm"
        assert response.total_count == 3
        assert response.has_more is False


class TestDecoratorSearchResponse:
    def test_decorator_search(self) -> None:
        response = DecoratorSearchResponse(
            decorator="depends",
            results=[{"model": "sale.order", "method": "_compute_total"}],
            grouped_by_model={"sale.order": [{"method": "_compute_total"}]},
        )
        assert response.decorator == "depends"
        assert "sale.order" in response.grouped_by_model


class TestViewUsageResponse:
    def test_view_usage(self) -> None:
        response = ViewUsageResponse(
            model_name="sale.order",
            views=[{"type": "form", "id": 1}],
            field_coverage={"name": 100.0, "partner_id": 85.5},
            unused_fields=["internal_note"],
            total_views=5,
            view_types={"form": 2, "tree": 2, "kanban": 1},
        )
        assert response.model_name == "sale.order"
        assert response.field_coverage["name"] == 100.0
        assert "internal_note" in response.unused_fields
        assert response.view_types["form"] == 2


class TestWorkflowStateResponse:
    def test_workflow_states(self) -> None:
        response = WorkflowStateResponse(
            model_name="sale.order",
            state_field="state",
            states=[{"value": "draft", "label": "Draft"}],
            transitions=[{"from": "draft", "to": "confirmed"}],
            has_workflow=True,
        )
        assert response.state_field == "state"
        assert len(response.states) == 1
        assert response.has_workflow is True

    def test_automated_transitions(self) -> None:
        response = WorkflowStateResponse(
            automated_transitions=[{"trigger": "payment_received", "from": "sale", "to": "done"}],
        )
        assert len(response.automated_transitions) == 1


class TestExecutionResponse:
    def test_successful_execution(self) -> None:
        response = ExecutionResponse(
            code="2 + 2",
            result=4,
            output="",
            execution_time_ms=0.5,
            success=True,
        )
        assert response.result == 4
        assert response.success is True
        assert response.error is None

    def test_failed_execution(self) -> None:
        response = ExecutionResponse(
            code="1 / 0",
            error="ZeroDivisionError: division by zero",
            success=False,
        )
        assert response.success is False
        assert "ZeroDivisionError" in response.error


class TestTestRunnerResponse:
    def test_test_runner_success(self) -> None:
        response = TestRunnerResponse(
            module="sale",
            passed=10,
            failed=0,
            total=10,
            duration_seconds=5.25,
            success=True,
        )
        assert response.passed == 10
        assert response.total == 10
        assert response.success is True

    def test_test_runner_failures(self) -> None:
        response = TestRunnerResponse(
            module="sale",
            test_class="TestSaleOrder",
            passed=8,
            failed=2,
            failures=[{"test": "test_compute", "error": "AssertionError"}],
            success=False,
        )
        assert response.failed == 2
        assert len(response.failures) == 1
        assert response.success is False


class TestFieldValueAnalysis:
    def test_field_value_analysis(self) -> None:
        analysis = FieldValueAnalysis(
            field="partner_id",
            type="many2one",
            total_records=1000,
            non_null_count=950,
            null_count=50,
            unique_count=200,
            data_quality_score=95.0,
        )
        assert analysis.non_null_count == 950
        assert analysis.unique_count == 200
        assert analysis.data_quality_score == 95.0

    def test_field_statistics(self) -> None:
        analysis = FieldValueAnalysis(
            field="amount",
            type="float",
            min_value=0.0,
            max_value=10000.0,
            avg_value=500.0,
            most_common=[(100.0, 50), (200.0, 30)],
        )
        assert analysis.min_value == 0.0
        assert analysis.max_value == 10000.0
        assert len(analysis.most_common) == 2


class TestDynamicFieldResponse:
    def test_dynamic_fields(self) -> None:
        response = DynamicFieldResponse(
            model_name="sale.order",
            computed_fields=[{"name": "total", "depends": ["line_ids"]}],
            related_fields=[{"name": "partner_name", "related": "partner_id.name"}],
            total_dynamic_fields=5,
        )
        assert response.model_name == "sale.order"
        assert len(response.computed_fields) == 1
        assert response.total_dynamic_fields == 5

    def test_circular_dependencies(self) -> None:
        response = DynamicFieldResponse(
            circular_dependencies=[["field1", "field2", "field1"]],
        )
        assert len(response.circular_dependencies) == 1


class TestFieldDependencyResponse:
    def test_field_dependencies(self) -> None:
        response = FieldDependencyResponse(
            model_name="sale.order",
            field_name="total",
            depends_on=[{"field": "line_ids", "type": "one2many"}],
            computation_chain=["line_ids", "line_ids.subtotal", "total"],
            total_dependencies=3,
        )
        assert response.field_name == "total"
        assert len(response.computation_chain) == 3
        assert response.total_dependencies == 3


class TestBaseFieldSearchResponse:
    def test_base_field_search(self) -> None:
        response = BaseFieldSearchResponse(
            results=[{"model": "sale.order", "field": "name"}],
            total_count=25,
            page=2,
            page_size=10,
            has_more=True,
        )
        assert response.total_count == 25
        assert response.page == 2
        assert response.has_more is True

    def test_grouped_results(self) -> None:
        response = BaseFieldSearchResponse(
            grouped_by_model={"sale.order": ["field1", "field2"], "res.partner": ["name"]},
        )
        assert "sale.order" in response.grouped_by_model
        assert len(response.grouped_by_model["sale.order"]) == 2


class TestFieldPropertySearchResponse:
    def test_property_search(self) -> None:
        response = FieldPropertySearchResponse(
            property="required",
            results=[{"model": "sale.order", "field": "partner_id"}],
            total_count=15,
        )
        assert response.property == "required"
        assert response.total_count == 15


class TestFieldTypeSearchResponse:
    def test_type_search(self) -> None:
        response = FieldTypeSearchResponse(
            field_type="many2one",
            results=[{"model": "sale.order", "field": "partner_id"}],
            total_count=50,
        )
        assert response.field_type == "many2one"
        assert response.total_count == 50


class TestOdooStatusResponse:
    def test_odoo_status(self) -> None:
        response = OdooStatusResponse(
            containers={"web": {"status": "running"}, "db": {"status": "running"}},
            database_connected=True,
            database_name="odoo",
            odoo_version="16.0",
            health_status="healthy",
        )
        assert response.database_connected is True
        assert response.odoo_version == "16.0"
        assert response.health_status == "healthy"

    def test_status_with_errors(self) -> None:
        response = OdooStatusResponse(
            database_connected=False,
            health_status="unhealthy",
            errors=["Database connection failed", "Redis not available"],
        )
        assert response.database_connected is False
        assert len(response.errors) == 2
        assert "Database connection failed" in response.errors
