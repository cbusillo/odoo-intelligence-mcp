import subprocess
from unittest.mock import patch

import pytest

from odoo_intelligence_mcp.tools.code.execute_code import execute_code, odoo_shell
from odoo_intelligence_mcp.type_defs.odoo_types import CompatibleEnvironment
from tests.fixtures.types import MockSubprocessRun


class TestExecuteCodeIntegration:
    @pytest.mark.asyncio
    async def test_execute_code_basic_model_access(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = "result = len(env.registry)"

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert isinstance(result["result"], int)
        assert result["result"] > 0  # Should have some models registered

    @pytest.mark.asyncio
    async def test_execute_code_model_search_count(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = 'result = env["res.users"].search_count([])'

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert isinstance(result["result"], int)
        assert result["result"] >= 1  # Should have at least admin user

    @pytest.mark.asyncio
    async def test_execute_code_model_browse_admin(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
admin_user = env["res.users"].browse(1)
result = {
    "id": admin_user.id,
    "login": admin_user.login,
    "name": admin_user.name,
    "is_admin": admin_user.id == 1
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["id"] == 1
        assert result["result"]["is_admin"] is True
        assert "login" in result["result"]
        assert "name" in result["result"]

    @pytest.mark.asyncio
    async def test_execute_code_field_access(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
partner_fields = env["res.partner"]._fields
result = {
    "has_name_field": "name" in partner_fields,
    "has_email_field": "email" in partner_fields,
    "name_field_type": partner_fields["name"].type if "name" in partner_fields else None,
    "total_fields": len(partner_fields)
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["has_name_field"] is True
        assert result["result"]["has_email_field"] is True
        assert result["result"]["name_field_type"] == "char"
        assert result["result"]["total_fields"] > 10  # res.partner has many fields

    @pytest.mark.asyncio
    async def test_execute_code_recordset_operations(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
# Get all companies
companies = env["res.partner"].search([("is_company", "=", True)], limit=5)
result = {
    "recordset_type": "recordset" if hasattr(companies, "_name") else "other",
    "model_name": companies._name if hasattr(companies, "_name") else None,
    "count": len(companies),
    "first_company_name": companies[0].name if companies else None,
    "ids": companies.ids[:3]  # First 3 IDs
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["recordset_type"] == "recordset"
        assert result["result"]["model_name"] == "res.partner"
        assert isinstance(result["result"]["count"], int)
        assert isinstance(result["result"]["ids"], list)

    @pytest.mark.asyncio
    async def test_execute_code_datetime_operations(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
from datetime import datetime, timedelta
now = datetime.now()
tomorrow = now + timedelta(days=1)
result = {
    "current_year": now.year,
    "is_future": tomorrow > now,
    "day_difference": (tomorrow - now).days
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["current_year"] >= 2024
        assert result["result"]["is_future"] is True
        assert result["result"]["day_difference"] == 1

    @pytest.mark.asyncio
    async def test_execute_code_json_operations(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
import json
data = {"test": "value", "number": 42}
json_str = json.dumps(data)
parsed = json.loads(json_str)
result = {
    "original": data,
    "json_string": json_str,
    "parsed_back": parsed,
    "are_equal": data == parsed
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["are_equal"] is True
        assert result["result"]["original"] == {"test": "value", "number": 42}
        assert '"test": "value"' in result["result"]["json_string"]

    @pytest.mark.asyncio
    async def test_execute_code_regex_operations(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
import re
text = "Email: test@example.com, Phone: 123-456-7890"
email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"
phone_pattern = r"\\d{3}-\\d{3}-\\d{4}"

email_match = re.search(email_pattern, text)
phone_match = re.search(phone_pattern, text)

result = {
    "email_found": email_match.group() if email_match else None,
    "phone_found": phone_match.group() if phone_match else None,
    "has_email": bool(email_match),
    "has_phone": bool(phone_match)
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["email_found"] == "test@example.com"
        assert result["result"]["phone_found"] == "123-456-7890"
        assert result["result"]["has_email"] is True
        assert result["result"]["has_phone"] is True

    @pytest.mark.asyncio
    async def test_execute_code_model_relationship_analysis(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
# Analyze res.partner model relationships
partner_model = env["res.partner"]
many2one_fields = []
one2many_fields = []

for field_name, field in partner_model._fields.items():
    if field.type == "many2one":
        many2one_fields.append({
            "name": field_name,
            "comodel": getattr(field, "comodel_name", None)
        })
    elif field.type == "one2many":
        one2many_fields.append({
            "name": field_name,
            "comodel": getattr(field, "comodel_name", None)
        })

result = {
    "many2one_count": len(many2one_fields),
    "one2many_count": len(one2many_fields),
    "sample_many2one": many2one_fields[:3],  # First 3
    "sample_one2many": one2many_fields[:3]   # First 3
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["many2one_count"] > 0
        assert result["result"]["one2many_count"] > 0
        assert isinstance(result["result"]["sample_many2one"], list)
        assert isinstance(result["result"]["sample_one2many"], list)

    @pytest.mark.asyncio
    async def test_execute_code_error_handling_with_real_env(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = 'result = env["nonexistent.model"].search([])'

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is False
        assert "error" in result
        assert "error_type" in result
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_execute_code_complex_data_analysis(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
# Analyze user distribution by creation date
users = env["res.users"].search([])
creation_years = {}

for user in users:
    if user.create_date:
        year = user.create_date.year
        creation_years[year] = creation_years.get(year, 0) + 1

result = {
    "total_users": len(users),
    "users_with_create_date": len([u for u in users if u.create_date]),
    "creation_year_distribution": creation_years,
    "latest_year": max(creation_years.keys()) if creation_years else None
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result"]["total_users"] >= 1
        assert result["result"]["users_with_create_date"] >= 1
        assert isinstance(result["result"]["creation_year_distribution"], dict)
        if result["result"]["latest_year"]:
            assert result["result"]["latest_year"] >= 2020

    @pytest.mark.asyncio
    async def test_execute_code_recordset_return_handling(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        # Search for any user to ensure we get results
        code = 'result = env["res.users"].search([], limit=5)'

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert result["result_type"] == "recordset"
        assert result["model"] == "res.users"
        assert result["count"] >= 1  # At least one user should exist
        assert isinstance(result["ids"], list)
        assert len(result["ids"]) >= 1
        assert isinstance(result["display_names"], list)
        assert len(result["display_names"]) >= 1

    @pytest.mark.asyncio
    async def test_execute_code_environment_context_access(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
result = {
    "env_context": dict(env.context),
    "env_uid": env.uid,
    "env_company": env.company.name if hasattr(env, "company") else "No company",
    "registry_size": len(env.registry),
    "has_cr": hasattr(env, "cr"),
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert isinstance(result["result"]["env_context"], dict)
        assert isinstance(result["result"]["env_uid"], int)
        assert result["result"]["registry_size"] > 0
        # Note: env.cr might not be available in all test environments

    @pytest.mark.asyncio
    async def test_execute_code_model_method_calls(self, real_odoo_env_if_available: CompatibleEnvironment) -> None:
        code = """
# Test calling model methods
partner_model = env["res.partner"]
fields_get_result = partner_model.fields_get(["name", "email"])

result = {
    "fields_get_keys": list(fields_get_result.keys()),
    "name_field_info": fields_get_result.get("name", {}),
    "email_field_info": fields_get_result.get("email", {}),
    "method_callable": callable(getattr(partner_model, "fields_get", None))
}
"""

        result = await execute_code(real_odoo_env_if_available, code)

        assert result["success"] is True
        assert "name" in result["result"]["fields_get_keys"]
        assert "email" in result["result"]["fields_get_keys"]
        assert result["result"]["method_callable"] is True
        assert "string" in result["result"]["name_field_info"]


class TestOdooShellIntegration:
    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_basic_execution(self, mock_subprocess_run: MockSubprocessRun) -> None:
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "5\n"
        mock_subprocess_run.return_value.stderr = ""

        code = "print(2 + 3)"
        result = odoo_shell(code)

        assert result["success"] is True
        assert result["stdout"] == "5\n"
        assert result["exit_code"] == 0

        # Verify Docker command was constructed correctly
        from odoo_intelligence_mcp.core.env import load_env_config

        config = load_env_config()

        mock_subprocess_run.assert_called_once()
        args = mock_subprocess_run.call_args[0][0]
        expected_args = [
            "docker",
            "exec",
            "-i",
            config.container_name,
            "/odoo/odoo-bin",
            "shell",
            f"--database={config.database}",
        ]
        assert args == expected_args

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_model_access(self, mock_subprocess_run: MockSubprocessRun) -> None:
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "Total partners: 50\n"
        mock_subprocess_run.return_value.stderr = ""

        code = """
partners = env['res.partner'].search([])
print(f"Total partners: {len(partners)}")
"""
        result = odoo_shell(code)

        assert result["success"] is True
        assert "Total partners: 50" in result["stdout"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_error_handling(self, mock_subprocess_run: MockSubprocessRun) -> None:
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = ""
        mock_subprocess_run.return_value.stderr = (
            'Traceback (most recent call last):\n  File "<console>", line 1\nSyntaxError: invalid syntax\n'
        )

        code = "print('unclosed string"
        result = odoo_shell(code)

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert "SyntaxError" in result["stderr"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_multiline_script(self, mock_subprocess_run: MockSubprocessRun) -> None:
        expected_output = "Starting analysis...\nFound 10 active users\nAnalysis complete.\n"
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = expected_output
        mock_subprocess_run.return_value.stderr = ""

        code = """
print("Starting analysis...")
users = env['res.users'].search([('active', '=', True)])
print(f"Found {len(users)} active users")
print("Analysis complete.")
"""
        result = odoo_shell(code)

        assert result["success"] is True
        assert result["stdout"] == expected_output
        assert "Starting analysis" in result["stdout"]
        assert "active users" in result["stdout"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_with_imports(self, mock_subprocess_run: MockSubprocessRun) -> None:
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "Current time: 2024-01-15 10:30:00\n"
        mock_subprocess_run.return_value.stderr = ""

        code = """
from datetime import datetime
current_time = datetime.now()
print(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
"""
        result = odoo_shell(code)

        assert result["success"] is True
        assert "Current time:" in result["stdout"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_timeout_handling(self, mock_subprocess_run: MockSubprocessRun) -> None:
        from odoo_intelligence_mcp.core.env import load_env_config

        config = load_env_config()

        mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd=["docker", "exec", "-i", config.container_name], timeout=5)

        code = "import time; time.sleep(10)"
        result = odoo_shell(code, timeout=5)

        assert result["success"] is False
        assert "error" in result
        assert "timed out after 5 seconds" in result["error"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_unicode_handling(self, mock_subprocess_run: MockSubprocessRun) -> None:
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "Partner: José García (España)\n"
        mock_subprocess_run.return_value.stderr = ""

        code = 'print("Partner: José García (España)")'
        result = odoo_shell(code)

        assert result["success"] is True
        assert "José García" in result["stdout"]
        assert "España" in result["stdout"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    @pytest.mark.asyncio
    async def test_odoo_shell_database_operations(self, mock_subprocess_run: MockSubprocessRun) -> None:
        """Test odoo_shell with database operation simulation."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "Created partner: Test Company (ID: 123)\nPartner saved successfully.\n"
        mock_subprocess_run.return_value.stderr = ""

        code = """
# Create a new partner
partner = env['res.partner'].create({
    'name': 'Test Company',
    'is_company': True,
    'email': 'test@example.com'
})
print(f"Created partner: {partner.name} (ID: {partner.id})")
env.cr.commit()
print("Partner saved successfully.")
"""
        result = odoo_shell(code)

        assert result["success"] is True
        assert "Created partner: Test Company" in result["stdout"]
        assert "ID: 123" in result["stdout"]
        assert "saved successfully" in result["stdout"]

    @pytest.mark.asyncio
    @patch("odoo_intelligence_mcp.core.env.subprocess.run")
    async def test_odoo_shell_vs_execute_code_consistency(
        self, mock_subprocess_run: MockSubprocessRun, real_odoo_env_if_available: CompatibleEnvironment
    ) -> None:
        # Mock both the execute_code path (via environment) and the direct odoo_shell path
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = '{"result": 5}'
        mock_subprocess_run.return_value.stderr = ""

        # Test execute_code through environment (mocked subprocess)
        code_for_execute = "result = 2 + 3"
        execute_result = await execute_code(real_odoo_env_if_available, code_for_execute)

        # Reset mock for odoo_shell direct call
        mock_subprocess_run.return_value.stdout = "5\n"

        # Test direct odoo_shell call (also mocked subprocess)
        code_for_shell = "print(2 + 3)"
        shell_result = odoo_shell(code_for_shell)

        assert execute_result["success"] is True
        assert execute_result["result"]["result"] == 5

        assert shell_result["success"] is True
        assert "5" in shell_result["stdout"]

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_odoo_shell_exception_types(self, mock_subprocess_run: MockSubprocessRun) -> None:
        mock_subprocess_run.side_effect = Exception("Docker daemon not running")

        code = "print('test')"
        result = odoo_shell(code)

        assert result["success"] is False
        assert result["error_type"] == "Exception"
        assert "Docker daemon not running" in result["error"]
