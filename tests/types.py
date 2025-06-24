from typing import Any, Protocol


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
