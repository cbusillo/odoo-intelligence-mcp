from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast
from unittest.mock import MagicMock

from odoo_intelligence_mcp.type_defs.odoo_types import Environment, Field, Model


class PytestConfig(Protocol):
    # noinspection SpellCheckingInspection
    def addinivalue_line(self, name: str, line: str) -> None: ...


class MockEnvironment(Protocol):
    def __getitem__(self, model_name: str) -> Any: ...
    def __contains__(self, model_name: str) -> bool: ...


class MockModel(Protocol):
    _name: str
    _fields: dict[str, Any]
    _description: str

    def search(self, domain: list[Any], limit: int | None = None) -> Any: ...
    def search_count(self, domain: list[Any]) -> int: ...
    def browse(self, ids: int | list[int]) -> Any: ...


MockEnvFixture = Any
MockFieldFixture = Any
MockRegistryFixture = dict[str, type[MockModel]]


class MockSubprocessRun(Protocol):
    return_value: MockCompletedProcess
    side_effect: Exception | None

    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
        timeout: float | None = None,
        **kwargs: object,
    ) -> MockCompletedProcess: ...

    def assert_called_once(self) -> None: ...
    def assert_called_once_with(self, *args: object, **kwargs: object) -> None: ...
    @property
    def call_args(self) -> tuple[tuple[object, ...], dict[str, object]]: ...


class MockCompletedProcess(Protocol):
    returncode: int
    stdout: str | bytes
    stderr: str | bytes
    args: list[str] | str


class MockOdooModel(Protocol):
    _name: str
    _fields: dict[str, MockField]
    _inherit: str | list[str] | None
    _inherits: dict[str, str] | None
    _description: str | None
    _rec_name: str | None
    _order: str | None
    _auto: bool
    _register: bool
    _abstract: bool
    _transient: bool

    def search(self, domain: list[tuple[str, str, object]] | None = None, **kwargs: object) -> MockRecordset: ...
    def browse(self, ids: int | list[int]) -> MockRecordset: ...
    def create(self, vals: dict[str, object]) -> MockRecordset: ...
    def fields_get(self, allfields: list[str] | None = None, **kwargs: object) -> dict[str, dict[str, object]]: ...


class MockField(Protocol):
    type: str
    string: str
    required: bool
    readonly: bool
    store: bool
    compute: str | None
    inverse: str | None
    search: str | None
    related: str | None
    comodel_name: str | None
    relation: str | None
    relation_field: str | None
    selection: list[tuple[str, str]] | None
    size: int | None
    help: str | None
    default: object


class MockRecordset(Protocol):
    ids: list[int]
    _name: str

    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...
    def __iter__(self) -> MockRecordset: ...
    def __next__(self) -> MockRecord: ...
    def exists(self) -> MockRecordset: ...
    def mapped(self, field_name: str) -> list[object]: ...


class MockRecord(Protocol):
    id: int
    _name: str

    def __getattr__(self, name: str) -> object: ...
    def __setattr__(self, name: str, value: object) -> None: ...
    def exists(self) -> bool: ...


class MockOdooEnvironment(Protocol):
    cr: MockCursor
    uid: int
    context: dict[str, object]
    su: bool
    lang: str | None
    user: MockRecord
    company: MockRecord
    companies: MockRecordset
    registry: MockRegistry

    def __getitem__(self, model_name: str) -> MockOdooModel: ...
    def __contains__(self, model_name: str) -> bool: ...
    def ref(self, xml_id: str) -> MockRecord | None: ...
    def is_superuser(self) -> bool: ...
    def is_admin(self) -> bool: ...
    def is_system(self) -> bool: ...


class MockRegistry(Protocol):
    models: dict[str, type[MockOdooModel]]

    def __getitem__(self, model_name: str) -> type[MockOdooModel]: ...
    def __contains__(self, model_name: str) -> bool: ...
    def __iter__(self) -> list[str]: ...


class MockCursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None: ...
    def fetchall(self) -> list[tuple[object, ...]]: ...
    def fetchone(self) -> tuple[object, ...] | None: ...


class MockPath(Protocol):
    name: str
    parent: MockPath
    parts: tuple[str, ...]
    exists_called: bool
    is_file_called: bool
    read_text_called: bool
    suffix: str

    def __str__(self) -> str: ...
    def __truediv__(self, other: str | Path) -> MockPath: ...
    def exists(self) -> bool: ...
    def is_file(self) -> bool: ...
    def is_dir(self) -> bool: ...
    def read_text(self, encoding: str = "utf-8") -> str: ...
    def write_text(self, content: str, encoding: str = "utf-8") -> int: ...
    def mkdir(self, parents: bool = False, exist_ok: bool = False) -> None: ...
    def unlink(self, missing_ok: bool = False) -> None: ...
    def glob(self, pattern: str) -> list[MockPath]: ...
    def rglob(self, pattern: str) -> list[MockPath]: ...
    def relative_to(self, other: MockPath | Path) -> MockPath: ...


def as_environment(mock_environment: MagicMock) -> Environment:
    return cast(Environment, cast(object, mock_environment))


def as_field(mock_field: MagicMock) -> Field:
    return cast(Field, cast(object, mock_field))


def as_model(mock_model: MagicMock) -> Model:
    return cast(Model, cast(object, mock_model))


class ConcreteModelMock:
    def __init__(
        self,
        name: str = "test.model",
        fields: dict[str, MagicMock] | None = None,
        inherit: str | list[str] | None = None,
        description: str | None = None,
    ) -> None:
        self._name = name
        self._fields = fields or {}
        self._inherit = inherit
        self._description = description or f"Test model {name}"
        self._rec_name = "name"
        self._order = "id"
        self._auto = True
        self._register = True
        self._abstract = False
        self._transient = False

        # Mock methods
        self.search = MagicMock(return_value=MagicMock(ids=[]))
        self.browse = MagicMock(return_value=MagicMock(ids=[]))
        self.create = MagicMock(return_value=MagicMock(id=1))
        self.fields_get = MagicMock(return_value={})
        self.name_search = MagicMock(return_value=[])
        self.read = MagicMock(return_value=[])
        self.write = MagicMock(return_value=True)
        self.unlink = MagicMock(return_value=True)
        self.copy = MagicMock(return_value=MagicMock(id=2))
        self.default_get = MagicMock(return_value={})
        self.name_get = MagicMock(return_value=[])

    def __getattr__(self, name: str) -> object:
        if name in self._fields:
            return self._fields[name]
        return MagicMock()

    def __repr__(self) -> str:
        return f"<MockModel {self._name}>"
