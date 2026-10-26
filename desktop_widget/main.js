const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  nativeImage,
  shell,
  ipcMain,
  screen,
} = require("electron");
const fs = require("fs");
const path = require("path");

const APP_DIR_NAME = app.isPackaged ? "mx-fantasy-widget" : "mx-fantasy-widget-dev";
try {
  app.setPath("userData", path.join(app.getPath("appData"), APP_DIR_NAME));
} catch (_) {
  /* before ready */
}

const CONFIG_NAME = "widget-config.json";
const DEFAULTS = {
  url: "",
  corner: "tr",
  size: "m",
  alwaysOnTop: false,
  autostart: false,
};

/** Base window sizes — grown so the full card (status + me + top 3) fits. */
const SIZE_PX = {
  s: { w: 360, h: 760 },
  m: { w: 400, h: 860 },
  l: { w: 460, h: 960 },
};

let settingsWin = null;
let widgetWin = null;
let tray = null;

function configPath() {
  return path.join(app.getPath("userData"), CONFIG_NAME);
}

function loadConfig() {
  try {
    const raw = fs.readFileSync(configPath(), "utf8");
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

function saveConfig(cfg) {
  const next = { ...DEFAULTS, ...cfg };
  fs.mkdirSync(app.getPath("userData"), { recursive: true });
  fs.writeFileSync(configPath(), JSON.stringify(next, null, 2), "utf8");
  applyAutostart(!!next.autostart);
  return next;
}

function applyAutostart(enabled) {
  try {
    app.setLoginItemSettings({
      openAtLogin: enabled,
      path: process.execPath,
      args: app.isPackaged ? [] : [path.resolve(__dirname)],
    });
  } catch (e) {
    console.warn("autostart failed", e);
  }
}

function buildWidgetUrl(cfg) {
  let raw = (cfg.url || "").trim();
  if (!raw) return "";
  let u;
  try {
    u = new URL(raw);
  } catch {
    return "";
  }
  u.searchParams.set("embedded", "1");
  u.searchParams.set("pos", cfg.corner || "tr");
  u.searchParams.set("size", cfg.size || "m");
  return u.toString();
}

function cornerBounds(corner, sizeKey, width, height) {
  const display = screen.getPrimaryDisplay();
  const wa = display.workArea;
  const dim = SIZE_PX[sizeKey] || SIZE_PX.m;
  const w = width || dim.w;
  const h = height || dim.h;
  const margin = 16;
  let x = wa.x + margin;
  let y = wa.y + margin;
  if (corner === "tr" || corner === "br") x = wa.x + wa.width - w - margin;
  if (corner === "bl" || corner === "br") y = wa.y + wa.height - h - margin;
  // Keep fully on screen.
  x = Math.min(Math.max(wa.x + margin, x), wa.x + wa.width - w - margin);
  y = Math.min(Math.max(wa.y + margin, y), wa.y + wa.height - h - margin);
  return { x: Math.round(x), y: Math.round(y), width: Math.round(w), height: Math.round(h) };
}

function trayIcon() {
  // 32x32 cyan rounded square with white M — readable in the system tray.
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">' +
    '<rect width="32" height="32" rx="7" fill="#0a1a2e"/>' +
    '<rect x="2" y="2" width="28" height="28" rx="6" fill="none" stroke="#19c3ff" stroke-width="2"/>' +
    '<text x="16" y="23" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" ' +
    'font-size="16" font-weight="900" fill="#19c3ff">M</text></svg>';
  const img = nativeImage.createFromDataURL(
    "data:image/svg+xml;base64," + Buffer.from(svg).toString("base64")
  );
  return img.isEmpty() ? nativeImage.createEmpty() : img;
}

function createTray() {
  if (tray) return;
  tray = new Tray(trayIcon());
  tray.setToolTip("MX Fantasy Widget");
  tray.on("click", () => {
    if (widgetWin && !widgetWin.isDestroyed() && widgetWin.isVisible()) {
      widgetWin.hide();
    } else {
      openWidget();
    }
  });
  tray.on("right-click", () => tray.popUpContextMenu());
  rebuildTrayMenu();
}

function rebuildTrayMenu() {
  if (!tray) return;
  const cfg = loadConfig();
  const menu = Menu.buildFromTemplate([
    {
      label: widgetWin && !widgetWin.isDestroyed() && widgetWin.isVisible() ? "Dölj widget" : "Visa widget",
      click: () => {
        if (widgetWin && !widgetWin.isDestroyed() && widgetWin.isVisible()) {
          widgetWin.hide();
        } else {
          openWidget();
        }
        rebuildTrayMenu();
      },
    },
    { label: "Inställningar", click: () => openSettings() },
    { type: "separator" },
    {
      label: "Hörn",
      submenu: ["tr", "tl", "br", "bl"].map((c) => ({
        label: { tr: "Höger upp", tl: "Vänster upp", br: "Höger ner", bl: "Vänster ner" }[c],
        type: "radio",
        checked: (cfg.corner || "tr") === c,
        click: () => openWidget(saveConfig({ ...cfg, corner: c })),
      })),
    },
    {
      label: "Storlek",
      submenu: ["s", "m", "l"].map((s) => ({
        label: s.toUpperCase(),
        type: "radio",
        checked: (cfg.size || "m") === s,
        click: () => openWidget(saveConfig({ ...cfg, size: s })),
      })),
    },
    {
      label: "Alltid överst",
      type: "checkbox",
      checked: !!cfg.alwaysOnTop,
      click: (item) => {
        const next = saveConfig({ ...cfg, alwaysOnTop: item.checked });
        if (widgetWin && !widgetWin.isDestroyed()) {
          widgetWin.setAlwaysOnTop(!!next.alwaysOnTop);
        }
        rebuildTrayMenu();
      },
    },
    {
      label: "Fäst bakom andra fönster",
      type: "checkbox",
      checked: !cfg.alwaysOnTop,
      click: () => {
        const next = saveConfig({ ...cfg, alwaysOnTop: false });
        if (widgetWin && !widgetWin.isDestroyed()) {
          widgetWin.setAlwaysOnTop(false);
        }
        rebuildTrayMenu();
        // Hint: with alwaysOnTop off, other windows cover the widget.
        void next;
      },
    },
    { type: "separator" },
    {
      label: "Öppna mx-fantasy.se",
      click: () => shell.openExternal("https://mx-fantasy.se/"),
    },
    { type: "separator" },
    { label: "Avsluta", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
}

function openSettings() {
  if (settingsWin && !settingsWin.isDestroyed()) {
    settingsWin.focus();
    return;
  }
  settingsWin = new BrowserWindow({
    width: 520,
    height: 640,
    resizable: false,
    title: "MX Fantasy Widget — Inställningar",
    backgroundColor: "#06101f",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  settingsWin.setMenuBarVisibility(false);
  settingsWin.loadFile(path.join(__dirname, "settings.html"));
  settingsWin.on("closed", () => {
    settingsWin = null;
  });
}

async function fitWidgetToContent() {
  if (!widgetWin || widgetWin.isDestroyed()) return;
  try {
    const size = await widgetWin.webContents.executeJavaScript(
      `(() => {
        const card = document.getElementById('w-card');
        if (!card) return null;
        const r = card.getBoundingClientRect();
        const h = Math.ceil(Math.max(card.scrollHeight, r.height, document.body.scrollHeight));
        const w = Math.ceil(Math.max(card.scrollWidth, r.width, 360));
        return { w, h };
      })()`
    );
    if (!size || !size.h) return;
    const cfg = loadConfig();
    const dim = SIZE_PX[cfg.size || "m"] || SIZE_PX.m;
    const width = Math.max(dim.w, Math.min(size.w + 8, 520));
    const height = Math.max(dim.h, Math.min(size.h + 12, screen.getPrimaryDisplay().workArea.height - 40));
    const bounds = cornerBounds(cfg.corner || "tr", cfg.size || "m", width, height);
    widgetWin.setBounds(bounds);
  } catch (e) {
    console.warn("fitWidgetToContent", e);
  }
}

function openInDefaultBrowser(url) {
  if (!url || !/^https?:\/\//i.test(url)) return false;
  shell.openExternal(url);
  return true;
}

function wireWidget(win) {
  // Links like "DU HAR TIPPAT" must open in the user's default browser, not Electron.
  win.webContents.setWindowOpenHandler(({ url }) => {
    openInDefaultBrowser(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    try {
      if (new URL(url).pathname.includes("/tv/widget")) return;
    } catch (_) {}
    event.preventDefault();
    openInDefaultBrowser(url);
  });
  win.webContents.on("did-finish-load", () => {
    setTimeout(fitWidgetToContent, 400);
    setTimeout(fitWidgetToContent, 1200);
  });
  win.on("hide", () => rebuildTrayMenu());
  win.on("show", () => rebuildTrayMenu());
}

function openWidget(cfgIn) {
  const cfg = cfgIn || loadConfig();
  const url = buildWidgetUrl(cfg);
  if (!url) {
    openSettings();
    return;
  }

  const bounds = cornerBounds(cfg.corner || "tr", cfg.size || "m");
  if (widgetWin && !widgetWin.isDestroyed()) {
    widgetWin.setBounds(bounds);
    widgetWin.setAlwaysOnTop(!!cfg.alwaysOnTop);
    widgetWin.loadURL(url);
    widgetWin.show();
    rebuildTrayMenu();
    return;
  }

  widgetWin = new BrowserWindow({
    ...bounds,
    frame: false,
    transparent: true,
    resizable: true,
    skipTaskbar: true,
    alwaysOnTop: !!cfg.alwaysOnTop,
    backgroundColor: "#00000000",
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  widgetWin.setMenuBarVisibility(false);
  wireWidget(widgetWin);
  widgetWin.loadURL(url);
  widgetWin.on("closed", () => {
    widgetWin = null;
    rebuildTrayMenu();
  });
  rebuildTrayMenu();
}

function hideWidget() {
  if (widgetWin && !widgetWin.isDestroyed()) {
    widgetWin.hide();
    rebuildTrayMenu();
  }
  return { ok: true };
}

ipcMain.handle("get-config", () => loadConfig());
ipcMain.handle("save-config", (_e, cfg) => {
  try {
    saveConfig(cfg);
    rebuildTrayMenu();
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
});
ipcMain.handle("open-widget", () => {
  openWidget();
  return { ok: true };
});
ipcMain.handle("hide-widget", () => hideWidget());
ipcMain.handle("open-settings", () => {
  openSettings();
  return { ok: true };
});
ipcMain.handle("set-always-on-top", (_e, on) => {
  const cfg = loadConfig();
  const next = saveConfig({ ...cfg, alwaysOnTop: !!on });
  if (widgetWin && !widgetWin.isDestroyed()) {
    widgetWin.setAlwaysOnTop(!!next.alwaysOnTop);
    if (!widgetWin.isVisible()) widgetWin.show();
  }
  rebuildTrayMenu();
  return { ok: true, alwaysOnTop: !!next.alwaysOnTop };
});
ipcMain.handle("open-external", (_e, url) => {
  if (typeof url === "string" && /^https?:\/\//i.test(url)) {
    shell.openExternal(url);
  }
  return { ok: true };
});

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const cfg = loadConfig();
    if (cfg.url) openWidget(cfg);
    else openSettings();
  });

  app.whenReady().then(() => {
    createTray();
    const cfg = loadConfig();
    applyAutostart(!!cfg.autostart);
    if (cfg.url) openWidget(cfg);
    else openSettings();
  });

  app.on("window-all-closed", () => {});
}
