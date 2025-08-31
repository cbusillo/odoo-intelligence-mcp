from datetime import UTC, datetime
from unittest.mock import patch

from odoo_intelligence_mcp.models.base import BaseModel


class TestBaseModel:
    def test_init_with_defaults(self) -> None:
        model = BaseModel()
        assert model.id is None
        assert isinstance(model.created_at, datetime)
        assert isinstance(model.updated_at, datetime)
        assert model.created_at.tzinfo == UTC
        assert model.updated_at.tzinfo == UTC

    def test_init_with_id(self) -> None:
        model = BaseModel(id=42)
        assert model.id == 42

    def test_init_with_timestamps(self) -> None:
        created = datetime(2024, 1, 1, 10, tzinfo=UTC)
        updated = datetime(2024, 1, 2, 10, tzinfo=UTC)
        model = BaseModel(id=1, created_at=created, updated_at=updated)
        assert model.created_at == created
        assert model.updated_at == updated

    def test_to_dict_basic(self) -> None:
        model = BaseModel(id=1)
        result = model.to_dict()
        assert isinstance(result, dict)
        assert result["id"] == 1
        assert "created_at" in result
        assert "updated_at" in result

    def test_to_dict_datetime_serialization(self) -> None:
        created = datetime(2024, 1, 1, 10, tzinfo=UTC)
        updated = datetime(2024, 1, 2, 10, tzinfo=UTC)
        model = BaseModel(id=1, created_at=created, updated_at=updated)
        result = model.to_dict()
        assert result["created_at"] == "2024-01-01T10:00:00+00:00"
        assert result["updated_at"] == "2024-01-02T10:00:00+00:00"

    def test_update_timestamp(self) -> None:
        model = BaseModel()
        original_updated = model.updated_at
        with patch("odoo_intelligence_mcp.models.base.datetime") as mock_datetime:
            new_time = datetime(2024, 12, 25, 12, tzinfo=UTC)
            mock_datetime.now.return_value = new_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            model.update_timestamp()
            assert model.updated_at == new_time
            assert model.updated_at != original_updated

    def test_created_updated_independence(self) -> None:
        model = BaseModel()
        original_created = model.created_at
        model.update_timestamp()
        assert model.created_at == original_created
        assert model.updated_at != model.created_at

    def test_multiple_instances_different_timestamps(self) -> None:
        model1 = BaseModel()
        model2 = BaseModel()
        assert model1.created_at != model2.created_at or model1.updated_at != model2.updated_at

    def test_to_dict_preserves_all_fields(self) -> None:
        model = BaseModel(id=99)
        result = model.to_dict()
        assert set(result.keys()) == {"id", "created_at", "updated_at"}
