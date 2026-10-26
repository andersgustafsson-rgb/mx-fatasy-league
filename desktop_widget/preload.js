const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("mxWidget", {
  getConfig: () => ipcRenderer.invoke("get-config"),
  saveConfig: (cfg) => ipcRenderer.invoke("save-config", cfg),
  openWidget: () => ipcRenderer.invoke("open-widget"),
  hideWidget: () => ipcRenderer.invoke("hide-widget"),
  setAlwaysOnTop: (on) => ipcRenderer.invoke("set-always-on-top", !!on),
  openSettings: () => ipcRenderer.invoke("open-settings"),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  isDesktopApp: true,
});
