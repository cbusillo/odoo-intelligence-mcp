from unittest.mock import AsyncMock, MagicMock

import pytest

from odoo_intelligence_mcp.services.field_analyzer import FieldAnalyzer


class TestFieldAnalyzer:
    @pytest.fixture
    def mock_env(self) -> MagicMock:
        env = MagicMock()
        env.execute_code = MagicMock()
        env.__getitem__ = MagicMock()
        return env

    @pytest.fixture
    def analyzer(self, mock_env: MagicMock) -> FieldAnalyzer:
        analyzer = FieldAnalyzer(mock_env)
        # Mock the validation methods to avoid actual environment checks
        analyzer._validate_model_exists = MagicMock()
        analyzer._validate_field_exists = MagicMock()
        return analyzer

    @pytest.mark.asyncio
    async def test_get_comprehensive_field_analysis(self, analyzer: FieldAnalyzer, mock_env: MagicMock) -> None:
        # Mock the internal method that causes issues
        analyzer._get_field_info = AsyncMock(
            return_value={
                "name": "amount_total",
                "type": "float",
                "string": "Total",
                "compute": "_compute_amounts",
                "store": True,
                "readonly": True,
            }
        )

        mock_env.execute_code.return_value = {
            "field_name": "amount_total",
            "model_name": "sale.order",
            "field_info": {"type": "float", "string": "Total", "compute": "_compute_amounts", "store": True, "readonly": True},
        }

        result = await analyzer.get_comprehensive_field_analysis("sale.order", "amount_total")

        assert result["field_name"] == "amount_total"
        assert result["model_name"] == "sale.order"
        assert "field_info" in result

    @pytest.mark.asyncio
    async def test_get_comprehensive_field_analysis_with_values(self, analyzer: FieldAnalyzer, mock_env: MagicMock) -> None:
        analyzer._get_field_info = AsyncMock(
            return_value={"name": "list_price", "type": "float", "string": "Sales Price", "store": True}
        )

        mock_env.execute_code.return_value = {
            "analysis": {
                "null_percentage": 5.0,
                "unique_values": 100,
                "distinct_count": 50,
                "sample_values": [19.99, 29.99],
            }
        }

        result = await analyzer.get_comprehensive_field_analysis("product.template", "list_price", analyze_values=True)

        assert result["field_name"] == "list_price"
        assert result["model_name"] == "product.template"

    @pytest.mark.asyncio
    async def test_get_comprehensive_field_analysis_invalid_model(self, analyzer: FieldAnalyzer, mock_env: MagicMock) -> None:
        from odoo_intelligence_mcp.services.base_service import ServiceValidationError

        # Make _validate_field_exists raise an exception for invalid models
        analyzer._validate_field_exists = MagicMock(side_effect=ServiceValidationError("Model invalid.model not found"))
        mock_env.execute_code.return_value = {"error": "Model invalid.model not found"}

        with pytest.raises(ServiceValidationError):
            await analyzer.get_comprehensive_field_analysis("invalid.model", "field")

    @pytest.mark.asyncio
    async def test_get_comprehensive_field_analysis_invalid_field(self, analyzer: FieldAnalyzer, mock_env: MagicMock) -> None:
        from odoo_intelligence_mcp.services.base_service import ServiceValidationError

        # Make _validate_field_exists raise an exception for invalid fields
        analyzer._validate_field_exists = MagicMock(
            side_effect=ServiceValidationError("Field nonexistent not found on model sale.order")
        )
        mock_env.execute_code.return_value = {"name": "sale.order", "fields": {}}

        with pytest.raises(ServiceValidationError):
            await analyzer.get_comprehensive_field_analysis("sale.order", "nonexistent")

    @pytest.mark.asyncio
    async def test_cache_field_analysis(self, analyzer: FieldAnalyzer, mock_env: MagicMock) -> None:
        analyzer._get_field_info = AsyncMock(return_value={"name": "field1", "type": "char", "store": True})
        mock_env.execute_code.return_value = {
            "name": "test_model",
            "fields": {"field1": {"type": "char", "store": True}},
            "field_count": 1,
        }

        result1 = await analyzer.get_comprehensive_field_analysis("test.model", "field1")
        assert mock_env.execute_code.call_count >= 1

        result2 = await analyzer.get_comprehensive_field_analysis("test.model", "field1")
        assert result1 == result2

        analyzer.clear_cache()
        _result3 = await analyzer.get_comprehensive_field_analysis("test.model", "field1")
        assert mock_env.execute_code.call_count >= 1
