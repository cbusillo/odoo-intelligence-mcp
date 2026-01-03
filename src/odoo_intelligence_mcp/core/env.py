import json
import logging
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from collections.abc import AsyncIterator, Callable, Iterator
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import Field as PydanticField
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..type_defs.odoo_types import Field, Model, Registry
from ..utils.error_utils import CodeExecutionError, DockerConnectionError, EnvironmentResolutionError

logger = logging.getLogger(__name__)


def _resolve_env_file_override() -> Path | None:
    override = os.getenv("ODOO_ENV_FILE")
    if not override:
        return None
    candidate = Path(override).expanduser()
    if candidate.is_dir():
        candidate /= ".env"
    if candidate.exists():
        return candidate
    logger.warning("ODOO_ENV_FILE does not exist: %s", candidate)
    return None


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if value and value[0] in {"\"", "'"} and value[-1:] == value[:1]:
        value = value[1:-1]
    else:
        if "#" in value:
            value = value.split("#", 1)[0].rstrip()
    return key, value


@lru_cache(maxsize=8)
def _load_env_file_values(env_path_text: str) -> dict[str, str]:
    env_path = Path(env_path_text)
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    values: dict[str, str] = {}
    for line in lines:
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed
        values[key] = value
    return values


def _get_env_value(config: "EnvConfig", key: str) -> str | None:
    env_file_path = getattr(config, "_env_file", None)
    env_priority = getattr(config, "_env_priority", None)
    if env_priority == "env_file" and env_file_path:
        env_values = _load_env_file_values(str(env_file_path))
        if key in env_values:
            return env_values[key]
    if key in os.environ:
        return os.environ[key]
    if not env_file_path:
        return None
    return _load_env_file_values(str(env_file_path)).get(key)


def _split_env_list(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [segment.strip() for segment in re.split(r"[,:]", raw) if segment.strip()]
    return parts


def _expand_path(raw: str | Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(raw)))
    return Path(expanded)


def _find_ops_repo_root(start_dir: Path) -> Path | None:
    current = start_dir.resolve()
    while True:
        ops_path = current / "docker" / "config" / "ops.toml"
        if ops_path.exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _get_ops_root(config: "EnvConfig") -> Path | None:
    project_dir = config.project_dir or _get_env_value(config, "ODOO_PROJECT_DIR")
    if project_dir:
        candidate = _expand_path(project_dir)
        if candidate.exists():
            return _find_ops_repo_root(candidate)
    env_file_path = getattr(config, "_env_file", None)
    if env_file_path:
        return _find_ops_repo_root(Path(env_file_path).parent)
    return _find_ops_repo_root(Path.cwd())


def should_allow_autostart(config: "EnvConfig") -> bool:
    ops_root = _get_ops_root(config)
    if not ops_root:
        return True
    env_file_path = getattr(config, "_env_file", None)
    if not env_file_path:
        return False
    env_path = Path(env_file_path)
    if env_path.name == ".compose.env":
        return True
    if env_path.parent.name == "stack-env":
        return True
    override = os.getenv("ODOO_ENV_FILE")
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_dir():
            candidate /= ".env"
        return candidate.exists()
    return False


def _load_ops_targets(repo_root: Path) -> list[str]:
    ops_path = repo_root / "docker" / "config" / "ops.toml"
    try:
        data = tomllib.loads(ops_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    targets = data.get("targets", {})
    if not isinstance(targets, dict):
        return []
    return [key for key in targets.keys() if isinstance(key, str) and key]


def _extract_json_payload(raw_text: str) -> dict[str, object] | None:
    if not raw_text:
        return None
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


@lru_cache(maxsize=16)
def _run_ops_info(repo_root_text: str, target: str) -> dict[str, object] | None:
    command_name: str = "uv"
    cmd = [command_name, "run", "ops", "local", "info", target, "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=repo_root_text)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return _extract_json_payload(result.stdout)


def _select_ops_targets(targets: list[str], project_name: str | None, stack_name: str | None) -> list[str]:
    desired: list[str] = []

    def _add(value: str | None) -> None:
        if not value:
            return
        if value not in desired:
            desired.append(value)

    _add(stack_name)
    if stack_name:
        _add(stack_name.split("-", 1)[0])
        if stack_name.endswith("-local"):
            _add(stack_name.removesuffix("-local"))

    _add(project_name)
    if project_name:
        if project_name.startswith("odoo-"):
            _add(project_name.removeprefix("odoo-"))
        _add(project_name.split("-", 1)[-1])

    candidates = [target for target in desired if target in targets]
    return candidates or targets


def _resolve_stack_env_file_from_ops(start_dir: Path, project_name: str | None, stack_name: str | None) -> Path | None:
    repo_root = _find_ops_repo_root(start_dir)
    if not repo_root:
        return None
    if not project_name and not stack_name:
        return None
    targets = _load_ops_targets(repo_root)
    if not targets:
        return None
    infos: list[dict[str, object]] = []
    for target in _select_ops_targets(targets, project_name, stack_name):
        info = _run_ops_info(str(repo_root), target)
        if info:
            infos.append(info)

    def _match(info: dict[str, object], key: str | None) -> bool:
        if not key:
            return False
        return key == info.get("project_name") or key == info.get("stack_name") or key == info.get("compose_project")

    if project_name:
        for info in infos:
            if _match(info, project_name):
                env_file = info.get("env_file")
                if isinstance(env_file, str):
                    candidate = Path(env_file)
                    if candidate.exists():
                        return candidate

    if stack_name:
        for info in infos:
            if info.get("stack_name") == stack_name:
                env_file = info.get("env_file")
                if isinstance(env_file, str):
                    candidate = Path(env_file)
                    if candidate.exists():
                        return candidate
    return None


def _resolve_stack_env_file() -> Path | None:
    cwd_env = Path.cwd() / ".env"
    cwd_env_values = _load_env_file_values(str(cwd_env)) if cwd_env.exists() else {}
    stack_name = os.getenv("ODOO_STACK_NAME") or os.getenv("ODOO_STACK") or os.getenv("ODOO_ENV_NAME")
    if not stack_name:
        stack_name = cwd_env_values.get("ODOO_STACK_NAME") or cwd_env_values.get("ODOO_STACK") or cwd_env_values.get(
            "ODOO_ENV_NAME"
        )

    project_name = os.getenv("ODOO_PROJECT_NAME") or cwd_env_values.get("ODOO_PROJECT_NAME")

    state_root = os.getenv("ODOO_STATE_ROOT") or cwd_env_values.get("ODOO_STATE_ROOT")
    if state_root:
        candidate = _expand_path(state_root) / ".compose.env"
        if candidate.exists():
            return candidate

    project_dir = os.getenv("ODOO_PROJECT_DIR") or cwd_env_values.get("ODOO_PROJECT_DIR")
    ops_start_dir = _expand_path(project_dir) if project_dir else Path.cwd()
    ops_env = _resolve_stack_env_file_from_ops(ops_start_dir, project_name, stack_name)
    if ops_env:
        return ops_env

    if project_name:
        candidate = Path.home() / "odoo-ai" / project_name / ".compose.env"
        if candidate.exists():
            return candidate
        fallback = Path.home() / ".odoo-ai" / "stack-env" / f"{project_name}.env"
        if fallback.exists():
            return fallback
    base = Path.home() / "odoo-ai"
    if base.exists():
        matches = [path / ".compose.env" for path in base.iterdir() if path.is_dir() and (path / ".compose.env").exists()]
        if len(matches) == 1:
            return matches[0]
        if project_name:
            for candidate in matches:
                values = _load_env_file_values(str(candidate))
                if values.get("ODOO_PROJECT_NAME") == project_name:
                    return candidate

    if stack_name:
        candidate = Path.home() / "odoo-ai" / stack_name / ".compose.env"
        if candidate.exists():
            return candidate
        fallback = Path.home() / ".odoo-ai" / "stack-env" / f"{stack_name}.env"
        if fallback.exists():
            return fallback
    fallback_dir = Path.home() / ".odoo-ai" / "stack-env"
    if fallback_dir.exists():
        candidates = [path for path in fallback_dir.iterdir() if path.is_file() and path.suffix == ".env"]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _sanitize_container_name(container_name: str) -> str:
    safe_name = container_name.split(";")[0].split("&&")[0].split("|")[0].split("`")[0].split("$(")[0].strip()
    if not re.fullmatch(r"^[a-zA-Z0-9_\-.]+$", safe_name):
        return "odoo-script-runner-1"
    return safe_name


def _container_candidates(config: "EnvConfig", requested: str | None = None) -> list[str]:
    candidates = [
        requested or "",
        config.container_name,
        config.script_runner_container,
        config.web_container,
    ]
    if config.container_prefix:
        candidates.extend(
            [
                f"{config.container_prefix}-odoo-1",
                f"{config.container_prefix}-app-1",
            ]
        )
    unique: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in unique:
            continue
        unique.append(normalized)
    return unique


def resolve_existing_container_name(config: "EnvConfig", requested: str) -> str | None:
    for candidate in _container_candidates(config, requested):
        safe_candidate = _sanitize_container_name(candidate)
        check_cmd = ["docker", "inspect", safe_candidate, "--format", "{{.State.Status}}"]
        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            return safe_candidate
    return None


def resolve_compose_env_file(config: "EnvConfig") -> Path | None:
    env_file_path = getattr(config, "_env_file", None)
    if env_file_path and Path(env_file_path).exists():
        return Path(env_file_path)
    return None


def resolve_compose_files(config: "EnvConfig") -> list[str]:
    raw = config.compose_files
    if not raw:
        raw = _get_env_value(config, "DEPLOY_COMPOSE_FILES")
    if not raw:
        raw = _get_env_value(config, "COMPOSE_FILE")
    if not raw:
        return []
    return _split_env_list(raw)


def _compose_files_exist(base: Path, compose_files: list[str]) -> bool:
    if not compose_files:
        return (base / "docker-compose.yml").exists() or (base / "compose.yml").exists()
    for entry in compose_files:
        path = _expand_path(entry)
        if path.is_absolute():
            if not path.exists():
                return False
        else:
            if not (base / path).exists():
                return False
    return True


def _scan_compose_roots(root: Path, compose_files: list[str], max_depth: int) -> Path | None:
    if max_depth < 0:
        return None
    if _compose_files_exist(root, compose_files):
        return root
    if max_depth == 0:
        return None
    try:
        entries = list(root.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.is_dir():
            continue
        resolved = _scan_compose_roots(entry, compose_files, max_depth - 1)
        if resolved:
            return resolved
    return None



def resolve_compose_project_directory(config: "EnvConfig", compose_files: list[str]) -> Path | None:
    override = config.project_dir or _get_env_value(config, "ODOO_PROJECT_DIR")
    if override:
        candidate = _expand_path(override)
        if candidate.exists():
            return candidate
    env_file_path = getattr(config, "_env_file", None)
    if env_file_path:
        env_parent = Path(env_file_path).parent
        for candidate in [env_parent, *env_parent.parents]:
            if _compose_files_exist(candidate, compose_files):
                return candidate
    cwd = Path.cwd()
    for candidate in [cwd, cwd.parent]:
        if _compose_files_exist(candidate, compose_files):
            return candidate
    absolute_paths = [path for path in (_expand_path(entry) for entry in compose_files) if path.is_absolute()]
    if absolute_paths:
        return absolute_paths[0].parent
    home = Path.home()
    for root in [home / "Developer", home / "dev", home / "projects", home / "src"]:
        if not root.exists():
            continue
        found = _scan_compose_roots(root, compose_files, 1)
        if found:
            return found
    return None


def build_compose_up_command(config: "EnvConfig", services: list[str]) -> tuple[list[str], Path | None]:
    compose_files = resolve_compose_files(config)
    project_dir = resolve_compose_project_directory(config, compose_files)
    env_file_path = resolve_compose_env_file(config)
    resolved_compose_files: list[Path] = []
    if project_dir:
        for entry in compose_files:
            resolved = _expand_path(entry)
            if not resolved.is_absolute():
                resolved = (project_dir / resolved).resolve()
            else:
                resolved = resolved.resolve()
            resolved_compose_files.append(resolved)

        base_candidates = [project_dir / "docker-compose.yml", project_dir / "compose.yml"]
        base_file = next((candidate.resolve() for candidate in base_candidates if candidate.exists()), None)
        override_file = (project_dir / "docker-compose.override.yml").resolve()
        merged: list[Path] = []
        seen: set[Path] = set()

        for candidate in [base_file, override_file if override_file.exists() else None]:
            if candidate and candidate not in seen:
                merged.append(candidate)
                seen.add(candidate)

        for candidate in resolved_compose_files:
            if candidate not in seen:
                merged.append(candidate)
                seen.add(candidate)

        resolved_compose_files = merged
    else:
        resolved_compose_files = [_expand_path(entry) for entry in compose_files]

    command = ["/usr/bin/env", "docker", "compose"]
    if env_file_path:
        command += ["--env-file", str(env_file_path)]
    for entry in resolved_compose_files:
        command += ["-f", str(entry)]
    command += ["up", "-d", *services]
    return command, project_dir



def _resolve_container_env(container_name: str) -> dict[str, str]:
    try:
        inspect_cmd = ["docker", "inspect", container_name, "--format", "{{json .Config.Env}}"]
        result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=3)
        if result.returncode != 0:
            return {}
        raw = json.loads(result.stdout)
        if not isinstance(raw, list):
            return {}
        env_vars: dict[str, str] = {}
        for entry in raw:
            if not isinstance(entry, str) or "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            env_vars[key] = value
        return env_vars
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return {}


class EnvConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ODOO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    container_prefix: str | None = PydanticField(default=None, alias="ODOO_PROJECT_NAME")
    db_name: str = PydanticField(default="odoo", alias="ODOO_DB_NAME")
    db_host: str = PydanticField(default="database", alias="ODOO_DB_HOST")
    db_port: str = PydanticField(default="5432", alias="ODOO_DB_PORT")
    addons_path: str = PydanticField(default="/opt/project/addons,/odoo/addons,/volumes/enterprise", alias="ODOO_ADDONS_PATH")
    project_dir: str | None = PydanticField(default=None, alias="ODOO_PROJECT_DIR")
    stack_name: str | None = PydanticField(default=None, alias="ODOO_STACK_NAME")
    compose_files: str | None = PydanticField(default=None, alias="ODOO_COMPOSE_FILES")
    container_name_override: str | None = PydanticField(default=None, alias="ODOO_CONTAINER_NAME")
    script_runner_container_override: str | None = PydanticField(default=None, alias="ODOO_SCRIPT_RUNNER_CONTAINER")
    web_container_override: str | None = PydanticField(default=None, alias="ODOO_WEB_CONTAINER")
    # Feature flags
    enhanced_errors: bool = PydanticField(default=False, alias="ODOO_MCP_ENHANCED_ERRORS")

    @property
    def container_name(self) -> str:
        return self.script_runner_container

    @property
    def script_runner_container(self) -> str:
        if self.script_runner_container_override:
            return self.script_runner_container_override
        if self.container_name_override:
            return self.container_name_override
        if not self.container_prefix:
            raise EnvironmentResolutionError(
                "ODOO_PROJECT_NAME is required to build container names. Set it in .env or pass ODOO_CONTAINER_NAME/"
                "ODOO_SCRIPT_RUNNER_CONTAINER to override."
            )
        return f"{self.container_prefix}-script-runner-1"

    @property
    def web_container(self) -> str:
        if self.web_container_override:
            return self.web_container_override
        if self.container_name_override:
            return self.container_name_override
        if not self.container_prefix:
            raise EnvironmentResolutionError(
                "ODOO_PROJECT_NAME is required to build container names. Set it in .env or pass ODOO_WEB_CONTAINER to override."
            )
        return f"{self.container_prefix}-web-1"

    @property
    def database(self) -> str:
        return self.db_name

    @property
    def database_container(self) -> str | None:
        host = (self.db_host or "").strip()
        if not host:
            return None
        lowered = host.lower()
        if lowered in {"localhost", "127.0.0.1"}:
            return None
        if "." in host:
            return None
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", host):
            return None
        if not self.container_prefix:
            return None
        return f"{self.container_prefix}-{host}-1"


class MockRegistry(Registry):
    models: ClassVar[dict[str, type[Model]]] = {}

    def __init__(self) -> None:
        self._models: dict[str, type[Model]] = {}

    def _get_models_dict(self) -> dict[str, type[Model]]:
        return self._models if self._models else self.models

    def __iter__(self) -> Iterator[str]:
        return iter(self._get_models_dict())

    def __getitem__(self, key: str) -> type[Model] | None:
        return self._get_models_dict().get(key)

    def __len__(self) -> int:
        return len(self._get_models_dict())

    def __contains__(self, key: str) -> bool:
        return key in self._get_models_dict()


class DockerRegistry:
    def __init__(self, env: "HostOdooEnvironment") -> None:
        self.env = env
        self._models: list[str] | None = None
        self.models: dict[str, type[Model]] = {}

    async def _fetch_models(self) -> list[str]:
        if self._models is None:
            code = """
# Get all model names from the registry
result = list(env.registry.models.keys())
"""
            try:
                models = await self.env.execute_code(code)
                self._models = models if isinstance(models, list) else []
            except Exception as e:
                logger.warning(f"Failed to fetch models from Docker: {e}")
                self._models = []
        return self._models

    def __iter__(self) -> Iterator[str]:
        logger.warning("Synchronous iteration over DockerRegistry is not supported. Use 'await env.get_model_names()' instead.")
        return iter([])

    async def __aiter__(self) -> AsyncIterator[str]:
        models = await self._fetch_models()
        for model in models:
            yield model

    def __getitem__(self, key: str) -> None:
        return None

    def __len__(self) -> int:
        return 0

    def __contains__(self, key: str) -> bool:
        return False


def _has_container_targets(config: EnvConfig) -> bool:
    candidates = [
        config.container_prefix,
        config.container_name_override,
        config.script_runner_container_override,
        config.web_container_override,
    ]
    return any(value and str(value).strip() for value in candidates)


def _validate_required_env(config: EnvConfig, env_file_path: Path | None) -> None:
    if _has_container_targets(config):
        return
    if env_file_path:
        raise EnvironmentResolutionError(
            f"Missing ODOO_PROJECT_NAME in {env_file_path}. Set it in the env file or pass ODOO_CONTAINER_NAME/"
            "ODOO_SCRIPT_RUNNER_CONTAINER/ODOO_WEB_CONTAINER to override."
        )
    raise EnvironmentResolutionError(
        "No .env file could be resolved. Set ODOO_ENV_FILE, run from the target repo root, or set ODOO_PROJECT_NAME (or container "
        "overrides) in the environment."
    )


def load_env_config() -> EnvConfig:
    # Detect if we're running in test mode
    is_testing = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None

    # Log the current working directory for debugging
    logger.debug("MCP server looking for .env file from working directory: %s", Path.cwd())

    # Find the .env file to use
    env_file_path = _resolve_env_file_override()

    if not env_file_path:
        env_file_path = _resolve_stack_env_file()

    if not env_file_path and is_testing:
        # For testing: Look for target project's .env file (../odoo-ai/.env)
        developer_dir = Path(__file__).parent.parent.parent.parent.parent  # Go up to Developer/ directory
        target_env_path = developer_dir / "odoo-ai" / ".env"
        if target_env_path.exists():
            env_file_path = target_env_path
            logger.info("Using target project .env from %s (test mode)", target_env_path)

    if not env_file_path:
        # First, check the current working directory (where Claude Code was launched)
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            env_file_path = cwd_env
            logger.info("Using .env from current working directory: %s", cwd_env)
        else:
            # Fall back to looking for .env in MCP server's project root
            current_path = Path(__file__).parent
            while current_path != current_path.parent:
                pyproject_path = current_path / "pyproject.toml"
                if pyproject_path.exists():
                    # Found project root
                    env_path = current_path / ".env"
                    if env_path.exists():
                        env_file_path = env_path
                        logger.info("Using local .env from %s", env_path)
                    break
                current_path = current_path.parent

    # Pydantic BaseSettings will automatically load from env vars and .env file
    if env_file_path:
        env_priority = os.getenv("ODOO_ENV_PRIORITY")
        if not env_priority and Path(env_file_path).name == ".compose.env":
            env_priority = "env_file"
        if not env_priority:
            env_priority = "process"

        config = EnvConfig(_env_file=env_file_path)
        env_values = _load_env_file_values(str(env_file_path))
        if env_priority == "env_file" and env_values:
            overrides: dict[str, object] = {}
            mapping = [
                ("container_prefix", "ODOO_PROJECT_NAME"),
                ("db_name", "ODOO_DB_NAME"),
                ("db_host", "ODOO_DB_HOST"),
                ("db_port", "ODOO_DB_PORT"),
                ("addons_path", "ODOO_ADDONS_PATH"),
                ("project_dir", "ODOO_PROJECT_DIR"),
                ("stack_name", "ODOO_STACK_NAME"),
                ("compose_files", "ODOO_COMPOSE_FILES"),
                ("container_name_override", "ODOO_CONTAINER_NAME"),
                ("script_runner_container_override", "ODOO_SCRIPT_RUNNER_CONTAINER"),
                ("web_container_override", "ODOO_WEB_CONTAINER"),
                ("enhanced_errors", "ODOO_MCP_ENHANCED_ERRORS"),
            ]
            for field_name, env_key in mapping:
                if env_key in env_values:
                    overrides[field_name] = env_values[env_key]
            if overrides:
                config = config.model_copy(update=overrides)

        config.__dict__["_env_file"] = Path(env_file_path)
        config.__dict__["_env_priority"] = env_priority
        _validate_required_env(config, Path(env_file_path))
        return config
    else:
        logger.info("No .env file found, using defaults and environment variables")
        config = EnvConfig()
        _validate_required_env(config, None)
        return config


# noinspection PyMethodMayBeStatic
class HostOdooEnvironmentManager:
    def __init__(self, container_name: str | None = None, database: str | None = None, *, lazy: bool = False) -> None:
        self._container_name_override = container_name
        self._database_override = database
        self._config: EnvConfig | None = None
        if not lazy:
            self._config = load_env_config()
            self._refresh_cached(self._config)

    def _get_config(self) -> EnvConfig:
        if self._config is None:
            self._config = load_env_config()
        return self._config

    def _refresh_cached(self, config: EnvConfig) -> None:
        self.container_name = self._container_name_override or config.container_name
        self.database = self._database_override or config.database
        self.addons_path = config.addons_path
        self.db_host = config.db_host
        self.db_port = config.db_port
        self.addons_path_explicit = _get_env_value(config, "ODOO_ADDONS_PATH") is not None

    async def get_environment(self) -> "HostOdooEnvironment":
        config = self._get_config()
        self._refresh_cached(config)
        return HostOdooEnvironment(
            self.container_name,
            self.database,
            self.addons_path,
            self.db_host,
            self.db_port,
            addons_path_explicit=self.addons_path_explicit,
        )

    def invalidate_environment_cache(self) -> None:
        logger.info("Cache invalidation called (no-op for Docker exec)")
        self._config = None


# noinspection PyMethodMayBeStatic
class HostOdooEnvironment:
    def __init__(
        self,
        container_name: str,
        database: str,
        addons_path: str,
        db_host: str,
        db_port: str,
        *,
        addons_path_explicit: bool = False,
    ) -> None:
        self.container_name = _sanitize_container_name(container_name)
        self.database = database
        self.addons_path = addons_path
        self.db_host = db_host
        self.db_port = db_port
        self._registry: Registry | None = None
        self.addons_path_explicit = addons_path_explicit

    def __getitem__(self, model_name: str) -> "ModelProxy":
        return ModelProxy(self, model_name)

    def __call__(self, *, _user: int | None = None, _context: dict[str, object] | None = None) -> "HostOdooEnvironment":
        return HostOdooEnvironment(
            self.container_name,
            self.database,
            self.addons_path,
            self.db_host,
            self.db_port,
            addons_path_explicit=self.addons_path_explicit,
        )

    def __contains__(self, model_name: str) -> bool:
        # For synchronous access, we assume the model exists
        # Tools should use await env.get_model_names() for proper model checking
        return True

    @property
    def env(self) -> "HostOdooEnvironment":
        return self

    @property
    def registry(self) -> Registry:
        if self._registry is None:
            self._registry = DockerRegistry(self)
        return self._registry

    @property
    def cr(self) -> object:
        return None

    @property
    def uid(self) -> int:
        return 1

    @property
    def context(self) -> dict[str, object]:
        return {}

    @property
    def su(self) -> bool:
        return False

    def ref(self, _xml_id: str, _raise_if_not_found: bool = True) -> object:
        return None

    def is_superuser(self) -> bool:
        return False

    def user(self) -> object:
        return None

    def company(self) -> object:
        return None

    def companies(self) -> object:
        return None

    def lang(self) -> str:
        return "en_US"

    async def get_model_names(self) -> list[str]:
        registry = self.registry
        if isinstance(registry, DockerRegistry):
            # noinspection PyProtectedMember
            return await registry._fetch_models()
        return []

    async def has_model(self, model_name: str) -> bool:
        model_names = await self.get_model_names()
        return model_name in model_names

    def _get_project_directory(self, config: EnvConfig) -> str | None:
        compose_files = resolve_compose_files(config)
        project_dir = resolve_compose_project_directory(config, compose_files)
        if project_dir:
            return str(project_dir)
        return None

    def ensure_container_running(self) -> None:
        try:
            # Check container status with health information
            check_cmd = ["docker", "inspect", self.container_name, "--format", "{{.State.Status}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                stderr_lower = result.stderr.lower()
                missing_container = "no such object" in stderr_lower or "no such container" in stderr_lower
                if missing_container:
                    config = load_env_config()
                    if not should_allow_autostart(config):
                        raise DockerConnectionError(
                            self.container_name,
                            "Auto-start disabled until stack env is resolved. Set ODOO_PROJECT_NAME/ODOO_STACK_NAME or ODOO_ENV_FILE.",
                        )
                    resolved_container = resolve_existing_container_name(config, self.container_name)
                    if resolved_container and resolved_container != self.container_name:
                        logger.info(f"Container {self.container_name} not found. Using {resolved_container}.")
                        self.container_name = resolved_container
                        check_cmd = ["docker", "inspect", self.container_name, "--format", "{{.State.Status}}"]
                        result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                # First check if Docker is accessible at all
                docker_check = subprocess.run(["/usr/bin/env", "docker", "version"], capture_output=True, text=True, timeout=2)
                if docker_check.returncode != 0:
                    raise DockerConnectionError(
                        self.container_name, f"Cannot connect to Docker daemon. Is Docker running? Error: {docker_check.stderr}"
                    )

                # Check Docker context
                context_check = subprocess.run(
                    ["/usr/bin/env", "docker", "context", "show"], capture_output=True, text=True, timeout=2
                )
                if context_check.returncode == 0:
                    logger.info(f"Current Docker context: {context_check.stdout.strip()}")

                # Check if it's a permission issue or container doesn't exist
                stderr_lower = result.stderr.lower()
                if "permission denied" in stderr_lower:
                    raise DockerConnectionError(
                        self.container_name,
                        "Permission denied accessing Docker. Try running with appropriate permissions or check Docker socket access.",
                    )
                if "no such object" in stderr_lower or "no such container" in stderr_lower:
                    logger.info(f"Container {self.container_name} does not exist: {result.stderr}")
                else:
                    # Unknown error - log it and try to continue
                    logger.warning(f"Docker inspect failed for {self.container_name}: {result.stderr}")
                    # Try to list containers to see what's available
                    list_cmd = ["docker", "ps", "-a", "--format", "table {{.Names}}"]
                    list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=5)
                    if list_result.returncode == 0:
                        logger.info(f"Available containers:\n{list_result.stdout}")
                    raise DockerConnectionError(self.container_name, f"Cannot inspect container. Docker error: {result.stderr}")

                # Container doesn't exist, try to create it with docker compose
                config = load_env_config()
                if not should_allow_autostart(config):
                    raise DockerConnectionError(
                        self.container_name,
                        "Auto-start disabled until stack env is resolved. Set ODOO_PROJECT_NAME/ODOO_STACK_NAME or ODOO_ENV_FILE.",
                    )
                if not config.container_prefix:
                    raise DockerConnectionError(
                        self.container_name,
                        "Auto-start requires ODOO_PROJECT_NAME so compose service names can be resolved.",
                    )
                service_name = self.container_name.replace(f"{config.container_prefix}-", "").replace("-1", "")
                logger.info(f"Attempting to create container {self.container_name} via docker compose service '{service_name}'...")

                # Start essential services: database, script-runner, and the requested service
                # This ensures all dependencies and related services are available
                essential_services = ["database", "script-runner", service_name]
                # Remove duplicates while preserving order
                services_to_start = list(dict.fromkeys(essential_services))
                compose_cmd, project_dir = build_compose_up_command(config, services_to_start)

                if not project_dir:
                    raise DockerConnectionError(self.container_name, "Cannot determine project directory for docker compose")

                compose_result = subprocess.run(compose_cmd, capture_output=True, text=True, timeout=60, cwd=project_dir)

                if compose_result.returncode == 0:
                    logger.info(f"Successfully created and started container {self.container_name} via compose")
                    import time

                    time.sleep(5)  # Give container time to fully start
                else:
                    logger.error(f"Failed to start container via compose: {compose_result.stderr}")
                    raise DockerConnectionError(self.container_name, f"Failed to create container: {compose_result.stderr}")
                return

            status = result.stdout.strip()

            # Even if main container is running, check all essential dependencies
            if status == "running":
                config = load_env_config()
                if not config.container_prefix:
                    return
                essential_containers = [
                    f"{config.container_prefix}-database-1",
                    f"{config.container_prefix}-script-runner-1",
                ]

                containers_to_start = []
                for container in essential_containers:
                    check_cmd = ["docker", "inspect", container, "--format", "{{.State.Status}}"]
                    result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode != 0:
                        stderr_lower = result.stderr.lower()
                        if "no such container" in stderr_lower or "no such object" in stderr_lower:
                            continue
                        service = container.replace(f"{config.container_prefix}-", "").replace("-1", "")
                        containers_to_start.append(service)
                        continue
                    if result.stdout.strip() != "running":
                        service = container.replace(f"{config.container_prefix}-", "").replace("-1", "")
                        containers_to_start.append(service)

                if containers_to_start:
                    logger.info(f"Essential containers not running: {containers_to_start}. Starting them...")
                    compose_cmd, project_dir = build_compose_up_command(config, containers_to_start)

                    if project_dir:
                        compose_result = subprocess.run(compose_cmd, capture_output=True, text=True, timeout=60, cwd=project_dir)
                        if compose_result.returncode == 0:
                            logger.info(f"Successfully started containers: {containers_to_start}")
                            import time

                            time.sleep(5)  # Give containers time to fully start
                        else:
                            logger.warning(f"Failed to start containers: {compose_result.stderr}")

            if status != "running":
                logger.info(f"Container {self.container_name} is {status}. Starting it...")
                start_cmd = ["/usr/bin/env", "docker", "start", self.container_name]
                start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=10)

                if start_result.returncode == 0:
                    logger.info(f"Successfully started container {self.container_name}")
                    import time

                    time.sleep(3)  # Give container more time to fully start

                    # Verify container is healthy after start
                    health_check_cmd = [
                        "/usr/bin/env",
                        "docker",
                        "inspect",
                        self.container_name,
                        "--format",
                        "{{.State.Health.Status}}",
                    ]
                    health_result = subprocess.run(health_check_cmd, capture_output=True, text=True, timeout=5)
                    if "unhealthy" in health_result.stdout:
                        logger.warning(f"Container {self.container_name} is unhealthy, attempting restart...")
                        restart_cmd = ["/usr/bin/env", "docker", "restart", self.container_name]
                        subprocess.run(restart_cmd, capture_output=True, text=True, timeout=15)
                        time.sleep(5)  # Wait for restart
                # If docker start failed, try docker compose up
                elif "No such container" in start_result.stderr or "not found" in start_result.stderr:
                    logger.info(f"Container {self.container_name} doesn't exist. Attempting to create with docker compose...")
                    config = load_env_config()
                    if not config.container_prefix:
                        raise DockerConnectionError(
                            self.container_name,
                            "Auto-start requires ODOO_PROJECT_NAME so compose service names can be resolved.",
                        )
                    service_name = self.container_name.replace(f"{config.container_prefix}-", "").replace("-1", "")
                    compose_cmd, project_dir = build_compose_up_command(config, [service_name])
                    compose_result = subprocess.run(
                        compose_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=project_dir,
                    )
                    if compose_result.returncode == 0:
                        logger.info(f"Successfully created and started container {self.container_name} via compose")
                    else:
                        logger.warning(f"Failed to start container via compose: {compose_result.stderr}")
                else:
                    logger.warning(f"Failed to start container {self.container_name}: {start_result.stderr}")
        except subprocess.TimeoutExpired as e:
            raise DockerConnectionError(self.container_name, f"Docker command timed out: {e}") from e
        except FileNotFoundError as e:
            raise DockerConnectionError(self.container_name, f"Docker command not found: {e}") from e

    def _maybe_refresh_addons_path_from_container(self) -> None:
        if self.addons_path_explicit:
            return
        env_vars = _resolve_container_env(self.container_name)
        container_addons_path = env_vars.get("ODOO_ADDONS_PATH")
        if container_addons_path and container_addons_path != self.addons_path:
            logger.info("Using ODOO_ADDONS_PATH from container %s", self.container_name)
            self.addons_path = container_addons_path

    def _parse_json_output(self, output: str, code: str) -> dict[str, object] | str | int | float | bool | None:
        output_lines = output.strip().split("\n")
        json_output = output_lines[-1] if output_lines else "{}"
        try:
            result = json.loads(json_output)
            if isinstance(result, dict) and "error" in result:
                raise CodeExecutionError(code, result["error"])
            return result
        except json.JSONDecodeError:
            return {"output": output, "raw": True}

    async def execute_code(self, code: str) -> dict[str, object] | str | int | float | bool | None:
        wrapped_code = textwrap.dedent(
            f"""
            import json
            import sys

            from io import StringIO
            original_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
{textwrap.indent(code, "                ")}

                output = sys.stdout.getvalue()
                sys.stdout = original_stdout

                if 'result' in locals():
                    # Handle recordsets specially
                    if hasattr(result, '_name'):
                        # It's a recordset
                        serialized = {{
                            "result_type": "recordset",
                            "model": result._name,
                            "count": len(result),
                            "ids": result.ids[:100],  # Limit to 100 IDs
                            "display_names": [rec.display_name for rec in result[:10]]  # First 10 names
                        }}
                        print(json.dumps(serialized))
                    else:
                        print(json.dumps(result))
                elif output:
                    print(json.dumps({{"output": output}}))
                else:
                    print(json.dumps({{"success": True}}))
            except Exception as e:
                sys.stdout = original_stdout
                print(json.dumps({{"error": str(e), "error_type": type(e).__name__}}))
        """
        )

        self.ensure_container_running()

        self._maybe_refresh_addons_path_from_container()

        docker_cmd = [
            "docker",
            "exec",
            "-i",
            self.container_name,
            "/odoo/odoo-bin",
            "shell",
            "--database",
            self.database,
            "--db_host",
            self.db_host,
            "--db_port",
            self.db_port,
            "--addons-path",
            self.addons_path,
            "--no-http",
        ]

        try:
            # Increase timeout and add memory limit handling
            process = subprocess.run(docker_cmd, input=wrapped_code, text=True, capture_output=True, timeout=60)  # noqa: ASYNC221

            if process.returncode == 137:  # Container killed due to OOM
                error_msg = "Container killed (likely OOM). Consider reducing data size or increasing memory limits."
                # Attempt to restart container
                restart_cmd = ["docker", "restart", self.container_name]
                subprocess.run(restart_cmd, capture_output=True, text=True, timeout=15)
                import time

                time.sleep(5)
                raise DockerConnectionError(self.container_name, error_msg)  # noqa: TRY301
            if process.returncode == 125:  # Docker run error
                if "executable file not found" in process.stderr:
                    error_msg = "Odoo executable not found in container. Check if container has Odoo installed at /odoo/odoo-bin"
                elif "no such container" in process.stderr.lower():
                    error_msg = (
                        f"Container {self.container_name} not found. Ensure containers are running with: docker compose up -d"
                    )
                else:
                    error_msg = f"Docker exec failed: {process.stderr}"
                raise DockerConnectionError(self.container_name, error_msg)  # noqa: TRY301
            if process.returncode == 126:  # Permission denied
                error_msg = f"Permission denied executing command in container: {process.stderr}"
                raise DockerConnectionError(self.container_name, error_msg)  # noqa: TRY301
            if process.returncode != 0:
                # Check for common Odoo errors in stderr
                if "database" in process.stderr.lower() and "does not exist" in process.stderr.lower():
                    error_msg = f"Database '{self.database}' does not exist. Check ODOO_DB_NAME in your .env file"
                elif "could not connect" in process.stderr.lower():
                    error_msg = f"Cannot connect to database at {self.db_host}:{self.db_port}. Check database is running"
                else:
                    error_msg = f"Command failed with return code {process.returncode}: {process.stderr}"
                raise DockerConnectionError(self.container_name, error_msg)  # noqa: TRY301

            return self._parse_json_output(process.stdout, code)

        except subprocess.TimeoutExpired:
            raise DockerConnectionError(self.container_name, "Command execution timed out after 30 seconds") from None
        except (DockerConnectionError, CodeExecutionError):
            raise
        except Exception as e:
            raise DockerConnectionError(self.container_name, f"Unexpected error: {e!s}") from e


# noinspection PyUnusedLocal,PyMethodMayBeStatic
class ModelProxy:
    def __init__(self, env: HostOdooEnvironment, model_name: str) -> None:
        self.env = env
        self.model_name = model_name
        self.id = 0
        self.display_name = ""

    async def search(self, domain: list | None = None, limit: int | None = None, offset: int = 0) -> "ModelProxy":
        if domain is None:
            domain = []

        code = f"""
model = env['{self.model_name}']
records = model.search({domain!r}, limit={limit!r}, offset={offset})
result = []
for record in records:
    result.append({{'id': record.id, 'display_name': record.display_name}})
"""
        await self.env.execute_code(code)
        return self

    def browse(self, _ids: int | list[int]) -> "ModelProxy":
        return ModelProxy(self.env, self.model_name)

    def create(self, _vals: dict[str, object] | list[dict[str, object]]) -> "ModelProxy":
        return ModelProxy(self.env, self.model_name)

    def write(self, _vals: dict[str, object]) -> bool:
        return True

    def read(self, _fields: list[str] | None = None) -> list[dict[str, object]]:
        return []

    def unlink(self) -> bool:
        return True

    def exists(self) -> bool:
        return True

    def ensure_one(self) -> "ModelProxy":
        return self

    def mapped(self, _path: str) -> list[object]:
        return []

    def filtered(self, _func: Callable[["ModelProxy"], bool]) -> "ModelProxy":
        return self

    def sorted(self, _key: Callable[["ModelProxy"], object] | None = None, _reverse: bool = False) -> "ModelProxy":
        return self

    def check_access(self, _operation: str, _raise_exception: bool = True) -> bool:
        return True

    def __getattr__(self, name: str) -> object:
        return None

    def __getitem__(self, key: int) -> "ModelProxy":
        return self

    def __len__(self) -> int:
        return 0

    def __iter__(self) -> object:
        return iter([])

    def __bool__(self) -> bool:
        return True

    async def search_count(self, domain: list | None = None) -> int:
        if domain is None:
            domain = []

        code = f"""
result = env['{self.model_name}'].search_count({domain!r})
"""
        result = await self.env.execute_code(code)
        return result if isinstance(result, int) else 0

    async def fields_get(self, allfields: bool = True) -> dict:
        code = f"""
result = env['{self.model_name}'].fields_get(allfields={allfields!r})
"""
        result = await self.env.execute_code(code)
        return result if isinstance(result, dict) else {}

    def _get_methods(self) -> list[str]:
        return []

    @property
    def _fields(self) -> dict[str, Field]:
        return {}

    @property
    def _description(self) -> str:
        return ""

    @property
    def _table(self) -> str:
        return ""

    @property
    def _name(self) -> str:
        return self.model_name

    @property
    def _rec_name(self) -> str:
        return "name"

    @property
    def _order(self) -> str:
        return "id"

    @property
    def registry(self) -> dict[str, object]:
        return {}

    @property
    def _module(self) -> str:
        return ""
