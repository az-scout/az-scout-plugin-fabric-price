"""HTTP client for the standalone BDD-SKU API (Fabric pricing subset).

Calls ``/v1/retail/prices/latest`` and ``/v1/retail/prices`` on the
bdd-api server.  The base URL is resolved from the bdd-sku plugin config.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from az_scout_fabric_price.models import ARM_SKU_NAME

try:
    from az_scout_bdd_sku.plugin_config import get_config, is_configured
except ImportError:  # az-scout-bdd-sku not installed

    def _read_api_url_from_toml() -> str:
        """Read api.base_url from the bdd-sku TOML config file."""
        for p in (
            Path.home() / ".config" / "az-scout" / "bdd-sku.toml",
            Path("/tmp/az-scout/bdd-sku.toml"),
        ):
            if p.exists():
                try:
                    import tomllib
                except ModuleNotFoundError:
                    import tomli as tomllib  # type: ignore[no-redef]
                with open(p, "rb") as f:
                    data = tomllib.load(f)
                return str(data.get("api", {}).get("base_url", ""))
        return ""

    def _resolve_api_url() -> str:
        return os.environ.get("BDD_SKU_API_URL", "") or _read_api_url_from_toml()

    class _FallbackConfig:
        @property
        def api_base_url(self) -> str:
            return _resolve_api_url()

    _fallback = _FallbackConfig()

    def get_config() -> _FallbackConfig:  # type: ignore[misc]
        return _fallback

    def is_configured() -> bool:  # type: ignore[misc]
        return bool(_resolve_api_url())


logger = logging.getLogger(__name__)

_TIMEOUT = 30
_session_instance: requests.Session | None = None


class BddClientNotConfiguredError(Exception):
    """Raised when the BDD-SKU API base URL has not been set."""


def _session() -> requests.Session:
    """Return a reusable session with retry logic for transient errors."""
    global _session_instance  # noqa: PLW0603
    if _session_instance is None:
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s = requests.Session()
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _session_instance = s
    return _session_instance


def _base_url() -> str:
    """Return the configured API base URL or raise."""
    if not is_configured():
        raise BddClientNotConfiguredError(
            "BDD-SKU API URL is not configured. "
            "Set it in the BDD SKU plugin settings or via BDD_SKU_API_URL env var."
        )
    url: str = get_config().api_base_url
    return url.rstrip("/")


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Issue a GET request with retry logic and return parsed JSON."""
    url = f"{_base_url()}{path}"
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}
    resp = _session().get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_latest_prices(
    region: str,
    currency: str = "USD",
) -> list[dict[str, Any]]:
    """Fetch latest Fabric retail prices from ``/v1/retail/prices/latest``.

    Automatically paginates through all pages and filters by
    ``sku=Fabric_Capacity_CU_Hour``.
    """
    all_items: list[dict[str, Any]] = []
    cursor: str = ""
    while True:
        data: dict[str, Any] = _get(
            "/v1/retail/prices/latest",
            {
                "region": region,
                "currency": currency,
                "sku": ARM_SKU_NAME,
                "limit": 200,
                "cursor": cursor,
            },
        )
        items = data.get("items", [])
        all_items.extend(items)
        page = data.get("page", {})
        if not page.get("hasMore"):
            break
        cursor = page.get("cursor", "")
        if not cursor:
            break
    return all_items


def fetch_prices(
    region: str,
    currency: str = "USD",
    updated_since: str = "",
) -> list[dict[str, Any]]:
    """Fetch Fabric retail price history from ``/v1/retail/prices``.

    Automatically paginates and filters by ``sku=Fabric_Capacity_CU_Hour``.
    ``updated_since`` is an ISO-8601 string; only rows updated after this
    date are returned (server-side filter via ``updatedSince``).
    """
    all_items: list[dict[str, Any]] = []
    cursor: str = ""
    while True:
        data: dict[str, Any] = _get(
            "/v1/retail/prices",
            {
                "region": region,
                "currency": currency,
                "sku": ARM_SKU_NAME,
                "updatedSince": updated_since,
                "limit": 200,
                "cursor": cursor,
            },
        )
        items = data.get("items", [])
        all_items.extend(items)
        page = data.get("page", {})
        if not page.get("hasMore"):
            break
        cursor = page.get("cursor", "")
        if not cursor:
            break
    return all_items
