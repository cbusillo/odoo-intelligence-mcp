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
    result = {"success": False, "user_error": f"Model {model} not found"}
else:
    valid_operations = ["read", "write", "create", "unlink"]
    if operation not in valid_operations:
        result = {"success": False, "user_error": f"Invalid operation {operation}. Must be one of: {valid_operations}"}
    else:
        try:
            # Find the user
            user_obj = None
            user_candidates = []
            user_model = env["res.users"]
            if hasattr(user_model, "sudo"):
                user_model = user_model.sudo()
            if hasattr(user_model, "with_context"):
                user_model = user_model.with_context(active_test=False)

            if user.isdigit():
                user_id = int(user)
                user_obj = user_model.browse(user_id)
                try:
                    if not user_obj.exists():
                        user_obj = None
                except Exception:
                    user_obj = user_model.search([("id", "=", user_id)], limit=1)
            else:
                user_search = user_model.search([("login", "=", user)], limit=1)
                if user_search:
                    user_obj = user_search
                else:
                    email_search = user_model.search([("email", "=", user)], limit=1)
                    if email_search:
                        user_obj = email_search
                    else:
                        name_search = user_model.search([("name", "ilike", user)], limit=1)
                        if name_search:
                            user_obj = name_search

            user_data = None
            if user_obj:
                try:
                    user_records = user_obj.read(["id", "login", "active", "display_name", "partner_id"])
                    if user_records:
                        user_data = user_records[0]
                except Exception:
                    user_data = None

            db_name = None
            try:
                db_name = env.cr.dbname if hasattr(env, "cr") and env.cr else None
            except Exception:
                db_name = None

            if not user_data:
                if not user.isdigit():
                    candidate_domain = [
                        "|",
                        "|",
                        ("login", "ilike", user),
                        ("email", "ilike", user),
                        ("name", "ilike", user),
                    ]
                    for candidate in user_model.search(candidate_domain, limit=5):
                        user_candidates.append(
                            {
                                "id": candidate.id,
                                "login": candidate.login,
                                "name": candidate.name,
                                "active": candidate.active,
                            }
                        )
                if user.isdigit():
                    result = {"success": False, "user_error": f"User with ID {user} not found. Please verify the user ID exists."}
                else:
                    result = {
                        "success": False,
                        "user_error": f"User '{user}' not found. Provide a user id or exact login (often the email address).",
                    }
                if user_candidates:
                    result["user_candidates"] = user_candidates
                if db_name:
                    result["db_name"] = db_name
                if user.isdigit():
                    try:
                        env.cr.execute("SELECT id, login, active, partner_id FROM res_users WHERE id = %s", (user_id,))
                        row = env.cr.fetchone()
                        if row:
                            result["user_sql"] = {
                                "id": row[0],
                                "login": row[1],
                                "active": row[2],
                                "partner_id": row[3],
                            }
                    except Exception:
                        pass
            else:
                user_id = user_data.get("id")
                group_records = env["res.groups"].sudo().search([("user_ids", "in", user_id)])
                group_ids = group_records.ids
                analysis = {
                    "user": {
                        "id": user_id,
                        "login": user_data.get("login"),
                        "name": user_data.get("display_name") or user_data.get("login"),
                        "active": user_data.get("active"),
                    },
                    "model": model,
                    "operation": operation,
                    "record_id": record_id,
                    "db_name": db_name,
                    "permissions": empty_dict.copy(),
                    "groups": [],
                    "record_rules": [],
                    "model_access_rules": [],
                    "access_summary": empty_dict.copy(),
                }

                # Get user groups
                for group in group_records:
                    category_name = None
                    try:
                        if hasattr(group, "category_id") and group.category_id:
                            category_name = group.category_id.name
                    except Exception:
                        category_name = None
                    analysis["groups"].append({
                        "id": group.id,
                        "name": group.name,
                        "category": category_name,
                    })

                # Check model access rights
                try:
                    # Create environment as the specific user
                    user_env = env(user=user_id) if user_id else env
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
                        if access.group_id and access.group_id.id in group_ids:
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
                            rule_groups = set(rule.groups.ids)
                            user_groups = set(group_ids)
                            rule_info["applies_to_user"] = bool(rule_groups & user_groups)
                        else:
                            rule_info["applies_to_user"] = False

                        analysis["record_rules"].append(rule_info)
                except Exception as e:
                    analysis["record_rules_error"] = str(e)

                # Test specific record access if record_id provided
                if record_id:
                    try:
                        user_env = env(user=user_id) if user_id else env
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
                "user_error": str(e),
                "error_type": type(e).__name__,
                "user": user,
                "model": model,
                "operation": operation,
            }
"""
    )

    try:
        result = await env.execute_code(code)
        if isinstance(result, dict) and "user_error" in result and "error" not in result:
            result["error"] = result.pop("user_error")
            result.setdefault("success", False)
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "user": user,
            "model": model,
            "operation": operation,
        }
