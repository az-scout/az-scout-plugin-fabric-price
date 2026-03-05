"""Service layer — transforms raw BDD-API data into Fabric pricing views."""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

from az_scout_fabric_price.bdd_client import fetch_latest_prices, fetch_prices
from az_scout_fabric_price.models import (
    SKU_CU_MAP,
    PricingModel,
    classify_model,
    extract_per_cu_hour,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = int(os.environ.get("FABRIC_PRICE_CACHE_TTL", "300"))
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_latest_prices(region: str, currency: str = "USD") -> dict[str, Any]:
    """Return the latest Fabric capacity pricing for *region*.

    Checks an in-memory TTL cache first.
    """
    cache_key = (region.lower(), currency.upper())
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached is not None:
        ts, data = cached
        if now - ts < _CACHE_TTL:
            return data

    items = fetch_latest_prices(region, currency)
    result = _build_latest_response(items, region, currency)

    _cache[cache_key] = (now, result)
    return result


def _build_latest_response(
    items: list[dict[str, Any]],
    region: str,
    currency: str,
) -> dict[str, Any]:
    """Group raw API items by pricing model and derive per-SKU prices."""
    warnings: list[str] = []
    per_cu_hour: dict[str, float] = {}
    sources: dict[str, dict[str, Any]] = {}

    # Group by model, keep only most recent per model
    by_model: dict[PricingModel, list[dict[str, Any]]] = {}
    for item in items:
        model = classify_model(
            item.get("pricingType", ""),
            item.get("reservationTerm"),
        )
        if model is None:
            continue
        by_model.setdefault(model, []).append(item)

    for model, model_items in by_model.items():
        # Sort by jobDatetime descending; pick the freshest
        model_items.sort(key=lambda x: x.get("jobDatetime", ""), reverse=True)
        best = model_items[0]
        per_cu_hour[model] = extract_per_cu_hour(best)
        sources[model] = {
            "effectiveStartDate": best.get("effectiveStartDate"),
            "jobDatetime": best.get("jobDatetime"),
        }
        if len(model_items) > 1:
            warnings.append(
                f"Multiple items found for model {model} — using most recent "
                f"(jobDatetime={best.get('jobDatetime')})"
            )

    # Derive per-SKU prices
    skus: dict[str, dict[str, Any]] = {}
    for sku_name, cu_count in SKU_CU_MAP.items():
        sku_entry: dict[str, Any] = {"capacityUnits": cu_count}
        for model_key, price in per_cu_hour.items():
            sku_entry[model_key] = round(price * cu_count, 6)
        skus[sku_name] = sku_entry

    return {
        "region": region,
        "currency": currency,
        "retrievedAt": _now_iso(),
        "perCuHour": per_cu_hour,
        "skus": skus,
        "warnings": warnings,
        "sources": sources,
    }


def get_price_series(
    region: str,
    sku: str,
    model: PricingModel = "PAYG",
    currency: str = "USD",
    from_dt: str = "",
    to_dt: str = "",
    bucket: str = "day",
) -> dict[str, Any]:
    """Return a time series of Fabric prices for a specific SKU.

    Each bucket contains the last-observed price within that time window.
    """
    cu_count = SKU_CU_MAP[sku]  # caller must validate sku beforehand

    raw = fetch_prices(region, currency, updated_since=from_dt)

    # Filter by model
    filtered: list[dict[str, Any]] = []
    for item in raw:
        item_model = classify_model(
            item.get("pricingType", ""),
            item.get("reservationTerm"),
        )
        if item_model != model:
            continue
        job_dt = item.get("jobDatetime", "")
        if to_dt and job_dt > to_dt:
            continue
        filtered.append(item)

    # Sort by jobDatetime ascending
    filtered.sort(key=lambda x: x.get("jobDatetime", ""))

    # Bucket
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in filtered:
        job_dt = item.get("jobDatetime", "")
        bucket_key = _date_trunc(job_dt, bucket)
        buckets.setdefault(bucket_key, []).append(item)

    # Per bucket: keep last point (max jobDatetime), compute per-SKU price
    series: list[dict[str, Any]] = []
    for bucket_ts, bucket_items in sorted(buckets.items()):
        last = max(bucket_items, key=lambda x: x.get("jobDatetime", ""))
        per_cu = extract_per_cu_hour(last)
        series.append(
            {
                "bucketTs": bucket_ts,
                "value": round(per_cu * cu_count, 6),
                "perCuHour": round(per_cu, 6),
                "points": len(bucket_items),
            }
        )

    return {
        "items": series,
        "meta": {
            "bucket": bucket,
            "region": region,
            "sku": sku,
            "model": model,
            "currency": currency,
            "capacityUnits": cu_count,
        },
    }


def _date_trunc(iso_dt: str, bucket: str) -> str:
    """Truncate an ISO-8601 datetime string to a bucket boundary.

    Returns an ISO-format date string (``YYYY-MM-DD`` for day,
    ``YYYY-Www`` for week, ``YYYY-MM`` for month).
    """
    if not iso_dt:
        return ""
    try:
        dt = datetime.fromisoformat(iso_dt.replace("Z", "+00:00"))
    except ValueError:
        # Best-effort: use the first 10 chars as date
        return iso_dt[:10]
    if bucket == "week":
        iso_cal = dt.isocalendar()
        return f"{iso_cal.year}-W{iso_cal.week:02d}"
    if bucket == "month":
        return dt.strftime("%Y-%m")
    # default: day
    return dt.strftime("%Y-%m-%d")
