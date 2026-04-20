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
  statusFilters: document.getElementById("statusFilters"),
  statusText: document.getElementById("statusText"),
  tableBody: document.getElementById("tableBody"),
  chartCanvas: document.getElementById("chartCanvas"),
};

function cleanStr(v) {
  if (v == null) return "";
  return String(v).replace(/\u00A0/g, " ").trim();
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
  const headers = (delim ? lines[0].split(delim) : lines[0].split(/\s{2,}/)).map(cleanStr);

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
  const low = headers.map((h) => cleanStr(h).toLowerCase());
  for (const w of wanted) {
    const idx = low.indexOf(w.toLowerCase());
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

  for (const row of rows) {
    const name = cleanStr(row[colName]);
    if (!name) continue;
    const fom = parseTimeToHours(row[colFom]);
    const tom = parseTimeToHours(row[colTom]);
    if (fom == null || tom == null) continue;
    const rastMin = colRast ? parseRastMinutes(row[colRast]) : 0;
    const gross = durationHours(fom, tom);
    const net = Math.max(0, gross - rastMin / 60);
    const status = normalizeOrsak(colOrsak ? row[colOrsak] : "");

    statusSet.add(status);
    if (!totals.has(name)) totals.set(name, new Map());
    const byStatus = totals.get(name);
    byStatus.set(status, (byStatus.get(status) || 0) + net);
  }

  const statuses = [
    ...ORSAK_ORDER.filter((s) => statusSet.has(s)),
    ...[...statusSet].filter((s) => !ORSAK_ORDER.includes(s)).sort((a, b) => a.localeCompare(b, "sv")),
  ];

  return { totals, statuses, errors: [] };
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

function buildStatusFilters(statuses, selected) {
  els.statusFilters.innerHTML = "";
  for (const st of statuses) {
    const id = `st_${btoa(unescape(encodeURIComponent(st))).replace(/=/g, "")}`;
    const label = document.createElement("label");
    label.className =
      "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/70 hover:bg-slate-700/70 cursor-pointer select-none";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.checked = selected.has(st);
    cb.className = "accent-emerald-500";
    cb.addEventListener("change", () => {
      if (cb.checked) selected.add(st);
      else selected.delete(st);
      renderAll(window.__tidrapport_state);
      saveLocal(window.__tidrapport_state);
    });
    const span = document.createElement("span");
    span.textContent = st;
    span.className = "text-xs text-slate-100";
    label.appendChild(cb);
    label.appendChild(span);
    els.statusFilters.appendChild(label);
  }
}

let chart = null;

function ensureChart() {
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
        legend: { position: "right", labels: { color: "#e2e8f0" } },
        title: { display: true, text: "Timmar per person (per status)", color: "#e2e8f0" },
      },
      scales: {
        x: { stacked: true, ticks: { color: "#cbd5e1" }, grid: { color: "rgba(148,163,184,0.15)" } },
        y: { stacked: true, ticks: { color: "#cbd5e1" }, grid: { color: "rgba(148,163,184,0.10)" } },
      },
    },
  });
  return chart;
}

function palette(i) {
  const colors = [
    "#34d399",
    "#60a5fa",
    "#fbbf24",
    "#f87171",
    "#a78bfa",
    "#22c55e",
    "#38bdf8",
    "#fb7185",
    "#c084fc",
    "#f59e0b",
  ];
  return colors[i % colors.length];
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

  const datasets = [];
  let idx = 0;
  for (const st of statuses) {
    if (!selectedStatuses.has(st)) continue;
    datasets.push({
      label: st,
      data: labels.map((name) => round2((totals.get(name)?.get(st) || 0))),
      backgroundColor: palette(idx),
      borderWidth: 0,
    });
    idx += 1;
  }

  c.data.labels = labels;
  c.data.datasets = datasets;
  c.update();
}

function renderAll(state) {
  const { totals, statuses, selectedStatuses } = state;
  const sortedPeople = computePeopleSorted(totals, selectedStatuses);
  renderTable(sortedPeople);
  renderChart(totals, statuses, selectedStatuses, sortedPeople);

  const totalNames = totals.size;
  const totalStatuses = statuses.length;
  els.statusText.textContent = `Namn: ${totalNames} • Statusar: ${totalStatuses} • Visar: ${selectedStatuses.size}`;
}

function saveLocal(state) {
  const payload = {
    text: els.pasteInput.value,
    selected: [...state.selectedStatuses],
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
  const { totals, statuses, errors } = aggregate(text);
  if (errors.length) {
    els.statusText.textContent = errors.join(" ");
    window.__tidrapport_state = { totals: new Map(), statuses: [], selectedStatuses: new Set() };
    renderAll(window.__tidrapport_state);
    return;
  }

  const selectedStatuses = new Set();
  const preferred = selectedOverride?.length ? selectedOverride : statuses;
  for (const st of preferred) if (statuses.includes(st)) selectedStatuses.add(st);

  window.__tidrapport_state = { totals, statuses, selectedStatuses };
  buildStatusFilters(statuses, selectedStatuses);
  renderAll(window.__tidrapport_state);
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
  regenerateFromText(els.pasteInput.value, data.selected || []);
});

els.btnAll.addEventListener("click", () => {
  const st = window.__tidrapport_state;
  st.selectedStatuses = new Set(st.statuses);
  buildStatusFilters(st.statuses, st.selectedStatuses);
  renderAll(st);
  saveLocal(st);
});

els.btnNone.addEventListener("click", () => {
  const st = window.__tidrapport_state;
  st.selectedStatuses = new Set();
  buildStatusFilters(st.statuses, st.selectedStatuses);
  renderAll(st);
  saveLocal(st);
});

els.btnDownload.addEventListener("click", () => {
  const c = ensureChart();
  const url = c.toBase64Image("image/png", 1);
  const a = document.createElement("a");
  a.href = url;
  a.download = `tidrapport_${new Date().toISOString().slice(0, 10)}.png`;
  a.click();
});

// Boot: try load saved, else show empty chart
(() => {
  const saved = loadLocal();
  if (saved?.text) {
    els.pasteInput.value = saved.text;
    regenerateFromText(saved.text, saved.selected || []);
  } else {
    window.__tidrapport_state = { totals: new Map(), statuses: [], selectedStatuses: new Set() };
    ensureChart();
    els.statusText.textContent = "Klistra in data och klicka på «Skapa / uppdatera diagram».";
  }
})();

