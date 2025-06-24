from collections.abc import Callable
from typing import Any

from ..tools.addon import addon_dependencies, module_structure
from ..tools.code.execute_code import execute_code
from ..tools.code.search_code import search_code
from ..tools.operations import container_logs, container_restart, container_status, module_update
from .base_service import BaseService, ServiceExecutionError

HIGH_COMPLEXITY_FILE_COUNT = 20
MEDIUM_COMPLEXITY_FILE_COUNT = 10
WIZARD_MODULE_THRESHOLD = 3
MANY_DEPENDENCIES_THRESHOLD = 10


class OdooAnalyzer(BaseService):
    def get_service_name(self) -> str:
        return "OdooAnalyzer"

    async def analyze_project_health(self) -> dict[str, Any]:
        try:
            container_status_result = await self._safe_execute("get container status", container_status.odoo_status)

            if not container_status_result.get("all_running", False):
                return {
                    "status": "unhealthy",
                    "reason": "Odoo containers not running",
                    "container_status": container_status_result,
                    "recommendations": ["Start Odoo containers", "Check Docker daemon"],
                }

            execution_test = await self._safe_execute("test odoo execution", execute_code, "print('health_check')")

            if not execution_test.get("success", False):
                return {
                    "status": "unhealthy",
                    "reason": "Cannot execute code in Odoo environment",
                    "execution_test": execution_test,
                    "recommendations": ["Restart Odoo containers", "Check database connection"],
                }

            return {
                "status": "healthy",
                "container_status": container_status_result,
                "execution_test": execution_test,
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to analyze project health: {e!s}") from e

    async def search_across_modules(self, pattern: str, file_type: str = "py") -> dict[str, Any]:
        try:
            search_results = await self._safe_execute("search code", search_code, pattern, file_type)

            if not search_results.get("results"):
                return {
                    "pattern": pattern,
                    "file_type": file_type,
                    "matches": [],
                    "summary": {"total_files": 0, "total_matches": 0},
                }

            organized_results = OdooAnalyzer._organize_search_results(search_results["results"])

            return {
                "pattern": pattern,
                "file_type": file_type,
                "matches": search_results["results"],
                "organized_by_module": organized_results,
                "summary": search_results.get("summary", {}),
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to search across modules: {e!s}") from e

    async def get_module_overview(self, module_name: str) -> dict[str, Any]:
        try:
            structure = await self._safe_execute("get module structure", module_structure.get_module_structure, module_name)

            if "error" in structure:
                return structure

            dependencies = await self._safe_execute(
                "get module dependencies", addon_dependencies.get_addon_dependencies, module_name
            )

            if "error" in dependencies:
                dependencies = {"error": dependencies["error"]}

            return {
                "module_name": module_name,
                "structure": structure,
                "dependencies": dependencies,
                "overview": OdooAnalyzer._generate_module_overview(structure, dependencies),
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to get module overview for '{module_name}': {e!s}") from e

    async def execute_odoo_command(self, code: str) -> dict[str, Any]:
        try:
            result = await self._safe_execute("execute odoo command", execute_code, code)

            return {
                "code": code,
                "success": result.get("success", False),
                "output": result.get("output", ""),
                "error": result.get("error"),
                "execution_time": result.get("execution_time"),
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to execute Odoo command: {e!s}") from e

    async def update_module(self, module_name: str, force_install: bool = False) -> dict[str, Any]:
        try:
            result = await self._safe_execute("update module", module_update.odoo_update_module, module_name, force_install)

            return {
                "module_name": module_name,
                "force_install": force_install,
                "success": result.get("success", False),
                "output": result.get("output", ""),
                "error": result.get("error"),
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to update module '{module_name}': {e!s}") from e

    async def restart_containers(self, services: str | None = None) -> dict[str, Any]:
        try:
            result = await self._safe_execute("restart containers", container_restart.odoo_restart, services)

            return {
                "services": services or "all",
                "success": result.get("success", False),
                "output": result.get("output", ""),
                "error": result.get("error"),
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to restart containers: {e!s}") from e

    async def get_container_logs(self, container: str = "odoo-opw-web-1", lines: int = 100) -> dict[str, Any]:
        try:
            result = await self._safe_execute("get container logs", container_logs.odoo_logs, container, lines)

            return {
                "container": container,
                "lines": lines,
                "logs": result.get("logs", ""),
                "error": result.get("error"),
            }

        except Exception as e:
            raise ServiceExecutionError(f"Failed to get container logs: {e!s}") from e

    @staticmethod
    def _organize_search_results(results: list[dict[str, Any]]) -> dict[str, Any]:
        organized = {}

        for result in results:
            file_path = result["file"]
            module_name = OdooAnalyzer._extract_module_name_from_path(file_path)

            if module_name not in organized:
                organized[module_name] = {
                    "module": module_name,
                    "files": [],
                    "total_matches": 0,
                }

            organized[module_name]["files"].append(result)
            organized[module_name]["total_matches"] += len(result.get("matches", []))

        return organized

    @staticmethod
    def _extract_module_name_from_path(file_path: str) -> str:
        parts = file_path.split("/")

        for i, part in enumerate(parts):
            if part in ["addons", "enterprise"] and i + 1 < len(parts):
                return parts[i + 1]

        return "unknown"

    @staticmethod
    def _calculate_total_files(structure: dict[str, Any]) -> int:
        total_files = 0
        if "structure" in structure:
            for section in structure["structure"].values():
                if isinstance(section, dict) and "count" in section:
                    total_files += section["count"]
        return total_files

    @staticmethod
    def _determine_complexity(total_files: int) -> str:
        if total_files > HIGH_COMPLEXITY_FILE_COUNT:
            return "high"
        if total_files > MEDIUM_COMPLEXITY_FILE_COUNT:
            return "medium"
        return "low"

    @staticmethod
    def _determine_module_type(struct: dict[str, Any]) -> str:
        if struct.get("controllers", {}).get("count", 0) > 0:
            return "web_module"
        if struct.get("reports", {}).get("count", 0) > 0:
            return "reporting_module"
        if struct.get("wizards", {}).get("count", 0) > WIZARD_MODULE_THRESHOLD:
            return "workflow_module"
        return "simple"

    @staticmethod
    def _identify_features(struct: dict[str, Any]) -> list[str]:
        features = []
        if struct.get("models", {}).get("count", 0) > 0:
            features.append("data_models")
        if struct.get("views", {}).get("count", 0) > 0:
            features.append("user_interface")
        if struct.get("static", {}).get("js", []):
            features.append("javascript_widgets")
        if struct.get("tests", {}).get("count", 0) > 0:
            features.append("automated_tests")
        return features

    @staticmethod
    def _check_concerns(dependencies: dict[str, Any]) -> list[str]:
        concerns = []
        if not dependencies.get("error") and isinstance(dependencies, dict):
            deps = dependencies.get("dependencies", [])
            if len(deps) > MANY_DEPENDENCIES_THRESHOLD:
                concerns.append("many_dependencies")

            external_deps = dependencies.get("external_dependencies", {})
            if external_deps.get("python") or external_deps.get("bin"):
                concerns.append("external_dependencies")
        return concerns

    @classmethod
    def _generate_module_overview(cls, structure: dict[str, Any], dependencies: dict[str, Any]) -> dict[str, Any]:
        if "error" in structure:
            return {"error": "Cannot generate overview - structure analysis failed"}

        total_files = cls._calculate_total_files(structure)
        complexity = cls._determine_complexity(total_files)

        struct = structure.get("structure", {})
        module_type = cls._determine_module_type(struct)
        features = cls._identify_features(struct)
        concerns = cls._check_concerns(dependencies)

        return {
            "complexity": complexity,
            "type": module_type,
            "features": features,
            "concerns": concerns,
        }

    async def _safe_execute(self, operation: str, func: Callable[..., Any], *args: object, **kwargs: object) -> Any:  # noqa: ANN401
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            raise ServiceExecutionError(f"Failed to execute {operation} in {self.get_service_name()}: {e!s}") from e
