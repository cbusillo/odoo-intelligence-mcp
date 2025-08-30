from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from ..type_defs.odoo_types import CompatibleEnvironment, Field, Model


class ModelIterator:
    def __init__(self, env: CompatibleEnvironment, exclude_system_models: bool = True) -> None:
        self.env = env
        self.exclude_system_models = exclude_system_models

    async def iter_models(self, filter_func: Callable[[str], bool] | None = None) -> AsyncIterator[tuple[str, Model]]:
        model_names = await self.env.get_model_names()
        for model_name in model_names:
            if self.exclude_system_models and self._is_system_model(model_name):
                continue

            if filter_func and not filter_func(model_name):
                continue

            yield model_name, self.env[model_name]

    def iter_model_fields(
        self, model_name: str, field_filter: Callable[[str, Field], bool] | None = None
    ) -> Iterator[tuple[str, Field]]:
        if model_name not in self.env:
            return  # Early return in generator function produces empty iterator

        model = self.env[model_name]
        # noinspection PyProtectedMember
        for field_name, field in model._fields.items():
            if field_filter and not field_filter(field_name, field):
                continue
            yield field_name, field

    @staticmethod
    def _is_system_model(model_name: str) -> bool:
        system_prefixes = ("ir.", "res.", "base.", "_")
        return model_name.startswith(system_prefixes)


def extract_field_info(field: Field) -> dict[str, Any]:
    return {
        "type": field.type,
        "string": getattr(field, "string", ""),
        "required": getattr(field, "required", False),
        "readonly": getattr(field, "readonly", False),
        "store": getattr(field, "store", True),
        "compute": getattr(field, "compute", None),
        "related": getattr(field, "related", None),
        "help": getattr(field, "help", ""),
    }


def extract_model_info(model: Model) -> dict[str, Any]:
    # noinspection PyProtectedMember
    return {
        "name": model._name,
        "description": getattr(model, "_description", ""),
        "table": getattr(model, "_table", ""),
        "rec_name": getattr(model, "_rec_name", "name"),
        "order": getattr(model, "_order", "id"),
        "auto": getattr(model, "_auto", True),
        "abstract": getattr(model, "_abstract", False),
        "transient": getattr(model, "_transient", False),
    }
