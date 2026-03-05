"""Domain constants and helpers for Microsoft Fabric capacity pricing."""

from __future__ import annotations

from typing import Any, Literal

ARM_SKU_NAME = "Fabric_Capacity_CU_Hour"
DEFAULT_CURRENCY = "USD"

PricingModel = Literal["PAYG", "RI_1Y", "RI_3Y"]

SKU_CU_MAP: dict[str, int] = {
    "F2": 2,
    "F4": 4,
    "F8": 8,
    "F16": 16,
    "F32": 32,
    "F64": 64,
    "F128": 128,
    "F256": 256,
    "F512": 512,
    "F1024": 1024,
    "F2048": 2048,
}


def classify_model(
    pricing_type: str,
    reservation_term: str | None,
) -> PricingModel | None:
    """Map a (pricingType, reservationTerm) pair to a ``PricingModel``.

    Returns ``None`` if the combination is unrecognised.
    """
    pt = pricing_type.lower()
    if pt == "consumption":
        return "PAYG"
    if pt == "reservation":
        rt = (reservation_term or "").strip()
        if rt == "1 Year":
            return "RI_1Y"
        if rt == "3 Years":
            return "RI_3Y"
    return None


def extract_per_cu_hour(item: dict[str, Any]) -> float:
    """Return the per-CU-hour price from a retail-price item.

    Prefers ``unitPrice`` when present, falls back to ``retailPrice``.
    """
    unit = item.get("unitPrice")
    if unit is not None:
        return float(unit)
    return float(item.get("retailPrice", 0))
