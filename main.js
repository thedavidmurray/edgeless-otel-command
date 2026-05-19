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
    };
    if (req.url === '/theme-builder.html') {
      const htmlPath = path.join(__dirname, 'theme-builder.html');
      fs.readFile(htmlPath, (err, data) => {
        if (err) { res.writeHead(500); res.end('Error loading theme builder'); return; }
        res.writeHead(200, { 'Content-Type': 'text/html' });
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

ipcMain.handle('open-external', (_evt, url) => {
  require('electron').shell.openExternal(url);
});
