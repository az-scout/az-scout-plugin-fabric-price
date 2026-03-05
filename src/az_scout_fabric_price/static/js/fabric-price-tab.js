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

        // History modal
        let historyModal = null;
        let activeSku = "";
        const historySkuEl   = document.getElementById("fp-history-sku");
        const bucketSelect   = document.getElementById("fp-bucket-select");
        const historyLoading = document.getElementById("fp-history-loading");
        const historyError   = document.getElementById("fp-history-error");
        const chartContainer = document.getElementById("fp-chart-container");

        tableWrapper.addEventListener("click", (e) => {
            const cell = e.target.closest("[data-action='history']");
            if (cell) openHistoryModal(cell.dataset.sku);
        });

        bucketSelect.addEventListener("change", () => {
            if (activeSku) fetchHistory(activeSku, bucketSelect.value);
        });

        document.getElementById("fp-history-modal")
            .addEventListener("hidden.bs.modal", () => { chartContainer.innerHTML = ""; });

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
                    `<td class="fp-td-sku" data-action="history" data-sku="${escAttr(name)}" role="button" title="View price history">${esc(name)} <i class="bi bi-graph-up fp-history-icon"></i></td>`,
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

        function escAttr(str) {
            return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
                      .replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        // --- History modal & D3 chart ---

        function openHistoryModal(sku) {
            activeSku = sku;
            historySkuEl.textContent = sku;
            if (!historyModal) {
                historyModal = new bootstrap.Modal(
                    document.getElementById("fp-history-modal")
                );
            }
            historyModal.show();
            fetchHistory(sku, bucketSelect.value);
        }

        async function fetchHistory(sku, bucket) {
            historyLoading.style.display = "";
            historyError.style.display = "none";
            chartContainer.innerHTML = "";

            const region   = getRegion();
            const currency = currencySelect.value;
            const models   = ["PAYG", "RI_1Y", "RI_3Y"];

            try {
                const results = await Promise.all(models.map(model =>
                    apiFetch(
                        `/plugins/${PLUGIN}/v1/fabric/prices/series?` +
                        `region=${encodeURIComponent(region)}` +
                        `&sku=${encodeURIComponent(sku)}` +
                        `&model=${encodeURIComponent(model)}` +
                        `&currency=${encodeURIComponent(currency)}` +
                        `&bucket=${encodeURIComponent(bucket)}`
                    )
                ));

                const datasets = {};
                models.forEach((model, i) => {
                    const res = results[i];
                    if (res.error) { datasets[model] = []; return; }
                    datasets[model] = (res.items || []).map(p => ({
                        date: new Date(p.bucketTs),
                        value: p.value,
                    }));
                });

                historyLoading.style.display = "none";
                renderChart(datasets, currency);
            } catch (err) {
                historyLoading.style.display = "none";
                historyError.textContent = err.message || "Failed to fetch price history";
                historyError.style.display = "";
            }
        }

        function renderChart(datasets, currency) {
            chartContainer.innerHTML = "";

            const MODELS = [
                { key: "PAYG",  label: "Pay-As-You-Go", color: "#0d6efd" },
                { key: "RI_1Y", label: "1-Year RI",     color: "#198754" },
                { key: "RI_3Y", label: "3-Year RI",     color: "#fd7e14" },
            ];
            const active = MODELS.filter(m =>
                datasets[m.key] && datasets[m.key].length > 0
            );
            if (active.length === 0) {
                chartContainer.innerHTML =
                    '<div class="fp-chart-nodata">No price history available.</div>';
                return;
            }

            for (const m of active) {
                datasets[m.key].sort((a, b) => a.date - b.date);
            }

            const allPts = active.flatMap(m => datasets[m.key]);
            const margin = { top: 32, right: 20, bottom: 36, left: 64 };
            const W = 800, H = 360;
            const iW = W - margin.left - margin.right;
            const iH = H - margin.top - margin.bottom;

            const svg = d3.select(chartContainer).append("svg")
                .attr("viewBox", `0 0 ${W} ${H}`)
                .attr("preserveAspectRatio", "xMidYMid meet")
                .classed("fp-chart-svg", true);

            const g = svg.append("g")
                .attr("transform", `translate(${margin.left},${margin.top})`);

            // Scales
            const xScale = d3.scaleTime()
                .domain(d3.extent(allPts, d => d.date))
                .range([0, iW]);

            const [yMin, yMax] = d3.extent(allPts, d => d.value);
            const yPad = (yMax - yMin) * 0.1 || yMin * 0.1 || 0.01;
            const yScale = d3.scaleLinear()
                .domain([Math.max(0, yMin - yPad), yMax + yPad])
                .range([iH, 0]);

            // Grid
            g.append("g").attr("class", "fp-chart-grid")
                .call(d3.axisLeft(yScale).ticks(6).tickSize(-iW).tickFormat(""));

            // Axes
            g.append("g").attr("class", "fp-chart-axis")
                .attr("transform", `translate(0,${iH})`)
                .call(d3.axisBottom(xScale).ticks(7));

            const fmt = priceFormatter(currency, 4);
            g.append("g").attr("class", "fp-chart-axis")
                .call(d3.axisLeft(yScale).ticks(6)
                    .tickFormat(v => fmt.format(v)));

            // Lines
            const lineFn = d3.line()
                .x(d => xScale(d.date))
                .y(d => yScale(d.value))
                .curve(d3.curveMonotoneX);

            for (const m of active) {
                g.append("path")
                    .datum(datasets[m.key])
                    .attr("fill", "none")
                    .attr("stroke", m.color)
                    .attr("stroke-width", 2)
                    .attr("d", lineFn);
            }

            // Legend
            const legend = svg.append("g")
                .attr("transform",
                    `translate(${margin.left + 8},${margin.top - 14})`);
            active.forEach((m, i) => {
                const lg = legend.append("g")
                    .attr("transform", `translate(${i * 140},0)`);
                lg.append("line")
                    .attr("x1", 0).attr("x2", 18)
                    .attr("stroke", m.color).attr("stroke-width", 2);
                lg.append("text").attr("x", 22).attr("y", 4)
                    .attr("class", "fp-chart-legend-text").text(m.label);
            });

            // Tooltip
            const tip = d3.select(chartContainer).append("div")
                .attr("class", "fp-chart-tooltip")
                .style("display", "none");

            const focusLine = g.append("line")
                .attr("class", "fp-chart-focus-line")
                .attr("y1", 0).attr("y2", iH)
                .style("display", "none");

            const dots = active.map(m =>
                g.append("circle").attr("r", 4)
                    .attr("fill", m.color)
                    .attr("stroke", "#fff").attr("stroke-width", 1.5)
                    .style("display", "none")
            );

            const bisect = d3.bisector(d => d.date).left;

            svg.append("rect")
                .attr("x", margin.left).attr("y", margin.top)
                .attr("width", iW).attr("height", iH)
                .attr("fill", "none").attr("pointer-events", "all")
                .on("mousemove", function (event) {
                    const [mx] = d3.pointer(event, g.node());
                    const xDate = xScale.invert(mx);
                    focusLine.attr("x1", mx).attr("x2", mx)
                        .style("display", null);

                    let html = '<div class="fp-tip-date">' +
                        d3.timeFormat("%b %d, %Y")(xDate) + '</div>';
                    active.forEach((m, i) => {
                        const data = datasets[m.key];
                        const idx = bisect(data, xDate, 1);
                        const d0 = data[idx - 1];
                        const d1 = data[idx];
                        if (!d0) return;
                        const d = (!d1 || xDate - d0.date < d1.date - xDate)
                            ? d0 : d1;
                        dots[i]
                            .attr("cx", xScale(d.date))
                            .attr("cy", yScale(d.value))
                            .style("display", null);
                        html += '<div class="fp-tip-line">' +
                            '<span class="fp-tip-swatch" style="background:' +
                            m.color + '"></span>' +
                            m.label + ': <strong>' +
                            fmt.format(d.value) + '</strong></div>';
                    });

                    tip.html(html).style("display", "block");
                    const cRect = chartContainer.getBoundingClientRect();
                    const evX = event.clientX - cRect.left;
                    const tipW = tip.node().offsetWidth;
                    const left = (evX + tipW + 20 > cRect.width)
                        ? evX - tipW - 10 : evX + 10;
                    tip.style("left", left + "px").style("top", "40px");
                })
                .on("mouseleave", function () {
                    focusLine.style("display", "none");
                    dots.forEach(d => d.style("display", "none"));
                    tip.style("display", "none");
                });
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
