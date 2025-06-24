from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from .base import BaseModel


@dataclass
class OdooField(BaseModel):
    name: str = ""
    type: str = ""
    string: str = ""
    required: bool = False
    readonly: bool = False
    store: bool = True
    compute: str | None = None
    related: str | None = None
    inverse: str | None = None
    depends: list[str] = dataclass_field(default_factory=list)
    help: str = ""
    default: Any = None
    selection: list[tuple] | None = None
    size: int | None = None
    digits: tuple | None = None
    comodel_name: str | None = None
    domain: str | None = None
    context: dict[str, Any] | None = None
    ondelete: str | None = None
    auto_join: bool = False
    delegate: bool = False
    copy: bool = True
    index: bool = False
    translate: bool = False
    sanitize: bool = True
    strip: bool = True
    groups: str | None = None
    states: dict[str, list[tuple]] | None = None
    change_default: bool = False
    deprecated: bool = False
    tracking: int | None = None
    group_expand: str | None = None
    group_operator: str | None = None
    attachment: bool = False
    prefetch: bool = True


@dataclass
class OdooRelationship(BaseModel):
    field_name: str = ""
    source_model: str = ""
    target_model: str = ""
    type: str = ""  # many2one, one2many, many2many
    inverse_field: str | None = None
    intermediate_model: str | None = None  # For many2many
    column1: str | None = None  # For many2many
    column2: str | None = None  # For many2many
    domain: str | None = None
    context: dict[str, Any] | None = None
    auto_join: bool = False
    delegate: bool = False
    ondelete: str | None = None


@dataclass
class OdooMethod(BaseModel):
    name: str = ""
    model: str = ""
    decorators: list[str] = dataclass_field(default_factory=list)
    parameters: list[str] = dataclass_field(default_factory=list)
    returns: str | None = None
    docstring: str | None = None
    is_private: bool = False
    is_api_method: bool = False
    depends_on: list[str] = dataclass_field(default_factory=list)
    constrains: list[str] = dataclass_field(default_factory=list)
    onchange: list[str] = dataclass_field(default_factory=list)
    line_number: int | None = None
    file_path: str | None = None


@dataclass
class OdooDecorator(BaseModel):
    name: str = ""
    type: str = ""  # depends, constrains, onchange, model_create_multi, etc.
    model: str = ""
    method: str = ""
    arguments: list[str] = dataclass_field(default_factory=list)
    line_number: int | None = None
    file_path: str | None = None


@dataclass
class OdooInheritance(BaseModel):
    model: str = ""
    inherit: list[str] = dataclass_field(default_factory=list)
    inherits: dict[str, str] = dataclass_field(default_factory=dict)
    inherited_fields: dict[str, str] = dataclass_field(default_factory=dict)
    mro: list[str] = dataclass_field(default_factory=list)
    abstract: bool = False
    transient: bool = False
    auto: bool = True


@dataclass
class OdooModel(BaseModel):
    name: str = ""
    table: str = ""
    description: str = ""
    module: str = ""
    fields: dict[str, OdooField] = dataclass_field(default_factory=dict)
    methods: list[OdooMethod] = dataclass_field(default_factory=list)
    relationships: list[OdooRelationship] = dataclass_field(default_factory=list)
    inheritance: OdooInheritance | None = None
    rec_name: str = "name"
    order: str = "id"
    auto: bool = True
    abstract: bool = False
    transient: bool = False
    inherits: dict[str, str] = dataclass_field(default_factory=dict)
    inherit: list[str] = dataclass_field(default_factory=list)
    sql_constraints: list[tuple] = dataclass_field(default_factory=list)
    constraints: list[OdooMethod] = dataclass_field(default_factory=list)
    compute_fields: list[str] = dataclass_field(default_factory=list)
    related_fields: list[str] = dataclass_field(default_factory=list)
    required_fields: list[str] = dataclass_field(default_factory=list)
    readonly_fields: list[str] = dataclass_field(default_factory=list)
    selection_fields: dict[str, list[tuple]] = dataclass_field(default_factory=dict)
    default_values: dict[str, Any] = dataclass_field(default_factory=dict)
    groups: dict[str, str] = dataclass_field(default_factory=dict)
    states: dict[str, dict[str, list[tuple]]] = dataclass_field(default_factory=dict)

    def get_dataclass_field(self, field_name: str) -> OdooField | None:
        return self.fields.get(field_name)

    def get_relational_fields(self) -> dict[str, OdooField]:
        relational_types = {"many2one", "one2many", "many2many"}
        return {name: field for name, field in self.fields.items() if field.type in relational_types}

    def get_computed_fields(self) -> dict[str, OdooField]:
        return {name: field for name, field in self.fields.items() if field.compute}

    def get_related_fields(self) -> dict[str, OdooField]:
        return {name: field for name, field in self.fields.items() if field.related}

    def get_stored_fields(self) -> dict[str, OdooField]:
        return {name: field for name, field in self.fields.items() if field.store}

    def get_required_fields(self) -> dict[str, OdooField]:
        return {name: field for name, field in self.fields.items() if field.required}

    def get_methods_by_decorator(self, decorator_type: str) -> list[OdooMethod]:
        return [method for method in self.methods if decorator_type in method.decorators]

    def get_api_methods(self) -> list[OdooMethod]:
        return [method for method in self.methods if method.is_api_method]

    def get_constraint_methods(self) -> list[OdooMethod]:
        return self.get_methods_by_decorator("constrains")

    def get_compute_methods(self) -> list[OdooMethod]:
        return self.get_methods_by_decorator("depends")

    def get_onchange_methods(self) -> list[OdooMethod]:
        return self.get_methods_by_decorator("onchange")
