from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock


def create_fs_ast_index(models: dict[str, dict[str, Any]] | None = None, include_defaults: bool = True) -> dict[str, Any]:
    base_models: dict[str, dict[str, Any]] = {
        "res.partner": {
            "class": "ResPartner",
            "module": "base",
            "file": "/odoo/addons/base/models/res_partner.py",
            "description": "Partner records",
            "fields": {
                "name": {"type": "char", "string": "Name", "required": True, "store": True},
                "state": {
                    "type": "selection",
                    "string": "State",
                    "selection": [("draft", "Draft"), ("done", "Done")],
                    "required": True,
                    "store": True,
                },
                "parent_id": {
                    "type": "many2one",
                    "string": "Parent",
                    "relation": "res.partner",
                    "required": False,
                    "store": True,
                },
                "child_ids": {
                    "type": "one2many",
                    "string": "Children",
                    "relation": "res.partner",
                    "inverse_name": "parent_id",
                    "store": True,
                },
                "tag_ids": {
                    "type": "many2many",
                    "string": "Tags",
                    "relation": "res.partner.category",
                    "store": True,
                },
                "display_name": {
                    "type": "char",
                    "string": "Display Name",
                    "compute": "_compute_display_name",
                    "store": False,
                },
                "manager_id": {
                    "type": "many2one",
                    "string": "Manager",
                    "relation": "res.users",
                    "related": "user_id.manager_id",
                    "store": True,
                },
            },
            "decorators": {
                "_compute_display_name": [{"type": "depends", "args": ["name"]}],
                "_onchange_state": [{"type": "onchange", "args": ["state"]}],
                "_check_state": [{"type": "constrains", "args": ["state"]}],
            },
            "methods": ["create", "write", "unlink", "search", "read", "exists", "custom_sync", "custom_validate"],
            "inherits": [],
            "delegates": {},
        },
        "sale.order": {
            "class": "SaleOrder",
            "module": "sale",
            "file": "/odoo/addons/sale/models/sale_order.py",
            "description": "Sale Order",
            "fields": {
                "name": {"type": "char", "string": "Order Reference", "required": True, "store": True},
                "state": {
                    "type": "selection",
                    "string": "Status",
                    "selection": [("draft", "Quotation"), ("sale", "Sale Order")],
                    "required": True,
                    "store": True,
                },
                "partner_id": {
                    "type": "many2one",
                    "string": "Customer",
                    "relation": "res.partner",
                    "required": True,
                    "store": True,
                },
                "order_line": {
                    "type": "one2many",
                    "string": "Order Lines",
                    "relation": "sale.order.line",
                    "inverse_name": "order_id",
                    "store": True,
                },
                "tag_ids": {
                    "type": "many2many",
                    "string": "Tags",
                    "relation": "sale.tag",
                    "store": True,
                },
                "amount_total": {
                    "type": "float",
                    "string": "Total",
                    "compute": "_compute_amount_total",
                    "store": True,
                },
                "display_name": {
                    "type": "char",
                    "string": "Display Name",
                    "compute": "_compute_display_name",
                    "store": False,
                },
            },
            "decorators": {
                "_compute_amount_total": [{"type": "depends", "args": ["order_line"]}],
                "_onchange_partner_id": [{"type": "onchange", "args": ["partner_id"]}],
            },
            "methods": ["create", "write", "unlink", "search", "read", "action_confirm", "action_cancel"],
            "inherits": ["res.partner"],
            "delegates": {"partner_id": "res.partner"},
        },
        "sale.order.line": {
            "class": "SaleOrderLine",
            "module": "sale",
            "file": "/odoo/addons/sale/models/sale_order_line.py",
            "description": "Order line",
            "fields": {
                "name": {"type": "char", "string": "Description", "store": True},
                "order_id": {"type": "many2one", "string": "Order", "relation": "sale.order", "store": True},
                "product_id": {"type": "many2one", "string": "Product", "relation": "product.product", "store": True},
                "qty": {"type": "integer", "string": "Quantity", "store": True},
            },
            "decorators": {},
            "methods": ["create", "write", "unlink", "search", "read"],
            "inherits": [],
            "delegates": {},
        },
        "product.template": {
            "class": "ProductTemplate",
            "module": "product",
            "file": "/odoo/addons/product/models/product_template.py",
            "description": "Product catalog entry",
            "fields": {
                "name": {"type": "char", "string": "Name", "required": True, "store": True},
                "default_code": {"type": "char", "string": "Internal Reference", "store": True},
                "sale_ok": {"type": "boolean", "string": "Can be Sold", "store": True},
                "categ_id": {"type": "many2one", "string": "Category", "relation": "product.category", "store": True},
                "tag_ids": {"type": "many2many", "string": "Tags", "relation": "product.tag", "store": True},
                "description_sale": {"type": "text", "string": "Sales Description", "related": "name", "store": True},
            },
            "decorators": {},
            "methods": ["create", "write", "unlink", "search", "read", "action_publish", "action_unpublish"],
            "inherits": [],
            "delegates": {},
        },
        "account.move": {
            "class": "AccountMove",
            "module": "account",
            "file": "/odoo/addons/account/models/account_move.py",
            "description": "Journal Entry",
            "fields": {
                "name": {"type": "char", "string": "Number", "store": True},
                "state": {
                    "type": "selection",
                    "string": "Status",
                    "selection": [("draft", "Draft"), ("posted", "Posted")],
                    "required": True,
                    "store": True,
                },
                "partner_id": {"type": "many2one", "string": "Partner", "relation": "res.partner", "store": True},
                "line_ids": {
                    "type": "one2many",
                    "string": "Lines",
                    "relation": "account.move.line",
                    "inverse_name": "move_id",
                    "store": True,
                },
                "tag_ids": {"type": "many2many", "string": "Tags", "relation": "account.tag", "store": True},
                "amount_total": {"type": "float", "string": "Total", "compute": "_compute_amount_total", "store": True},
            },
            "decorators": {
                "_compute_amount_total": [{"type": "depends", "args": ["line_ids"]}],
                "_check_balanced": [{"type": "constrains", "args": ["line_ids"]}],
            },
            "methods": ["create", "write", "unlink", "search", "read", "action_post", "action_reverse"],
            "inherits": ["mail.thread", "mail.activity.mixin"],
            "delegates": {},
        },
        "mail.thread": {
            "class": "MailThread",
            "module": "mail",
            "file": "/odoo/addons/mail/models/mail_thread.py",
            "description": "Mail thread",
            "fields": {
                "message_ids": {
                    "type": "one2many",
                    "string": "Messages",
                    "relation": "mail.message",
                    "inverse_name": "res_id",
                    "store": True,
                }
            },
            "decorators": {},
            "methods": ["create", "write", "unlink", "search", "read"],
            "inherits": [],
            "delegates": {},
        },
        "mail.activity.mixin": {
            "class": "MailActivityMixin",
            "module": "mail",
            "file": "/odoo/addons/mail/models/mail_activity_mixin.py",
            "description": "Activities",
            "fields": {
                "activity_ids": {
                    "type": "one2many",
                    "string": "Activities",
                    "relation": "mail.activity",
                    "inverse_name": "res_id",
                    "store": True,
                }
            },
            "decorators": {},
            "methods": ["create", "write", "unlink", "search", "read"],
            "inherits": [],
            "delegates": {},
        },
        "helpdesk.ticket": {
            "class": "HelpdeskTicket",
            "module": "helpdesk",
            "file": "/odoo/addons/helpdesk/models/helpdesk_ticket.py",
            "description": "Support ticket",
            "fields": {
                "name": {"type": "char", "string": "Subject", "store": True},
                "stage_id": {"type": "many2one", "string": "Stage", "relation": "helpdesk.stage", "store": True},
                "priority": {"type": "selection", "string": "Priority", "selection": [("0", "Low"), ("1", "High")], "store": True},
            },
            "decorators": {},
            "methods": ["create", "write", "unlink", "search", "read", "action_close"],
            "inherits": [],
            "delegates": {},
        },
    }

    if not include_defaults:
        base_models = {}

    if models:
        base_models.update(deepcopy(models))

    return {"models": base_models}


def create_mock_build_ast_index(models: dict[str, dict[str, Any]] | None = None, include_defaults: bool = True) -> AsyncMock:
    return AsyncMock(return_value=create_fs_ast_index(models, include_defaults=include_defaults))


def create_mock_get_models_index(models: dict[str, dict[str, Any]] | None = None, include_defaults: bool = True) -> AsyncMock:
    return AsyncMock(return_value=create_fs_ast_index(models, include_defaults=include_defaults)["models"])
