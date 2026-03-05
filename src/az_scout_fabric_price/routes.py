"""FastAPI routes for the Fabric pricing plugin.

Mounted at ``/plugins/fabric-price/`` by the plugin host.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from az_scout_fabric_price.bdd_client import BddClientNotConfiguredError
from az_scout_fabric_price.models import SKU_CU_MAP, PricingModel

router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_BUCKETS = ("day", "week", "month")


@router.get("/v1/fabric/capacities")
async def list_capacities() -> dict[str, Any]:
    """Return the static list of Fabric capacity SKUs and their CU counts."""
    capacities = [{"sku": sku, "capacityUnits": cu} for sku, cu in SKU_CU_MAP.items()]
    return {"capacities": capacities}


@router.get("/v1/fabric/prices/latest")
async def prices_latest(
    region: str = Query(..., description="Azure region name"),
    currency: str = Query("USD", description="ISO 4217 currency code"),
) -> Any:
    """Return the latest Fabric capacity pricing for a region."""
    from az_scout_fabric_price.service import get_latest_prices

    try:
        return get_latest_prices(region, currency)
    except BddClientNotConfiguredError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )
    except Exception as exc:
        logger.exception("Failed to fetch latest prices")
        return JSONResponse(
            status_code=502,
            content={"error": f"Upstream API error: {exc}"},
        )


@router.get("/v1/fabric/prices/series")
async def price_series(
    region: str = Query(..., description="Azure region name"),
    sku: str = Query(..., description="Fabric SKU (e.g. F2, F64, F1024)"),
    model: PricingModel = Query("PAYG", description="Pricing model"),  # noqa: B008
    currency: str = Query("USD", description="ISO 4217 currency code"),
    from_dt: str = Query("", alias="from", description="Start date (ISO 8601)"),
    to_dt: str = Query("", alias="to", description="End date (ISO 8601)"),
    bucket: str = Query("day", description="Time bucket: day, week, month"),
) -> Any:
    """Return a price time series for a specific Fabric SKU."""
    if sku not in SKU_CU_MAP:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Unknown SKU '{sku}'. Valid: {', '.join(SKU_CU_MAP)}",
            },
        )
    if bucket not in _VALID_BUCKETS:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Invalid bucket '{bucket}'. Valid: {', '.join(_VALID_BUCKETS)}",
            },
        )

    from az_scout_fabric_price.service import get_price_series

    try:
        return get_price_series(
            region=region,
            sku=sku,
            model=model,
            currency=currency,
            from_dt=from_dt,
            to_dt=to_dt,
            bucket=bucket,
        )
    except BddClientNotConfiguredError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )
    except Exception as exc:
        logger.exception("Failed to fetch price series")
        return JSONResponse(
            status_code=502,
            content={"error": f"Upstream API error: {exc}"},
        )
