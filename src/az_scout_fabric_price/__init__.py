"""az-scout plugin for Microsoft Fabric capacity pricing.

Reads Fabric pricing data from the standalone BDD-API server,
transforms it into capacity-level pricing (PAYG, RI 1Y, RI 3Y),
and derives per-SKU costs using a fixed CU mapping.
"""

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from az_scout.plugin_api import ChatMode, TabDefinition, get_plugin_logger
from fastapi import APIRouter

logger = get_plugin_logger("fabric-price")

_STATIC_DIR = Path(__file__).parent / "static"

try:
    __version__ = _pkg_version("az-scout-plugin-fabric-price")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


class FabricPricePlugin:
    """Microsoft Fabric capacity pricing plugin."""

    name = "fabric-price"
    version = __version__

    def get_router(self) -> APIRouter | None:
        """Return API routes."""
        from az_scout_fabric_price.routes import router

        return router

    def get_mcp_tools(self) -> list[Callable[..., Any]] | None:
        """Return MCP tool functions."""
        from az_scout_fabric_price.tools import (
            fabric_capacities,
            fabric_price_series,
            fabric_prices_latest,
        )

        return [fabric_capacities, fabric_prices_latest, fabric_price_series]

    def get_static_dir(self) -> Path | None:
        """Return path to static assets directory."""
        return _STATIC_DIR

    def get_tabs(self) -> list[TabDefinition] | None:
        """Return UI tab definitions."""
        return [
            TabDefinition(
                id="fabric-price",
                label="Fabric Pricing",
                icon="bi bi-microsoft",
                js_entry="js/fabric-price-tab.js",
                css_entry="css/fabric-price.css",
            )
        ]

    def get_chat_modes(self) -> list[ChatMode] | None:
        """No custom chat modes."""
        return None


# Module-level instance — referenced by the entry point
plugin = FabricPricePlugin()
