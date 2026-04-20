/* global Chart */

const STORAGE_KEY_V1 = "mx_tidrapport_v1";
const STORAGE_KEY_V2 = "mx_tidrapport_v2";

/** Månadsnamn i samma ordning som i tidrapport.html */
const SWEDISH_MONTHS = [
  "Januari",
  "Februari",
  "Mars",
  "April",
  "Maj",
  "Juni",
  "Juli",
  "Augusti",
  "September",
  "Oktober",
  "November",
  "December",
];

const els = {
  pasteInput: document.getElementById("pasteInput"),
  btnGenerate: document.getElementById("btnGenerate"),
  btnDownload: document.getElementById("btnDownload"),
  btnClear: document.getElementById("btnClear"),
  btnClearNearGenerate: document.getElementById("btnClearNearGenerate"),
  btnLoad: document.getElementById("btnLoad"),
  btnAll: document.getElementById("btnAll"),
  btnNone: document.getElementById("btnNone"),
  monthSelect: document.getElementById("monthSelect"),
  yearInput: document.getElementById("yearInput"),
  titleInput: document.getElementById("titleInput"),
  titlePreview: document.getElementById("titlePreview"),
  colorLegend: document.getElementById("colorLegend"),
  orientationSelect: document.getElementById("orientationSelect"),
  verticalNamesSelect: document.getElementById("verticalNamesSelect"),
  layoutSelect: document.getElementById("layoutSelect"),
  statusFilters: document.getElementById("statusFilters"),
  statusText: document.getElementById("statusText"),
  employeeInput: document.getElementById("employeeInput"),
  employeeList: document.getElementById("employeeList"),
  btnClearEmployee: document.getElementById("btnClearEmployee"),
  tableBody: document.getElementById("tableBody"),
  chartCanvas: document.getElementById("chartCanvas"),
  layoutGrid: document.getElementById("layoutGrid"),
  savedSlotSelect: document.getElementById("savedSlotSelect"),
  btnLoadSlot: document.getElementById("btnLoadSlot"),
  btnSaveSlot: document.getElementById("btnSaveSlot"),
  btnDeleteSlot: document.getElementById("btnDeleteSlot"),
  analysisModeSelect: document.getElementById("analysisModeSelect"),
  comparePanel: document.getElementById("comparePanel"),
  forecastPanel: document.getElementById("forecastPanel"),
  compareSlotA: document.getElementById("compareSlotA"),
  compareSlotB: document.getElementById("compareSlotB"),
  btnRefreshCompare: document.getElementById("btnRefreshCompare"),
  forecastThroughDay: document.getElementById("forecastThroughDay"),
  forecastMonthInfo: document.getElementById("forecastMonthInfo"),
  tableHeadRow: document.getElementById("tableHeadRow"),
  mergeQueueList: document.getElementById("mergeQueueList"),
  btnAddToMerge: document.getElementById("btnAddToMerge"),
  btnAddSavedToMerge: document.getElementById("btnAddSavedToMerge"),
  btnMergePickFiles: document.getElementById("btnMergePickFiles"),
  mergeFileInput: document.getElementById("mergeFileInput"),
  btnClearMergeQueue: document.getElementById("btnClearMergeQueue"),
  btnApplyMerge: document.getElementById("btnApplyMerge"),
};

/** Råtext per del för sammanslagen period (jan–mars m.m.), endast i minnet */
const mergeQueue = [];

let __slotFeedbackTimer = null;
/** Synlig bekräftelse under «Spara flera månader» (användaren scrollar ofta inte till statusraden). */
function setSlotFeedback(msg) {
  const el = document.getElementById("slotActionFeedback");
  if (!el) return;
  el.textContent = msg || "";
  if (__slotFeedbackTimer) {
    clearTimeout(__slotFeedbackTimer);
    __slotFeedbackTimer = null;
  }
  if (msg) {
    __slotFeedbackTimer = setTimeout(() => {
      el.textContent = "";
      __slotFeedbackTimer = null;
    }, 14000);
  }
}

function getAnalysisMode() {
  return cleanStr(els.analysisModeSelect?.value) || "normal";
}

function updateFilterContextBanner() {
  const el = document.getElementById("filterContextBanner");
  if (!el) return;
  const mode = getAnalysisMode();
  const base =
    "ring-1 ring-inset transition-colors";
  if (mode === "compare") {
    el.className = `text-xs rounded-lg px-3 py-2.5 mb-4 border ${base} bg-amber-950/50 border-amber-700/60 text-amber-100/95`;
    el.textContent =
      "Jämförelseläge: kryssrutorna väljer vilka statusar (Orsak) som summeras för varje person — en stapel för månad A och en för månad B. Namnfilter nedan begränsar vilka personer som visas i båda.";
  } else if (mode === "forecast") {
    el.className = `text-xs rounded-lg px-3 py-2.5 mb-4 border ${base} bg-sky-950/40 border-sky-800/70 text-sky-100/95`;
    el.textContent =
      "Prognosläge: samma status- och namnfilter som nedan används först; därefter skalas timmarna upp mot hela månaden enligt «Data till dag» under Prognos ovan.";
  } else {
    el.className = `text-xs rounded-lg px-3 py-2.5 mb-4 border ${base} bg-emerald-950/35 border-emerald-800/50 text-emerald-50/95`;
    el.textContent =
      "Vanlig vy: välj vilka statusar som ska ingå i staplarna och valfritt ett namn. Gäller den data som finns i rutan (en månad eller redan sammanslagen period).";
  }
}

function updateAnalysisPanels() {
  const m = getAnalysisMode();
  els.comparePanel?.classList.toggle("hidden", m !== "compare");
  els.forecastPanel?.classList.toggle("hidden", m !== "forecast");
  updateFilterContextBanner();
}

function cleanStr(v) {
  if (v == null) return "";
  // Normalize "weird" whitespace from Excel/Sheets copy (NBSP, thin NBSP, figure space, etc.)
  return String(v)
    .replace(/[\u00A0\u2007\u202F]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normHeader(s) {
  return cleanStr(s).toLowerCase();
}

function parseRastMinutes(raw) {
  const s = cleanStr(raw).replace(",", ".");
  if (!s) return 0;
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function parseTimeToHours(raw) {
  const s = cleanStr(raw);
  if (!s) return null;

  // Common when copying from Excel/Sheets: "06:30" or "6:30"
  const m = s.match(/^(\d{1,2})[:.](\d{2})$/);
  if (m) {
    const h = Number(m[1]);
    const mi = Number(m[2]);
    if (Number.isFinite(h) && Number.isFinite(mi)) return h + mi / 60;
  }

  // Sometimes: "06:30:00"
  const m2 = s.match(/^(\d{1,2})[:.](\d{2})[:.](\d{2})$/);
  if (m2) {
    const h = Number(m2[1]);
    const mi = Number(m2[2]);
    const se = Number(m2[3]);
    if (Number.isFinite(h) && Number.isFinite(mi) && Number.isFinite(se)) return h + mi / 60 + se / 3600;
  }

  return null;
}

function durationHours(fom, tom) {
  if (fom == null || tom == null) return 0;
  let delta = tom - fom;
  if (delta <= 0) delta += 24;
  return delta;
}

const ORSAK_ORDER = [
  "Poäng inst kort ledig",
  "Poäng åter StBy/Förskj",
  "Arbtid kontering",
  "Stand by schema",
  "Stand by ledig",
];

function normalizeOrsak(raw) {
  const r = cleanStr(raw);
  if (!r) return "Övrigt";
  const low = r.toLowerCase();
  if (low.includes("poäng inst") || low.includes("pong inst") || low.includes("kort ledig")) return ORSAK_ORDER[0];
  if (low.includes("stby") || low.includes("förskj") || low.includes("forskj") || low.includes("ater st"))
    return ORSAK_ORDER[1];
  if (low.includes("kontering") || low.includes("arbtid")) return ORSAK_ORDER[2];
  if (low.includes("stand by schema") || (low.includes("stand") && low.includes("schema"))) return ORSAK_ORDER[3];
  if (low.includes("stand by ledig") || (low.includes("stand") && low.includes("ledig"))) return ORSAK_ORDER[4];
  return r || "Övrigt";
}

function splitRows(text) {
  const rawLines = text.replace(/\r\n/g, "\n").split("\n");
  return rawLines.map((l) => l.trimEnd()).filter((l) => l.trim().length > 0);
}

function detectDelimiter(headerLine) {
  if (headerLine.includes("\t")) return "\t";
  if (headerLine.includes(";")) return ";";
  if (headerLine.includes(",")) return ",";
  // fallback: multiple spaces
  return null;
}

function parseTable(text) {
  const raw = String(text ?? "").replace(/^\uFEFF/, "");
  const lines = splitRows(raw);
  if (lines.length === 0) return { headers: [], rows: [] };

  const delim = detectDelimiter(lines[0]);
  let headers = (delim ? lines[0].split(delim) : lines[0].split(/\s{2,}/)).map(cleanStr);
  // Remove empty trailing headers if the header row ends with separators/tabs.
  while (headers.length > 0 && !headers[headers.length - 1]) headers.pop();

  const rows = [];
  for (let i = 1; i < lines.length; i += 1) {
    const parts = (delim ? lines[i].split(delim) : lines[i].split(/\s{2,}/)).map(cleanStr);
    // pad
    while (parts.length < headers.length) parts.push("");
    const row = {};
    for (let c = 0; c < headers.length; c += 1) row[headers[c]] = parts[c] ?? "";
    rows.push(row);
  }
  return { headers, rows };
}

function pickCol(headers, wanted) {
  const low = headers.map(normHeader);
  for (const w of wanted) {
    const idx = low.indexOf(String(w).toLowerCase());
    if (idx >= 0) return headers[idx];
  }
  return null;
}

function validateHeadersForAggregate(headers) {
  const errors = [];
  if (!headers.length) {
    errors.push("Saknar rubrikrad.");
    return errors;
  }
  const colName = pickCol(headers, ["Namn", "Name"]);
  const colFom = pickCol(headers, ["Kl Fom", "Från", "From", "Fom", "F.o.m"]);
  const colTom = pickCol(headers, ["Kl Tom", "Till", "To", "Tom"]);
  const colOrsak = pickCol(headers, ["Orsak", "Status", "Typ"]);
  if (!colName) errors.push("Hittar inte kolumnen «Namn».");
  if (!colFom) errors.push("Hittar inte kolumnen «Kl Fom» (starttid).");
  if (!colTom) errors.push("Hittar inte kolumnen «Kl Tom» (sluttid).");
  if (!colOrsak) errors.push("Hittar inte kolumnen «Orsak»/«Status».");
  return errors;
}

function aggregateParsed(headers, rows) {
  const errors = validateHeadersForAggregate(headers);
  if (errors.length) return { totals: new Map(), statuses: [], errors, stats: null };

  const colName = pickCol(headers, ["Namn", "Name"]);
  const colFom = pickCol(headers, ["Kl Fom", "Från", "From", "Fom", "F.o.m"]);
  const colTom = pickCol(headers, ["Kl Tom", "Till", "To", "Tom"]);
  const colRast = pickCol(headers, ["Rast", "Kl rast", "Break"]);
  const colOrsak = pickCol(headers, ["Orsak", "Status", "Typ"]);

  const totals = new Map();
  const statusSet = new Set();
  let usedRows = 0;
  let skippedNoName = 0;
  let skippedNoTime = 0;

  for (const row of rows) {
    const name = cleanStr(row[colName]);
    if (!name) {
      skippedNoName += 1;
      continue;
    }
    const fom = parseTimeToHours(row[colFom]);
    const tom = parseTimeToHours(row[colTom]);
    if (fom == null || tom == null) {
      skippedNoTime += 1;
      continue;
    }
    const rastMin = colRast ? parseRastMinutes(row[colRast]) : 0;
    const gross = durationHours(fom, tom);
    const net = Math.max(0, gross - rastMin / 60);
    const status = normalizeOrsak(colOrsak ? row[colOrsak] : "");

    statusSet.add(status);
    if (!totals.has(name)) totals.set(name, new Map());
    const byStatus = totals.get(name);
    byStatus.set(status, (byStatus.get(status) || 0) + net);
    usedRows += 1;
  }

  const statuses = [
    ...ORSAK_ORDER.filter((s) => statusSet.has(s)),
    ...[...statusSet].filter((s) => !ORSAK_ORDER.includes(s)).sort((a, b) => a.localeCompare(b, "sv")),
  ];

  return {
    totals,
    statuses,
    errors: [],
    stats: {
      rawRows: rows.length,
      usedRows,
      skippedNoName,
      skippedNoTime,
    },
  };
}

function aggregate(text) {
  const { headers, rows } = parseTable(text);
  if (!headers.length) return { totals: new Map(), statuses: [], errors: ["Ingen data."], stats: null };
  return aggregateParsed(headers, rows);
}

function remapRowToBaseHeaders(row, sourceHeaders, baseHeaders) {
  const newRow = {};
  for (const bh of baseHeaders) {
    const match = sourceHeaders.find((sh) => normHeader(sh) === normHeader(bh));
    newRow[bh] = match ? row[match] ?? "" : "";
  }
  return newRow;
}

function mergeParsedTables(parsedList) {
  if (!parsedList.length) {
    return { headers: [], rows: [], errors: ["Inga tabeller att slå ihop."] };
  }
  const base = parsedList[0];
  if (!base.headers.length) {
    return { headers: [], rows: [], errors: ["Första delen saknar rubrikrad."] };
  }
  const v0 = validateHeadersForAggregate(base.headers);
  if (v0.length) return { headers: [], rows: [], errors: v0 };

  const allRows = [...base.rows];
  for (let i = 1; i < parsedList.length; i += 1) {
    const p = parsedList[i];
    if (!p.headers.length) {
      return { headers: [], rows: [], errors: [`Del ${i + 1}: saknar rubrikrad.`] };
    }
    const ve = validateHeadersForAggregate(p.headers);
    if (ve.length) {
      return { headers: [], rows: [], errors: [`Del ${i + 1}: ${ve.join(" ")}`] };
    }
    for (const row of p.rows) {
      allRows.push(remapRowToBaseHeaders(row, p.headers, base.headers));
    }
  }
  return { headers: base.headers, rows: allRows, errors: [] };
}

function tableToTsv(headers, rows) {
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    if (s.includes("\t") || s.includes("\n") || s.includes('"')) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const lines = [headers.map(esc).join("\t")];
  for (const row of rows) {
    lines.push(headers.map((h) => esc(row[h] ?? "")).join("\t"));
  }
  return lines.join("\n");
}

function renderMergeQueueList() {
  if (!els.mergeQueueList) return;
  els.mergeQueueList.innerHTML = "";
  if (mergeQueue.length === 0) {
    const li = document.createElement("li");
    li.className = "text-slate-500 italic px-1";
    li.textContent = "Inget tillagt ännu.";
    els.mergeQueueList.appendChild(li);
    return;
  }
  mergeQueue.forEach((item, idx) => {
    const li = document.createElement("li");
    li.className = "flex items-center justify-between gap-2 border-b border-slate-800/60 py-1.5";
    const span = document.createElement("span");
    const dataRows = Math.max(0, splitRows(item.text).length - 1);
    span.textContent = `${idx + 1}. ${item.label} (${dataRows} rader)`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "shrink-0 px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-xs";
    btn.textContent = "Ta bort";
    btn.addEventListener("click", () => {
      mergeQueue.splice(idx, 1);
      renderMergeQueueList();
    });
    li.appendChild(span);
    li.appendChild(btn);
    els.mergeQueueList.appendChild(li);
  });
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

function buildStatusColorMap(statuses) {
  const m = new Map();
  statuses.forEach((st, idx) => m.set(st, palette(idx)));
  return m;
}

function buildStatusFilters(statuses, selected) {
  els.statusFilters.innerHTML = "";
  const colorByStatus = buildStatusColorMap(statuses);
  for (const st of statuses) {
    const id = `st_${btoa(unescape(encodeURIComponent(st))).replace(/=/g, "")}`;
    const label = document.createElement("label");
    label.className =
      "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/70 hover:bg-slate-700/70 cursor-pointer select-none border border-slate-700";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.checked = selected.has(st);
    cb.className = "accent-emerald-500";
    cb.addEventListener("change", () => {
      if (cb.checked) selected.add(st);
      else selected.delete(st);
      safeRenderAll(window.__tidrapport_state);
      saveLocal(window.__tidrapport_state);
    });
    const sw = document.createElement("span");
    sw.className = "inline-block w-3 h-3 rounded-sm border border-slate-900";
    sw.style.background = colorByStatus.get(st) || "#94a3b8";
    const span = document.createElement("span");
    span.textContent = st;
    span.className = "text-xs text-slate-100";
    label.appendChild(cb);
    label.appendChild(sw);
    label.appendChild(span);
    els.statusFilters.appendChild(label);
  }
}

let chart = null;

function resetChartFully() {
  if (chart) {
    try {
      chart.destroy();
    } catch (e) {
      console.warn("resetChartFully", e);
    }
    chart = null;
  }
}

/** Jämförelse / annan diagramtyp än staplad status */
window.__chart_kind = "normal";

function desiredIndexAxis(mode) {
  return mode === "vertical" ? "x" : "y";
}

function resetChartIfOrientationChanged(mode) {
  if (!chart) return;
  const want = desiredIndexAxis(mode);
  const cur = chart?.options?.indexAxis || "y";
  if (cur !== want) {
    try {
      chart.destroy();
    } catch (e) {
      console.warn("Failed to destroy chart cleanly", e);
    }
    chart = null;
  }
}

function ensureChart(mode = "horizontal") {
  if (typeof Chart === "undefined") {
    throw new Error("Chart.js laddades inte. Ladda om sidan och testa igen.");
  }
  if (chart) return chart;
  const ctx = els.chartCanvas.getContext("2d");
  const indexAxis = desiredIndexAxis(mode);
  chart = new Chart(ctx, {
    type: "bar",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      // IMPORTANT: create the chart in the right orientation from start.
      indexAxis,
      // Workaround: some environments/plugins try to bind DOM events and can crash.
      // We don't need hover/click interactions for this report chart.
      events: [],
      animation: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#e2e8f0", boxWidth: 14, boxHeight: 14, padding: 14, font: { size: 12 } },
        },
        tooltip: { enabled: false },
        title: { display: true, text: "Timmar per person (per status)", color: "#e2e8f0", font: { size: 14 } },
      },
      scales: {
        x: { stacked: true, ticks: { color: "#cbd5e1", font: { size: 12 } }, grid: { color: "rgba(148,163,184,0.15)" } },
        y: {
          stacked: true,
          beginAtZero: true,
          ticks: { color: "#cbd5e1", font: { size: 12 } },
          grid: { color: "rgba(148,163,184,0.10)" },
        },
      },
    },
  });
  return chart;
}

function showUiError(err) {
  const msg = err && err.message ? String(err.message) : String(err || "Okänt fel");
  els.statusText.textContent = `Fel: ${msg}`;
}

function safeRenderAll(state) {
  try {
    if (state?.layout) applyLayoutMode(state.layout);
    renderAll(state);
  } catch (e) {
    console.error(e);
    showUiError(e);
  }
}

function getMonthYearLabel() {
  const month = cleanStr(els.monthSelect?.value) || "";
  const y = cleanStr(els.yearInput?.value) || "";
  const year = y || String(new Date().getFullYear());
  if (!month) return year;
  return `${month} ${year}`;
}

function getSelectedEmployeeName(totals) {
  const v = cleanStr(els.employeeInput?.value);
  if (!v) return null;
  // only accept exact match against known names to avoid accidental filtering
  for (const name of totals.keys()) {
    if (cleanStr(name).toLowerCase() === v.toLowerCase()) return name;
  }
  return null;
}

function getSelectedEmployeeNameFromUnion(totalsA, totalsB) {
  const v = cleanStr(els.employeeInput?.value);
  if (!v) return null;
  const names = new Set([...totalsA.keys(), ...totalsB.keys()]);
  for (const name of names) {
    if (cleanStr(name).toLowerCase() === v.toLowerCase()) return name;
  }
  return null;
}

function buildTitleText(state) {
  const base = cleanStr(els.titleInput?.value) || getMonthYearLabel();
  const employee = state.employeeName ? ` — ${state.employeeName}` : "";
  const selected = [...state.selectedStatuses];
  const allCount = state.statuses.length;
  let filt = "";
  if (selected.length === 0) {
    filt = " — (inga statusar)";
  } else if (selected.length !== allCount) {
    // Keep it readable; list a few statuses, then count.
    const shown = selected.slice(0, 3).join(", ");
    const more = selected.length > 3 ? ` (+${selected.length - 3})` : "";
    filt = ` — ${shown}${more}`;
  }
  return `${base}${employee}${filt}`;
}

function palette(i) {
  // High-contrast, colorblind-friendlier palette
  const colors = [
    "#22c55e", // green
    "#3b82f6", // blue
    "#f59e0b", // amber
    "#ef4444", // red
    "#a855f7", // purple
    "#06b6d4", // cyan
    "#f97316", // orange
    "#14b8a6", // teal
    "#eab308", // yellow
    "#ec4899", // pink
  ];
  return colors[i % colors.length];
}

function setChartHeightByLabels(labelCount) {
  const container = els.chartCanvas?.parentElement;
  if (!container) return;
  const h = Math.max(360, Math.min(1200, 140 + labelCount * 26));
  container.style.height = `${h}px`;
}

function setChartHeightByMode(mode, labelCount) {
  // In vertical mode, height should be stable; in horizontal mode, scale with number of names.
  const container = els.chartCanvas?.parentElement;
  if (!container) return;
  if (mode === "vertical") {
    // Vertical needs a lot more height when showing many names (desktop use-case).
    const h = Math.max(520, Math.min(4200, 320 + labelCount * 22));
    container.style.height = `${h}px`;
    return;
  }
  setChartHeightByLabels(labelCount);
}

function applyOrientation(mode, opts = {}) {
  const c = ensureChart(mode);
  const isVertical = mode === "vertical";
  const verticalLimit = String(opts.verticalLimit || "");

  // Improve readability in vertical mode (many labels).
  if (isVertical) {
    c.options.plugins.legend.position = "top";
    c.options.plugins.legend.labels.font = { size: 11 };

    const forceAllLabels = verticalLimit === "all";
    c.options.scales.x.ticks.autoSkip = !forceAllLabels;
    c.options.scales.x.ticks.maxRotation = 90;
    c.options.scales.x.ticks.minRotation = forceAllLabels ? 90 : 60;
    c.options.scales.x.ticks.font = { size: forceAllLabels ? 8 : 10 };
    c.options.scales.y.ticks.precision = 0;
  } else {
    c.options.plugins.legend.position = "right";
    c.options.plugins.legend.labels.font = { size: 12 };
    // Reset rotations (Chart.js ignores some of these in horizontal mode, but safe).
    c.options.scales.x.ticks.maxRotation = 0;
    c.options.scales.x.ticks.minRotation = 0;
    c.options.scales.x.ticks.autoSkip = true;
    c.options.scales.x.ticks.font = { size: 12 };
  }
}

function limitForVerticalIfNeeded(mode, sortedPeople, hasEmployeeFilter, verticalLimit) {
  if (mode !== "vertical") return sortedPeople;
  if (hasEmployeeFilter) return sortedPeople;
  if (verticalLimit === "all") return sortedPeople;
  const maxN = Number(verticalLimit || 20);
  const MAX = Number.isFinite(maxN) ? maxN : 20;
  if (sortedPeople.length <= MAX) return sortedPeople;
  els.statusText.textContent = `${els.statusText.textContent} • Stående: visar Top ${MAX}`;
  return sortedPeople.slice(0, MAX);
}

function renderColorLegend(datasets) {
  if (!els.colorLegend) return;
  if (!datasets || datasets.length === 0) {
    els.colorLegend.innerHTML = "";
    return;
  }
  const wrap = document.createElement("div");
  wrap.className = "flex flex-wrap gap-2";
  for (const ds of datasets) {
    const pill = document.createElement("div");
    pill.className = "inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700";
    const sw = document.createElement("span");
    sw.className = "inline-block w-3.5 h-3.5 rounded-sm border border-slate-900";
    sw.style.background = ds.backgroundColor;
    const tx = document.createElement("span");
    tx.className = "text-xs text-slate-100";
    tx.textContent = ds.label;
    pill.appendChild(sw);
    pill.appendChild(tx);
    wrap.appendChild(pill);
  }
  els.colorLegend.innerHTML = "";
  els.colorLegend.appendChild(wrap);
}

function computePeopleSorted(totals, selectedStatuses) {
  const rows = [];
  for (const [name, byStatus] of totals.entries()) {
    let sum = 0;
    for (const st of selectedStatuses) sum += byStatus.get(st) || 0;
    rows.push({ name, sum: round2(sum) });
  }
  rows.sort((a, b) => (b.sum - a.sum) || a.name.localeCompare(b.name, "sv"));
  return rows;
}

function ensureNormalTableHeader() {
  if (!els.tableHeadRow) return;
  els.tableHeadRow.innerHTML = "";
  const th1 = document.createElement("th");
  th1.className = "text-left px-3 py-2";
  th1.textContent = "Namn";
  const th2 = document.createElement("th");
  th2.className = "text-right px-3 py-2";
  th2.textContent = "Summa (h)";
  els.tableHeadRow.appendChild(th1);
  els.tableHeadRow.appendChild(th2);
}

function renderTable(sortedPeople) {
  els.tableBody.innerHTML = "";
  for (const r of sortedPeople) {
    const tr = document.createElement("tr");
    tr.className = "border-b border-slate-800";
    const tdName = document.createElement("td");
    tdName.className = "px-3 py-2 whitespace-nowrap";
    tdName.textContent = r.name;
    const tdSum = document.createElement("td");
    tdSum.className = "px-3 py-2 text-right tabular-nums";
    tdSum.textContent = r.sum.toFixed(2);
    tr.appendChild(tdName);
    tr.appendChild(tdSum);
    els.tableBody.appendChild(tr);
  }
}

function renderChart(totals, statuses, selectedStatuses, sortedPeople, chartOpts = {}) {
  const scale = typeof chartOpts.scale === "number" && chartOpts.scale > 0 ? chartOpts.scale : 1;
  const titleSuffix = chartOpts.titleSuffix || "";
  const previewNote = chartOpts.previewNote;

  if (window.__chart_kind === "compare") {
    resetChartFully();
    window.__chart_kind = "normal";
  }

  const mode = window.__tidrapport_state?.orientation || "horizontal";
  // If the user changed orientation, recreate chart BEFORE we set data.
  resetChartIfOrientationChanged(mode);
  const c = ensureChart(mode);
  applyOrientation(mode);

  const limitedPeople = limitForVerticalIfNeeded(
    mode,
    sortedPeople,
    !!window.__tidrapport_state?.employeeName,
    window.__tidrapport_state?.verticalNames || "20"
  );
  const labels = limitedPeople.map((p) => p.name);
  setChartHeightByMode(mode, labels.length);

  const colorByStatus = buildStatusColorMap(statuses);
  const datasets = [];
  for (const st of statuses) {
    if (!selectedStatuses.has(st)) continue;
    datasets.push({
      label: st,
      data: labels.map((name) => round2((totals.get(name)?.get(st) || 0) * scale)),
      backgroundColor: colorByStatus.get(st) || "#94a3b8",
      borderWidth: 0,
    });
  }

  c.data.labels = labels;
  c.data.datasets = datasets;
  if (window.__tidrapport_state) {
    let titleText = buildTitleText(window.__tidrapport_state);
    if (titleSuffix) titleText = `${titleText} — ${titleSuffix}`;
    c.options.plugins.title.text = titleText;
    if (els.titlePreview) els.titlePreview.textContent = previewNote != null ? previewNote : titleText;
  }
  renderColorLegend(datasets);
  applyOrientation(mode, { verticalLimit: window.__tidrapport_state?.verticalNames || "20" });
  c.update();
  window.__chart_kind = "normal";
}

function getForecastParams() {
  const y = parseInt(cleanStr(els.yearInput?.value), 10) || new Date().getFullYear();
  const mIdx = SWEDISH_MONTHS.indexOf(cleanStr(els.monthSelect?.value));
  const dim = mIdx >= 0 ? new Date(y, mIdx + 1, 0).getDate() : 30;
  let through = parseInt(cleanStr(els.forecastThroughDay?.value), 10);
  if (!Number.isFinite(through) || through < 1) {
    const now = new Date();
    const sameMonth = now.getFullYear() === y && now.getMonth() === mIdx;
    through = sameMonth ? now.getDate() : Math.min(15, dim);
  }
  through = Math.max(1, Math.min(through, dim));
  const factor = dim / through;
  const note = `Prognos: jämn fördelning — ${dim} dagar i månaden, data till dag ${through} (× ${dim}/${through} = ${round2(factor)}).`;
  return { factor, through, dim, note, y, mIdx };
}

function updateForecastMonthInfo() {
  if (!els.forecastMonthInfo) return;
  const y = parseInt(cleanStr(els.yearInput?.value), 10) || new Date().getFullYear();
  const mIdx = SWEDISH_MONTHS.indexOf(cleanStr(els.monthSelect?.value));
  if (mIdx < 0) {
    els.forecastMonthInfo.textContent = "Välj månad och år ovan.";
    return;
  }
  const dim = new Date(y, mIdx + 1, 0).getDate();
  els.forecastMonthInfo.textContent = `${SWEDISH_MONTHS[mIdx]} ${y}: ${dim} kalenderdagar.`;
  if (els.forecastThroughDay) els.forecastThroughDay.max = String(dim);
}

function populateCompareSlotSelects(store) {
  if (!els.compareSlotA || !els.compareSlotB) return;
  const keys = Object.keys(store.slots).sort((a, b) => b.localeCompare(a));
  const prevA = cleanStr(els.compareSlotA.value);
  const prevB = cleanStr(els.compareSlotB.value);
  for (const sel of [els.compareSlotA, els.compareSlotB]) {
    sel.innerHTML = "";
    const ph = document.createElement("option");
    ph.value = "";
    ph.textContent = "— Välj —";
    sel.appendChild(ph);
    for (const k of keys) {
      const o = document.createElement("option");
      o.value = k;
      o.textContent = slotLabelFromKey(k);
      sel.appendChild(o);
    }
  }
  if (prevA && keys.includes(prevA)) els.compareSlotA.value = prevA;
  if (prevB && keys.includes(prevB)) els.compareSlotB.value = prevB;
}

function ensureCompareDefaults(store) {
  const keys = Object.keys(store.slots).sort((a, b) => b.localeCompare(a));
  if (keys.length < 2) return;
  if (!cleanStr(els.compareSlotA?.value)) els.compareSlotA.value = keys[0];
  if (!cleanStr(els.compareSlotB?.value)) els.compareSlotB.value = keys[1];
}

function buildCompareStatusFilters(statuses, selected) {
  els.statusFilters.innerHTML = "";
  const colorByStatus = buildStatusColorMap(statuses);
  for (const st of statuses) {
    const id = `cmp_${btoa(unescape(encodeURIComponent(st))).replace(/=/g, "")}`;
    const label = document.createElement("label");
    label.className =
      "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/70 hover:bg-slate-700/70 cursor-pointer select-none border border-slate-700";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.checked = selected.has(st);
    cb.className = "accent-emerald-500";
    cb.addEventListener("change", () => {
      if (!window.__tidrapport_compare) return;
      if (cb.checked) window.__tidrapport_compare.selectedStatuses.add(st);
      else window.__tidrapport_compare.selectedStatuses.delete(st);
      renderCompareAll();
    });
    const sw = document.createElement("span");
    sw.className = "inline-block w-3 h-3 rounded-sm border border-slate-900";
    sw.style.background = colorByStatus.get(st) || "#94a3b8";
    const span = document.createElement("span");
    span.textContent = st;
    span.className = "text-xs text-slate-100";
    label.appendChild(cb);
    label.appendChild(sw);
    label.appendChild(span);
    els.statusFilters.appendChild(label);
  }
}

function renderCompareAll() {
  if (getAnalysisMode() !== "compare") return;
  updateAnalysisPanels();
  const layout = cleanStr(els.layoutSelect?.value) || "side";
  applyLayoutMode(layout);

  const store = readStore();
  populateCompareSlotSelects(store);
  ensureCompareDefaults(store);

  const keyA = cleanStr(els.compareSlotA?.value);
  const keyB = cleanStr(els.compareSlotB?.value);
  if (!keyA || !keyB) {
    els.statusText.textContent = "Jämförelse: välj två sparade månader (spara minst två rapporter först).";
    return;
  }
  if (keyA === keyB) {
    els.statusText.textContent = "Välj två olika månader.";
    return;
  }

  const textA = store.slots[keyA]?.text;
  const textB = store.slots[keyB]?.text;
  if (!cleanStr(textA) || !cleanStr(textB)) {
    els.statusText.textContent = "Saknar inklistrad data i en av de valda månaderna.";
    return;
  }

  const aggA = aggregate(textA);
  const aggB = aggregate(textB);
  if (aggA.errors.length || aggB.errors.length) {
    els.statusText.textContent = [...aggA.errors, ...aggB.errors].join(" ");
    return;
  }

  const statusSet = new Set([...aggA.statuses, ...aggB.statuses]);
  const statusesMerged = [
    ...ORSAK_ORDER.filter((s) => statusSet.has(s)),
    ...[...statusSet].filter((s) => !ORSAK_ORDER.includes(s)).sort((a, b) => a.localeCompare(b, "sv")),
  ];

  const pair = `${keyA}|${keyB}`;
  const isNewPair = !window.__tidrapport_compare || window.__tidrapport_compare.keyPair !== pair;
  if (isNewPair) {
    window.__tidrapport_compare = {
      keyPair: pair,
      selectedStatuses: new Set(statusesMerged),
      statuses: statusesMerged,
    };
    buildCompareStatusFilters(statusesMerged, window.__tidrapport_compare.selectedStatuses);
  }

  const sel = window.__tidrapport_compare.selectedStatuses;
  if (sel.size === 0) {
    els.statusText.textContent = "Bocka minst en status för jämförelsen.";
    resetChartFully();
    els.tableBody.innerHTML = "";
    return;
  }

  const emp = getSelectedEmployeeNameFromUnion(aggA.totals, aggB.totals);
  let totalsA = aggA.totals;
  let totalsB = aggB.totals;
  if (emp) {
    totalsA = new Map([[emp, totalsA.get(emp) || new Map()]]);
    totalsB = new Map([[emp, totalsB.get(emp) || new Map()]]);
  }

  const names = new Set([...totalsA.keys(), ...totalsB.keys()]);
  const rows = [];
  for (const name of names) {
    let sumA = 0;
    let sumB = 0;
    for (const st of sel) {
      sumA += totalsA.get(name)?.get(st) || 0;
      sumB += totalsB.get(name)?.get(st) || 0;
    }
    rows.push({ name, sumA: round2(sumA), sumB: round2(sumB), diff: round2(sumB - sumA) });
  }
  rows.sort((a, b) => Math.max(b.sumA, b.sumB) - Math.max(a.sumA, a.sumB) || a.name.localeCompare(b.name, "sv"));

  const la = slotLabelFromKey(keyA);
  const lb = slotLabelFromKey(keyB);

  if (!els.tableHeadRow) return;
  els.tableHeadRow.innerHTML = "";
  const h1 = document.createElement("th");
  h1.className = "text-left px-3 py-2";
  h1.textContent = "Namn";
  const h2 = document.createElement("th");
  h2.className = "text-right px-3 py-2";
  h2.textContent = la;
  const h3 = document.createElement("th");
  h3.className = "text-right px-3 py-2";
  h3.textContent = lb;
  const h4 = document.createElement("th");
  h4.className = "text-right px-3 py-2";
  h4.textContent = "Diff (B−A)";
  els.tableHeadRow.appendChild(h1);
  els.tableHeadRow.appendChild(h2);
  els.tableHeadRow.appendChild(h3);
  els.tableHeadRow.appendChild(h4);

  els.tableBody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = "border-b border-slate-800";
    const tdN = document.createElement("td");
    tdN.className = "px-3 py-2 whitespace-nowrap";
    tdN.textContent = r.name;
    const tdA = document.createElement("td");
    tdA.className = "px-3 py-2 text-right tabular-nums";
    tdA.textContent = r.sumA.toFixed(2);
    const tdB = document.createElement("td");
    tdB.className = "px-3 py-2 text-right tabular-nums";
    tdB.textContent = r.sumB.toFixed(2);
    const tdD = document.createElement("td");
    tdD.className = "px-3 py-2 text-right tabular-nums";
    tdD.textContent = (r.diff >= 0 ? "+" : "") + r.diff.toFixed(2);
    tr.appendChild(tdN);
    tr.appendChild(tdA);
    tr.appendChild(tdB);
    tr.appendChild(tdD);
    els.tableBody.appendChild(tr);
  }

  resetChartFully();
  window.__chart_kind = "compare";
  const ctx = els.chartCanvas.getContext("2d");
  const labels = rows.map((r) => r.name);
  setChartHeightByLabels(labels.length);
  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: la, data: rows.map((r) => r.sumA), backgroundColor: "#22c55e", borderWidth: 0 },
        { label: lb, data: rows.map((r) => r.sumB), backgroundColor: "#3b82f6", borderWidth: 0 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      events: [],
      animation: false,
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#e2e8f0", boxWidth: 14, boxHeight: 14, padding: 14, font: { size: 12 } },
        },
        tooltip: { enabled: false },
        title: {
          display: true,
          text: "Jämförelse: timmar per person (valda statusar)",
          color: "#e2e8f0",
          font: { size: 14 },
        },
      },
      scales: {
        x: {
          stacked: false,
          beginAtZero: true,
          ticks: { color: "#cbd5e1", font: { size: 12 } },
          grid: { color: "rgba(148,163,184,0.15)" },
        },
        y: {
          stacked: false,
          ticks: { color: "#cbd5e1", font: { size: 12 } },
          grid: { color: "rgba(148,163,184,0.10)" },
        },
      },
    },
  });
  renderColorLegend(chart.data.datasets);
  if (els.titlePreview) els.titlePreview.textContent = `${la} mot ${lb} — summerat per vald status`;

  const statsText = `Jämförelse: ${la} vs ${lb} • Namn: ${rows.length} • Statusar: ${sel.size}${emp ? ` • ${emp}` : ""}`;
  els.statusText.textContent = statsText;
}

function renderForecastAll(state) {
  updateAnalysisPanels();
  const layout = state?.layout || cleanStr(els.layoutSelect?.value) || "side";
  applyLayoutMode(layout);

  if (!state?.totals || state.totals.size === 0) {
    ensureNormalTableHeader();
    els.tableBody.innerHTML = "";
    els.statusText.textContent = "Prognos: ingen data — klistra in och skapa diagram först.";
    resetChartFully();
    return;
  }

  const { factor, through, dim, note } = getForecastParams();
  const { totals, statuses, selectedStatuses } = state;
  const totalsView = state.employeeName
    ? new Map([[state.employeeName, totals.get(state.employeeName) || new Map()]])
    : totals;
  const sortedPeople = computePeopleSorted(totalsView, selectedStatuses);

  if (!els.tableHeadRow) return;
  els.tableHeadRow.innerHTML = "";
  const th1 = document.createElement("th");
  th1.className = "text-left px-3 py-2";
  th1.textContent = "Namn";
  const th2 = document.createElement("th");
  th2.className = "text-right px-3 py-2";
  th2.textContent = "Ack. (h)";
  const th3 = document.createElement("th");
  th3.className = "text-right px-3 py-2";
  th3.textContent = "Prognos (h)";
  els.tableHeadRow.appendChild(th1);
  els.tableHeadRow.appendChild(th2);
  els.tableHeadRow.appendChild(th3);

  els.tableBody.innerHTML = "";
  for (const r of sortedPeople) {
    const tr = document.createElement("tr");
    tr.className = "border-b border-slate-800";
    const tdN = document.createElement("td");
    tdN.className = "px-3 py-2 whitespace-nowrap";
    tdN.textContent = r.name;
    const tdA = document.createElement("td");
    tdA.className = "px-3 py-2 text-right tabular-nums";
    tdA.textContent = r.sum.toFixed(2);
    const tdP = document.createElement("td");
    tdP.className = "px-3 py-2 text-right tabular-nums";
    tdP.textContent = round2(r.sum * factor).toFixed(2);
    tr.appendChild(tdN);
    tr.appendChild(tdA);
    tr.appendChild(tdP);
    els.tableBody.appendChild(tr);
  }

  const titleSuffix = `Prognos linjär till dag ${through}/${dim} (×${round2(factor)})`;
  renderChart(totalsView, statuses, selectedStatuses, sortedPeople, {
    scale: factor,
    titleSuffix,
    previewNote: note,
  });

  const totalNames = totals.size;
  const stats = state.stats;
  const statsText = stats
    ? ` • Rader: ${stats.usedRows}/${stats.rawRows} (skip: tid=${stats.skippedNoTime}, namn=${stats.skippedNoName})`
    : "";
  const emp = state.employeeName ? ` • Anställd: ${state.employeeName}` : "";
  els.statusText.textContent = `Prognos • Namn: ${totalNames} • Visar: ${selectedStatuses.size}${emp}${statsText}`;
}

function renderAll(state) {
  const mode = getAnalysisMode();
  if (mode === "compare") {
    renderCompareAll();
    return;
  }
  if (mode === "forecast") {
    renderForecastAll(state);
    return;
  }

  ensureNormalTableHeader();
  const { totals, statuses, selectedStatuses } = state;
  const totalsView = state.employeeName
    ? new Map([[state.employeeName, totals.get(state.employeeName) || new Map()]])
    : totals;
  const sortedPeople = computePeopleSorted(totalsView, selectedStatuses);
  renderTable(sortedPeople);
  renderChart(totalsView, statuses, selectedStatuses, sortedPeople);

  const totalNames = totals.size;
  const totalStatuses = statuses.length;
  const stats = state.stats;
  const statsText = stats
    ? ` • Rader: ${stats.usedRows}/${stats.rawRows} (skip: tid=${stats.skippedNoTime}, namn=${stats.skippedNoName})`
    : "";
  const emp = state.employeeName ? ` • Anställd: ${state.employeeName}` : "";
  const chartOrient = state.orientation || "horizontal";
  const limit = state.verticalNames || "20";
  const shownNames = chartOrient === "vertical" && !state.employeeName
    ? (limit === "all" ? totalsView.size : Math.min(totalsView.size, Number(limit || 20)))
    : totalsView.size;
  const shownText = chartOrient === "vertical" && !state.employeeName ? ` • Visar namn: ${shownNames}/${totalsView.size}` : "";
  els.statusText.textContent = `Namn: ${totalNames} • Statusar: ${totalStatuses} • Visar: ${selectedStatuses.size}${emp}${shownText}${statsText}`;
}

function slotKeyFromMonthYear(monthLabel, yearStr) {
  const m = cleanStr(monthLabel);
  const y = cleanStr(yearStr) || String(new Date().getFullYear());
  const idx = SWEDISH_MONTHS.indexOf(m);
  if (idx < 0) return null;
  const mm = String(idx + 1).padStart(2, "0");
  return `${y}-${mm}`;
}

function slotLabelFromKey(key) {
  const parts = key.split("-");
  if (parts.length < 2) return key;
  const y = parts[0];
  const mm = parts[1];
  const n = parseInt(mm, 10);
  if (!Number.isFinite(n) || n < 1 || n > 12) return key;
  return `${SWEDISH_MONTHS[n - 1]} ${y}`;
}

function readStore() {
  try {
    const raw2 = localStorage.getItem(STORAGE_KEY_V2);
    if (raw2) {
      const s = JSON.parse(raw2);
      if (s && s.version === 2 && s.slots && typeof s.slots === "object") {
        return { version: 2, slots: s.slots, lastKey: s.lastKey || null };
      }
    }
    const raw1 = localStorage.getItem(STORAGE_KEY_V1);
    if (raw1) {
      const data = JSON.parse(raw1);
      const key =
        slotKeyFromMonthYear(data.month, data.year) ||
        `importerad_${new Date().toISOString().slice(0, 10)}`;
      const store = { version: 2, slots: { [key]: { ...data, savedAt: Date.now() } }, lastKey: key };
      localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(store));
      localStorage.removeItem(STORAGE_KEY_V1);
      return store;
    }
  } catch (e) {
    console.warn("readStore", e);
  }
  return { version: 2, slots: {}, lastKey: null };
}

function writeStore(store) {
  localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(store));
}

function refreshSavedSlotSelect(store, preferKey) {
  if (!els.savedSlotSelect) return;
  const keys = Object.keys(store.slots).sort((a, b) => b.localeCompare(a));
  els.savedSlotSelect.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = keys.length ? "— Välj sparad månad —" : "Inget sparat ännu";
  els.savedSlotSelect.appendChild(empty);
  for (const k of keys) {
    const o = document.createElement("option");
    o.value = k;
    const pl = store.slots[k];
    const short = pl?.savedAt ? ` · ${new Date(pl.savedAt).toLocaleDateString("sv-SE")}` : "";
    o.textContent = `${slotLabelFromKey(k)}${short}`;
    els.savedSlotSelect.appendChild(o);
  }
  const pick = preferKey && keys.includes(preferKey) ? preferKey : store.lastKey && keys.includes(store.lastKey) ? store.lastKey : "";
  if (pick) els.savedSlotSelect.value = pick;
  populateCompareSlotSelects(store);
  updateForecastMonthInfo();
}

function buildPayloadFromUi(state) {
  const selected = state?.selectedStatuses instanceof Set ? [...state.selectedStatuses] : [];
  return {
    text: els.pasteInput.value,
    selected,
    month: cleanStr(els.monthSelect?.value),
    year: cleanStr(els.yearInput?.value),
    title: cleanStr(els.titleInput?.value),
    employee: cleanStr(els.employeeInput?.value),
    orientation: cleanStr(els.orientationSelect?.value) || "horizontal",
    verticalNames: cleanStr(els.verticalNamesSelect?.value) || "20",
    layout: cleanStr(els.layoutSelect?.value) || "side",
    savedAt: Date.now(),
  };
}

function resolveSlotKey(store, payload) {
  let key = slotKeyFromMonthYear(payload.month, payload.year);
  if (!key) key = store.lastKey;
  if (!key) {
    const d = new Date();
    key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }
  return key;
}

function saveLocal(state) {
  const store = readStore();
  const payload = buildPayloadFromUi(state);
  const key = resolveSlotKey(store, payload);
  store.slots[key] = payload;
  store.lastKey = key;
  writeStore(store);
  refreshSavedSlotSelect(store, key);
}

function loadLocal() {
  try {
    const store = readStore();
    if (!store.lastKey || !store.slots[store.lastKey]) return null;
    return store.slots[store.lastKey];
  } catch {
    return null;
  }
}

function applyPayloadToUi(data) {
  els.pasteInput.value = data.text || "";
  if (els.monthSelect && data.month) els.monthSelect.value = data.month;
  if (els.yearInput && data.year) els.yearInput.value = data.year;
  if (els.titleInput && data.title != null) els.titleInput.value = data.title;
  if (els.employeeInput && data.employee != null) els.employeeInput.value = data.employee;
  if (els.orientationSelect && data.orientation) els.orientationSelect.value = data.orientation;
  if (els.verticalNamesSelect && data.verticalNames) els.verticalNamesSelect.value = data.verticalNames;
  if (els.layoutSelect && data.layout) els.layoutSelect.value = data.layout;
}

function loadFromStoreKey(key) {
  const store = readStore();
  const data = store.slots[key];
  if (!data) return false;
  applyPayloadToUi(data);
  store.lastKey = key;
  writeStore(store);
  refreshSavedSlotSelect(store, key);
  regenerateFromText(els.pasteInput.value, data.selected || []);
  return true;
}

function regenerateFromText(text, selectedOverride) {
  // Jämförelseläge ritar bara från sparade månader — ignorera inklistring om vi inte byter vy.
  if (cleanStr(text) && getAnalysisMode() === "compare") {
    if (els.analysisModeSelect) els.analysisModeSelect.value = "normal";
    window.__tidrapport_compare = null;
    updateAnalysisPanels();
  }

  const { totals, statuses, errors, stats } = aggregate(text);
  if (errors.length) {
    els.statusText.textContent = errors.join(" ");
    window.__tidrapport_state = { totals: new Map(), statuses: [], selectedStatuses: new Set(), employeeName: null, stats: null };
    safeRenderAll(window.__tidrapport_state);
    return;
  }

  const selectedStatuses = new Set();
  const preferred = selectedOverride?.length ? selectedOverride : statuses;
  for (const st of preferred) if (statuses.includes(st)) selectedStatuses.add(st);

  const employeeName = getSelectedEmployeeName(totals);

  const orientation = cleanStr(els.orientationSelect?.value) || "horizontal";
  const verticalNames = cleanStr(els.verticalNamesSelect?.value) || "20";
  const layout = cleanStr(els.layoutSelect?.value) || "side";
  window.__tidrapport_state = { totals, statuses, selectedStatuses, employeeName, stats, orientation, verticalNames, layout };
  // update datalist with names
  if (els.employeeList) {
    els.employeeList.innerHTML = "";
    [...totals.keys()].sort((a, b) => a.localeCompare(b, "sv")).forEach((n) => {
      const opt = document.createElement("option");
      opt.value = n;
      els.employeeList.appendChild(opt);
    });
  }
  buildStatusFilters(statuses, selectedStatuses);
  safeRenderAll(window.__tidrapport_state);
}

els.btnGenerate.addEventListener("click", () => {
  const text = els.pasteInput.value || "";
  regenerateFromText(text, null);
  saveLocal(window.__tidrapport_state);
  const key = slotKeyFromMonthYear(cleanStr(els.monthSelect?.value), cleanStr(els.yearInput?.value));
  if (key && cleanStr(text) && window.__tidrapport_state?.totals?.size) {
    setSlotFeedback(
      `Automatiskt sparat lokalt som «${slotLabelFromKey(key)}». (Samma innehåll som om du tryckte «Spara vald månad».)`
    );
  } else if (!cleanStr(text)) {
    setSlotFeedback("");
  }
});

function clearPasteAndChart() {
  els.pasteInput.value = "";
  setSlotFeedback("");
  regenerateFromText("", null);
}

els.btnClear.addEventListener("click", clearPasteAndChart);
els.btnClearNearGenerate?.addEventListener("click", clearPasteAndChart);

els.btnLoad.addEventListener("click", () => {
  const store = readStore();
  if (!store.lastKey || !store.slots[store.lastKey]) {
    els.statusText.textContent = "Inget sparat hittades.";
    return;
  }
  loadFromStoreKey(store.lastKey);
});

els.btnLoadSlot?.addEventListener("click", () => {
  const key = cleanStr(els.savedSlotSelect?.value);
  if (!key) {
    const m = "Välj en sparad rapport i listan.";
    els.statusText.textContent = m;
    setSlotFeedback(m);
    return;
  }
  if (!loadFromStoreKey(key)) {
    const m = "Kunde inte ladda (saknas).";
    els.statusText.textContent = m;
    setSlotFeedback(m);
  } else {
    const ok = `Laddade «${slotLabelFromKey(key)}» från sparade rapporter.`;
    els.statusText.textContent = ok;
    setSlotFeedback(ok);
  }
});

els.btnSaveSlot?.addEventListener("click", () => {
  const key = slotKeyFromMonthYear(cleanStr(els.monthSelect?.value), cleanStr(els.yearInput?.value));
  if (!key) {
    const m = "Välj månad och år ovan innan du sparar — de styr nyckeln (t.ex. Februari 2026).";
    els.statusText.textContent = m;
    setSlotFeedback(m);
    return;
  }
  if (!cleanStr(els.pasteInput?.value)) {
    const m = "Inklistringsrutan är tom — inget att spara. Klistra in data eller ladda en rapport först.";
    els.statusText.textContent = m;
    setSlotFeedback(m);
    return;
  }
  const stub = window.__tidrapport_state || { selectedStatuses: new Set() };
  saveLocal(stub);
  const ok = `Sparat under «${slotLabelFromKey(key)}» i denna webbläsare. Du ser den i listan «Sparade rapporter».`;
  els.statusText.textContent = ok;
  setSlotFeedback(ok);
});

els.btnDeleteSlot?.addEventListener("click", () => {
  const key = cleanStr(els.savedSlotSelect?.value);
  if (!key) {
    const m = "Välj en sparad rapport att ta bort.";
    els.statusText.textContent = m;
    setSlotFeedback(m);
    return;
  }
  const store = readStore();
  if (!store.slots[key]) {
    const m = "Finns inte i sparade listan.";
    els.statusText.textContent = m;
    setSlotFeedback(m);
    return;
  }
  delete store.slots[key];
  if (store.lastKey === key) {
    const remain = Object.keys(store.slots).sort((a, b) => b.localeCompare(a));
    store.lastKey = remain[0] || null;
  }
  writeStore(store);
  refreshSavedSlotSelect(store, store.lastKey);
  const ok = `Tog bort «${slotLabelFromKey(key)}» från sparade rapporter.`;
  els.statusText.textContent = ok;
  setSlotFeedback(ok);
});

els.btnAll.addEventListener("click", () => {
  if (getAnalysisMode() === "compare" && window.__tidrapport_compare) {
    window.__tidrapport_compare.selectedStatuses = new Set(window.__tidrapport_compare.statuses);
    buildCompareStatusFilters(window.__tidrapport_compare.statuses, window.__tidrapport_compare.selectedStatuses);
    renderCompareAll();
    return;
  }
  const st = window.__tidrapport_state;
  st.selectedStatuses = new Set(st.statuses);
  buildStatusFilters(st.statuses, st.selectedStatuses);
  safeRenderAll(st);
  saveLocal(st);
});

els.btnNone.addEventListener("click", () => {
  if (getAnalysisMode() === "compare" && window.__tidrapport_compare) {
    window.__tidrapport_compare.selectedStatuses = new Set();
    buildCompareStatusFilters(window.__tidrapport_compare.statuses, window.__tidrapport_compare.selectedStatuses);
    renderCompareAll();
    return;
  }
  const st = window.__tidrapport_state;
  st.selectedStatuses = new Set();
  buildStatusFilters(st.statuses, st.selectedStatuses);
  safeRenderAll(st);
  saveLocal(st);
});

els.btnClearEmployee?.addEventListener("click", () => {
  if (els.employeeInput) els.employeeInput.value = "";
  if (window.__tidrapport_state) {
    window.__tidrapport_state.employeeName = null;
    safeRenderAll(window.__tidrapport_state);
    saveLocal(window.__tidrapport_state);
  }
});

els.employeeInput?.addEventListener("input", () => {
  if (!window.__tidrapport_state) return;
  const nm = getSelectedEmployeeName(window.__tidrapport_state.totals);
  window.__tidrapport_state.employeeName = nm;
  safeRenderAll(window.__tidrapport_state);
  saveLocal(window.__tidrapport_state);
});

for (const el of [els.monthSelect, els.yearInput, els.titleInput]) {
  el?.addEventListener("input", () => {
    updateForecastMonthInfo();
    if (!window.__tidrapport_state) return;
    safeRenderAll(window.__tidrapport_state);
    saveLocal(window.__tidrapport_state);
  });
}

els.analysisModeSelect?.addEventListener("change", () => {
  updateAnalysisPanels();
  window.__tidrapport_compare = null;
  const m = getAnalysisMode();
  if (m === "compare") {
    renderCompareAll();
    return;
  }
  resetChartFully();
  window.__chart_kind = "normal";
  if (!window.__tidrapport_state) return;
  if (m === "forecast") {
    safeRenderAll(window.__tidrapport_state);
    return;
  }
  buildStatusFilters(window.__tidrapport_state.statuses, window.__tidrapport_state.selectedStatuses);
  safeRenderAll(window.__tidrapport_state);
});

els.compareSlotA?.addEventListener("change", () => {
  window.__tidrapport_compare = null;
  if (getAnalysisMode() === "compare") renderCompareAll();
});

els.compareSlotB?.addEventListener("change", () => {
  window.__tidrapport_compare = null;
  if (getAnalysisMode() === "compare") renderCompareAll();
});

els.btnRefreshCompare?.addEventListener("click", () => {
  window.__tidrapport_compare = null;
  if (getAnalysisMode() === "compare") renderCompareAll();
});

els.forecastThroughDay?.addEventListener("input", () => {
  if (getAnalysisMode() === "forecast" && window.__tidrapport_state) safeRenderAll(window.__tidrapport_state);
});

els.orientationSelect?.addEventListener("change", () => {
  if (!window.__tidrapport_state) return;
  window.__tidrapport_state.orientation = cleanStr(els.orientationSelect.value) || "horizontal";
  safeRenderAll(window.__tidrapport_state);
  saveLocal(window.__tidrapport_state);
});

els.verticalNamesSelect?.addEventListener("change", () => {
  if (!window.__tidrapport_state) return;
  window.__tidrapport_state.verticalNames = cleanStr(els.verticalNamesSelect.value) || "20";
  safeRenderAll(window.__tidrapport_state);
  saveLocal(window.__tidrapport_state);
});

function applyLayoutMode(mode) {
  if (!els.layoutGrid) return;
  const isStack = mode === "stack";
  els.layoutGrid.classList.toggle("lg:grid-cols-2", !isStack);
  els.layoutGrid.classList.toggle("lg:grid-cols-1", isStack);
}

els.layoutSelect?.addEventListener("change", () => {
  if (!window.__tidrapport_state) return;
  window.__tidrapport_state.layout = cleanStr(els.layoutSelect.value) || "side";
  applyLayoutMode(window.__tidrapport_state.layout);
  safeRenderAll(window.__tidrapport_state);
  saveLocal(window.__tidrapport_state);
});

els.btnAddToMerge?.addEventListener("click", () => {
  const text = cleanStr(els.pasteInput?.value);
  if (!text) {
    els.statusText.textContent = "Klistra in data i rutan först.";
    return;
  }
  const parsed = parseTable(text);
  const ve = validateHeadersForAggregate(parsed.headers);
  if (ve.length) {
    els.statusText.textContent = ve.join(" ");
    return;
  }
  if (!parsed.rows.length) {
    els.statusText.textContent = "Inga datarader (bara rubrik?).";
    return;
  }
  const month = cleanStr(els.monthSelect?.value);
  const year = cleanStr(els.yearInput?.value);
  const label = [month, year].filter(Boolean).join(" ").trim() || `Del ${mergeQueue.length + 1}`;
  mergeQueue.push({ label, text });
  renderMergeQueueList();
  els.statusText.textContent = `Tillagt «${label}» — ${mergeQueue.length} delar i kön.`;
});

els.btnAddSavedToMerge?.addEventListener("click", () => {
  const key = cleanStr(els.savedSlotSelect?.value);
  if (!key) {
    els.statusText.textContent = "Välj en sparad månad i listan «Sparade rapporter» först.";
    return;
  }
  const store = readStore();
  const payload = store.slots[key];
  const text = cleanStr(payload?.text);
  if (!text) {
    els.statusText.textContent = "Den sparade månaden saknar data.";
    return;
  }
  const parsed = parseTable(text);
  const ve = validateHeadersForAggregate(parsed.headers);
  if (ve.length) {
    els.statusText.textContent = ve.join(" ");
    return;
  }
  if (!parsed.rows.length) {
    els.statusText.textContent = "Sparad månad har inga datarader.";
    return;
  }
  const label = slotLabelFromKey(key);
  mergeQueue.push({ label, text });
  renderMergeQueueList();
  els.statusText.textContent = `Tillagd sparad «${label}» — ${mergeQueue.length} delar i kön.`;
});

els.btnMergePickFiles?.addEventListener("click", () => {
  els.mergeFileInput?.click();
});

els.mergeFileInput?.addEventListener("change", async (e) => {
  const files = e.target?.files ? [...e.target.files] : [];
  e.target.value = "";
  if (!files.length) return;
  let added = 0;
  for (const f of files) {
    try {
      const text = await f.text();
      const label = f.name.replace(/\.[^/.]+$/, "") || f.name || "Fil";
      const parsed = parseTable(text);
      const ve = validateHeadersForAggregate(parsed.headers);
      if (ve.length) {
        els.statusText.textContent = `${f.name}: ${ve.join(" ")}`;
        continue;
      }
      if (!parsed.rows.length) {
        els.statusText.textContent = `${f.name}: inga datarader.`;
        continue;
      }
      mergeQueue.push({ label, text });
      added += 1;
    } catch {
      els.statusText.textContent = `Kunde inte läsa ${f.name}.`;
    }
  }
  renderMergeQueueList();
  if (added > 0) els.statusText.textContent = `Tillagde ${added} fil(er). Kö: ${mergeQueue.length} delar.`;
});

els.btnClearMergeQueue?.addEventListener("click", () => {
  mergeQueue.length = 0;
  renderMergeQueueList();
  els.statusText.textContent = "Sammanslagningskön är tömd.";
});

els.btnApplyMerge?.addEventListener("click", () => {
  if (mergeQueue.length < 2) {
    els.statusText.textContent = "Lägg till minst två delar (t.ex. två månader eller två filer) för samlad vy.";
    return;
  }
  const parsedList = mergeQueue.map((q) => parseTable(q.text));
  const { headers, rows, errors } = mergeParsedTables(parsedList);
  if (errors.length) {
    els.statusText.textContent = errors.join(" ");
    return;
  }
  const agg = aggregateParsed(headers, rows);
  if (agg.errors.length) {
    els.statusText.textContent = agg.errors.join(" ");
    return;
  }
  const tsv = tableToTsv(headers, rows);
  els.pasteInput.value = tsv;
  const labels = mergeQueue.map((q) => q.label).join(", ");
  if (els.titleInput) els.titleInput.value = `Samlat: ${labels}`;
  if (els.analysisModeSelect) {
    els.analysisModeSelect.value = "normal";
    updateAnalysisPanels();
  }
  window.__tidrapport_compare = null;
  resetChartFully();
  window.__chart_kind = "normal";
  regenerateFromText(tsv, null);
  els.statusText.textContent = `Samlat diagram: ${mergeQueue.length} delar • ${rows.length} rader • ${agg.totals.size} personer.`;
});

els.btnDownload.addEventListener("click", () => {
  const c = ensureChart();
  const url = c.toBase64Image("image/png", 1);
  const a = document.createElement("a");
  a.href = url;
  const safeTitle = (buildTitleText(window.__tidrapport_state || { statuses: [], selectedStatuses: [], employeeName: null }) || "tidrapport")
    .replace(/[^\w\s\-ÅÄÖåäö]/g, "")
    .trim()
    .replace(/\s+/g, "_")
    .slice(0, 80);
  a.download = `${safeTitle || "tidrapport"}_${new Date().toISOString().slice(0, 10)}.png`;
  a.click();
});

// Boot: try load saved, else show empty chart
(() => {
  renderMergeQueueList();
  updateForecastMonthInfo();
  updateAnalysisPanels();
  const store = readStore();
  refreshSavedSlotSelect(store, store.lastKey);
  const saved = loadLocal();
  if (saved?.text) {
    applyPayloadToUi(saved);
    regenerateFromText(saved.text, saved.selected || []);
  } else {
    if (els.yearInput && !els.yearInput.value) els.yearInput.value = String(new Date().getFullYear());
    window.__tidrapport_state = {
      totals: new Map(),
      statuses: [],
      selectedStatuses: new Set(),
      employeeName: null,
      stats: null,
      orientation: "horizontal",
      verticalNames: "20",
      layout: "side",
    };
    ensureChart();
    els.statusText.textContent = "Klistra in data och klicka på «Skapa / uppdatera diagram».";
  }
})();

