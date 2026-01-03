import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any

from ..type_defs.odoo_types import CompatibleEnvironment, Field, Model
from .error_utils import CodeExecutionError


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
            return

        model = self.env[model_name]
        fields_by_name = getattr(model, "_fields", {})
        if not isinstance(fields_by_name, dict):
            return
        for field_name, field in fields_by_name.items():
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
    return {
        "name": getattr(model, "_name", ""),
        "description": getattr(model, "_description", ""),
        "table": getattr(model, "_table", ""),
        "rec_name": getattr(model, "_rec_name", "name"),
        "order": getattr(model, "_order", "id"),
        "auto": getattr(model, "_auto", True),
        "abstract": getattr(model, "_abstract", False),
        "transient": getattr(model, "_transient", False),
    }


@dataclass(frozen=True)
class ModelCandidate:
    name: str
    strategy: str


@dataclass
class ModelResolutionPlan:
    attempts: list[ModelCandidate]
    suggestions: list[str]


def _fallback_candidates(value: str) -> list[str]:
    candidates: list[str] = []

    def _add(candidate: str) -> None:
        if candidate and candidate != value and candidate not in candidates:
            candidates.append(candidate)

    trimmed = value
    if trimmed.startswith("odoo.addons."):
        trimmed = trimmed.split("odoo.addons.", 1)[-1]
        _add(trimmed)
    if ".models." in trimmed:
        trimmed = trimmed.split(".models.", 1)[-1]
        _add(trimmed)
    if "." in trimmed:
        parts = trimmed.split(".")
        if len(parts) > 1:
            tail = ".".join(parts[1:])
            _add(tail)
            if "_" in tail:
                _add(tail.replace("_", "."))
            if tail.endswith("template") and "." not in tail:
                prefix_tail = tail[: -len("template")].rstrip("_")
                if prefix_tail:
                    _add(f"{parts[0]}.{prefix_tail}.template")
        last_segment = trimmed.rsplit(".", 1)[-1]
        _add(last_segment)
        if "_" in last_segment:
            _add(last_segment.replace("_", "."))
    if "." not in trimmed and "_" in trimmed:
        _add(trimmed.replace("_", "."))
    if "." in value:
        _add(value.rsplit(".", 1)[-1])
    return candidates


def _normalized_keys(value: str) -> list[str]:
    keys: list[str] = []

    def _add(raw_key: str) -> None:
        cleaned = "".join(ch for ch in raw_key.lower() if ch.isalnum())
        if cleaned and cleaned not in keys:
            keys.append(cleaned)

    raw = value.strip()
    if not raw:
        return keys

    lower = raw.lower()
    if lower.startswith("odoo.addons."):
        lower = lower.split("odoo.addons.", 1)[-1]
    if ".models." in lower:
        lower = lower.split(".models.", 1)[-1]
    _add(lower)

    if "." in lower:
        after_prefix = lower.split(".", 1)[-1]
        _add(after_prefix)
        _add(after_prefix.replace("_", "."))
        _add(after_prefix.replace("_", ""))
    if "_" in lower:
        _add(lower.replace("_", "."))

    camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw).lower()
    _add(camel)
    if "." in lower:
        _add("".join(ch for ch in lower.split(".", 1)[-1] if ch.isalnum()))
    return keys


async def _models_by_module(env: CompatibleEnvironment, module_name: str) -> list[str]:
    code = f"""
module = {module_name!r}
names = []
try:
    if module:
        for rec in env['ir.model'].search([('modules', 'ilike', module)]):
            if rec.model:
                names.append(rec.model)
except Exception:
    names = []
result = sorted(set(names))
"""
    result = await env.execute_code(code)
    return _extract_string_list(result)


def _extract_string_list(result: object) -> list[str]:
    if isinstance(result, dict):
        values = result.get("result")
        if isinstance(values, list):
            return [item for item in values if isinstance(item, str)]
        return []
    if isinstance(result, list):
        return [item for item in result if isinstance(item, str)]
    return []


async def _module_candidates(env: CompatibleEnvironment, value: str) -> tuple[list[str], list[str]]:
    if not value or "." not in value:
        return [], []
    module_name = value.split(".", 1)[0]
    module_models = await _models_by_module(env, module_name)
    if not module_models:
        return [], []
    suffix = value.split(".", 1)[-1]
    matches = [model for model in module_models if model == suffix or model.endswith(f".{suffix}")]
    if matches:
        return matches[:5], []
    return [], module_models[:5]


async def _fuzzy_model_candidates(env: CompatibleEnvironment, value: str, limit: int = 5) -> list[str]:
    keys = _normalized_keys(value)
    if not keys:
        return []
    code = f"""
import re

keys = {keys!r}
matches = []
try:
    for rec in env['ir.model'].search([]):
        model = rec.model or ''
        norm = re.sub(r'[^a-z0-9]', '', model.lower())
        for key in keys:
            if not key:
                continue
            if key in norm or norm in key:
                score = abs(len(norm) - len(key))
                matches.append((score, len(model), model))
                break
except Exception:
    matches = []

matches.sort()
result = [model for _, _, model in matches][:max(1, int({limit!r}))]
"""
    try:
        result = await env.execute_code(code)
    except CodeExecutionError:
        return []
    return _extract_string_list(result)


def is_model_not_found_result(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    error_type = result.get("error_type")
    if isinstance(error_type, str) and error_type.lower() == "modelnotfounderror":
        return True
    error_text = result.get("error")
    if not isinstance(error_text, str):
        return False
    lowered = error_text.lower()
    return "model" in lowered and "not found" in lowered


def _error_payload_from_exception(exc: CodeExecutionError) -> dict[str, object]:
    message = str(exc)
    error_type = "ModelNotFoundError" if "model" in message.lower() and "not found" in message.lower() else "CodeExecutionError"
    return {"success": False, "error": message, "error_type": error_type}


async def resolve_model_candidates(
    env: CompatibleEnvironment,
    model_name: str,
    *,
    allow_suffix: bool = True,
    allow_module: bool = True,
    allow_fuzzy: bool = True,
    fuzzy_limit: int = 5,
) -> ModelResolutionPlan:
    attempts: list[ModelCandidate] = []
    suggestions: list[str] = []

    def _add_attempt(candidate_name: str, strategy: str) -> None:
        if not candidate_name:
            return
        if candidate_name == model_name:
            return
        if any(existing.name == candidate_name for existing in attempts):
            return
        attempts.append(ModelCandidate(candidate_name, strategy))

    if allow_suffix:
        for candidate_name in _fallback_candidates(model_name):
            _add_attempt(candidate_name, "suffix")

    if allow_module:
        module_matches, module_suggestions = await _module_candidates(env, model_name)
        for candidate_name in module_matches:
            _add_attempt(candidate_name, "module_search")
        for suggestion in module_suggestions:
            if suggestion not in suggestions:
                suggestions.append(suggestion)

    if allow_fuzzy:
        fuzzy_candidates = await _fuzzy_model_candidates(env, model_name, fuzzy_limit)
        for candidate_name in fuzzy_candidates:
            _add_attempt(candidate_name, "fuzzy")

    return ModelResolutionPlan(attempts=attempts, suggestions=suggestions)


async def resolve_model_with_runner(
    env: CompatibleEnvironment,
    model_name: str,
    runner: Callable[[str], Awaitable[object]],
    *,
    allow_suffix: bool = True,
    allow_module: bool = True,
    allow_fuzzy: bool = True,
    fuzzy_limit: int = 5,
    fuzzy_attempt_limit: int = 3,
    include_candidates_on_success: bool = False,
    include_candidates_on_failure: bool = True,
) -> object:
    async def _invoke(candidate_name: str) -> object:
        try:
            return await runner(candidate_name)
        except CodeExecutionError as exc:
            return _error_payload_from_exception(exc)

    result = await _invoke(model_name)
    if not is_model_not_found_result(result):
        return result

    plan = await resolve_model_candidates(
        env,
        model_name,
        allow_suffix=allow_suffix,
        allow_module=allow_module,
        allow_fuzzy=allow_fuzzy,
        fuzzy_limit=fuzzy_limit,
    )

    fuzzy_attempts = 0
    for candidate in plan.attempts:
        if candidate.strategy == "fuzzy":
            if fuzzy_attempts >= max(0, fuzzy_attempt_limit):
                continue
            fuzzy_attempts += 1
        result = await _invoke(candidate.name)
        if is_model_not_found_result(result):
            continue
        if isinstance(result, dict):
            result["resolved_model"] = candidate.name
            result["resolution_strategy"] = candidate.strategy
            if include_candidates_on_success:
                result["resolution_candidates"] = [item.name for item in plan.attempts]
            if plan.suggestions:
                result["resolution_suggestions"] = plan.suggestions
        return result

    if isinstance(result, dict) and include_candidates_on_failure:
        result["resolution_candidates"] = [item.name for item in plan.attempts]
        if plan.suggestions:
            result["resolution_suggestions"] = plan.suggestions
    return result
