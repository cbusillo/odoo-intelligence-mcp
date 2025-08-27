from odoo_intelligence_mcp.models.odoo_models import (
    OdooDecorator,
    OdooField,
    OdooInheritance,
    OdooMethod,
    OdooModel,
    OdooRelationship,
)


class TestOdooField:
    def test_init_defaults(self) -> None:
        field = OdooField()
        assert field.name == ""
        assert field.type == ""
        assert field.required is False
        assert field.store is True
        assert field.compute is None
        assert field.depends == []

    def test_init_with_values(self) -> None:
        field = OdooField(
            name="partner_id",
            type="many2one",
            string="Partner",
            required=True,
            comodel_name="res.partner",
            ondelete="cascade",
        )
        assert field.name == "partner_id"
        assert field.type == "many2one"
        assert field.string == "Partner"
        assert field.required is True
        assert field.comodel_name == "res.partner"
        assert field.ondelete == "cascade"

    def test_selection_field(self) -> None:
        field = OdooField(
            name="state",
            type="selection",
            selection=[("draft", "Draft"), ("done", "Done")],
        )
        assert field.selection == [("draft", "Draft"), ("done", "Done")]

    def test_computed_field(self) -> None:
        field = OdooField(
            name="total",
            type="float",
            compute="_compute_total",
            store=True,
            depends=["line_ids", "line_ids.subtotal"],
        )
        assert field.compute == "_compute_total"
        assert field.store is True
        assert field.depends == ["line_ids", "line_ids.subtotal"]

    def test_related_field(self) -> None:
        field = OdooField(name="partner_name", type="char", related="partner_id.name", store=False)
        assert field.related == "partner_id.name"
        assert field.store is False


class TestOdooRelationship:
    def test_many2one_relationship(self) -> None:
        rel = OdooRelationship(
            field_name="partner_id",
            source_model="sale.order",
            target_model="res.partner",
            type="many2one",
            ondelete="restrict",
        )
        assert rel.field_name == "partner_id"
        assert rel.source_model == "sale.order"
        assert rel.target_model == "res.partner"
        assert rel.type == "many2one"
        assert rel.ondelete == "restrict"

    def test_one2many_relationship(self) -> None:
        rel = OdooRelationship(
            field_name="order_line",
            source_model="sale.order",
            target_model="sale.order.line",
            type="one2many",
            inverse_field="order_id",
        )
        assert rel.type == "one2many"
        assert rel.inverse_field == "order_id"

    def test_many2many_relationship(self) -> None:
        rel = OdooRelationship(
            field_name="tag_ids",
            source_model="res.partner",
            target_model="res.partner.category",
            type="many2many",
            intermediate_model="res_partner_res_partner_category_rel",
            column1="partner_id",
            column2="category_id",
        )
        assert rel.type == "many2many"
        assert rel.intermediate_model == "res_partner_res_partner_category_rel"
        assert rel.column1 == "partner_id"
        assert rel.column2 == "category_id"


class TestOdooMethod:
    def test_basic_method(self) -> None:
        method = OdooMethod(
            name="_compute_total",
            model="sale.order",
            parameters=["self"],
            is_private=True,
        )
        assert method.name == "_compute_total"
        assert method.model == "sale.order"
        assert method.parameters == ["self"]
        assert method.is_private is True
        assert method.is_api_method is False

    def test_decorated_method(self) -> None:
        method = OdooMethod(
            name="_check_date",
            model="sale.order",
            decorators=["api.constrains"],
            constrains=["date_order", "date_delivery"],
            is_api_method=True,
        )
        assert method.decorators == ["api.constrains"]
        assert method.constrains == ["date_order", "date_delivery"]
        assert method.is_api_method is True

    def test_onchange_method(self) -> None:
        method = OdooMethod(
            name="_onchange_partner",
            model="sale.order",
            decorators=["api.onchange"],
            onchange=["partner_id"],
        )
        assert "api.onchange" in method.decorators
        assert method.onchange == ["partner_id"]

    def test_method_with_location(self) -> None:
        method = OdooMethod(
            name="action_confirm",
            model="sale.order",
            line_number=150,
            file_path="sale/models/sale.py",
        )
        assert method.line_number == 150
        assert method.file_path == "sale/models/sale.py"


class TestOdooDecorator:
    def test_depends_decorator(self) -> None:
        decorator = OdooDecorator(
            name="depends",
            type="depends",
            model="sale.order",
            method="_compute_amount",
            arguments=["order_line", "order_line.price_total"],
        )
        assert decorator.type == "depends"
        assert decorator.arguments == ["order_line", "order_line.price_total"]

    def test_constrains_decorator(self) -> None:
        decorator = OdooDecorator(
            name="constrains",
            type="constrains",
            model="sale.order",
            method="_check_date",
            arguments=["date_order"],
            line_number=200,
        )
        assert decorator.type == "constrains"
        assert decorator.line_number == 200


class TestOdooInheritance:
    def test_simple_inheritance(self) -> None:
        inheritance = OdooInheritance(
            model="sale.order",
            inherit=["mail.thread"],
            mro=["sale.order", "mail.thread", "BaseModel"],
        )
        assert inheritance.inherit == ["mail.thread"]
        assert inheritance.mro == ["sale.order", "mail.thread", "BaseModel"]
        assert inheritance.abstract is False

    def test_delegation_inheritance(self) -> None:
        inheritance = OdooInheritance(
            model="res.users",
            inherits={"res.partner": "partner_id"},
            inherited_fields={"name": "res.partner", "email": "res.partner"},
        )
        assert inheritance.inherits == {"res.partner": "partner_id"}
        assert inheritance.inherited_fields == {"name": "res.partner", "email": "res.partner"}

    def test_abstract_model(self) -> None:
        inheritance = OdooInheritance(model="mail.thread", abstract=True, transient=False)
        assert inheritance.abstract is True
        assert inheritance.transient is False


class TestOdooModel:
    def test_basic_model(self) -> None:
        model = OdooModel(
            name="sale.order",
            table="sale_order",
            description="Sales Order",
            module="sale",
        )
        assert model.name == "sale.order"
        assert model.table == "sale_order"
        assert model.description == "Sales Order"
        assert model.module == "sale"

    def test_model_with_fields(self) -> None:
        field1 = OdooField(name="name", type="char", required=True)
        field2 = OdooField(name="partner_id", type="many2one")
        model = OdooModel(
            name="sale.order",
            fields={"name": field1, "partner_id": field2},
        )
        assert len(model.fields) == 2
        assert model.get_dataclass_field("name") == field1
        assert model.get_dataclass_field("partner_id") == field2
        assert model.get_dataclass_field("nonexistent") is None

    def test_get_relational_fields(self) -> None:
        model = OdooModel(
            fields={
                "name": OdooField(name="name", type="char"),
                "partner_id": OdooField(name="partner_id", type="many2one"),
                "line_ids": OdooField(name="line_ids", type="one2many"),
                "tag_ids": OdooField(name="tag_ids", type="many2many"),
                "amount": OdooField(name="amount", type="float"),
            }
        )
        relational = model.get_relational_fields()
        assert len(relational) == 3
        assert "partner_id" in relational
        assert "line_ids" in relational
        assert "tag_ids" in relational
        assert "name" not in relational

    def test_get_computed_fields(self) -> None:
        model = OdooModel(
            fields={
                "name": OdooField(name="name", type="char"),
                "total": OdooField(name="total", type="float", compute="_compute_total"),
                "subtotal": OdooField(name="subtotal", type="float", compute="_compute_subtotal"),
            }
        )
        computed = model.get_computed_fields()
        assert len(computed) == 2
        assert "total" in computed
        assert "subtotal" in computed

    def test_get_related_fields(self) -> None:
        model = OdooModel(
            fields={
                "partner_name": OdooField(name="partner_name", type="char", related="partner_id.name"),
                "partner_email": OdooField(name="partner_email", type="char", related="partner_id.email"),
                "name": OdooField(name="name", type="char"),
            }
        )
        related = model.get_related_fields()
        assert len(related) == 2
        assert "partner_name" in related
        assert "partner_email" in related

    def test_get_stored_fields(self) -> None:
        model = OdooModel(
            fields={
                "name": OdooField(name="name", type="char", store=True),
                "computed": OdooField(name="computed", type="char", compute="_compute", store=False),
                "stored_compute": OdooField(name="stored_compute", type="char", compute="_compute", store=True),
            }
        )
        stored = model.get_stored_fields()
        assert len(stored) == 2
        assert "name" in stored
        assert "stored_compute" in stored

    def test_get_required_fields(self) -> None:
        model = OdooModel(
            fields={
                "name": OdooField(name="name", type="char", required=True),
                "partner_id": OdooField(name="partner_id", type="many2one", required=True),
                "optional": OdooField(name="optional", type="char", required=False),
            }
        )
        required = model.get_required_fields()
        assert len(required) == 2
        assert "name" in required
        assert "partner_id" in required

    def test_get_methods_by_decorator(self) -> None:
        method1 = OdooMethod(name="compute", decorators=["depends"])
        method2 = OdooMethod(name="check", decorators=["constrains"])
        method3 = OdooMethod(name="compute2", decorators=["depends"])
        model = OdooModel(methods=[method1, method2, method3])
        depends_methods = model.get_methods_by_decorator("depends")
        assert len(depends_methods) == 2
        assert method1 in depends_methods
        assert method3 in depends_methods

    def test_get_api_methods(self) -> None:
        method1 = OdooMethod(name="public_method", is_api_method=True)
        method2 = OdooMethod(name="_private_method", is_api_method=False)
        method3 = OdooMethod(name="api_method", is_api_method=True)
        model = OdooModel(methods=[method1, method2, method3])
        api_methods = model.get_api_methods()
        assert len(api_methods) == 2
        assert method1 in api_methods
        assert method3 in api_methods

    def test_get_constraint_methods(self) -> None:
        method1 = OdooMethod(name="check1", decorators=["constrains"])
        method2 = OdooMethod(name="compute", decorators=["depends"])
        method3 = OdooMethod(name="check2", decorators=["constrains"])
        model = OdooModel(methods=[method1, method2, method3])
        constraints = model.get_constraint_methods()
        assert len(constraints) == 2
        assert method1 in constraints
        assert method3 in constraints

    def test_get_compute_methods(self) -> None:
        method1 = OdooMethod(name="compute1", decorators=["depends"])
        method2 = OdooMethod(name="check", decorators=["constrains"])
        method3 = OdooMethod(name="compute2", decorators=["depends"])
        model = OdooModel(methods=[method1, method2, method3])
        computes = model.get_compute_methods()
        assert len(computes) == 2
        assert method1 in computes
        assert method3 in computes

    def test_get_onchange_methods(self) -> None:
        method1 = OdooMethod(name="onchange1", decorators=["onchange"])
        method2 = OdooMethod(name="compute", decorators=["depends"])
        method3 = OdooMethod(name="onchange2", decorators=["onchange"])
        model = OdooModel(methods=[method1, method2, method3])
        onchanges = model.get_onchange_methods()
        assert len(onchanges) == 2
        assert method1 in onchanges
        assert method3 in onchanges

    def test_model_inheritance_properties(self) -> None:
        model = OdooModel(
            name="custom.model",
            inherit=["mail.thread", "mail.activity.mixin"],
            abstract=True,
            transient=False,
        )
        assert model.inherit == ["mail.thread", "mail.activity.mixin"]
        assert model.abstract is True
        assert model.transient is False

    def test_model_sql_constraints(self) -> None:
        model = OdooModel(
            name="sale.order",
            sql_constraints=[
                ("name_uniq", "unique(name)", "Order name must be unique"),
                ("positive_amount", "check(amount > 0)", "Amount must be positive"),
            ],
        )
        assert len(model.sql_constraints) == 2
        assert model.sql_constraints[0] == ("name_uniq", "unique(name)", "Order name must be unique")
