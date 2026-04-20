/* global Chart */

const STORAGE_KEY = "mx_tidrapport_v1";

const els = {
  pasteInput: document.getElementById("pasteInput"),
  btnGenerate: document.getElementById("btnGenerate"),
  btnDownload: document.getElementById("btnDownload"),
  btnClear: document.getElementById("btnClear"),
  btnLoad: document.getElementById("btnLoad"),
  btnAll: document.getElementById("btnAll"),
  btnNone: document.getElementById("btnNone"),
  monthSelect: document.getElementById("monthSelect"),
  yearInput: document.getElementById("yearInput"),
  titleInput: document.getElementById("titleInput"),
  titlePreview: document.getElementById("titlePreview"),
  colorLegend: document.getElementById("colorLegend"),
  statusFilters: document.getElementById("statusFilters"),
  statusText: document.getElementById("statusText"),
  employeeInput: document.getElementById("employeeInput"),
  employeeList: document.getElementById("employeeList"),
  btnClearEmployee: document.getElementById("btnClearEmployee"),
  tableBody: document.getElementById("tableBody"),
  chartCanvas: document.getElementById("chartCanvas"),
};

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
  const lines = splitRows(text);
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

function aggregate(text) {
  const { headers, rows } = parseTable(text);
  if (!headers.length) return { totals: new Map(), statuses: [], errors: ["Ingen data."] };

  const colName = pickCol(headers, ["Namn", "Name"]);
  const colFom = pickCol(headers, ["Kl Fom", "Från", "From", "Fom", "F.o.m"]);
  const colTom = pickCol(headers, ["Kl Tom", "Till", "To", "Tom"]);
  const colRast = pickCol(headers, ["Rast", "Kl rast", "Break"]);
  const colOrsak = pickCol(headers, ["Orsak", "Status", "Typ"]);

  const errors = [];
  if (!colName) errors.push("Hittar inte kolumnen «Namn».");
  if (!colFom) errors.push("Hittar inte kolumnen «Kl Fom» (starttid).");
  if (!colTom) errors.push("Hittar inte kolumnen «Kl Tom» (sluttid).");
  if (!colOrsak) errors.push("Hittar inte kolumnen «Orsak»/«Status».");
  if (errors.length) return { totals: new Map(), statuses: [], errors };

  const totals = new Map(); // name -> Map(status -> hours)
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

function ensureChart() {
  if (typeof Chart === "undefined") {
    throw new Error("Chart.js laddades inte. Ladda om sidan och testa igen.");
  }
  if (chart) return chart;
  const ctx = els.chartCanvas.getContext("2d");
  chart = new Chart(ctx, {
    type: "bar",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      plugins: {
        legend: {
          position: "right",
          labels: { color: "#e2e8f0", boxWidth: 14, boxHeight: 14, padding: 14, font: { size: 12 } },
        },
        title: { display: true, text: "Timmar per person (per status)", color: "#e2e8f0", font: { size: 14 } },
      },
      scales: {
        x: { stacked: true, ticks: { color: "#cbd5e1", font: { size: 12 } }, grid: { color: "rgba(148,163,184,0.15)" } },
        y: { stacked: true, ticks: { color: "#cbd5e1", font: { size: 12 } }, grid: { color: "rgba(148,163,184,0.10)" } },
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

function renderChart(totals, statuses, selectedStatuses, sortedPeople) {
  const c = ensureChart();
  const labels = sortedPeople.map((p) => p.name);

  setChartHeightByLabels(labels.length);

  const colorByStatus = buildStatusColorMap(statuses);
  const datasets = [];
  for (const st of statuses) {
    if (!selectedStatuses.has(st)) continue;
    datasets.push({
      label: st,
      data: labels.map((name) => round2((totals.get(name)?.get(st) || 0))),
      backgroundColor: colorByStatus.get(st) || "#94a3b8",
      borderWidth: 0,
    });
  }

  c.data.labels = labels;
  c.data.datasets = datasets;
  if (window.__tidrapport_state) {
    const titleText = buildTitleText(window.__tidrapport_state);
    c.options.plugins.title.text = titleText;
    if (els.titlePreview) els.titlePreview.textContent = titleText;
  }
  renderColorLegend(datasets);
  c.update();
}

function renderAll(state) {
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
  els.statusText.textContent = `Namn: ${totalNames} • Statusar: ${totalStatuses} • Visar: ${selectedStatuses.size}${emp}${statsText}`;
}

function saveLocal(state) {
  const payload = {
    text: els.pasteInput.value,
    selected: [...state.selectedStatuses],
    month: cleanStr(els.monthSelect?.value),
    year: cleanStr(els.yearInput?.value),
    title: cleanStr(els.titleInput?.value),
    employee: cleanStr(els.employeeInput?.value),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function loadLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function clearLocal() {
  localStorage.removeItem(STORAGE_KEY);
}

function regenerateFromText(text, selectedOverride) {
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

  window.__tidrapport_state = { totals, statuses, selectedStatuses, employeeName, stats };
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
});

els.btnClear.addEventListener("click", () => {
  els.pasteInput.value = "";
  clearLocal();
  regenerateFromText("", null);
});

els.btnLoad.addEventListener("click", () => {
  const data = loadLocal();
  if (!data) {
    els.statusText.textContent = "Inget sparat hittades.";
    return;
  }
  els.pasteInput.value = data.text || "";
  if (els.monthSelect && data.month) els.monthSelect.value = data.month;
  if (els.yearInput && data.year) els.yearInput.value = data.year;
  if (els.titleInput && data.title) els.titleInput.value = data.title;
  if (els.employeeInput && data.employee) els.employeeInput.value = data.employee;
  regenerateFromText(els.pasteInput.value, data.selected || []);
});

els.btnAll.addEventListener("click", () => {
  const st = window.__tidrapport_state;
  st.selectedStatuses = new Set(st.statuses);
  buildStatusFilters(st.statuses, st.selectedStatuses);
  safeRenderAll(st);
  saveLocal(st);
});

els.btnNone.addEventListener("click", () => {
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
    if (!window.__tidrapport_state) return;
    safeRenderAll(window.__tidrapport_state);
    saveLocal(window.__tidrapport_state);
  });
}

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
  const saved = loadLocal();
  if (saved?.text) {
    els.pasteInput.value = saved.text;
    if (els.monthSelect && saved.month) els.monthSelect.value = saved.month;
    if (els.yearInput && saved.year) els.yearInput.value = saved.year;
    if (els.titleInput && saved.title) els.titleInput.value = saved.title;
    if (els.employeeInput && saved.employee) els.employeeInput.value = saved.employee;
    regenerateFromText(saved.text, saved.selected || []);
  } else {
    if (els.yearInput && !els.yearInput.value) els.yearInput.value = String(new Date().getFullYear());
    window.__tidrapport_state = { totals: new Map(), statuses: [], selectedStatuses: new Set(), employeeName: null, stats: null };
    ensureChart();
    els.statusText.textContent = "Klistra in data och klicka på «Skapa / uppdatera diagram».";
  }
})();

