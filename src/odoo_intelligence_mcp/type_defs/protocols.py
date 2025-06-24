from typing import Protocol, runtime_checkable


@runtime_checkable
class OdooModelProtocol(Protocol):
    _name: str
    _table: str
    _description: str
    _fields: dict[str, object]
    _rec_name: str
    _order: str

    def search(self, domain: list | None = None, limit: int | None = None, offset: int = 0) -> list["OdooModelProtocol"]: ...

    def search_count(self, domain: list | None = None) -> int: ...

    def fields_get(self, allfields: bool = True) -> dict[str, dict[str, object]]: ...


@runtime_checkable
class OdooEnvironmentProtocol(Protocol):
    def __getitem__(self, model_name: str) -> OdooModelProtocol: ...

    @property
    def cr(self) -> object: ...

    @property
    def registry(self) -> dict[str, object]: ...
