from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock


class MockSubprocessRun(Protocol):
    return_value: "MockCompletedProcess"
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
    ) -> "MockCompletedProcess": ...

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
    _fields: dict[str, "MockField"]
    _inherit: str | list[str] | None
    _inherits: dict[str, str] | None
    _description: str | None
    _rec_name: str | None
    _order: str | None
    _auto: bool
    _register: bool
    _abstract: bool
    _transient: bool

    def search(self, domain: list[tuple[str, str, object]] | None = None, **kwargs: object) -> "MockRecordset": ...
    def browse(self, ids: int | list[int]) -> "MockRecordset": ...
    def create(self, vals: dict[str, object]) -> "MockRecordset": ...
    def fields_get(self, allfields: list[str] | None = None, **kwargs: object) -> dict[str, dict[str, object]]: ...


class MockField(Protocol):
    type: str
    string: str
    required: bool
    readonly: bool
    store: bool
    compute: str | None
    related: str | None
    comodel_name: str | None
    inverse_name: str | None
    relation: str | None
    column1: str | None
    column2: str | None
    domain: list[tuple[str, str, object]] | None
    help: str | None
    selection: list[tuple[str, str]] | None


class MockRecordset(Protocol):
    _name: str
    ids: list[int]

    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...
    def __iter__(self) -> "MockRecordset": ...
    def __getitem__(self, index: int) -> "MockRecord": ...
    def mapped(self, field_name: str) -> list[object]: ...
    def filtered(self, func: object) -> "MockRecordset": ...
    def sorted(self, key: str | None = None, reverse: bool = False) -> "MockRecordset": ...


class MockRecord(Protocol):
    id: int
    display_name: str
    create_date: object | None
    write_date: object | None

    def __getattr__(self, name: str) -> object: ...


class MockOdooEnvironment(Protocol):
    @property
    def registry(self) -> "MockRegistry": ...

    @property
    def uid(self) -> int: ...

    @property
    def context(self) -> dict[str, object]: ...

    @property
    def cr(self) -> "MockCursor": ...

    @property
    def user(self) -> MockRecord: ...

    @property
    def company(self) -> MockRecord: ...

    @property
    def lang(self) -> str: ...

    def __getitem__(self, model_name: str) -> MockOdooModel: ...
    def ref(self, xml_id: str) -> MockRecord | None: ...


class MockRegistry(Protocol):
    @property
    def models(self) -> dict[str, type[MockOdooModel]]: ...

    def __len__(self) -> int: ...
    def __contains__(self, model_name: str) -> bool: ...
    def __getitem__(self, model_name: str) -> type[MockOdooModel]: ...


class MockCursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None: ...
    def fetchall(self) -> list[tuple[object, ...]]: ...
    def fetchone(self) -> tuple[object, ...] | None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class MockPath(Protocol):
    def exists(self) -> bool: ...
    def is_file(self) -> bool: ...
    def is_dir(self) -> bool: ...
    def read_text(self, encoding: str = "utf-8") -> str: ...
    def write_text(self, data: str, encoding: str = "utf-8") -> int: ...
    def glob(self, pattern: str) -> list[Path]: ...
    def rglob(self, pattern: str) -> list[Path]: ...
    def open(self, mode: str = "r", **kwargs: object) -> object: ...

    @property
    def name(self) -> str: ...

    @property
    def stem(self) -> str: ...

    @property
    def suffix(self) -> str: ...

    @property
    def parent(self) -> Path: ...


# Type aliases for common mock patterns
MockMagicMock = MagicMock  # When we truly need a dynamic mock
MockFunction = MagicMock  # For mocked functions with unknown signatures


# Concrete mock implementation for tests
class ConcreteModelMock:
    """A concrete mock model class that satisfies type[Model] requirements for tests."""

    _name: str = "mock.model"
    _fields: dict = {}
    _description: str = "Mock Model"
    _table: str = "mock_model"
    _rec_name: str = "name"
    _order: str = "id"
    id: int = 1
    display_name: str = "Mock Model"
