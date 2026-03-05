"""Tests for az_scout_fabric_price.service."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from az_scout_fabric_price.service import (
    _build_latest_response,
    _date_trunc,
    get_latest_prices,
    get_price_series,
)


def _make_item(
    pricing_type: str = "Consumption",
    reservation_term: str | None = None,
    unit_price: float = 0.36,
    job_datetime: str = "2025-01-15T02:00:00Z",
    effective_start_date: str = "2025-01-01",
) -> dict[str, Any]:
    return {
        "pricingType": pricing_type,
        "reservationTerm": reservation_term,
        "unitPrice": unit_price,
        "retailPrice": unit_price,
        "jobDatetime": job_datetime,
        "effectiveStartDate": effective_start_date,
    }


class TestBuildLatestResponse:
    def test_single_payg_item(self) -> None:
        items = [_make_item(unit_price=0.36)]
        result = _build_latest_response(items, "eastus", "USD")

        assert result["region"] == "eastus"
        assert result["currency"] == "USD"
        assert result["perCuHour"]["PAYG"] == 0.36
        assert result["skus"]["F2"]["PAYG"] == 0.36 * 2
        assert result["skus"]["F64"]["PAYG"] == 0.36 * 64

    def test_multiple_models(self) -> None:
        items = [
            _make_item(pricing_type="Consumption", unit_price=0.36),
            _make_item(pricing_type="Reservation", reservation_term="1 Year", unit_price=0.24),
            _make_item(pricing_type="Reservation", reservation_term="3 Years", unit_price=0.18),
        ]
        result = _build_latest_response(items, "westeurope", "EUR")

        assert set(result["perCuHour"].keys()) == {"PAYG", "RI_1Y", "RI_3Y"}
        assert result["perCuHour"]["RI_1Y"] == 0.24
        assert result["perCuHour"]["RI_3Y"] == 0.18

    def test_all_skus_present(self) -> None:
        items = [_make_item()]
        result = _build_latest_response(items, "eastus", "USD")

        assert len(result["skus"]) == 11
        assert "F2" in result["skus"]
        assert "F2048" in result["skus"]

    def test_warning_on_duplicate_model(self) -> None:
        items = [
            _make_item(unit_price=0.36, job_datetime="2025-01-15T02:00:00Z"),
            _make_item(unit_price=0.35, job_datetime="2025-01-14T02:00:00Z"),
        ]
        result = _build_latest_response(items, "eastus", "USD")

        assert len(result["warnings"]) == 1
        assert "Multiple items" in result["warnings"][0]
        # Uses the most recent
        assert result["perCuHour"]["PAYG"] == 0.36

    def test_unknown_model_ignored(self) -> None:
        items = [_make_item(pricing_type="Unknown")]
        result = _build_latest_response(items, "eastus", "USD")

        assert result["perCuHour"] == {}

    def test_empty_items(self) -> None:
        result = _build_latest_response([], "eastus", "USD")

        assert result["perCuHour"] == {}
        assert len(result["skus"]) == 11
        # SKUs should exist but have no pricing model keys
        assert "PAYG" not in result["skus"]["F2"]


class TestGetLatestPrices:
    @patch("az_scout_fabric_price.service.fetch_latest_prices")
    def test_caches_result(self, mock_fetch: Any) -> None:
        mock_fetch.return_value = [_make_item()]

        # Clear the cache
        from az_scout_fabric_price.service import _cache

        _cache.clear()

        result1 = get_latest_prices("eastus", "USD")
        result2 = get_latest_prices("eastus", "USD")

        assert result1 == result2
        assert mock_fetch.call_count == 1

    @patch("az_scout_fabric_price.service.fetch_latest_prices")
    def test_different_region_not_cached(self, mock_fetch: Any) -> None:
        mock_fetch.return_value = [_make_item()]

        from az_scout_fabric_price.service import _cache

        _cache.clear()

        get_latest_prices("eastus", "USD")
        get_latest_prices("westeurope", "USD")

        assert mock_fetch.call_count == 2


class TestGetPriceSeries:
    @patch("az_scout_fabric_price.service.fetch_prices")
    def test_basic_series(self, mock_fetch: Any) -> None:
        mock_fetch.return_value = [
            _make_item(unit_price=0.36, job_datetime="2025-01-15T02:00:00Z"),
            _make_item(unit_price=0.37, job_datetime="2025-01-16T02:00:00Z"),
        ]

        result = get_price_series("eastus", "F4", "PAYG", "USD", "", "", "day")

        assert result["meta"]["sku"] == "F4"
        assert result["meta"]["capacityUnits"] == 4
        assert len(result["items"]) == 2
        assert result["items"][0]["bucketTs"] == "2025-01-15"
        assert result["items"][0]["value"] == round(0.36 * 4, 6)

    @patch("az_scout_fabric_price.service.fetch_prices")
    def test_filters_by_model(self, mock_fetch: Any) -> None:
        mock_fetch.return_value = [
            _make_item(pricing_type="Consumption", unit_price=0.36),
            _make_item(
                pricing_type="Reservation",
                reservation_term="1 Year",
                unit_price=0.24,
            ),
        ]

        result = get_price_series("eastus", "F2", "RI_1Y", "USD", "", "", "day")

        assert len(result["items"]) == 1
        assert result["items"][0]["value"] == round(0.24 * 2, 6)

    @patch("az_scout_fabric_price.service.fetch_prices")
    def test_month_bucket(self, mock_fetch: Any) -> None:
        mock_fetch.return_value = [
            _make_item(unit_price=0.36, job_datetime="2025-01-15T02:00:00Z"),
            _make_item(unit_price=0.37, job_datetime="2025-01-20T02:00:00Z"),
        ]

        result = get_price_series("eastus", "F2", "PAYG", "USD", "", "", "month")

        assert len(result["items"]) == 1
        assert result["items"][0]["bucketTs"] == "2025-01"

    @patch("az_scout_fabric_price.service.fetch_prices")
    def test_empty_series(self, mock_fetch: Any) -> None:
        mock_fetch.return_value = []

        result = get_price_series("eastus", "F2", "PAYG", "USD", "", "", "day")

        assert result["items"] == []


class TestDateTrunc:
    def test_day(self) -> None:
        assert _date_trunc("2025-01-15T02:30:00Z", "day") == "2025-01-15"

    def test_week(self) -> None:
        result = _date_trunc("2025-01-15T02:30:00Z", "week")
        assert result.startswith("2025-W")

    def test_month(self) -> None:
        assert _date_trunc("2025-01-15T02:30:00Z", "month") == "2025-01"

    def test_empty_string(self) -> None:
        assert _date_trunc("", "day") == ""

    def test_invalid_date_fallback(self) -> None:
        result = _date_trunc("not-a-date", "day")
        assert result == "not-a-date"[:10]
