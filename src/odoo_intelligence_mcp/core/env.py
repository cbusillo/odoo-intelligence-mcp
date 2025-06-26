import json
import logging
import os
import subprocess
import textwrap
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv

from ..type_defs.odoo_types import Field, Model, Registry
from ..utils.error_utils import CodeExecutionError, DockerConnectionError

logger = logging.getLogger(__name__)


class MockRegistry:
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


def load_env_config() -> dict[str, str]:
    # Look for .env file in project root (where pyproject.toml is)
    current_path = Path(__file__).parent
    while current_path != current_path.parent:
        env_path = current_path / ".env"
        pyproject_path = current_path / "pyproject.toml"
        if pyproject_path.exists():
            # Found project root
            if env_path.exists():
                load_dotenv(env_path)
                logger.info("Loaded .env from %s", env_path)
            else:
                logger.debug(".env file not found at %s (optional)", env_path)
            break
        current_path = current_path.parent

    return {
        "container_name": os.getenv("ODOO_CONTAINER_NAME", "odoo-opw-shell-1"),
        "database": os.getenv("ODOO_DB_NAME", "opw"),
        "addons_path": os.getenv("ODOO_ADDONS_PATH", "/opt/project/addons,/odoo/addons,/volumes/enterprise"),
    }


# noinspection PyMethodMayBeStatic
class HostOdooEnvironmentManager:
    def __init__(self, container_name: str | None = None, database: str | None = None) -> None:
        config = load_env_config()
        self.container_name = container_name or config["container_name"]
        self.database = database or config["database"]
        self.addons_path = config["addons_path"]

    async def get_environment(self) -> "HostOdooEnvironment":
        return HostOdooEnvironment(self.container_name, self.database, self.addons_path)

    def invalidate_environment_cache(self) -> None:
        logger.info("Cache invalidation called (no-op for Docker exec)")


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class HostOdooEnvironment:
    def __init__(self, container_name: str, database: str, addons_path: str) -> None:
        self.container_name = container_name
        self.database = database
        self.addons_path = addons_path

    def __getitem__(self, model_name: str) -> "ModelProxy":
        return ModelProxy(self, model_name)

    def __call__(self, *, _user: int | None = None, _context: dict[str, object] | None = None) -> "HostOdooEnvironment":
        return HostOdooEnvironment(self.container_name, self.database, self.addons_path)

    def __contains__(self, model_name: str) -> bool:
        # For synchronous access, we assume the model exists
        # Tools should use await env.get_model_names() for proper model checking
        return True

    @property
    def env(self) -> "HostOdooEnvironment":
        return self

    @property
    def registry(self) -> Registry:
        return DockerRegistry(self)

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
        """Get all model names from the Odoo registry."""
        registry = self.registry
        if isinstance(registry, DockerRegistry):
            return await registry._fetch_models()
        return []

    async def has_model(self, model_name: str) -> bool:
        """Check if a model exists in the registry."""
        model_names = await self.get_model_names()
        return model_name in model_names

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

        docker_cmd = [
            "docker",
            "exec",
            "-i",
            self.container_name,
            "/odoo/odoo-bin",
            "shell",
            "--database",
            self.database,
            "--addons-path",
            self.addons_path,
            "--no-http",
        ]

        try:
            process = subprocess.run(docker_cmd, input=wrapped_code, text=True, capture_output=True, timeout=30)  # noqa: ASYNC221

            if process.returncode != 0:
                raise DockerConnectionError(
                    self.container_name, f"Command failed with return code {process.returncode}: {process.stderr}"
                )

            output_lines = process.stdout.strip().split("\n")
            json_output = output_lines[-1] if output_lines else "{}"

            try:
                result = json.loads(json_output)
                # Check if the code execution returned an error
                if isinstance(result, dict) and "error" in result:
                    raise CodeExecutionError(code, result["error"])
                return result
            except json.JSONDecodeError:
                # If we can't parse JSON, return the raw output
                return {"output": process.stdout, "raw": True}

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
