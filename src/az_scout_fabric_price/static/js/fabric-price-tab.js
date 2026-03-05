// Fabric Pricing plugin tab logic
// Globals from app.js: apiFetch, regions
(function () {
    const PLUGIN = "fabric-price";
    const HOURS_PER_MONTH = 730;
    const container = document.getElementById("plugin-tab-" + PLUGIN);
    if (!container) return;

    // ---------------------------------------------------------------
    // 1. Load HTML fragment
    // ---------------------------------------------------------------
    fetch(`/plugins/${PLUGIN}/static/html/fabric-price-tab.html`)
        .then(r => r.text())
        .then(html => { container.innerHTML = html; init(); })
        .catch(err => {
            container.innerHTML =
                `<div class="alert alert-danger">Failed to load plugin UI: ${err.message}</div>`;
        });

    // ---------------------------------------------------------------
    // 2. Init
    // ---------------------------------------------------------------
    function init() {
        const regionEl       = document.getElementById("region-select"); // core hidden input
        const regionBadge    = document.getElementById("fp-region-badge");
        const currencySelect = document.getElementById("fp-currency-select");
        const loadBtn        = document.getElementById("fp-load-btn");
        const loadingEl      = document.getElementById("fp-loading");
        const errorEl        = document.getElementById("fp-error");
        const warningsEl     = document.getElementById("fp-warnings");
        const tableWrapper   = document.getElementById("fp-table-wrapper");
        const tableBody      = document.getElementById("fp-table-body");
        const sourceInfo     = document.getElementById("fp-source-info");
        const retrievedAt    = document.getElementById("fp-retrieved-at");
        const cuhrSummary    = document.getElementById("fp-cuhr-summary");
        const cuhrCards      = document.getElementById("fp-cuhr-cards");
        const notConfigured  = document.getElementById("fp-not-configured");

        function getRegion() { return regionEl ? regionEl.value : ""; }

        function getRegionDisplayName() {
            const name = getRegion();
            if (!name) return "No region";
            const list = (typeof regions !== "undefined") ? regions : [];
            const found = list.find(r => r.name === name);
            return found ? (found.displayName || name) : name;
        }

        function updateRegionBadge() {
            const name = getRegion();
            if (regionBadge) {
                regionBadge.textContent = getRegionDisplayName();
                regionBadge.className = name
                    ? "badge bg-success"
                    : "badge bg-secondary";
            }
            loadBtn.disabled = !name;
        }

        // React to core region changes (hidden input)
        if (regionEl) {
            let lastRegion = regionEl.value;
            new MutationObserver(() => {
                if (regionEl.value !== lastRegion) {
                    lastRegion = regionEl.value;
                    updateRegionBadge();
                    if (regionEl.value) loadPrices();
                }
            }).observe(regionEl, { attributes: true, attributeFilter: ["value"] });

            regionEl.addEventListener("change", () => {
                updateRegionBadge();
                if (getRegion()) loadPrices();
            });
        }

        // Currency change → reload
        currencySelect.addEventListener("change", () => {
            if (getRegion()) loadPrices();
        });

        loadBtn.addEventListener("click", loadPrices);

        // Initial state
        updateRegionBadge();
        if (getRegion()) loadPrices();

        // --- load prices ---
        async function loadPrices() {
            const region = getRegion();
            const currency = currencySelect.value;
            if (!region) return;

            showLoading(true);
            hideError();
            hideWarnings();
            hideTable();
            hideCuhrSummary();
            notConfigured.style.display = "none";

            try {
                const data = await apiFetch(
                    `/plugins/${PLUGIN}/v1/fabric/prices/latest?region=${encodeURIComponent(region)}&currency=${encodeURIComponent(currency)}`
                );

                if (data.error) {
                    if (data.error.includes("not configured")) {
                        notConfigured.style.display = "";
                    } else {
                        showError(data.error);
                    }
                    return;
                }

                renderTable(data, currency);
                renderCuhrSummary(data, currency);
                renderWarnings(data.warnings || []);
                renderSourceInfo(data.retrievedAt);
            } catch (err) {
                showError(err.message || "Failed to fetch pricing data");
            } finally {
                showLoading(false);
            }
        }

        // --- render pricing table ---
        function renderTable(data, currency) {
            const skus = data.skus || {};
            const skuNames = Object.keys(skus);
            if (skuNames.length === 0) {
                showError("No pricing data available for this region.");
                return;
            }

            // Sort by CU count
            skuNames.sort((a, b) => (skus[a].capacityUnits || 0) - (skus[b].capacityUnits || 0));

            tableBody.innerHTML = "";
            const fmt = priceFormatter(currency);
            const pctFmt = new Intl.NumberFormat(undefined, {
                style: "percent",
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            });

            for (const name of skuNames) {
                const s = skus[name];
                const cu = s.capacityUnits || 0;
                const payg = s.PAYG;
                const ri1y = s.RI_1Y;
                const ri3y = s.RI_3Y;

                const paygMonth = payg != null ? payg * HOURS_PER_MONTH : null;
                const ri1yMonth = ri1y != null ? ri1y * HOURS_PER_MONTH : null;
                const ri3yMonth = ri3y != null ? ri3y * HOURS_PER_MONTH : null;

                const savings1y = (payg != null && ri1y != null && payg > 0)
                    ? (payg - ri1y) / payg : null;
                const savings3y = (payg != null && ri3y != null && payg > 0)
                    ? (payg - ri3y) / payg : null;

                const tr = document.createElement("tr");
                tr.innerHTML = [
                    `<td class="fp-td-sku">${esc(name)}</td>`,
                    `<td class="fp-td-cu">${cu}</td>`,
                    `<td class="fp-td-price">${fmtPrice(fmt, payg)}</td>`,
                    `<td class="fp-td-price">${fmtPrice(fmt, paygMonth)}</td>`,
                    `<td class="fp-td-price">${fmtPrice(fmt, ri1y)}</td>`,
                    `<td class="fp-td-price">${fmtPrice(fmt, ri1yMonth)}</td>`,
                    `<td class="fp-td-price">${fmtPrice(fmt, ri3y)}</td>`,
                    `<td class="fp-td-price">${fmtPrice(fmt, ri3yMonth)}</td>`,
                    `<td class="fp-td-savings">${fmtSavings(pctFmt, savings1y)}</td>`,
                    `<td class="fp-td-savings">${fmtSavings(pctFmt, savings3y)}</td>`,
                ].join("");
                tableBody.appendChild(tr);
            }

            tableWrapper.style.display = "";
        }

        // --- render per-CU-hour summary cards ---
        function renderCuhrSummary(data, currency) {
            const perCu = data.perCuHour || {};
            const models = Object.keys(perCu);
            if (models.length === 0) return;

            const fmt = priceFormatter(currency, 6);
            cuhrCards.innerHTML = "";

            const labelMap = { PAYG: "Pay-As-You-Go", RI_1Y: "1-Year RI", RI_3Y: "3-Year RI" };
            for (const model of ["PAYG", "RI_1Y", "RI_3Y"]) {
                if (perCu[model] == null) continue;
                const card = document.createElement("div");
                card.className = "fp-cuhr-card";
                card.innerHTML = `
                    <span class="fp-cuhr-label">${esc(labelMap[model] || model)}</span>
                    <span class="fp-cuhr-value">${fmt.format(perCu[model])}</span>
                `;
                cuhrCards.appendChild(card);
            }

            cuhrSummary.style.display = "";
        }

        // --- helpers ---
        function priceFormatter(currency, maxDecimals) {
            return new Intl.NumberFormat(undefined, {
                style: "currency",
                currency: currency,
                minimumFractionDigits: 2,
                maximumFractionDigits: maxDecimals || 4,
            });
        }

        function fmtPrice(fmt, val) {
            return val != null ? fmt.format(val) : '<span class="fp-na">—</span>';
        }

        function fmtSavings(fmt, val) {
            if (val == null) return '<span class="fp-na">—</span>';
            const cls = val > 0 ? "fp-savings-positive" : "";
            return `<span class="${cls}">${fmt.format(val)}</span>`;
        }

        function esc(str) {
            const el = document.createElement("span");
            el.textContent = str;
            return el.innerHTML;
        }

        // --- UI toggles ---
        function showLoading(on) { loadingEl.style.display = on ? "" : "none"; }

        function showError(msg) {
            errorEl.textContent = msg;
            errorEl.style.display = "";
        }
        function hideError() { errorEl.style.display = "none"; }

        function renderWarnings(warnings) {
            if (!warnings.length) { hideWarnings(); return; }
            warningsEl.innerHTML = warnings.map(w =>
                `<div class="fp-warning"><i class="bi bi-exclamation-triangle"></i> ${esc(w)}</div>`
            ).join("");
            warningsEl.style.display = "";
        }
        function hideWarnings() { warningsEl.style.display = "none"; }

        function hideTable() { tableWrapper.style.display = "none"; }
        function hideCuhrSummary() { cuhrSummary.style.display = "none"; }

        function renderSourceInfo(retrievedAtStr) {
            if (!retrievedAtStr) { sourceInfo.style.display = "none"; return; }
            try {
                const d = new Date(retrievedAtStr);
                retrievedAt.textContent = d.toLocaleString();
            } catch {
                retrievedAt.textContent = retrievedAtStr;
            }
            sourceInfo.style.display = "";
        }
    }
})();
