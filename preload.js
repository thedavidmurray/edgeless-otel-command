const { contextBridge, ipcRenderer } = require('electron');

// Expose a minimal safe API to the renderer
contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getJaegerStatus: () => ipcRenderer.invoke('get-jaeger-status'),
});
