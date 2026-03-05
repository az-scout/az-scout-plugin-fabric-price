"""Tests for az_scout_fabric_price.routes (FastAPI endpoints)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from az_scout_fabric_price.bdd_client import BddClientNotConfiguredError
from az_scout_fabric_price.routes import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestCapacities:
    def test_returns_all_skus(self) -> None:
        resp = client.get("/v1/fabric/capacities")
        assert resp.status_code == 200
        data = resp.json()
        assert "capacities" in data
        assert len(data["capacities"]) == 11
        skus = {c["sku"] for c in data["capacities"]}
        assert "F2" in skus
        assert "F2048" in skus

    def test_cu_values_present(self) -> None:
        resp = client.get("/v1/fabric/capacities")
        data = resp.json()
        f64 = next(c for c in data["capacities"] if c["sku"] == "F64")
        assert f64["capacityUnits"] == 64


class TestPricesLatest:
    @patch("az_scout_fabric_price.service.get_latest_prices")
    def test_success(self, mock_svc: Any) -> None:
        mock_svc.return_value = {
            "region": "eastus",
            "currency": "USD",
            "perCuHour": {"PAYG": 0.36},
            "skus": {},
            "warnings": [],
        }

        resp = client.get("/v1/fabric/prices/latest?region=eastus")
        assert resp.status_code == 200
        data = resp.json()
        assert data["region"] == "eastus"
        mock_svc.assert_called_once_with("eastus", "USD")

    @patch("az_scout_fabric_price.service.get_latest_prices")
    def test_custom_currency(self, mock_svc: Any) -> None:
        mock_svc.return_value = {"region": "eastus", "currency": "EUR"}

        resp = client.get("/v1/fabric/prices/latest?region=eastus&currency=EUR")
        assert resp.status_code == 200
        mock_svc.assert_called_once_with("eastus", "EUR")

    def test_missing_region(self) -> None:
        resp = client.get("/v1/fabric/prices/latest")
        assert resp.status_code == 422

    @patch("az_scout_fabric_price.service.get_latest_prices")
    def test_not_configured(self, mock_svc: Any) -> None:
        mock_svc.side_effect = BddClientNotConfiguredError("not configured")

        resp = client.get("/v1/fabric/prices/latest?region=eastus")
        assert resp.status_code == 503
        assert "not configured" in resp.json()["error"]

    @patch("az_scout_fabric_price.service.get_latest_prices")
    def test_upstream_error(self, mock_svc: Any) -> None:
        mock_svc.side_effect = RuntimeError("connection refused")

        resp = client.get("/v1/fabric/prices/latest?region=eastus")
        assert resp.status_code == 502
        assert "Upstream API error" in resp.json()["error"]


class TestPriceSeries:
    @patch("az_scout_fabric_price.service.get_price_series")
    def test_success(self, mock_svc: Any) -> None:
        mock_svc.return_value = {"items": [], "meta": {}}

        resp = client.get("/v1/fabric/prices/series?region=eastus&sku=F64")
        assert resp.status_code == 200
        mock_svc.assert_called_once()

    def test_missing_region(self) -> None:
        resp = client.get("/v1/fabric/prices/series?sku=F64")
        assert resp.status_code == 422

    def test_missing_sku(self) -> None:
        resp = client.get("/v1/fabric/prices/series?region=eastus")
        assert resp.status_code == 422

    def test_invalid_sku(self) -> None:
        resp = client.get("/v1/fabric/prices/series?region=eastus&sku=F99")
        assert resp.status_code == 400
        assert "Unknown SKU" in resp.json()["error"]

    def test_invalid_bucket(self) -> None:
        resp = client.get("/v1/fabric/prices/series?region=eastus&sku=F64&bucket=year")
        assert resp.status_code == 400
        assert "Invalid bucket" in resp.json()["error"]

    @patch("az_scout_fabric_price.service.get_price_series")
    def test_not_configured(self, mock_svc: Any) -> None:
        mock_svc.side_effect = BddClientNotConfiguredError("not configured")

        resp = client.get("/v1/fabric/prices/series?region=eastus&sku=F64")
        assert resp.status_code == 503

    @patch("az_scout_fabric_price.service.get_price_series")
    def test_upstream_error(self, mock_svc: Any) -> None:
        mock_svc.side_effect = RuntimeError("timeout")

        resp = client.get("/v1/fabric/prices/series?region=eastus&sku=F64")
        assert resp.status_code == 502
