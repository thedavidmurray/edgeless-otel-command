const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const APP_PORT = 8766;
const DEFAULT_JAEGER = 'http://localhost:16687';

// Settings persistence
const settingsPath = () => path.join(app.getPath('userData'), 'settings.json');

const DEFAULT_SETTINGS = {
  jaegerUrl: DEFAULT_JAEGER,
  serviceFilter: null,          // null = all services
  refreshIntervalMs: 10000,
  defaultTheme: 'phosphor',
  anomalyThresholds: {
    ghostAgentMin: 30,          // a service silent this long -> ghost
    phantomStallMin: 30,        // a non-leaf span open this long -> phantom
    loopThreshold: 5,           // N spans of same op...
    loopWindowSec: 300,         // ...within this window from one service -> loop
  },
  firstRunComplete: false,
};

function readSettings() {
  try {
    const raw = fs.readFileSync(settingsPath(), 'utf8');
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function writeSettings(s) {
  try {
    fs.mkdirSync(path.dirname(settingsPath()), { recursive: true });
    fs.writeFileSync(settingsPath(), JSON.stringify(s, null, 2));
    return true;
  } catch (e) {
    console.error('[Settings] write failed:', e.message);
    return false;
  }
}

let mainWindow;
let tray;
let server;
let currentJaeger = DEFAULT_JAEGER;

// ── Proxy server (embedded) ────────────────────────────────────────
function startProxyServer() {
  server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

    // Static files
    const staticRoutes = {
      '/': { file: 'index.html', mime: 'text/html' },
      '/index.html': { file: 'index.html', mime: 'text/html' },
      '/themes.css': { file: 'themes.css', mime: 'text/css' },
      '/app.js': { file: 'app.js', mime: 'application/javascript' },
      '/theme-builder.html': { file: 'theme-builder.html', mime: 'text/html' },
    };
    if (staticRoutes[req.url]) {
      const { file, mime } = staticRoutes[req.url];
      fs.readFile(path.join(__dirname, file), (err, data) => {
        if (err) { res.writeHead(500); res.end(`Error loading ${file}`); return; }
        res.writeHead(200, { 'Content-Type': mime });
        res.end(data);
      });
      return;
    }

    // Serve plug-in files: /plugins/<id>/<filename>
    if (req.url.startsWith('/plugins/')) {
      const safe = req.url.replace(/\.\.\//g, '');           // strip parent traversal
      const subPath = safe.slice('/plugins/'.length);
      const filePath = path.join(pluginsDir(), subPath);
      if (!filePath.startsWith(pluginsDir())) {
        res.writeHead(403); res.end('forbidden'); return;
      }
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end('not found'); return; }
        const ext = path.extname(filePath).toLowerCase();
        const mimeMap = {
          '.js':   'application/javascript',
          '.json': 'application/json',
          '.css':  'text/css',
          '.html': 'text/html',
          '.png':  'image/png',
          '.svg':  'image/svg+xml',
          '.md':   'text/markdown',
        };
        res.writeHead(200, { 'Content-Type': mimeMap[ext] || 'application/octet-stream' });
        res.end(data);
      });
      return;
    }

    // Proxy /jaeger/* to the configured Jaeger backend
    if (req.url.startsWith('/jaeger/')) {
      const targetPath = req.url.slice('/jaeger'.length);
      const targetUrl = new URL(targetPath, currentJaeger);
      const client = targetUrl.protocol === 'https:' ? https : http;
      const proxyReq = client.request(targetUrl, {
        method: req.method,
        headers: { ...req.headers, host: targetUrl.host },
      }, (proxyRes) => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      });
      proxyReq.on('error', (err) => {
        res.writeHead(502, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      });
      req.pipe(proxyReq);
      return;
    }

    res.writeHead(404); res.end('Not found');
  });

  server.listen(APP_PORT, '127.0.0.1', () => {
    console.log(`[Proxy] Dashboard: http://127.0.0.1:${APP_PORT}`);
    console.log(`[Proxy] Jaeger:    ${currentJaeger}`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`[Proxy] Port ${APP_PORT} already in use, assuming another instance is running`);
    } else {
      console.error('[Proxy] Server error:', err);
    }
  });
}

// ── Window ─────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 1000, minHeight: 600,
    title: 'EDGELESS :: OTEL COMMAND',
    backgroundColor: '#070a07',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
    },
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 12, y: 10 },
  });

  mainWindow.loadURL(`http://127.0.0.1:${APP_PORT}`);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (process.env.EDGELESS_DEVTOOLS === '1') mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  // Forward renderer console to main log so crashes are visible without devtools.
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    const levels = { 0: 'log', 1: 'warning', 2: 'error', 3: 'info' };
    console.log(`[renderer ${levels[level] || level}] ${message} (${sourceId}:${line})`);
  });
  mainWindow.webContents.on('render-process-gone', (_e, details) => {
    console.error('[renderer crash]', details);
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Tray ───────────────────────────────────────────────────────────
function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'trayTemplate.png');
  let icon = fs.existsSync(iconPath) ? nativeImage.createFromPath(iconPath) : nativeImage.createEmpty();

  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show Command Center', click: () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      } else { createWindow(); }
    }},
    { type: 'separator' },
    { label: 'Open Jaeger UI', click: () => {
      require('electron').shell.openExternal(currentJaeger);
    }},
    { label: 'Theme Builder', click: () => {
      require('electron').shell.openExternal('http://127.0.0.1:' + APP_PORT + '/theme-builder.html');
    }},
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);
  tray.setToolTip('EDGELESS :: OTEL COMMAND');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    } else { createWindow(); }
  });
}

// ── App lifecycle ──────────────────────────────────────────────────
app.whenReady().then(() => {
  const settings = readSettings();
  currentJaeger = settings.jaegerUrl || DEFAULT_JAEGER;
  startProxyServer();
  createWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // keep alive in tray
});

app.on('quit', () => { if (server) server.close(); });

// ── IPC ────────────────────────────────────────────────────────────
ipcMain.handle('get-app-version', () => app.getVersion());

ipcMain.handle('get-jaeger-status', async () => {
  return new Promise((resolve) => {
    const req = http.get(`${currentJaeger}/api/services`, { timeout: 3000 }, (res) => {
      resolve({ online: res.statusCode === 200, url: currentJaeger });
    });
    req.on('error', () => resolve({ online: false, url: currentJaeger }));
    req.on('timeout', () => { req.destroy(); resolve({ online: false, url: currentJaeger }); });
  });
});

ipcMain.handle('settings:get', () => readSettings());

ipcMain.handle('settings:set', (_evt, partial) => {
  const next = { ...readSettings(), ...partial };
  const ok = writeSettings(next);
  if (ok && next.jaegerUrl && next.jaegerUrl !== currentJaeger) {
    currentJaeger = next.jaegerUrl;
    console.log(`[Settings] Jaeger URL switched to ${currentJaeger}`);
  }
  return { ok, settings: next };
});

// Test connection to an arbitrary Jaeger URL (used by settings wizard)
ipcMain.handle('jaeger:test', async (_evt, urlStr) => {
  return new Promise((resolve) => {
    try {
      const u = new URL('/api/services', urlStr);
      const client = u.protocol === 'https:' ? https : http;
      const req = client.get(u.toString(), { timeout: 3000 }, (res) => {
        let body = '';
        res.on('data', (c) => { body += c.toString(); });
        res.on('end', () => {
          if (res.statusCode === 200) {
            try {
              const j = JSON.parse(body);
              resolve({ ok: true, services: (j.data || []).length });
            } catch {
              resolve({ ok: false, error: 'invalid JSON response' });
            }
          } else {
            resolve({ ok: false, error: `HTTP ${res.statusCode}` });
          }
        });
      });
      req.on('error', (err) => resolve({ ok: false, error: err.message }));
      req.on('timeout', () => { req.destroy(); resolve({ ok: false, error: 'timeout' }); });
    } catch (e) {
      resolve({ ok: false, error: e.message });
    }
  });
});

// ── Plug-in system ─────────────────────────────────────────────────
const pluginsDir = () => path.join(app.getPath('userData'), 'plugins');

const MANIFEST_REQUIRED = ['id', 'name', 'version', 'minAppVersion'];

function validateManifest(m, pluginPath) {
  for (const k of MANIFEST_REQUIRED) {
    if (!m[k]) return { ok: false, error: `missing required field: ${k}` };
  }
  if (!/^[a-z0-9.-]+$/i.test(m.id)) return { ok: false, error: `invalid id format: ${m.id}` };
  if (!fs.existsSync(path.join(pluginPath, 'index.js'))) return { ok: false, error: 'index.js not found' };
  // basic minAppVersion semver check (major-only)
  const appMajor = parseInt(app.getVersion().split('.')[0], 10);
  const minMajor = parseInt(String(m.minAppVersion).split('.')[0], 10);
  if (!Number.isNaN(minMajor) && minMajor > appMajor) {
    return { ok: false, error: `requires app ≥ ${m.minAppVersion}, this is ${app.getVersion()}` };
  }
  return { ok: true };
}

function discoverPlugins() {
  const dir = pluginsDir();
  try { fs.mkdirSync(dir, { recursive: true }); } catch {}
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const out = [];
  for (const e of entries) {
    if (!e.isDirectory()) continue;
    const pluginPath = path.join(dir, e.name);
    const manifestPath = path.join(pluginPath, 'manifest.json');
    if (!fs.existsSync(manifestPath)) continue;
    let manifest;
    try {
      manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    } catch (err) {
      out.push({ id: e.name, error: `manifest.json parse error: ${err.message}`, enabled: false });
      continue;
    }
    const v = validateManifest(manifest, pluginPath);
    const disabledList = readSettings().disabledPlugins || [];
    out.push({
      ...manifest,
      pluginPath,
      enabled: v.ok && !disabledList.includes(manifest.id),
      error: v.ok ? null : v.error,
    });
  }
  return out;
}

ipcMain.handle('plugins:list', () => discoverPlugins());

ipcMain.handle('plugins:toggle', (_evt, pluginId, enabled) => {
  const s = readSettings();
  const disabled = new Set(s.disabledPlugins || []);
  if (enabled) disabled.delete(pluginId);
  else disabled.add(pluginId);
  s.disabledPlugins = [...disabled];
  writeSettings(s);
  return { ok: true, disabledPlugins: s.disabledPlugins };
});

ipcMain.handle('plugins:remove', (_evt, pluginId) => {
  // Find plugin path by id
  const all = discoverPlugins();
  const p = all.find(x => x.id === pluginId);
  if (!p || !p.pluginPath) return { ok: false, error: 'not found' };
  try {
    fs.rmSync(p.pluginPath, { recursive: true, force: true });
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

ipcMain.handle('plugins:install-local', (_evt, srcPath) => {
  // Copy a local folder (containing manifest.json + index.js) into pluginsDir/<id>
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(srcPath, 'manifest.json'), 'utf8'));
    const v = validateManifest(manifest, srcPath);
    if (!v.ok) return { ok: false, error: v.error };
    const dest = path.join(pluginsDir(), manifest.id);
    fs.mkdirSync(pluginsDir(), { recursive: true });
    if (fs.existsSync(dest)) fs.rmSync(dest, { recursive: true, force: true });
    fs.cpSync(srcPath, dest, { recursive: true });
    return { ok: true, id: manifest.id };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// Default registry. User can override in settings.
const DEFAULT_REGISTRY_URL =
  'https://raw.githubusercontent.com/thedavidmurray/edgeless-otel-plugins-registry/main/plugins.json';

ipcMain.handle('plugins:fetch-registry', async () => {
  const settings = readSettings();
  const url = settings.registryUrl || DEFAULT_REGISTRY_URL;
  return new Promise((resolve) => {
    try {
      const u = new URL(url);
      const client = u.protocol === 'https:' ? https : http;
      const req = client.get(u.toString(), { timeout: 10000 }, (res) => {
        if (res.statusCode !== 200) {
          resolve({ ok: false, error: `HTTP ${res.statusCode}` });
          return;
        }
        let body = '';
        res.on('data', (c) => { body += c.toString(); });
        res.on('end', () => {
          try {
            const reg = JSON.parse(body);
            resolve({ ok: true, registry: reg, fetchedFrom: url, fetchedAt: new Date().toISOString() });
          } catch (e) {
            resolve({ ok: false, error: `invalid JSON: ${e.message}` });
          }
        });
      });
      req.on('error', (err) => resolve({ ok: false, error: err.message }));
      req.on('timeout', () => { req.destroy(); resolve({ ok: false, error: 'timeout' }); });
    } catch (e) {
      resolve({ ok: false, error: e.message });
    }
  });
});

// Install a plug-in by cloning its GitHub repo into pluginsDir/<id>.
// Validates manifest after clone; on failure, removes the directory.
ipcMain.handle('plugins:install-from-repo', async (_evt, { repo, id }) => {
  const { spawn } = require('child_process');
  if (!repo || !/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(repo)) {
    return { ok: false, error: 'invalid repo format — expected "owner/name"' };
  }
  const dest = path.join(pluginsDir(), id);
  try { fs.mkdirSync(pluginsDir(), { recursive: true }); } catch {}
  if (fs.existsSync(dest)) {
    return { ok: false, error: `already installed: ${id} (remove first to reinstall)` };
  }
  const cloneUrl = `https://github.com/${repo}.git`;
  return new Promise((resolve) => {
    const child = spawn('git', ['clone', '--depth=1', cloneUrl, dest], { stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', (c) => { stderr += c.toString(); });
    child.on('close', (code) => {
      if (code !== 0) {
        // cleanup partial
        try { fs.rmSync(dest, { recursive: true, force: true }); } catch {}
        resolve({ ok: false, error: `git clone failed (${code}): ${stderr.trim().slice(0, 200)}` });
        return;
      }
      // Validate manifest
      try {
        const mPath = path.join(dest, 'manifest.json');
        if (!fs.existsSync(mPath)) {
          fs.rmSync(dest, { recursive: true, force: true });
          resolve({ ok: false, error: 'cloned repo has no manifest.json' });
          return;
        }
        const m = JSON.parse(fs.readFileSync(mPath, 'utf8'));
        if (m.id !== id) {
          fs.rmSync(dest, { recursive: true, force: true });
          resolve({ ok: false, error: `manifest id "${m.id}" does not match registry id "${id}"` });
          return;
        }
        const v = validateManifest(m, dest);
        if (!v.ok) {
          fs.rmSync(dest, { recursive: true, force: true });
          resolve({ ok: false, error: v.error });
          return;
        }
        resolve({ ok: true, id: m.id, name: m.name, version: m.version });
      } catch (e) {
        try { fs.rmSync(dest, { recursive: true, force: true }); } catch {}
        resolve({ ok: false, error: `validation: ${e.message}` });
      }
    });
    child.on('error', (err) => {
      resolve({ ok: false, error: `git not available: ${err.message}` });
    });
  });
});

ipcMain.handle('open-external', (_evt, url) => {
  require('electron').shell.openExternal(url);
});
