from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

ModelT = TypeVar("ModelT", bound="Model")
FieldValue = str | int | float | bool | list[int] | list[str] | dict[str, object] | None
ValuesDict = dict[str, FieldValue]
FieldsDict = dict[str, dict[str, object]]
DomainTuple = tuple[str, str, object]
Domain = list[DomainTuple]
ContextValue = str | int | bool | list[int] | None
ContextDict = dict[str, ContextValue]

if TYPE_CHECKING:
    type Environment = "odoo.api.Environment"
    type Model = "odoo.models.Model"
    type Cursor = "odoo.sql_db.Cursor"
    type Field = "odoo.fields.Field"

    type ResUsers = "odoo.model.res_users"
    type ResPartner = "odoo.model.res_partner"
    type ResGroups = "odoo.model.res_groups"
    type ResCompany = "odoo.model.res_company"

    type IrModelAccess = "odoo.model.ir_model_access"
    type IrRule = "odoo.model.ir_rule"
    type IrModel = "odoo.model.ir_model"
    type IrModelFields = "odoo.model.ir_model_fields"

    type ProductTemplate = "odoo.model.product_template"
    type ProductProduct = "odoo.model.product_product"
    type MotorProduct = "odoo.model.motor_product"

    type ResPartnerValues = "odoo.values.res_partner"
    type ResUsersValues = "odoo.values.res_users"
    type ProductTemplateValues = "odoo.values.product_template"


else:

    @runtime_checkable
    class Cursor(Protocol):
        def execute(self, query: str, params: tuple[object, ...] | None = None) -> None: ...
        def fetchall(self) -> list[tuple[object, ...]]: ...
        def fetchone(self) -> tuple[object, ...] | None: ...
        def fetchmany(self, size: int = 1) -> list[tuple[object, ...]]: ...
        def commit(self) -> None: ...
        def rollback(self) -> None: ...
        def close(self) -> None: ...

    @runtime_checkable
    class Field(Protocol):
        type: str
        string: str
        required: bool
        readonly: bool
        store: bool
        compute: str | None
        related: str | None

    @runtime_checkable
    class Model(Protocol):
        id: int
        display_name: str
        _fields: dict[str, Field]
        _description: str
        _table: str
        _name: str
        _rec_name: str
        _order: str

        def search(self, domain: Domain = ..., limit: int = ..., offset: int = ..., order: str | None = ...) -> "Model": ...
        def browse(self, ids: int | list[int]) -> "Model": ...
        def create(self, vals: ValuesDict | list[ValuesDict]) -> "Model": ...
        def write(self, vals: ValuesDict) -> bool: ...
        def read(self, fields: list[str] | None = None) -> list[ValuesDict]: ...
        def unlink(self) -> bool: ...
        def exists(self) -> bool: ...
        def ensure_one(self) -> "Model": ...
        def mapped(self, path: str) -> list[FieldValue]: ...
        def filtered(self, func: Callable[["Model"], bool]) -> "Model": ...
        def sorted(self, key: Callable[["Model"], object] | None = None, reverse: bool = False) -> "Model": ...
        def check_access(self, operation: str, raise_exception: bool = True) -> bool: ...

        def __getattr__(self, name: str) -> FieldValue: ...
        def __getitem__(self, key: int) -> "Model": ...
        def __len__(self) -> int: ...
        def __iter__(self) -> Iterator["Model"]: ...
        def __bool__(self) -> bool: ...

    @runtime_checkable
    class Registry(Protocol):
        models: dict[str, type[Model]]

    @runtime_checkable
    class Environment(Protocol):
        registry: Registry

        def __getitem__(self, model_name: str) -> Model: ...
        def __call__(self, *, user: int | None = None, context: ContextDict | None = None) -> "Environment": ...

        @property
        def uid(self) -> int: ...

        @property
        def context(self) -> ContextDict: ...

        @property
        def cr(self) -> Cursor: ...

        @property
        def su(self) -> bool: ...

        def ref(self, xml_id: str, raise_if_not_found: bool = True) -> Model | None: ...
        def is_superuser(self) -> bool: ...
        def user(self) -> Model: ...
        def company(self) -> Model: ...
        def companies(self) -> Model: ...
        def lang(self) -> str: ...
        def __contains__(self, model_name: str) -> bool: ...

    ResUsers = Model
    ResPartner = Model
    ResGroups = Model
    ResCompany = Model
    IrModelAccess = Model
    IrRule = Model
    IrModel = Model
    IrModelFields = Model
    ProductTemplate = Model
    ProductProduct = Model
    MotorProduct = Model

    ResPartnerValues = ValuesDict
    ResUsersValues = ValuesDict
    ProductTemplateValues = ValuesDict


if TYPE_CHECKING:
    CompatibleEnvironment = Environment | "HostOdooEnvironment"
else:
    CompatibleEnvironment = Environment | object

FlexibleEnvironment = Environment | object

OdooEnvironment = Environment
OdooModel = Model
OdooField = Field
