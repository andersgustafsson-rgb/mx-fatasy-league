/**
 * Smoke-check: tidrapport export wiring + MHTML builder.
 * Run: node scripts/smoke_tidrapport_export.js
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "templates/tidrapport.html"), "utf8");
const js = fs.readFileSync(path.join(root, "static/tidrapport.js"), "utf8");

const requiredButtons = [
  "btnDownload",
  "btnExportExcel",
  "btnOvertimeDownload",
  "btnOvertimeExportExcel",
  "btnSickManualDownload",
  "btnSickManualExportExcel",
];
const requiredFns = [
  "downloadMhtmlExcel",
  "exportExcelAndChart",
  "exportOvertimeExcelAndChart",
  "exportSickManualExcelAndChart",
];

let failed = 0;
for (const id of requiredButtons) {
  if (!html.includes(`id="${id}"`)) {
    console.error(`MISSING HTML button: ${id}`);
    failed += 1;
  }
  if (!js.includes(`getElementById("${id}")`)) {
    console.error(`MISSING JS element bind: ${id}`);
    failed += 1;
  }
}
for (const fn of requiredFns) {
  if (!js.includes(`function ${fn}`)) {
    console.error(`MISSING function: ${fn}`);
    failed += 1;
  }
}
if (!js.includes('btnOvertimeExportExcel?.addEventListener("click"')) {
  console.error("MISSING overtime excel click handler");
  failed += 1;
}
if (!js.includes('btnSickManualExportExcel?.addEventListener("click"')) {
  console.error("MISSING sick excel click handler");
  failed += 1;
}
if (!js.includes('btnExportExcel?.addEventListener("click"')) {
  console.error("MISSING main excel click handler");
  failed += 1;
}

// Minimal MHTML builder parity check (inline copy of core rules).
function buildMhtml(title, pngDataUrl) {
  const boundary = "----=_NextPart_Tidrapport";
  const hasPng = !!(pngDataUrl && pngDataUrl.startsWith("data:image/png;base64,"));
  const imgHtml = hasPng ? '<p><img src="diagram.png" alt="Diagram"></p>' : "<p>noimg</p>";
  const htmlBody = `<html><body><h1>${title}</h1>${imgHtml}<table><tr><td>A</td></tr></table></body></html>`;
  let mhtml =
    `MIME-Version: 1.0\r\nContent-Type: multipart/related; boundary="${boundary}"\r\n\r\n` +
    `--${boundary}\r\nContent-Type: text/html; charset="utf-8"\r\nContent-Location: tidrapport.htm\r\n\r\n${htmlBody}\r\n`;
  if (hasPng) {
    const b64 = pngDataUrl.slice("data:image/png;base64,".length);
    mhtml += `--${boundary}\r\nContent-Type: image/png\r\nContent-Transfer-Encoding: base64\r\nContent-Location: diagram.png\r\n\r\n${b64}\r\n`;
  }
  mhtml += `--${boundary}--\r\n`;
  return { mhtml, hasPng };
}

const tinyPng =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
const withImg = buildMhtml("Juni 2025", tinyPng);
if (!withImg.hasPng || !withImg.mhtml.includes("Content-Location: diagram.png")) {
  console.error("MHTML with image failed");
  failed += 1;
}
const noImg = buildMhtml("Test", "");
if (noImg.hasPng || noImg.mhtml.includes("Content-Location: diagram.png")) {
  console.error("MHTML without image should omit png part");
  failed += 1;
}

if (failed) {
  console.error(`FAIL: ${failed} check(s)`);
  process.exit(1);
}
console.log("OK: all three chart panels have PNG + Excel export wiring; MHTML shape looks good.");
