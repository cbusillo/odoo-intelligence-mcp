import json
import logging
import os
import subprocess
import sys
import textwrap
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import ClassVar

from pydantic import Field as PydanticField
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..type_defs.odoo_types import Field, Model, Registry
from ..utils.error_utils import CodeExecutionError, DockerConnectionError

logger = logging.getLogger(__name__)


class EnvConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ODOO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    container_prefix: str = PydanticField(default="odoo", alias="ODOO_PROJECT_NAME")
    db_name: str = PydanticField(default="odoo", alias="ODOO_DB_NAME")
    db_host: str = PydanticField(default="database", alias="ODOO_DB_HOST")
    db_port: str = PydanticField(default="5432", alias="ODOO_DB_PORT")
    addons_path: str = PydanticField(default="/opt/project/addons,/odoo/addons,/volumes/enterprise", alias="ODOO_ADDONS_PATH")

    @property
    def container_name(self) -> str:
        return f"{self.container_prefix}-script-runner-1"

    @property
    def script_runner_container(self) -> str:
        return f"{self.container_prefix}-script-runner-1"

    @property
    def web_container(self) -> str:
        return f"{self.container_prefix}-web-1"

    @property
    def shell_container(self) -> str:
        return f"{self.container_prefix}-shell-1"

    @property
    def database(self) -> str:
        return self.db_name


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


def load_env_config() -> EnvConfig:
    # Detect if we're running in test mode
    is_testing = "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") is not None

    # Find the .env file to use
    env_file_path = None

    if is_testing:
        # For testing: Look for target project's .env file (../odoo-ai/.env)
        developer_dir = Path(__file__).parent.parent.parent.parent.parent  # Go up to Developer/ directory
        target_env_path = developer_dir / "odoo-ai" / ".env"
        if target_env_path.exists():
            env_file_path = target_env_path
            logger.info("Using target project .env from %s (test mode)", target_env_path)

    if not env_file_path:
        # Look for local .env file in project root (where pyproject.toml is)
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
        return EnvConfig(_env_file=env_file_path)
    else:
        return EnvConfig()


# noinspection PyMethodMayBeStatic
class HostOdooEnvironmentManager:
    def __init__(self, container_name: str | None = None, database: str | None = None) -> None:
        config = load_env_config()
        self.container_name = container_name or config.container_name
        self.database = database or config.database
        self.addons_path = config.addons_path
        self.db_host = config.db_host
        self.db_port = config.db_port

    async def get_environment(self) -> "HostOdooEnvironment":
        return HostOdooEnvironment(self.container_name, self.database, self.addons_path, self.db_host, self.db_port)

    def invalidate_environment_cache(self) -> None:
        logger.info("Cache invalidation called (no-op for Docker exec)")


# noinspection PyMethodMayBeStatic
class HostOdooEnvironment:
    def __init__(self, container_name: str, database: str, addons_path: str, db_host: str, db_port: str) -> None:
        # Sanitize container name to prevent command injection
        import re

        # Remove dangerous shell characters
        safe_name = container_name.split(";")[0].split("&&")[0].split("|")[0].split("`")[0].split("$(")[0].strip()
        # Only allow alphanumeric, underscore, dash, and dot
        safe_pattern = re.compile(r"^[a-zA-Z0-9_\-\.]+$")
        if not safe_pattern.match(safe_name):
            # If still not safe, use a default
            safe_name = "odoo-script-runner-1"
        self.container_name = safe_name
        self.database = database
        self.addons_path = addons_path
        self.db_host = db_host
        self.db_port = db_port
        self._registry: Registry | None = None

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
        """Get all model names from the Odoo registry."""
        registry = self.registry
        if isinstance(registry, DockerRegistry):
            # noinspection PyProtectedMember
            return await registry._fetch_models()
        return []

    async def has_model(self, model_name: str) -> bool:
        """Check if a model exists in the registry."""
        model_names = await self.get_model_names()
        return model_name in model_names

    def ensure_container_running(self) -> None:
        try:
            # Check container status with health information
            check_cmd = ["docker", "inspect", self.container_name, "--format", "{{.State.Status}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                logger.info(f"Container {self.container_name} not found: {result.stderr}")
                # Container doesn't exist, try to create it with docker compose
                config = load_env_config()
                service_name = self.container_name.replace(f"{config.container_prefix}-", "").replace("-1", "")
                logger.info(f"Attempting to create container {self.container_name} via docker compose service '{service_name}'...")

                # Get the project directory from the config's .env file path
                project_dir = None
                if hasattr(config, "_env_file") and config._env_file:
                    project_dir = str(Path(config._env_file).parent)
                else:
                    # Fallback: try to find compose files relative to this package
                    developer_dir = Path(__file__).parent.parent.parent.parent.parent
                    potential_project_dir = developer_dir / "odoo-ai"
                    if (potential_project_dir / "docker-compose.yml").exists():
                        project_dir = str(potential_project_dir)

                if not project_dir:
                    raise DockerConnectionError(self.container_name, "Cannot determine project directory for docker compose")

                # Start all essential services: database, script-runner, shell, and the requested service
                # This ensures all dependencies and related services are available
                essential_services = ["database", "script-runner", "shell", service_name]
                # Remove duplicates while preserving order
                services_to_start = list(dict.fromkeys(essential_services))
                compose_cmd = ["docker", "compose", "up", "-d"] + services_to_start
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
                essential_containers = [
                    f"{config.container_prefix}-database-1",
                    f"{config.container_prefix}-script-runner-1",
                    f"{config.container_prefix}-shell-1",
                ]

                containers_to_start = []
                for container in essential_containers:
                    check_cmd = ["docker", "inspect", container, "--format", "{{.State.Status}}"]
                    result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5)
                    if result.returncode != 0 or result.stdout.strip() != "running":
                        # Extract service name from container name
                        service = container.replace(f"{config.container_prefix}-", "").replace("-1", "")
                        containers_to_start.append(service)

                if containers_to_start:
                    logger.info(f"Essential containers not running: {containers_to_start}. Starting them...")
                    # Get the project directory from the config's .env file path
                    project_dir = None
                    if hasattr(config, "_env_file") and config._env_file:
                        project_dir = str(Path(config._env_file).parent)
                    else:
                        # Fallback: try to find compose files relative to this package
                        developer_dir = Path(__file__).parent.parent.parent.parent.parent
                        potential_project_dir = developer_dir / "odoo-ai"
                        if (potential_project_dir / "docker-compose.yml").exists():
                            project_dir = str(potential_project_dir)

                    if project_dir:
                        compose_cmd = ["docker", "compose", "up", "-d"] + containers_to_start
                        compose_result = subprocess.run(compose_cmd, capture_output=True, text=True, timeout=60, cwd=project_dir)
                        if compose_result.returncode == 0:
                            logger.info(f"Successfully started containers: {containers_to_start}")
                            import time

                            time.sleep(5)  # Give containers time to fully start
                        else:
                            logger.warning(f"Failed to start containers: {compose_result.stderr}")

            if status != "running":
                logger.info(f"Container {self.container_name} is {status}. Starting it...")
                start_cmd = ["docker", "start", self.container_name]
                start_result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=10)

                if start_result.returncode == 0:
                    logger.info(f"Successfully started container {self.container_name}")
                    import time

                    time.sleep(3)  # Give container more time to fully start

                    # Verify container is healthy after start
                    health_check_cmd = ["docker", "inspect", self.container_name, "--format", "{{.State.Health.Status}}"]
                    health_result = subprocess.run(health_check_cmd, capture_output=True, text=True, timeout=5)
                    if "unhealthy" in health_result.stdout:
                        logger.warning(f"Container {self.container_name} is unhealthy, attempting restart...")
                        restart_cmd = ["docker", "restart", self.container_name]
                        subprocess.run(restart_cmd, capture_output=True, text=True, timeout=15)
                        time.sleep(5)  # Wait for restart
                # If docker start failed, try docker compose up
                elif "No such container" in start_result.stderr or "not found" in start_result.stderr:
                    logger.info(f"Container {self.container_name} doesn't exist. Attempting to create with docker compose...")
                    service_name = self.container_name.replace(f"{self.config.container_prefix}-", "").replace("-1", "")
                    compose_cmd = ["docker", "compose", "up", "-d", service_name]
                    compose_result = subprocess.run(compose_cmd, capture_output=True, text=True, timeout=30)
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

    async def execute_code(self, code: str) -> dict[str, object] | str | int | float | bool | None:
        self.ensure_container_running()

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
            if process.returncode != 0:
                error_msg = f"Command failed with return code {process.returncode}: {process.stderr}"
                raise DockerConnectionError(self.container_name, error_msg)  # noqa: TRY301

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
