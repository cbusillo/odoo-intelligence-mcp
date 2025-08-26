import json
import pprint
import re
import subprocess
from pathlib import Path
from typing import Any

from ...core.env import load_env_config
from ...type_defs.odoo_types import CompatibleEnvironment


# noinspection PyTooManyReturnStatements
async def execute_code(env: CompatibleEnvironment, code: str) -> dict[str, Any]:
    try:
        # Check if the environment has a Docker-based execute_code method
        if hasattr(env, "execute_code"):
            # Use the environment's execute_code method which properly handles Docker execution
            result = await env.execute_code(code)

            # The Docker execution returns raw results, format them appropriately
            if isinstance(result, dict):
                if "error" in result:
                    return {
                        "success": False,
                        "error": result["error"],
                        "error_type": result.get("error_type", "ExecutionError"),
                        "hint": "Make sure to use 'env' to access Odoo models, e.g., env['product.template'].search([])",
                    }
                elif "output" in result and result.get("raw"):
                    # Raw output from Docker
                    return {"success": True, "output": result["output"]}
                else:
                    return {"success": True, "result": result}
        else:
            # Fallback to local execution for testing with mock environments
            namespace = {
                "env": env,
                "fields": env["ir.model.fields"],
                "datetime": __import__("datetime"),
                "date": __import__("datetime").date,
                "timedelta": __import__("datetime").timedelta,
                "json": json,
                "re": re,
                "Path": Path,
                "pprint": pprint,
            }

            compiled_code = compile(code, "<mcp_execute>", "exec")
            exec(compiled_code, namespace)  # noqa: S102

            if "result" in namespace:
                result_value = namespace["result"]
                if hasattr(result_value, "_name"):
                    # noinspection PyProtectedMember
                    model_name = result_value._name
                    # noinspection PyTypeChecker
                    display_names = [rec.display_name for rec in result_value[:10]]
                    return {
                        "success": True,
                        "result_type": "recordset",
                        "model": model_name,
                        "count": len(result_value),
                        "ids": result_value.ids[:100],
                        "display_names": display_names,
                    }
                if isinstance(result_value, (dict, list, str, int, float, bool, type(None))):
                    return {"success": True, "result": result_value}
                return {"success": True, "result": str(result_value), "result_type": type(result_value).__name__}
            return {"success": True, "message": "Code executed successfully. Assign to 'result' variable to see output."}

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "hint": "Make sure to use 'env' to access Odoo models, e.g., env['product.template'].search([])",
        }


def odoo_shell(code: str, timeout: int = 30) -> dict[str, Any]:
    try:
        config = load_env_config()
        container_name = config["container_name"]
        database = config["database"]
        cmd = ["docker", "exec", "-i", container_name, "/odoo/odoo-bin", "shell", f"--database={database}"]

        result = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=timeout)

        return {
            "success": result.returncode == 0,
            "code": code,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timeout": timeout,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Shell command timed out after {timeout} seconds", "code": code}
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "code": code}
