"""MCP tools for the Fabric pricing plugin.

All tools delegate to the service layer and catch configuration errors.
"""

from __future__ import annotations

from typing import Any

from az_scout_fabric_price.bdd_client import BddClientNotConfiguredError
from az_scout_fabric_price.models import SKU_CU_MAP, PricingModel

_NOT_CONFIGURED = {
    "error": "BDD-SKU API URL is not configured. Set it in the BDD SKU plugin settings."
}


def _safe_call(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Call *fn* and catch configuration + request errors."""
    try:
        return fn(*args, **kwargs)  # type: ignore[no-any-return]
    except BddClientNotConfiguredError:
        return _NOT_CONFIGURED
    except Exception as exc:
        return {"error": f"API call failed: {exc}"}


def fabric_capacities() -> dict[str, Any]:
    """List all Microsoft Fabric capacity SKUs and their CU (Capacity Unit) counts.

    Returns the mapping from SKU name (F2, F4, … F2048) to the number of
    Capacity Units included. No external API call is needed.
    """
    return {"capacities": [{"sku": sku, "capacityUnits": cu} for sku, cu in SKU_CU_MAP.items()]}


def fabric_prices_latest(
    region: str,
    currency: str = "USD",
) -> dict[str, Any]:
    """Get the latest Microsoft Fabric capacity pricing for a region.

    Returns per-CU-hour prices for each pricing model (PAYG, RI_1Y, RI_3Y)
    and derived per-SKU hourly costs for all capacity tiers (F2–F2048).
    """
    from az_scout_fabric_price.service import get_latest_prices

    return _safe_call(get_latest_prices, region, currency)


def fabric_price_series(
    region: str,
    sku: str,
    model: PricingModel = "PAYG",
    currency: str = "USD",
    from_dt: str = "",
    to_dt: str = "",
    bucket: str = "day",
) -> dict[str, Any]:
    """Get a price time series for a specific Microsoft Fabric capacity SKU.

    Returns bucketed price history (day/week/month) for the given SKU and
    pricing model. Each bucket contains the last observed price.
    """
    if sku not in SKU_CU_MAP:
        return {"error": f"Unknown SKU '{sku}'. Valid: {', '.join(SKU_CU_MAP)}"}
    if bucket not in ("day", "week", "month"):
        return {"error": f"Invalid bucket '{bucket}'. Valid: day, week, month"}

    from az_scout_fabric_price.service import get_price_series

    return _safe_call(
        get_price_series,
        region=region,
        sku=sku,
        model=model,
        currency=currency,
        from_dt=from_dt,
        to_dt=to_dt,
        bucket=bucket,
    )
