from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from odoo_intelligence_mcp.type_defs.odoo_types import Field, Model
from odoo_intelligence_mcp.utils.model_utils import (
    ModelIterator,
    extract_field_info,
    extract_model_info,
)


class TestModelIterator:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        env = MagicMock()
        env.get_model_names = AsyncMock(return_value=["sale.order", "res.partner", "ir.model", "product.product"])
        env.__contains__ = Mock(return_value=True)
        env.__getitem__ = Mock(side_effect=lambda x: MagicMock(_name=x))
        return env

    @pytest.fixture
    def iterator(self, mock_env: MagicMock) -> ModelIterator:
        return ModelIterator(mock_env)

    @pytest.mark.asyncio
    async def test_iter_models_excludes_system_models(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        models = []
        async for model_name, model in iterator.iter_models():
            models.append(model_name)

        assert "sale.order" in models
        assert "product.product" in models
        assert "ir.model" not in models  # System model excluded
        assert "res.partner" not in models  # System model excluded

    @pytest.mark.asyncio
    async def test_iter_models_include_system_models(self, mock_env: MagicMock) -> None:
        iterator = ModelIterator(mock_env, exclude_system_models=False)
        models = []
        async for model_name, model in iterator.iter_models():
            models.append(model_name)

        assert "sale.order" in models
        assert "product.product" in models
        assert "ir.model" in models
        assert "res.partner" in models

    @pytest.mark.asyncio
    async def test_iter_models_with_filter(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        def filter_func(name: str) -> bool:
            return "product" in name

        models = []
        async for model_name, model in iterator.iter_models(filter_func):
            models.append(model_name)

        assert "product.product" in models
        assert "sale.order" not in models

    @pytest.mark.asyncio
    async def test_iter_models_returns_model_objects(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        async for model_name, model in iterator.iter_models():
            assert model._name == model_name
            break

    @staticmethod
    def _setup_mock_model_fields(mock_env: MagicMock) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Helper to setup mock model with standard fields to avoid duplication."""
        mock_field1 = MagicMock(type="char", name="name")
        mock_field2 = MagicMock(type="many2one", name="partner_id")
        mock_field3 = MagicMock(type="float", name="amount")

        mock_model = MagicMock()
        mock_model._fields = {
            "name": mock_field1,
            "partner_id": mock_field2,
            "amount": mock_field3,
        }
        mock_env.__getitem__.side_effect = lambda x: mock_model if x == "sale.order" else MagicMock(_name=x)
        return mock_field1, mock_field2, mock_field3

    def test_iter_model_fields(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        mock_field1, mock_field2, mock_field3 = TestModelIterator._setup_mock_model_fields(mock_env)

        fields = list(iterator.iter_model_fields("sale.order"))
        assert len(fields) == 3
        assert ("name", mock_field1) in fields
        assert ("partner_id", mock_field2) in fields
        assert ("amount", mock_field3) in fields

    def test_iter_model_fields_with_filter(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        mock_field1, mock_field2, mock_field3 = TestModelIterator._setup_mock_model_fields(mock_env)

        # noinspection PyUnusedLocal
        def field_filter(name: str, field: Any) -> bool:
            return field.type == "many2one"

        fields = list(iterator.iter_model_fields("sale.order", field_filter))
        assert len(fields) == 1
        assert ("partner_id", mock_field2) in fields

    def test_iter_model_fields_nonexistent_model(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        mock_env.__contains__.return_value = False
        fields = list(iterator.iter_model_fields("nonexistent.model"))
        assert fields == []

    def test_is_system_model(self, iterator: ModelIterator) -> None:
        assert iterator._is_system_model("ir.model")
        assert iterator._is_system_model("res.partner")
        assert iterator._is_system_model("base.model")
        assert iterator._is_system_model("_transient_model")
        assert not iterator._is_system_model("sale.order")
        assert not iterator._is_system_model("product.product")

    @pytest.mark.asyncio
    async def test_iter_models_empty_list(self, mock_env: MagicMock) -> None:
        mock_env.get_model_names = AsyncMock(return_value=[])
        iterator = ModelIterator(mock_env)
        models = []
        async for model_name, model in iterator.iter_models():
            models.append(model_name)
        assert models == []

    def test_iter_model_fields_empty_fields(self, iterator: ModelIterator, mock_env: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model._fields = {}
        mock_env.__getitem__.return_value = mock_model

        fields = list(iterator.iter_model_fields("sale.order"))
        assert fields == []


class TestExtractFieldInfo:
    def test_extract_field_info_basic(self) -> None:
        field = MagicMock(
            type="char",
            string="Name",
            required=True,
            readonly=False,
            store=True,
            compute=None,
            related=None,
            help="Field help text",
        )

        info = extract_field_info(cast("Field", field))
        assert info["type"] == "char"
        assert info["string"] == "Name"
        assert info["required"] is True
        assert info["readonly"] is False
        assert info["store"] is True
        assert info["compute"] is None
        assert info["related"] is None
        assert info["help"] == "Field help text"

    def test_extract_field_info_computed(self) -> None:
        field = MagicMock(
            type="float",
            string="Total",
            required=False,
            readonly=True,
            store=False,
            compute="_compute_total",
            related=None,
            help="",
        )

        info = extract_field_info(cast("Field", field))
        assert info["type"] == "float"
        assert info["compute"] == "_compute_total"
        assert info["store"] is False
        assert info["readonly"] is True

    def test_extract_field_info_related(self) -> None:
        field = MagicMock(
            type="char",
            string="Partner Name",
            required=False,
            readonly=True,
            store=False,
            compute=None,
            related="partner_id.name",
            help="",
        )

        info = extract_field_info(cast("Field", field))
        assert info["related"] == "partner_id.name"
        assert info["store"] is False

    def test_extract_field_info_missing_attributes(self) -> None:
        field = MagicMock(type="integer")
        # Remove optional attributes
        del field.string
        del field.required
        del field.readonly
        del field.store
        del field.compute
        del field.related
        del field.help

        info = extract_field_info(cast("Field", field))
        assert info["type"] == "integer"
        assert info["string"] == ""
        assert info["required"] is False
        assert info["readonly"] is False
        assert info["store"] is True
        assert info["compute"] is None
        assert info["related"] is None
        assert info["help"] == ""


class TestExtractModelInfo:
    def test_extract_model_info_basic(self) -> None:
        model = MagicMock(
            _name="sale.order",
            _description="Sales Order",
            _table="sale_order",
            _rec_name="name",
            _order="date_order desc",
            _auto=True,
            _abstract=False,
            _transient=False,
        )

        info = extract_model_info(cast("Model", model))
        assert info["name"] == "sale.order"
        assert info["description"] == "Sales Order"
        assert info["table"] == "sale_order"
        assert info["rec_name"] == "name"
        assert info["order"] == "date_order desc"
        assert info["auto"] is True
        assert info["abstract"] is False
        assert info["transient"] is False

    def test_extract_model_info_abstract(self) -> None:
        model = MagicMock(
            _name="mail.thread",
            _description="Mail Thread",
            _abstract=True,
            _transient=False,
        )
        del model._table  # Abstract models might not have a table
        del model._rec_name
        del model._order
        del model._auto

        info = extract_model_info(cast("Model", model))
        assert info["name"] == "mail.thread"
        assert info["abstract"] is True
        assert info["transient"] is False
        assert info["table"] == ""
        assert info["rec_name"] == "name"  # Default value
        assert info["order"] == "id"  # Default value
        assert info["auto"] is True  # Default value

    def test_extract_model_info_transient(self) -> None:
        model = MagicMock(
            _name="wizard.model",
            _description="Wizard Model",
            _transient=True,
            _abstract=False,
        )
        del model._table
        del model._rec_name
        del model._order
        del model._auto

        info = extract_model_info(cast("Model", model))
        assert info["name"] == "wizard.model"
        assert info["transient"] is True
        assert info["abstract"] is False

    def test_extract_model_info_minimal(self) -> None:
        model = MagicMock(_name="minimal.model")
        # Remove all optional attributes
        del model._description
        del model._table
        del model._rec_name
        del model._order
        del model._auto
        del model._abstract
        del model._transient

        info = extract_model_info(cast("Model", model))
        assert info["name"] == "minimal.model"
        assert info["description"] == ""
        assert info["table"] == ""
        assert info["rec_name"] == "name"
        assert info["order"] == "id"
        assert info["auto"] is True
        assert info["abstract"] is False
        assert info["transient"] is False

    def test_extract_model_info_custom_values(self) -> None:
        model = MagicMock(
            _name="custom.model",
            _description="Custom Model",
            _table="custom_table_name",
            _rec_name="display_name",
            _order="sequence, id",
            _auto=False,
            _abstract=False,
            _transient=False,
        )

        info = extract_model_info(cast("Model", model))
        assert info["table"] == "custom_table_name"
        assert info["rec_name"] == "display_name"
        assert info["order"] == "sequence, id"
        assert info["auto"] is False
