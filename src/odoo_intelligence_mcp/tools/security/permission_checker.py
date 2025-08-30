from typing import Any

from ...type_defs.odoo_types import CompatibleEnvironment


async def check_permissions(
    env: CompatibleEnvironment, user: str, model: str, operation: str, record_id: int | None = None
) -> dict[str, Any]:
    code = (
        """
user = """
        + repr(user)
        + """
model = """
        + repr(model)
        + """
operation = """
        + repr(operation)
        + """
record_id = """
        + repr(record_id)
        + """
empty_dict = dict()

# Validate inputs
if model not in env:
    result = {"error": f"Model {model} not found"}
else:
    valid_operations = ["read", "write", "create", "unlink"]
    if operation not in valid_operations:
        result = {"error": f"Invalid operation {operation}. Must be one of: {valid_operations}"}
    else:
        try:
            # Find the user
            if user.isdigit():
                user_id = int(user)
                # Check if user exists before browsing
                user_exists = env["res.users"].search_count([("id", "=", user_id)])
                if user_exists:
                    user_obj = env["res.users"].browse(user_id)
                else:
                    user_obj = None
            else:
                user_search = env["res.users"].search([("login", "=", user)], limit=1)
                user_obj = user_search if user_search else None

            if not user_obj:
                if user.isdigit():
                    result = {"error": f"User with ID {user} not found. Please verify the user ID exists."}
                else:
                    result = {"error": f"User with login '{user}' not found. Try using the user ID instead of login, or verify the login exists."}
            else:
                analysis = {
                    "user": {
                        "id": user_obj.id,
                        "login": user_obj.login,
                        "name": user_obj.name,
                        "active": user_obj.active
                    },
                    "model": model,
                    "operation": operation,
                    "record_id": record_id,
                    "permissions": empty_dict.copy(),
                    "groups": [],
                    "record_rules": [],
                    "model_access_rules": [],
                    "access_summary": empty_dict.copy(),
                }

                # Get user groups
                for group in user_obj.groups_id:
                    analysis["groups"].append({
                        "id": group.id,
                        "name": group.name,
                        "category": group.category_id.name if group.category_id else None
                    })

                # Check model access rights
                try:
                    # Create environment as the specific user
                    user_env = env(user=user_obj.id)
                    user_model = user_env[model]

                    # Test each operation
                    for op in valid_operations:
                        try:
                            # Try check_access_rights method instead of check_access
                            if hasattr(user_model, 'check_access_rights'):
                                has_access = user_model.check_access_rights(op, raise_exception=False)
                            else:
                                # Fallback: try to perform the operation and catch exception
                                if op == "read":
                                    user_model.search([], limit=1)
                                    has_access = True
                                elif op == "create":
                                    # Don't actually create, just check if we can
                                    has_access = hasattr(user_model, 'create')
                                elif op == "write":
                                    has_access = hasattr(user_model, 'write')
                                elif op == "unlink":
                                    has_access = hasattr(user_model, 'unlink')
                                else:
                                    has_access = False
                            analysis["permissions"][op] = bool(has_access)
                        except Exception as e:
                            analysis["permissions"][op] = False
                            if "Access" not in str(e):
                                analysis[f"{op}_error"] = str(e)
                except Exception as e:
                    analysis["permissions_error"] = str(e)

                # Get model access rules
                try:
                    ir_model_access = env["ir.model.access"]
                    model_access_records = ir_model_access.search([("model_id.model", "=", model)])

                    for access in model_access_records:
                        rule = {
                            "name": access.name,
                            "group": access.group_id.name if access.group_id else "All Users",
                            "permissions": {
                                "read": access.perm_read,
                                "write": access.perm_write,
                                "create": access.perm_create,
                                "unlink": access.perm_unlink,
                            },
                        }

                        # Check if user has this group
                        if access.group_id and access.group_id in user_obj.groups_id:
                            rule["user_has_group"] = True
                        elif not access.group_id:
                            rule["user_has_group"] = True  # No group = all users
                        else:
                            rule["user_has_group"] = False

                        analysis["model_access_rules"].append(rule)
                except Exception as e:
                    analysis["model_access_error"] = str(e)

                # Get record rules (row-level security)
                try:
                    ir_rule = env["ir.rule"]
                    record_rules = ir_rule.search([("model_id.model", "=", model), ("active", "=", True)])

                    for rule in record_rules:
                        rule_info = {
                            "name": rule.name,
                            "domain": rule.domain_force or "[]",
                            "groups": [g.name for g in rule.groups] if rule.groups else [],
                            "global": getattr(rule, "global", getattr(rule, "global_rule", False)),
                            "permissions": {
                                "read": rule.perm_read,
                                "write": rule.perm_write,
                                "create": rule.perm_create,
                                "unlink": rule.perm_unlink,
                            },
                        }

                        # Check if rule applies to user
                        is_global = getattr(rule, "global", getattr(rule, "global_rule", False))
                        if is_global:
                            rule_info["applies_to_user"] = True
                        elif rule.groups:
                            rule_groups = set(rule.groups)
                            user_groups = set(user_obj.groups_id)
                            rule_info["applies_to_user"] = bool(rule_groups & user_groups)
                        else:
                            rule_info["applies_to_user"] = False

                        analysis["record_rules"].append(rule_info)
                except Exception as e:
                    analysis["record_rules_error"] = str(e)

                # Test specific record access if record_id provided
                if record_id:
                    try:
                        user_env = env(user=user_obj.id)
                        user_model = user_env[model]
                        record = user_model.browse(record_id)

                        analysis["record_access"] = {
                            "record_id": record_id,
                            "exists": bool(record.exists()),
                            "can_read": False,
                            "can_write": False,
                            "can_unlink": False,
                        }

                        if record.exists():
                            # Test read access
                            try:
                                record.read(["id"])
                                analysis["record_access"]["can_read"] = True
                            except Exception as e:
                                analysis["record_access"]["read_error"] = str(e)

                            # Test write access
                            try:
                                record.check_access("write")
                                analysis["record_access"]["can_write"] = True
                            except Exception as e:
                                analysis["record_access"]["write_error"] = str(e)

                            # Test unlink access
                            try:
                                record.check_access("unlink")
                                analysis["record_access"]["can_unlink"] = True
                            except Exception as e:
                                analysis["record_access"]["unlink_error"] = str(e)
                        else:
                            analysis["record_access"]["error"] = "Record does not exist or user cannot access it"
                    except Exception as e:
                        analysis["record_access"] = {"record_id": record_id, "error": f"Failed to check record access: {str(e)}"}

                # Generate summary
                has_model_access = analysis["permissions"].get(operation, False)
                record_rules_list = analysis["record_rules"]
                applicable_rules = [
                    r for r in record_rules_list
                    if r.get("applies_to_user") and r.get("permissions", empty_dict).get(operation)
                ]

                analysis["access_summary"] = {
                    "has_model_access": has_model_access,
                    "applicable_record_rules_count": len(applicable_rules),
                    "likely_has_access": has_model_access and (not record_rules_list or applicable_rules),
                }

                # Add recommendation
                if analysis["permissions"].get(operation, False):
                    if record_rules_list:
                        if applicable_rules:
                            recommendation = f"User has {operation} access. Check record rules if specific records are inaccessible."
                        else:
                            recommendation = f"User has model {operation} access but no applicable record rules. May be blocked by record-level security."
                    else:
                        recommendation = f"User has {operation} access with no record rules restrictions."
                else:
                    missing_groups = []
                    for rule in analysis["model_access_rules"]:
                        if rule.get("permissions", empty_dict).get(operation) and not rule.get("user_has_group"):
                            group = rule.get("group")
                            if group and group != "All Users":
                                missing_groups.append(str(group))

                    if missing_groups:
                        recommendation = f"User lacks {operation} access. Consider adding user to groups: {', '.join(set(missing_groups))}"
                    else:
                        recommendation = f"User lacks {operation} access. No model access rules grant {operation} permission for this user."

                analysis["access_summary"]["recommendation"] = recommendation

                result = analysis

        except Exception as e:
            result = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "user": user,
                "model": model,
                "operation": operation,
            }
"""
    )

    try:
        return await env.execute_code(code)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "user": user,
            "model": model,
            "operation": operation,
        }
