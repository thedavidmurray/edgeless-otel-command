const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('edgeless', {
  getVersion: () => ipcRenderer.invoke('get-app-version'),
  getJaegerStatus: () => ipcRenderer.invoke('get-jaeger-status'),
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (partial) => ipcRenderer.invoke('settings:set', partial),
  testJaeger: (url) => ipcRenderer.invoke('jaeger:test', url),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  // Plug-in IPC
  pluginsList: () => ipcRenderer.invoke('plugins:list'),
  pluginsToggle: (id, enabled) => ipcRenderer.invoke('plugins:toggle', id, enabled),
  pluginsRemove: (id) => ipcRenderer.invoke('plugins:remove', id),
  pluginsInstallLocal: (srcPath) => ipcRenderer.invoke('plugins:install-local', srcPath),
});

// Legacy alias for backward compatibility with v1.0.0 code
contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getJaegerStatus: () => ipcRenderer.invoke('get-jaeger-status'),
});
