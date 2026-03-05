# az-scout-plugin-fabric-price

An [az-scout](https://github.com/lrivallain/az-scout) plugin that surfaces **Microsoft Fabric capacity pricing** — PAYG, 1-Year RI, and 3-Year RI — directly inside the az-scout UI, REST API, and MCP server.

Data is sourced from the [az-scout-bdd-api](https://github.com/rsabile/az_scout_bdd_api) pricing database and enriched with per-SKU costs using the Fabric CU (Capacity Unit) mapping.

## Features

- **UI tab** — interactive pricing table with region/currency selectors, per-SKU hourly & monthly costs, savings percentages, and per-CU-hour summary cards
- **3 REST endpoints** — capacities list, latest prices, and price time series
- **3 MCP tools** — `fabric_capacities`, `fabric_prices_latest`, `fabric_price_series`
- **Dark/light theme** support via CSS custom properties
- **In-memory TTL cache** (configurable via `FABRIC_PRICE_CACHE_TTL` env var, default 300 s)

## Prerequisites

- [az-scout](https://github.com/lrivallain/az-scout) installed
- [az-scout-bdd-sku](https://github.com/rsabile/az-scout-plugin-bdd-sku) plugin installed and configured with a valid API URL pointing to a running [az-scout-bdd-api](https://github.com/rsabile/az_scout_bdd_api) instance

## Installation

```bash
uv pip install -e .     # development
# or
uv pip install az-scout-plugin-fabric-price  # from PyPI
```

The plugin is auto-discovered at startup — no extra configuration needed.

## Configuration

This plugin reuses the BDD-SKU plugin's API URL. Set it via any of:

1. **BDD-SKU Settings UI** — `PUT /plugins/bdd-sku/settings`
2. **Environment variable** — `BDD_SKU_API_URL`
3. **TOML config** — `~/.config/az-scout/bdd-sku.toml` → `[api] base_url = "…"`

Cache TTL can be overridden:

```bash
export FABRIC_PRICE_CACHE_TTL=600  # seconds
```

## REST API

All endpoints are mounted at `/plugins/fabric-price/`.

### `GET /v1/fabric/capacities`

Static list of Fabric SKUs and CU counts.

```bash
curl http://localhost:5001/plugins/fabric-price/v1/fabric/capacities
```

### `GET /v1/fabric/prices/latest`

Latest per-CU-hour and per-SKU pricing for a region.

| Parameter  | Required | Default | Description              |
|------------|----------|---------|--------------------------|
| `region`   | yes      | —       | Azure region name        |
| `currency` | no       | `USD`   | ISO 4217 currency code   |

```bash
curl "http://localhost:5001/plugins/fabric-price/v1/fabric/prices/latest?region=eastus&currency=EUR"
```

### `GET /v1/fabric/prices/series`

Price time series for a specific SKU.

| Parameter  | Required | Default | Description                          |
|------------|----------|---------|--------------------------------------|
| `region`   | yes      | —       | Azure region name                    |
| `sku`      | yes      | —       | Fabric SKU (F2, F4, … F2048)        |
| `model`    | no       | `PAYG`  | Pricing model: PAYG, RI_1Y, RI_3Y   |
| `currency` | no       | `USD`   | ISO 4217 currency code               |
| `from`     | no       | —       | Start date (ISO 8601)                |
| `to`       | no       | —       | End date (ISO 8601)                  |
| `bucket`   | no       | `day`   | Time bucket: day, week, month        |

```bash
curl "http://localhost:5001/plugins/fabric-price/v1/fabric/prices/series?region=eastus&sku=F64&bucket=week"
```

## MCP tools

| Tool                    | Parameters                                              | Description                                 |
|-------------------------|---------------------------------------------------------|---------------------------------------------|
| `fabric_capacities`     | —                                                       | List all Fabric SKUs and their CU counts    |
| `fabric_prices_latest`  | `region`, `currency?`                                   | Latest pricing (per-CU-hour + per-SKU)      |
| `fabric_price_series`   | `region`, `sku`, `model?`, `currency?`, `from_dt?`, `to_dt?`, `bucket?` | Price time series for a SKU |

## Project structure

```
az-scout-plugin-fabric-price/
├── pyproject.toml
├── README.md
└── src/
    └── az_scout_fabric_price/
        ├── __init__.py          # FabricPricePlugin class
        ├── bdd_client.py        # HTTP client → bdd-api server
        ├── models.py            # SKU_CU_MAP, classify_model, extract_per_cu_hour
        ├── routes.py            # FastAPI endpoints (3 routes)
        ├── service.py           # Business logic + caching
        ├── tools.py             # MCP tool functions (3 tools)
        └── static/
            ├── css/fabric-price.css
            ├── html/fabric-price-tab.html
            └── js/fabric-price-tab.js
tests/
    ├── test_models.py
    ├── test_routes.py
    └── test_service.py
```

## Development

```bash
uv sync
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest
```

## Versioning

Version is derived from git tags via `hatch-vcs`. Tags follow CalVer: `v2026.2.0`.

## How it works

1. The plugin JS loads the HTML fragment into `#plugin-tab-example`.
2. It watches `#tenant-select` and `#region-select` for changes.
3. When both are set, it fetches subscriptions from `/api/subscriptions`.
4. The user picks a subscription and clicks the button.
5. The plugin calls `GET /plugins/example/hello?subscription_name=…&tenant=…&region=…`.

## Quality checks

The scaffold includes GitHub Actions workflows in `.github/workflows/`:

- **`ci.yml`** — Runs lint (ruff + mypy) and tests (pytest) on Python 3.11–3.13, triggered on push/PR to `main`.
- **`publish.yml`** — Builds, creates a GitHub Release, and publishes to PyPI via trusted publishing (OIDC). Triggered on version tags (`v*`). Requires a `pypi` environment configured in your repo settings with OIDC trusted publishing.

Run the same checks locally:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest
```

To publish a release:

```bash
git tag v2026.2.0
git push origin v2026.2.0
```

## Copilot support

The `.github/copilot-instructions.md` file provides context to GitHub Copilot about
the plugin structure, conventions, and az-scout plugin API. It helps Copilot generate
code that follows the project patterns.


## License

[MIT](LICENSE.txt)

## Disclaimer

> **This tool is not affiliated with Microsoft.** All capacity, pricing, and latency information are indicative and not a guarantee of deployment success. Spot placement scores are probabilistic. Quota values and pricing are dynamic and may change between planning and actual deployment. Latency values are based on [Microsoft published statistics](https://learn.microsoft.com/en-us/azure/networking/azure-network-latency) and must be validated with in-tenant measurements.
