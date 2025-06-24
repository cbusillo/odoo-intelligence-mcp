from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from .base import BaseModel
from .odoo_models import OdooField, OdooModel, OdooRelationship


@dataclass
class ModelInfoResponse(BaseModel):
    model: OdooModel = dataclass_field(default_factory=OdooModel)
    field_count: int = 0
    method_count: int = 0
    relationship_count: int = 0
    has_workflow: bool = False
    is_abstract: bool = False
    is_transient: bool = False
    inherited_from: list[str] = dataclass_field(default_factory=list)
    extended_by: list[str] = dataclass_field(default_factory=list)
    used_in_views: list[str] = dataclass_field(default_factory=list)
    access_rights: dict[str, bool] = dataclass_field(default_factory=dict)
    record_count: int | None = None


@dataclass
class FieldAnalysisResponse(BaseModel):
    field: OdooField = dataclass_field(default_factory=OdooField)
    model_name: str = ""
    usage_count: int = 0
    used_in_views: list[str] = dataclass_field(default_factory=list)
    used_in_methods: list[str] = dataclass_field(default_factory=list)
    used_in_domains: list[str] = dataclass_field(default_factory=list)
    used_in_reports: list[str] = dataclass_field(default_factory=list)
    depends_on: list[str] = dataclass_field(default_factory=list)
    depended_by: list[str] = dataclass_field(default_factory=list)
    has_index: bool = False
    is_searchable: bool = True
    is_sortable: bool = True
    is_groupable: bool = True


@dataclass
class PermissionCheckResponse(BaseModel):
    user: str = ""
    model: str = ""
    operation: str = ""
    record_id: int | None = None
    allowed: bool = False
    reason: str = ""
    access_rights: dict[str, bool] = dataclass_field(default_factory=dict)
    record_rules: list[dict[str, Any]] = dataclass_field(default_factory=list)
    field_rights: dict[str, dict[str, bool]] = dataclass_field(default_factory=dict)
    groups: list[str] = dataclass_field(default_factory=list)
    sudo_required: bool = False


@dataclass
class SearchModelResponse(BaseModel):
    pattern: str = ""
    exact_matches: list[dict[str, Any]] = dataclass_field(default_factory=list)
    partial_matches: list[dict[str, Any]] = dataclass_field(default_factory=list)
    description_matches: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_matches: int = 0
    search_time_ms: float = 0.0


@dataclass
class RelationshipAnalysisResponse(BaseModel):
    model_name: str = ""
    many2one_fields: list[OdooRelationship] = dataclass_field(default_factory=list)
    one2many_fields: list[OdooRelationship] = dataclass_field(default_factory=list)
    many2many_fields: list[OdooRelationship] = dataclass_field(default_factory=list)
    reverse_relationships: list[OdooRelationship] = dataclass_field(default_factory=list)
    relationship_graph: dict[str, list[str]] = dataclass_field(default_factory=dict)
    circular_dependencies: list[list[str]] = dataclass_field(default_factory=list)
    total_relationships: int = 0


@dataclass
class FieldUsageResponse(BaseModel):
    model_name: str = ""
    field_name: str = ""
    views: list[dict[str, Any]] = dataclass_field(default_factory=list)
    methods: list[dict[str, Any]] = dataclass_field(default_factory=list)
    domains: list[dict[str, Any]] = dataclass_field(default_factory=list)
    reports: list[dict[str, Any]] = dataclass_field(default_factory=list)
    computed_fields: list[dict[str, Any]] = dataclass_field(default_factory=list)
    related_fields: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_usages: int = 0


@dataclass
class PerformanceIssue:
    type: str = ""
    severity: str = ""  # low, medium, high, critical
    description: str = ""
    location: str = ""
    suggestion: str = ""
    estimated_impact: str = ""
    query_example: str | None = None
    affected_records: int | None = None


@dataclass
class PerformanceAnalysisResponse(BaseModel):
    model_name: str = ""
    issues: list[PerformanceIssue] = dataclass_field(default_factory=list)
    missing_indexes: list[str] = dataclass_field(default_factory=list)
    n_plus_one_queries: list[dict[str, Any]] = dataclass_field(default_factory=list)
    inefficient_domains: list[dict[str, Any]] = dataclass_field(default_factory=list)
    large_computed_fields: list[str] = dataclass_field(default_factory=list)
    missing_store_flags: list[str] = dataclass_field(default_factory=list)
    prefetch_suggestions: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_issues: int = 0
    performance_score: float = 100.0


@dataclass
class PatternAnalysisResponse(BaseModel):
    pattern_type: str = ""
    patterns: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 100
    has_more: bool = False
    statistics: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass
class InheritanceChainResponse(BaseModel):
    model_name: str = ""
    mro: list[str] = dataclass_field(default_factory=list)
    inherit: list[str] = dataclass_field(default_factory=list)
    inherits: dict[str, str] = dataclass_field(default_factory=dict)
    inherited_fields: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)
    overridden_methods: list[str] = dataclass_field(default_factory=list)
    extended_by: list[str] = dataclass_field(default_factory=list)
    inheritance_depth: int = 0
    is_abstract: bool = False
    is_mixin: bool = False


@dataclass
class AddonDependencyResponse(BaseModel):
    addon_name: str = ""
    manifest: dict[str, Any] = dataclass_field(default_factory=dict)
    depends: list[str] = dataclass_field(default_factory=list)
    dependents: list[str] = dataclass_field(default_factory=list)
    external_dependencies: dict[str, list[str]] = dataclass_field(default_factory=dict)
    auto_install: bool = False
    installable: bool = True
    application: bool = False
    category: str = ""
    version: str = ""
    author: str = ""
    website: str = ""
    license: str = ""
    summary: str = ""
    models: list[str] = dataclass_field(default_factory=list)
    views: list[str] = dataclass_field(default_factory=list)
    data_files: list[str] = dataclass_field(default_factory=list)


@dataclass
class CodeSearchResult:
    file_path: str = ""
    line_number: int = 0
    line_content: str = ""
    match_context: list[str] = dataclass_field(default_factory=list)
    module: str = ""
    model: str | None = None
    method: str | None = None


@dataclass
class ModuleStructureResponse(BaseModel):
    module_name: str = ""
    path: str = ""
    manifest: dict[str, Any] = dataclass_field(default_factory=dict)
    models: list[dict[str, Any]] = dataclass_field(default_factory=list)
    views: list[dict[str, Any]] = dataclass_field(default_factory=list)
    controllers: list[dict[str, Any]] = dataclass_field(default_factory=list)
    wizards: list[dict[str, Any]] = dataclass_field(default_factory=list)
    reports: list[dict[str, Any]] = dataclass_field(default_factory=list)
    security: dict[str, Any] = dataclass_field(default_factory=dict)
    data_files: list[str] = dataclass_field(default_factory=list)
    static_files: dict[str, list[str]] = dataclass_field(default_factory=dict)
    python_files: int = 0
    xml_files: int = 0
    js_files: int = 0
    total_lines: int = 0


@dataclass
class MethodSearchResponse(BaseModel):
    method_name: str = ""
    results: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 100
    has_more: bool = False


@dataclass
class DecoratorSearchResponse(BaseModel):
    decorator: str = ""
    results: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_count: int = 0
    grouped_by_model: dict[str, list[dict[str, Any]]] = dataclass_field(default_factory=dict)


@dataclass
class ViewUsageResponse(BaseModel):
    model_name: str = ""
    views: list[dict[str, Any]] = dataclass_field(default_factory=list)
    field_coverage: dict[str, float] = dataclass_field(default_factory=dict)
    unused_fields: list[str] = dataclass_field(default_factory=list)
    buttons: list[dict[str, Any]] = dataclass_field(default_factory=list)
    actions: list[dict[str, Any]] = dataclass_field(default_factory=list)
    menus: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_views: int = 0
    view_types: dict[str, int] = dataclass_field(default_factory=dict)


@dataclass
class WorkflowStateResponse(BaseModel):
    model_name: str = ""
    state_field: str | None = None
    states: list[dict[str, Any]] = dataclass_field(default_factory=list)
    transitions: list[dict[str, Any]] = dataclass_field(default_factory=list)
    buttons: list[dict[str, Any]] = dataclass_field(default_factory=list)
    automated_transitions: list[dict[str, Any]] = dataclass_field(default_factory=list)
    state_dependencies: dict[str, list[str]] = dataclass_field(default_factory=dict)
    has_workflow: bool = False


@dataclass
class ExecutionResponse(BaseModel):
    code: str = ""
    result: Any = None
    output: str = ""
    error: str | None = None
    execution_time_ms: float = 0.0
    success: bool = True


@dataclass
class TestRunnerResponse(BaseModel):
    module: str = ""
    test_class: str | None = None
    test_method: str | None = None
    test_tags: str | None = None
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_seconds: float = 0.0
    output: str = ""
    failures: list[dict[str, Any]] = dataclass_field(default_factory=list)
    success: bool = True


@dataclass
class FieldValueAnalysis:
    field: str = ""
    type: str = ""
    total_records: int = 0
    non_null_count: int = 0
    null_count: int = 0
    unique_count: int = 0
    min_value: Any = None
    max_value: Any = None
    avg_value: Any = None
    most_common: list[tuple] = dataclass_field(default_factory=list)
    sample_values: list[Any] = dataclass_field(default_factory=list)
    value_distribution: dict[str, int] = dataclass_field(default_factory=dict)
    data_quality_score: float = 100.0
    issues: list[str] = dataclass_field(default_factory=list)


@dataclass
class DynamicFieldResponse(BaseModel):
    model_name: str = ""
    computed_fields: list[dict[str, Any]] = dataclass_field(default_factory=list)
    related_fields: list[dict[str, Any]] = dataclass_field(default_factory=list)
    cross_model_dependencies: dict[str, list[str]] = dataclass_field(default_factory=dict)
    runtime_patterns: list[dict[str, Any]] = dataclass_field(default_factory=list)
    circular_dependencies: list[list[str]] = dataclass_field(default_factory=list)
    total_dynamic_fields: int = 0


@dataclass
class FieldDependencyResponse(BaseModel):
    model_name: str = ""
    field_name: str = ""
    depends_on: list[dict[str, Any]] = dataclass_field(default_factory=list)
    depended_by: list[dict[str, Any]] = dataclass_field(default_factory=list)
    dependency_graph: dict[str, list[str]] = dataclass_field(default_factory=dict)
    computation_chain: list[str] = dataclass_field(default_factory=list)
    circular_dependencies: list[list[str]] = dataclass_field(default_factory=list)
    total_dependencies: int = 0


@dataclass
class BaseFieldSearchResponse(BaseModel):
    results: list[dict[str, Any]] = dataclass_field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 100
    has_more: bool = False
    grouped_by_model: dict[str, list[str]] = dataclass_field(default_factory=dict)


@dataclass
class FieldPropertySearchResponse(BaseFieldSearchResponse):
    property: str = ""


@dataclass
class FieldTypeSearchResponse(BaseFieldSearchResponse):
    field_type: str = ""


@dataclass
class OdooStatusResponse(BaseModel):
    containers: dict[str, dict[str, Any]] = dataclass_field(default_factory=dict)
    database_connected: bool = False
    database_name: str | None = None
    odoo_version: str | None = None
    installed_modules: list[str] = dataclass_field(default_factory=list)
    python_version: str | None = None
    system_info: dict[str, Any] = dataclass_field(default_factory=dict)
    health_status: str = "unknown"
    errors: list[str] = dataclass_field(default_factory=list)
