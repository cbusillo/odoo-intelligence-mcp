from typing import Any, Literal, NotRequired, Protocol, TypedDict


class FieldInfo(TypedDict):
    type: str
    string: str
    required: bool
    readonly: bool
    store: bool
    relation: NotRequired[str]
    selection: NotRequired[list[tuple[str, str]] | str]
    related: NotRequired[str]
    compute: NotRequired[str]
    inverse: NotRequired[str]
    inverse_name: NotRequired[str]
    relation_table: NotRequired[str]


class ModelInfo(TypedDict):
    name: str
    table: str
    description: str
    rec_name: str
    order: str
    fields: dict[str, FieldInfo]
    field_count: int
    methods: list[str]
    method_count: int


class ErrorResponse(TypedDict):
    error: str


class SuccessResponse(TypedDict):
    success: bool
    data: NotRequired[Any]
    error: NotRequired[str]
    error_type: NotRequired[str]


class ViewInfo(TypedDict):
    id: int
    name: str
    type: str
    inherit_id: str | None


class DomainUsage(TypedDict):
    type: str
    name: str
    domain: str
    user: NotRequired[str]


class MethodUsage(TypedDict):
    type: Literal["compute", "constraint", "onchange", "method"]
    method: str
    field: NotRequired[str]
    depends: NotRequired[list[str]]
    constrains: NotRequired[list[str]]
    onchange: NotRequired[list[str]]


class FieldUsageInfo(TypedDict):
    model: str
    field: str
    field_info: FieldInfo
    used_in_views: list[ViewInfo]
    used_in_domains: list[DomainUsage]
    used_in_methods: list[MethodUsage]
    usage_summary: dict[str, int]


class RelationInfo(TypedDict):
    field: str
    type: Literal["many2one", "one2many", "many2many"]
    target_model: str
    inverse_field: NotRequired[str]
    relation_table: NotRequired[str]


class ModelRelationships(TypedDict):
    model: str
    many2one_fields: list[RelationInfo]
    one2many_fields: list[RelationInfo]
    many2many_fields: list[RelationInfo]
    reverse_relationships: dict[str, list[dict[str, str]]]
    summary: dict[str, int]


class PerformanceIssue(TypedDict):
    type: str
    severity: Literal["critical", "warning", "info"]
    field: NotRequired[str]
    description: str
    recommendation: str


class PerformanceAnalysis(TypedDict):
    model: str
    issues: list[PerformanceIssue]
    recommendations: list[str]
    summary: dict[str, int]


class ModelInfoArgs(TypedDict):
    model_name: str


class SearchModelsArgs(TypedDict):
    pattern: str


class ModelRelationshipsArgs(TypedDict):
    model_name: str


class FieldUsagesArgs(TypedDict):
    model_name: str
    field_name: str


class PerformanceAnalysisArgs(TypedDict):
    model_name: str


class PatternAnalysisArgs(TypedDict):
    pattern_type: NotRequired[
        Literal["computed_fields", "related_fields", "api_decorators", "custom_methods", "state_machines", "all"]
    ]
    page: NotRequired[int]
    page_size: NotRequired[int]
    offset: NotRequired[int]
    limit: NotRequired[int]
    filter: NotRequired[str]


class InheritanceChainArgs(TypedDict):
    model_name: str


class AddonDependenciesArgs(TypedDict):
    addon_name: str


class SearchCodeArgs(TypedDict):
    pattern: str
    file_type: NotRequired[str]
    page: NotRequired[int]
    page_size: NotRequired[int]
    offset: NotRequired[int]
    limit: NotRequired[int]
    filter: NotRequired[str]


class ModuleStructureArgs(TypedDict):
    module_name: str


class FindMethodArgs(TypedDict):
    method_name: str
    page: NotRequired[int]
    page_size: NotRequired[int]
    offset: NotRequired[int]
    limit: NotRequired[int]
    filter: NotRequired[str]


class SearchDecoratorsArgs(TypedDict):
    decorator: Literal["depends", "constrains", "onchange", "model_create_multi"]


class ViewModelUsageArgs(TypedDict):
    model_name: str


class WorkflowStatesArgs(TypedDict):
    model_name: str


class ExecuteCodeArgs(TypedDict):
    code: str


class TestRunnerArgs(TypedDict):
    module: str
    test_class: NotRequired[str]
    test_method: NotRequired[str]
    test_tags: NotRequired[str]


class FieldValueAnalyzerArgs(TypedDict):
    model: str
    field: str
    domain: NotRequired[list[list]]
    sample_size: NotRequired[int]


class PermissionCheckerArgs(TypedDict):
    user: str
    model: str
    operation: Literal["read", "write", "create", "unlink"]
    record_id: NotRequired[int]


class ResolveDynamicFieldsArgs(TypedDict):
    model_name: str


class FieldDependenciesArgs(TypedDict):
    model_name: str
    field_name: str


class SearchFieldPropertiesArgs(TypedDict):
    property: Literal["computed", "related", "stored", "required", "readonly"]
    page: NotRequired[int]
    page_size: NotRequired[int]
    offset: NotRequired[int]
    limit: NotRequired[int]
    filter: NotRequired[str]


class SearchFieldTypeArgs(TypedDict):
    field_type: Literal[
        "many2one",
        "one2many",
        "many2many",
        "char",
        "text",
        "integer",
        "float",
        "boolean",
        "date",
        "datetime",
        "binary",
        "selection",
        "json",
    ]
    page: NotRequired[int]
    page_size: NotRequired[int]
    offset: NotRequired[int]
    limit: NotRequired[int]
    filter: NotRequired[str]


class OdooUpdateModuleArgs(TypedDict):
    modules: str
    force_install: NotRequired[bool]


class OdooShellArgs(TypedDict):
    code: str
    timeout: NotRequired[int]


class OdooStatusArgs(TypedDict):
    pass


class OdooRestartArgs(TypedDict):
    services: NotRequired[str]


class OdooInstallModuleArgs(TypedDict):
    modules: str


class OdooLogsArgs(TypedDict):
    container: NotRequired[str]
    lines: NotRequired[int]


ToolArguments = (
    ModelInfoArgs
    | SearchModelsArgs
    | ModelRelationshipsArgs
    | FieldUsagesArgs
    | PerformanceAnalysisArgs
    | PatternAnalysisArgs
    | InheritanceChainArgs
    | AddonDependenciesArgs
    | SearchCodeArgs
    | ModuleStructureArgs
    | FindMethodArgs
    | SearchDecoratorsArgs
    | ViewModelUsageArgs
    | WorkflowStatesArgs
    | ExecuteCodeArgs
    | TestRunnerArgs
    | FieldValueAnalyzerArgs
    | PermissionCheckerArgs
    | ResolveDynamicFieldsArgs
    | FieldDependenciesArgs
    | SearchFieldPropertiesArgs
    | SearchFieldTypeArgs
    | OdooUpdateModuleArgs
    | OdooShellArgs
    | OdooStatusArgs
    | OdooRestartArgs
    | OdooInstallModuleArgs
    | OdooLogsArgs
)


class OdooEnvironment(Protocol):
    def __getitem__(self, model_name: str) -> object: ...

    @property
    def cr(self) -> object: ...

    @property
    def registry(self) -> dict[str, object]: ...
