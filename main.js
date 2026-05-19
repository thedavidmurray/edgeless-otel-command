const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

const JAEGER = 'http://localhost:16687';
const APP_PORT = 8766; // different from python proxy to avoid collision

let mainWindow;
let tray;
let server;

// ── Proxy server (embedded, no python needed) ─────────────────────
function startProxyServer() {
  server = http.createServer((req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    if (req.method === 'OPTIONS') { res.writeHead(200); res.end(); return; }

    // Serve static files
    if (req.url === '/' || req.url === '/index.html') {
      const htmlPath = path.join(__dirname, 'index.html');
      fs.readFile(htmlPath, (err, data) => {
        if (err) { res.writeHead(500); res.end('Error loading dashboard'); return; }
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(data);
      });
      return;
    }
    if (req.url === '/themes.css') {
      const cssPath = path.join(__dirname, 'themes.css');
      fs.readFile(cssPath, (err, data) => {
        if (err) { res.writeHead(500); res.end('Error loading themes'); return; }
        res.writeHead(200, { 'Content-Type': 'text/css' });
        res.end(data);
      });
      return;
    }

    // Proxy /jaeger/* to Jaeger
    if (req.url.startsWith('/jaeger/')) {
      const targetPath = req.url.slice('/jaeger'.length);
      const targetUrl = new URL(targetPath + (req.url.includes('?') ? '' : ''), JAEGER);
      if (req.url.includes('?')) {
        targetUrl.search = req.url.split('?')[1];
      }

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
    console.log(`[Proxy] Jaeger:    ${JAEGER}`);
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
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    title: 'EDGELESS :: OTEL COMMAND',
    backgroundColor: '#070a07',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false, // allow file:// to fetch localhost
    },
    titleBarStyle: 'hiddenInset', // macOS native feel with hidden title bar
    trafficLightPosition: { x: 12, y: 10 },
  });

  mainWindow.loadURL(`http://127.0.0.1:${APP_PORT}`);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    // mainWindow.webContents.openDevTools(); // uncomment for debug
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ── Tray ───────────────────────────────────────────────────────────
function createTray() {
  // Generate a simple 16x16 icon from text (we'll use a colored square)
  const iconPath = path.join(__dirname, 'assets', 'trayTemplate.png');
  let icon;
  if (fs.existsSync(iconPath)) {
    icon = nativeImage.createFromPath(iconPath);
  } else {
    // Fallback: create blank icon
    icon = nativeImage.createEmpty();
  }

  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show Command Center', click: () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      } else {
        createWindow();
      }
    }},
    { type: 'separator' },
    { label: 'Open Jaeger UI', click: () => {
      require('electron').shell.openExternal('http://localhost:16687');
    }},
    { type: 'separator' },
    { label: 'Quit', click: () => {
      app.quit();
    }},
  ]);
  tray.setToolTip('EDGELESS :: OTEL COMMAND');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    } else {
      createWindow();
    }
  });
}

// ── App lifecycle ──────────────────────────────────────────────────
app.whenReady().then(() => {
  startProxyServer();
  createWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // Keep alive in tray on macOS
  // app.quit();
});

app.on('quit', () => {
  if (server) server.close();
});

// ── IPC ────────────────────────────────────────────────────────────
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('get-jaeger-status', async () => {
  return new Promise((resolve) => {
    const req = http.get(`${JAEGER}/api/services`, { timeout: 3000 }, (res) => {
      resolve({ online: res.statusCode === 200 });
    });
    req.on('error', () => resolve({ online: false }));
    req.on('timeout', () => { req.destroy(); resolve({ online: false }); });
  });
});
