/* global Chart */

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

/** Rubriker som räknas som «Orsak»/status (vissa exportformat använder t.ex. Bemanningstyp). */
const ORSAK_HEADER_ALIASES = [
  "Orsak",
  "Status",
  "Typ",
  "Bemanningstyp",
  "Bemaningstyp",
];

/** Kolumn som sätts vid «Skapa samlat diagram» så varje rad vet vilken kö-del den kommer från. */
const MERGE_SOURCE_COL = "Samlad del";
const MERGE_SOURCE_COL_FALLBACK = "__MxKälla";

function sortStatusesLikeOrder(statusSet) {
  const arr = [...statusSet];
  const head = ORSAK_ORDER.filter((s) => arr.includes(s));
  const tail = arr.filter((s) => !ORSAK_ORDER.includes(s)).sort((a, b) => a.localeCompare(b, "sv"));
  return [...head, ...tail];
}

function mergeSourceHeaderToUse(baseHeaders) {
  if (pickCol(baseHeaders, [MERGE_SOURCE_COL])) return MERGE_SOURCE_COL_FALLBACK;
  return MERGE_SOURCE_COL;
}

function collectMergeSourceOrder(rows, colMerge) {
  const order = [];
  const seen = new Set();
  for (const row of rows) {
    const s = cleanStr(row[colMerge]);
    if (!s || seen.has(s)) continue;
    seen.add(s);
    order.push(s);
  }
  return order;
}

function sortCompoundSeriesKeys(keys, seriesMeta, sourceOrder) {
  const rankSrc = new Map(sourceOrder.map((s, i) => [s, i]));
  const rankSt = (st) => {
    const i = ORSAK_ORDER.indexOf(st);
    return i >= 0 ? i : 999;
  };
  return [...keys].sort((a, b) => {
    const ma = seriesMeta.get(a);
    const mb = seriesMeta.get(b);
    if (!ma || !mb) return a.localeCompare(b, "sv");
    const ra = rankSrc.get(ma.source) ?? 999;
    const rb = rankSrc.get(mb.source) ?? 999;
    if (ra !== rb) return ra - rb;
    const sa = rankSt(ma.status);
    const sb = rankSt(mb.status);
    if (sa !== sb) return sa - sb;
    return a.localeCompare(b, "sv");
  });
}

function rgbaFromHex(hex, alpha) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || "");
  if (!m) return `rgba(148,163,184,${alpha})`;
  const r = parseInt(m[1], 16);
  const g = parseInt(m[2], 16);
  const b = parseInt(m[3], 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

/** Kort månadstext på stapel i samlat läge (t.ex. Jan, Feb). */
function shortMergeSourceLabel(full) {
  const s = cleanStr(full);
  if (!s) return "?";
  const lower = s.toLowerCase();
  for (const m of SWEDISH_MONTHS) {
    if (lower.startsWith(m.toLowerCase())) {
      const abbr = m.slice(0, 3);
      return abbr.charAt(0).toUpperCase() + abbr.slice(1).toLowerCase();
    }
  }
  if (s.length <= 5) return s;
  return `${s.slice(0, 4)}…`;
}

const els = {
  pasteInput: document.getElementById("pasteInput"),
  btnGenerate: document.getElementById("btnGenerate"),
  btnDownload: document.getElementById("btnDownload"),
  btnClear: document.getElementById("btnClear"),
  btnClearNearGenerate: document.getElementById("btnClearNearGenerate"),
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
  analysisModeSelect: document.getElementById("analysisModeSelect"),
  forecastPanel: document.getElementById("forecastPanel"),
  forecastThroughDay: document.getElementById("forecastThroughDay"),
  forecastMonthInfo: document.getElementById("forecastMonthInfo"),
  tableHeadRow: document.getElementById("tableHeadRow"),
  mergeQueueList: document.getElementById("mergeQueueList"),
  btnAddToMerge: document.getElementById("btnAddToMerge"),
  btnMergePickFiles: document.getElementById("btnMergePickFiles"),
  mergeFileInput: document.getElementById("mergeFileInput"),
  btnClearMergeQueue: document.getElementById("btnClearMergeQueue"),
  btnApplyMerge: document.getElementById("btnApplyMerge"),
  mergeQueueFeedback: document.getElementById("mergeQueueFeedback"),
};

/** Råtext per del för sammanslagen period (jan–mars m.m.), endast i minnet */
const mergeQueue = [];

let __mergeFeedbackTimer = null;
/** Meddelande direkt under sammanslagningsknapparna (användaren ser sällan statusraden längre ner). */
function setMergeFeedback(msg, kind) {
  const el = els.mergeQueueFeedback || document.getElementById("mergeQueueFeedback");
  if (!el) return;
  const tone =
    kind === "err"
      ? "text-red-400"
      : kind === "ok"
        ? "text-emerald-400"
        : "text-slate-400";
  el.className = `text-xs mt-1 min-h-[1.25rem] font-medium ${tone}`;
  el.textContent = msg || "";
  if (__mergeFeedbackTimer) {
    clearTimeout(__mergeFeedbackTimer);
    __mergeFeedbackTimer = null;
  }
  if (msg) {
    __mergeFeedbackTimer = setTimeout(() => {
      el.textContent = "";
      el.className = "text-xs mt-1 min-h-[1.25rem] font-medium text-slate-400";
      __mergeFeedbackTimer = null;
    }, 16000);
  }
}

/** Tabelltext från Excel/Sheets — behåll radbrytningar och tabbar (cleanStr på hela strängen förstör strukturen). */
function normalizePastedTableString(raw) {
  let s = String(raw ?? "").replace(/^\uFEFF/, "");
  s = s.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  s = s.replace(/[\u00A0\u2007\u202F]/g, " ");
  return s.trim();
}

function rawPasteFromInput() {
  return normalizePastedTableString(els.pasteInput?.value);
}

function flashMergeQueueList() {
  if (!els.mergeQueueList) return;
  els.mergeQueueList.classList.remove("ring-2", "ring-teal-500/50");
  // reflow så animationen kan triggas igen
  void els.mergeQueueList.offsetWidth;
  els.mergeQueueList.classList.add("ring-2", "ring-teal-500/50", "transition-shadow", "duration-300");
  setTimeout(() => {
    els.mergeQueueList?.classList.remove("ring-2", "ring-teal-500/50", "transition-shadow", "duration-300");
  }, 900);
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
  if (mode === "forecast") {
    el.className = `text-xs rounded-lg px-3 py-2.5 mb-4 border ${base} bg-sky-950/40 border-sky-800/70 text-sky-100/95`;
    el.textContent =
      "Prognosläge: status och namn styrs här först; därefter skalas timmarna upp mot hela månaden enligt «Data fram till dag» i avsnittet «Vy-läge».";
  } else {
    el.className = `text-xs rounded-lg px-3 py-2.5 mb-4 border ${base} bg-emerald-950/35 border-emerald-800/50 text-emerald-50/95`;
    el.textContent =
      "Vanlig vy: välj statusar och valfritt namn. Gäller datan i huvudrutan (en månad eller redan sammanslagen period). Prognos: öppna «Vy-läge» längre ned.";
  }
}

function updateAnalysisPanels() {
  const m = getAnalysisMode();
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

function splitCellsForTable(line, delim) {
  if (delim == null) return line.split(/\s{2,}/).map(cleanStr);
  return line.split(delim).map(cleanStr);
}

function trimTrailingEmptyCells(cells) {
  const out = [...cells];
  while (out.length > 0 && !out[out.length - 1]) out.pop();
  return out;
}

function lineDelimFromContent(headerLine) {
  if (headerLine.includes("\t")) return "\t";
  if (headerLine.includes(";")) return ";";
  if (headerLine.includes(",")) return ",";
  return null;
}

function buildTableFromHeaderRow(lines, headerRowIndex, delim, headers) {
  const rows = [];
  for (let i = headerRowIndex + 1; i < lines.length; i += 1) {
    const parts = splitCellsForTable(lines[i], delim);
    while (parts.length < headers.length) parts.push("");
    const row = {};
    for (let c = 0; c < headers.length; c += 1) row[headers[c]] = parts[c] ?? "";
    rows.push(row);
  }
  return { headers, rows };
}

function parseTable(text) {
  const raw = String(text ?? "").replace(/^\uFEFF/, "");
  const lines = splitRows(raw);
  if (lines.length === 0) return { headers: [], rows: [] };

  const delims = ["\t", ";", ",", null];
  const maxStart = Math.min(lines.length, 35);

  for (let start = 0; start < maxStart; start += 1) {
    const line = lines[start];
    for (const delim of delims) {
      const headers = trimTrailingEmptyCells(splitCellsForTable(line, delim));
      if (headers.length < 3) continue;
      if (validateHeadersForAggregate(headers).length === 0) {
        return buildTableFromHeaderRow(lines, start, delim, headers);
      }
    }
  }

  const delim = lineDelimFromContent(lines[0]);
  const headers = trimTrailingEmptyCells(splitCellsForTable(lines[0], delim));
  return buildTableFromHeaderRow(lines, 0, delim, headers);
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
  const colFom = pickCol(headers, ["Kl Fom", "Kl. Fom", "Från", "From", "Fom", "F.o.m"]);
  const colTom = pickCol(headers, ["Kl Tom", "Kl. Tom", "Till", "To", "Tom"]);
  const colOrsak = pickCol(headers, ORSAK_HEADER_ALIASES);
  if (!colName) errors.push("Hittar inte kolumnen «Namn».");
  if (!colFom) errors.push("Hittar inte kolumnen «Kl Fom» (starttid).");
  if (!colTom) errors.push("Hittar inte kolumnen «Kl Tom» (sluttid).");
  if (!colOrsak) errors.push("Hittar inte kolumnen «Orsak»/«Status» (t.ex. Bemanningstyp).");
  return errors;
}

function aggregateParsed(headers, rows) {
  const emptyMeta = {
    seriesMeta: null,
    mergedSourceSplit: false,
    baseStatuses: null,
    mergeSourceOrder: null,
  };
  const errors = validateHeadersForAggregate(headers);
  if (errors.length) {
    return { totals: new Map(), statuses: [], errors, stats: null, ...emptyMeta };
  }

  const colName = pickCol(headers, ["Namn", "Name"]);
  const colFom = pickCol(headers, ["Kl Fom", "Kl. Fom", "Från", "From", "Fom", "F.o.m"]);
  const colTom = pickCol(headers, ["Kl Tom", "Kl. Tom", "Till", "To", "Tom"]);
  const colRast = pickCol(headers, ["Rast", "Kl rast", "Break"]);
  const colOrsak = pickCol(headers, ORSAK_HEADER_ALIASES);
  const colMerge = pickCol(headers, [MERGE_SOURCE_COL, MERGE_SOURCE_COL_FALLBACK]);

  const totals = new Map();
  let usedRows = 0;
  let skippedNoName = 0;
  let skippedNoTime = 0;

  if (colMerge) {
    const seriesMeta = new Map();
    const baseStatusSet = new Set();

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
      const source = cleanStr(row[colMerge]) || "Okänd del";
      const seriesKey = `${source} — ${status}`;

      baseStatusSet.add(status);
      if (!seriesMeta.has(seriesKey)) seriesMeta.set(seriesKey, { source, status });

      if (!totals.has(name)) totals.set(name, new Map());
      const bySeries = totals.get(name);
      bySeries.set(seriesKey, (bySeries.get(seriesKey) || 0) + net);
      usedRows += 1;
    }

    const mergeSourceOrder = collectMergeSourceOrder(rows, colMerge);
    const compoundKeys = [...seriesMeta.keys()];
    const statuses = sortCompoundSeriesKeys(compoundKeys, seriesMeta, mergeSourceOrder);
    const baseStatuses = sortStatusesLikeOrder(baseStatusSet);

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
      seriesMeta,
      mergedSourceSplit: true,
      baseStatuses,
      mergeSourceOrder,
    };
  }

  const statusSet = new Set();
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
    ...emptyMeta,
  };
}

function aggregate(text) {
  const { headers, rows } = parseTable(text);
  if (!headers.length) {
    return {
      totals: new Map(),
      statuses: [],
      errors: ["Ingen data."],
      stats: null,
      seriesMeta: null,
      mergedSourceSplit: false,
      baseStatuses: null,
      mergeSourceOrder: null,
    };
  }
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

function mergeParsedTablesFromQueue(mergeQueue) {
  if (!mergeQueue.length) {
    return { headers: [], rows: [], errors: ["Inga tabeller att slå ihop."] };
  }
  const parsedList = mergeQueue.map((q) => parseTable(q.text));
  const base = parsedList[0];
  if (!base.headers.length) {
    return { headers: [], rows: [], errors: ["Första delen saknar rubrikrad."] };
  }
  const v0 = validateHeadersForAggregate(base.headers);
  if (v0.length) return { headers: [], rows: [], errors: v0 };

  const srcHeader = mergeSourceHeaderToUse(base.headers);
  const headersOut = [...base.headers];
  if (!pickCol(headersOut, [srcHeader])) headersOut.push(srcHeader);

  const allRows = [];
  for (let i = 0; i < parsedList.length; i += 1) {
    const p = parsedList[i];
    if (!p.headers.length) {
      return { headers: [], rows: [], errors: [`Del ${i + 1}: saknar rubrikrad.`] };
    }
    const ve = validateHeadersForAggregate(p.headers);
    if (ve.length) {
      return { headers: [], rows: [], errors: [`Del ${i + 1}: ${ve.join(" ")}`] };
    }
    const label = cleanStr(mergeQueue[i]?.label) || `Del ${i + 1}`;
    for (const row of p.rows) {
      const r = remapRowToBaseHeaders(row, p.headers, base.headers);
      r[srcHeader] = label;
      allRows.push(r);
    }
  }
  return { headers: headersOut, rows: allRows, errors: [] };
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

(() => {
  if (typeof Chart === "undefined" || window.__tidrapport_merge_bar_plugin) return;
  window.__tidrapport_merge_bar_plugin = true;
  Chart.register({
    id: "tidrapportMergeBarLabels",
    afterDatasetsDraw(chart) {
      const plug = chart.options.plugins?.tidrapportMergeBarLabels;
      if (!plug?.enabled || !plug.shortLabels?.length) return;
      const { ctx } = chart;
      ctx.save();
      ctx.font = "600 11px system-ui, Segoe UI, sans-serif";
      chart.data.datasets.forEach((ds, di) => {
        const meta = chart.getDatasetMeta(di);
        if (meta.hidden) return;
        const short = plug.shortLabels[di];
        if (!short) return;
        meta.data.forEach((el, i) => {
          const v = ds.data[i];
          if (v == null || !(Number(v) > 0) || !el || typeof el.getProps !== "function") return;
          const props = el.getProps(["x", "y", "base", "horizontal"], true);
          const horiz = !!props.horizontal;
          if (horiz) {
            const left = Math.min(props.x, props.base) + 5;
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.lineWidth = 3;
            ctx.strokeStyle = "rgba(15, 23, 42, 0.85)";
            ctx.fillStyle = "#f8fafc";
            ctx.strokeText(short, left, props.y);
            ctx.fillText(short, left, props.y);
          } else {
            const top = Math.min(props.y, props.base) - 4;
            ctx.textAlign = "center";
            ctx.textBaseline = "bottom";
            ctx.lineWidth = 3;
            ctx.strokeStyle = "rgba(15, 23, 42, 0.85)";
            ctx.fillStyle = "#f8fafc";
            ctx.strokeText(short, props.x, top);
            ctx.fillText(short, props.x, top);
          }
        });
      });
      ctx.restore();
    },
  });
})();

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

/** Diagramläge (alltid staplad status i denna vy) */
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
        tidrapportMergeBarLabels: { enabled: false, shortLabels: [] },
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

function buildTitleText(state) {
  const base = cleanStr(els.titleInput?.value) || getMonthYearLabel();
  const employee = state.employeeName ? ` — ${state.employeeName}` : "";
  const selected = [...state.selectedStatuses];
  const allCount =
    state.mergedSourceSplit && state.baseStatuses?.length
      ? state.baseStatuses.length
      : state.statuses.length;
  let filt = "";
  if (selected.length === 0) {
    filt = " — (inga statusar)";
  } else if (selected.length !== allCount) {
    // Keep it readable; list a few statuses, then count.
    const shown = selected.slice(0, 3).join(", ");
    const more = selected.length > 3 ? ` (+${selected.length - 3})` : "";
    filt = ` — ${shown}${more}`;
  }
  let out = `${base}${employee}${filt}`;
  if (state.mergedSourceSplit) {
    out = `${out} · Samlat: grupperade staplar per månad/del (valda orsaker summerade)`;
  }
  return out;
}

/** Statusfilter (kryssrutor): vid sammanslagning är det «Orsak»-typer, inte en rad per månad. */
function filterStatusesForUi(state) {
  if (state?.mergedSourceSplit && state.baseStatuses?.length) return state.baseStatuses;
  return state?.statuses ?? [];
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

function computePeopleSorted(totals, selectedStatuses, splitState) {
  const rows = [];
  const merged = splitState?.mergedSourceSplit && splitState?.seriesMeta;
  for (const [name, byStatus] of totals.entries()) {
    let sum = 0;
    if (merged) {
      for (const [seriesKey, hours] of byStatus.entries()) {
        const meta = splitState.seriesMeta.get(seriesKey);
        if (meta && selectedStatuses.has(meta.status)) sum += hours;
      }
    } else {
      for (const st of selectedStatuses) sum += byStatus.get(st) || 0;
    }
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

  const state = window.__tidrapport_state;
  const mode = state?.orientation || "horizontal";
  resetChartIfOrientationChanged(mode);
  const c = ensureChart(mode);
  applyOrientation(mode);

  const merged = state?.mergedSourceSplit;
  const seriesMeta = state?.seriesMeta;
  const sourceOrder = state?.mergeSourceOrder || [];
  const useMergedGrouped = !!(merged && seriesMeta && sourceOrder.length);

  const limitedPeople = limitForVerticalIfNeeded(
    mode,
    sortedPeople,
    !!state?.employeeName,
    state?.verticalNames || "20"
  );
  const labels = limitedPeople.map((p) => p.name);

  if (useMergedGrouped && mode === "horizontal") {
    const nk = sourceOrder.length;
    const perRow = 26 + Math.max(0, nk - 1) * 5;
    const container = els.chartCanvas?.parentElement;
    if (container) {
      const h = Math.max(400, Math.min(2000, 160 + labels.length * perRow));
      container.style.height = `${h}px`;
    }
  } else {
    setChartHeightByMode(mode, labels.length);
  }

  const stackScales = !useMergedGrouped;
  const ix = desiredIndexAxis(mode);
  if (ix === "y") {
    c.options.scales.x.stacked = stackScales;
    c.options.scales.y.stacked = false;
  } else {
    c.options.scales.x.stacked = false;
    c.options.scales.y.stacked = stackScales;
  }

  if (useMergedGrouped) {
    c.options.datasets.bar = {
      categoryPercentage: Math.max(0.48, 0.9 - sourceOrder.length * 0.055),
      barPercentage: 0.85,
    };
  } else {
    c.options.datasets.bar = {};
  }

  const datasets = [];
  let shortLabelsForPlugin = [];

  if (useMergedGrouped) {
    sourceOrder.forEach((source, srcIdx) => {
      const bg = palette(srcIdx);
      const row = labels.map((name) => {
        let sum = 0;
        const by = totals.get(name);
        if (!by) return 0;
        for (const [seriesKey, hours] of by.entries()) {
          const meta = seriesMeta.get(seriesKey);
          if (meta && meta.source === source && selectedStatuses.has(meta.status)) sum += hours;
        }
        return round2(sum * scale);
      });
      datasets.push({
        label: source,
        data: row,
        backgroundColor: bg,
        borderWidth: 1,
        borderColor: "rgba(15,23,42,0.5)",
      });
      shortLabelsForPlugin.push(shortMergeSourceLabel(source));
    });
  } else {
    const colorByStatus = buildStatusColorMap(statuses);
    for (const st of statuses) {
      if (!selectedStatuses.has(st)) continue;
      datasets.push({
        label: st,
        data: labels.map((name) => round2((totals.get(name)?.get(st) || 0) * scale)),
        backgroundColor: colorByStatus.get(st) || "#94a3b8",
        borderWidth: 0,
      });
    }
  }

  c.data.labels = labels;
  c.data.datasets = datasets;

  if (!c.options.plugins.tidrapportMergeBarLabels) {
    c.options.plugins.tidrapportMergeBarLabels = { enabled: false, shortLabels: [] };
  }
  c.options.plugins.tidrapportMergeBarLabels.enabled = useMergedGrouped;
  c.options.plugins.tidrapportMergeBarLabels.shortLabels = useMergedGrouped ? shortLabelsForPlugin : [];

  if (state) {
    let titleText = buildTitleText(state);
    if (titleSuffix) titleText = `${titleText} — ${titleSuffix}`;
    c.options.plugins.title.text = titleText;
    if (els.titlePreview) els.titlePreview.textContent = previewNote != null ? previewNote : titleText;
  }
  renderColorLegend(datasets);
  applyOrientation(mode, { verticalLimit: state?.verticalNames || "20" });
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
  const sortedPeople = computePeopleSorted(totalsView, selectedStatuses, state);

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
  if (mode === "forecast") {
    renderForecastAll(state);
    return;
  }

  ensureNormalTableHeader();
  const { totals, statuses, selectedStatuses } = state;
  const totalsView = state.employeeName
    ? new Map([[state.employeeName, totals.get(state.employeeName) || new Map()]])
    : totals;
  const sortedPeople = computePeopleSorted(totalsView, selectedStatuses, state);
  renderTable(sortedPeople);
  renderChart(totalsView, statuses, selectedStatuses, sortedPeople);

  const totalNames = totals.size;
  const totalStatusKinds =
    state.mergedSourceSplit && state.baseStatuses?.length ? state.baseStatuses.length : statuses.length;
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
  const nSrc = state.mergeSourceOrder?.length || 0;
  const mergeHint = state.mergedSourceSplit
    ? ` · Samlat: ${nSrc} staplar sida-vid-sida per person · ${totalStatusKinds} orsak-typer i filter · kort månad på stapeln.`
    : "";
  els.statusText.textContent = `Namn: ${totalNames} • Statusar: ${totalStatusKinds} • Visar: ${selectedStatuses.size}${emp}${shownText}${statsText}${mergeHint}`;
}

function regenerateFromText(text, selectedOverride) {
  const agg = aggregate(text);
  if (agg.errors.length) {
    els.statusText.textContent = agg.errors.join(" ");
    window.__tidrapport_state = {
      totals: new Map(),
      statuses: [],
      selectedStatuses: new Set(),
      employeeName: null,
      stats: null,
      seriesMeta: null,
      mergedSourceSplit: false,
      baseStatuses: null,
      mergeSourceOrder: null,
    };
    safeRenderAll(window.__tidrapport_state);
    return;
  }

  const {
    totals,
    statuses,
    stats,
    seriesMeta,
    mergedSourceSplit,
    baseStatuses,
    mergeSourceOrder,
  } = agg;

  const filterStatuses =
    mergedSourceSplit && baseStatuses?.length ? baseStatuses : statuses;
  const selectedStatuses = new Set();
  const preferred = selectedOverride?.length ? selectedOverride : filterStatuses;
  for (const st of preferred) if (filterStatuses.includes(st)) selectedStatuses.add(st);

  const employeeName = getSelectedEmployeeName(totals);

  const orientation = cleanStr(els.orientationSelect?.value) || "horizontal";
  const verticalNames = cleanStr(els.verticalNamesSelect?.value) || "20";
  const layout = cleanStr(els.layoutSelect?.value) || "side";
  window.__tidrapport_state = {
    totals,
    statuses,
    selectedStatuses,
    employeeName,
    stats,
    orientation,
    verticalNames,
    layout,
    seriesMeta,
    mergedSourceSplit: !!mergedSourceSplit,
    baseStatuses,
    mergeSourceOrder,
  };
  // update datalist with names
  if (els.employeeList) {
    els.employeeList.innerHTML = "";
    [...totals.keys()].sort((a, b) => a.localeCompare(b, "sv")).forEach((n) => {
      const opt = document.createElement("option");
      opt.value = n;
      els.employeeList.appendChild(opt);
    });
  }
  buildStatusFilters(filterStatuses, selectedStatuses);
  safeRenderAll(window.__tidrapport_state);
}

els.btnGenerate.addEventListener("click", () => {
  const text = els.pasteInput.value || "";
  regenerateFromText(text, null);
});

function clearPasteAndChart() {
  els.pasteInput.value = "";
  regenerateFromText("", null);
}

els.btnClear.addEventListener("click", clearPasteAndChart);
els.btnClearNearGenerate?.addEventListener("click", clearPasteAndChart);

els.btnAll.addEventListener("click", () => {
  const st = window.__tidrapport_state;
  const fs = filterStatusesForUi(st);
  st.selectedStatuses = new Set(fs);
  buildStatusFilters(fs, st.selectedStatuses);
  safeRenderAll(st);
});

els.btnNone.addEventListener("click", () => {
  const st = window.__tidrapport_state;
  st.selectedStatuses = new Set();
  buildStatusFilters(filterStatusesForUi(st), st.selectedStatuses);
  safeRenderAll(st);
});

els.btnClearEmployee?.addEventListener("click", () => {
  if (els.employeeInput) els.employeeInput.value = "";
  if (window.__tidrapport_state) {
    window.__tidrapport_state.employeeName = null;
    safeRenderAll(window.__tidrapport_state);
  }
});

els.employeeInput?.addEventListener("input", () => {
  if (!window.__tidrapport_state) return;
  const nm = getSelectedEmployeeName(window.__tidrapport_state.totals);
  window.__tidrapport_state.employeeName = nm;
  safeRenderAll(window.__tidrapport_state);
});

for (const el of [els.monthSelect, els.yearInput, els.titleInput]) {
  el?.addEventListener("input", () => {
    updateForecastMonthInfo();
    if (!window.__tidrapport_state) return;
    safeRenderAll(window.__tidrapport_state);
  });
}

els.analysisModeSelect?.addEventListener("change", () => {
  updateAnalysisPanels();
  const m = getAnalysisMode();
  resetChartFully();
  window.__chart_kind = "normal";
  if (!window.__tidrapport_state) return;
  if (m === "forecast") {
    safeRenderAll(window.__tidrapport_state);
    return;
  }
  buildStatusFilters(
    filterStatusesForUi(window.__tidrapport_state),
    window.__tidrapport_state.selectedStatuses
  );
  safeRenderAll(window.__tidrapport_state);
});

els.forecastThroughDay?.addEventListener("input", () => {
  if (getAnalysisMode() === "forecast" && window.__tidrapport_state) safeRenderAll(window.__tidrapport_state);
});

els.orientationSelect?.addEventListener("change", () => {
  if (!window.__tidrapport_state) return;
  window.__tidrapport_state.orientation = cleanStr(els.orientationSelect.value) || "horizontal";
  safeRenderAll(window.__tidrapport_state);
});

els.verticalNamesSelect?.addEventListener("change", () => {
  if (!window.__tidrapport_state) return;
  window.__tidrapport_state.verticalNames = cleanStr(els.verticalNamesSelect.value) || "20";
  safeRenderAll(window.__tidrapport_state);
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
});

els.btnAddToMerge?.addEventListener("click", () => {
  const text = rawPasteFromInput();
  if (!text) {
    const m = "Rutan ovanför är tom — klistra in tabellen där först, sedan klicka igen.";
    els.statusText.textContent = m;
    setMergeFeedback(m, "err");
    return;
  }
  const parsed = parseTable(text);
  const ve = validateHeadersForAggregate(parsed.headers);
  if (ve.length) {
    const m = ve.join(" ");
    els.statusText.textContent = m;
    setMergeFeedback(m, "err");
    return;
  }
  if (!parsed.rows.length) {
    const m = "Inga datarader (bara rubrik?). Kontrollera att du kopierat hela tabellen med rubrikrad.";
    els.statusText.textContent = m;
    setMergeFeedback(m, "err");
    return;
  }
  const month = cleanStr(els.monthSelect?.value);
  const year = cleanStr(els.yearInput?.value);
  const label = [month, year].filter(Boolean).join(" ").trim() || `Del ${mergeQueue.length + 1}`;
  mergeQueue.push({ label, text });
  renderMergeQueueList();
  flashMergeQueueList();
  const ok = `Tillagt «${label}» — ${mergeQueue.length} del${mergeQueue.length === 1 ? "" : "ar"} i kön.`;
  els.statusText.textContent = ok;
  setMergeFeedback(ok, "ok");
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
        const m = `${f.name}: ${ve.join(" ")}`;
        els.statusText.textContent = m;
        setMergeFeedback(m, "err");
        continue;
      }
      if (!parsed.rows.length) {
        const m = `${f.name}: inga datarader.`;
        els.statusText.textContent = m;
        setMergeFeedback(m, "err");
        continue;
      }
      mergeQueue.push({ label, text });
      added += 1;
    } catch {
      const m = `Kunde inte läsa ${f.name}.`;
      els.statusText.textContent = m;
      setMergeFeedback(m, "err");
    }
  }
  renderMergeQueueList();
  if (added > 0) {
    flashMergeQueueList();
    const ok = `Tillagde ${added} fil(er). Kö: ${mergeQueue.length} delar.`;
    els.statusText.textContent = ok;
    setMergeFeedback(ok, "ok");
  }
});

els.btnClearMergeQueue?.addEventListener("click", () => {
  mergeQueue.length = 0;
  renderMergeQueueList();
  const m = "Kön är tömd.";
  els.statusText.textContent = m;
  setMergeFeedback(m, "ok");
});

els.btnApplyMerge?.addEventListener("click", () => {
  if (mergeQueue.length < 2) {
    const m =
      "Lägg till minst två delar i listan nedan (samma knapp flera gånger med ny data, eller lägg till filer).";
    els.statusText.textContent = m;
    setMergeFeedback(m, "err");
    return;
  }
  const { headers, rows, errors } = mergeParsedTablesFromQueue(mergeQueue);
  if (errors.length) {
    const m = errors.join(" ");
    els.statusText.textContent = m;
    setMergeFeedback(m, "err");
    return;
  }
  const agg = aggregateParsed(headers, rows);
  if (agg.errors.length) {
    const m = agg.errors.join(" ");
    els.statusText.textContent = m;
    setMergeFeedback(m, "err");
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
  resetChartFully();
  window.__chart_kind = "normal";
  regenerateFromText(tsv, null);
  const ok = `Klart: samlat diagram — ${mergeQueue.length} delar, ${rows.length} rader, ${agg.totals.size} personer. (Kolla diagrammet nedan.)`;
  els.statusText.textContent = ok;
  setMergeFeedback(ok, "ok");
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

// Boot: rensa gamla sparade månader (localStorage) och visa tomt läge
(() => {
  try {
    localStorage.removeItem("mx_tidrapport_v1");
    localStorage.removeItem("mx_tidrapport_v2");
  } catch (e) {
    console.warn("tidrapport localStorage cleanup", e);
  }
  if (els.analysisModeSelect?.value === "compare") els.analysisModeSelect.value = "normal";
  renderMergeQueueList();
  updateForecastMonthInfo();
  updateAnalysisPanels();
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
    seriesMeta: null,
    mergedSourceSplit: false,
    baseStatuses: null,
    mergeSourceOrder: null,
  };
  ensureChart();
  els.statusText.textContent = "Klistra in data och klicka på «Skapa / uppdatera diagram».";
})();

