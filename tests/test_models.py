"""Tests for az_scout_fabric_price.models."""

from az_scout_fabric_price.models import (
    SKU_CU_MAP,
    classify_model,
    extract_per_cu_hour,
)


class TestSkuCuMap:
    def test_contains_all_tiers(self) -> None:
        expected = {"F2", "F4", "F8", "F16", "F32", "F64", "F128", "F256", "F512", "F1024", "F2048"}
        assert set(SKU_CU_MAP.keys()) == expected

    def test_cu_values_match_names(self) -> None:
        for sku, cu in SKU_CU_MAP.items():
            assert cu == int(sku[1:])


class TestClassifyModel:
    def test_consumption_returns_payg(self) -> None:
        assert classify_model("Consumption", None) == "PAYG"

    def test_consumption_case_insensitive(self) -> None:
        assert classify_model("CONSUMPTION", None) == "PAYG"

    def test_reservation_1_year(self) -> None:
        assert classify_model("Reservation", "1 Year") == "RI_1Y"

    def test_reservation_3_years(self) -> None:
        assert classify_model("Reservation", "3 Years") == "RI_3Y"

    def test_reservation_unknown_term(self) -> None:
        assert classify_model("Reservation", "5 Years") is None

    def test_reservation_no_term(self) -> None:
        assert classify_model("Reservation", None) is None

    def test_unknown_pricing_type(self) -> None:
        assert classify_model("SomethingElse", None) is None


class TestExtractPerCuHour:
    def test_prefers_unit_price(self) -> None:
        item = {"unitPrice": 0.36, "retailPrice": 0.50}
        assert extract_per_cu_hour(item) == 0.36

    def test_falls_back_to_retail_price(self) -> None:
        item = {"retailPrice": 0.50}
        assert extract_per_cu_hour(item) == 0.50

    def test_zero_when_no_prices(self) -> None:
        assert extract_per_cu_hour({}) == 0.0

    def test_unit_price_zero_is_used(self) -> None:
        item = {"unitPrice": 0, "retailPrice": 0.50}
        assert extract_per_cu_hour(item) == 0.0
