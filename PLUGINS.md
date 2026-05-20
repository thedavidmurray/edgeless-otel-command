# Building Plug-ins for Edgeless OTel Command

This guide is for developers who want to extend Edgeless OTel Command with custom panels, anomaly rules, and themes. If you just want to use the app, you do not need this.

---

## Quick Start: Build Your First Plug-in

### Step 1: Scaffold from example

```bash
git clone https://github.com/edgeless-dev/edgeless-plugin-example.git ~/edgeless-plugin-hello
cd ~/edgeless-plugin-hello
```

The example plug-in has everything you need:
- `manifest.json` — declares what you register
- `index.js` — your code
- `README.md` — user-facing docs

### Step 2: Edit and test

```bash
# Change the plug-in id to your namespace
# Edit manifest.json:
#   "id": "myorg.plugin.hello"

# Write your panel or rule in index.js
# Use `edgeless.*` API (documented below)

# Install to the app:
mkdir -p ~/Library/Application\ Support/edgeless-otel-command/plugins
ln -s ~/edgeless-plugin-hello ~/Library/Application\ Support/edgeless-otel-command/plugins/myorg.plugin.hello
```

(On Windows: `%APPDATA%\edgeless-otel-command\plugins\`  
On Linux: `~/.config/edgeless-otel-command/plugins/`)

### Step 3: Reload and verify

Open Edgeless OTel Command. Press **Cmd+R** (macOS) or **Ctrl+Shift+R** (Windows/Linux) to reload all plug-ins.

Check **Settings** → **Installed Plug-ins** to see your plug-in listed. If there's an error, click the plug-in row to see the stack trace.

Done. You now have a live plug-in. 👋

---

## Anatomy of a Plug-in

Every plug-in is a folder containing these files:

```
my-plugin/
├── manifest.json          # required — metadata
├── index.js               # required — entry point
├── README.md              # recommended — user docs
├── icon.png               # optional — 64x64 logo
└── styles.css             # optional — scoped styles
```

### manifest.json

```json
{
  "id": "myorg.plugin.service-map",
  "name": "Service Map",
  "version": "1.0.0",
  "description": "Visualize service relationships from span data.",
  "author": "your-name",
  "homepage": "https://github.com/yourname/edgeless-plugin-service-map",
  "license": "MIT",
  "minAppVersion": "1.2.0",
  "contributes": {
    "panels": [
      { "id": "service-map", "label": "Service Map" }
    ],
    "anomalyRules": [
      { "id": "service-map.orphan", "label": "Orphaned service" }
    ],
    "themes": [],
    "alertSinks": []
  }
}
```

**Required fields:**
- `id` — unique identifier in dotted form: `<org>.<plugin>.<feature>`. All contributions must use this prefix.
- `name` — display name (shown in settings)
- `version` — semver (`1.0.0`)
- `minAppVersion` — oldest app version this plug-in works with (e.g., `1.2.0`)

**Optional:**
- `author`, `license`, `homepage`, `description` — metadata

**`contributes`:**
- `panels` — list of panels you register (each has `id` and `label`)
- `anomalyRules` — list of anomaly detectors
- `themes` — list of themes (deferred to v2.0)
- `alertSinks` — alert integrations (deferred to v1.3.0)

### index.js

The entry point. Export a single async function named `default`:

```js
export default function activate(edgeless) {
  // Register your panels, anomalies, themes here.
  // Called once when the plug-in loads.
  // Throws on error — errors are caught and logged.
}
```

The `edgeless` object is your API. See "The `edgeless` Host API" below.

### README.md

Document what your plug-in does, how to install it, and any configuration. Users read this.

Example:
```markdown
# Service Map

Visualizes service relationships from OpenTelemetry span parent-child references.

## Install

1. Download the latest release from GitHub
2. Unzip into `~/.config/edgeless-otel-command/plugins/`
3. Restart the app

## Usage

The panel appears in the main dashboard. It auto-detects services from your Jaeger trace data.

## Config

None. Just install and go.
```

---

## Manifest Reference

### Top-level fields

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `id` | string | yes | `"edgeless.plugin.profiler"` |
| `name` | string | yes | `"Profiler"` |
| `version` | string | yes | `"1.2.3"` |
| `description` | string | no | `"CPU flame graph panel"` |
| `author` | string | no | `"Alice"` |
| `homepage` | string | no | `"https://..."` |
| `license` | string | no | `"MIT"` |
| `minAppVersion` | string | yes | `"1.2.0"` |
| `contributes` | object | yes | See below |

### `contributes.panels`

Array of objects. Each object:

```json
{
  "id": "profiler-flame",
  "label": "Flame Graph"
}
```

- `id` — unique within your plug-in (prepend your plugin id: `edgeless.plugin.profiler.flame`)
- `label` — displayed in the panel list

### `contributes.anomalyRules`

Array of objects. Each object:

```json
{
  "id": "profiler.cpu-spike",
  "label": "CPU spike detected"
}
```

Same structure as panels. Register the logic in `index.js` with `edgeless.anomalies.register()`.

### `contributes.themes`

Not yet active. Deferred to v2.0.

### `contributes.alertSinks`

Not yet active. Deferred to v1.3.0.

---

## The `edgeless` Host API

Your `activate(edgeless)` function receives this API object. All methods are stable and documented here.

### `edgeless.app`

```js
edgeless.app.version        // "1.2.0"
edgeless.app.log(msg, level)
```

**`log(msg, level?)`** — Write a message to the plug-in log (visible in Settings).

- `msg` (string) — message
- `level` (string, optional) — `'info'`, `'warn'`, or `'error'`. Defaults to `'info'`.

Example:
```js
edgeless.app.log('Plug-in loaded', 'info');
edgeless.app.log('No traces found', 'warn');
edgeless.app.log('Failed to connect', 'error');
```

---

### `edgeless.panels`

```js
edgeless.panels.register(id, def)
edgeless.panels.list()
```

**`register(id, def)`** — Register a panel.

- `id` (string) — must start with your plugin id (e.g., `"myorg.plugin.profiler.flame"`)
- `def` (object) — panel definition (see below)

Panel definition:

```js
{
  label: "Flame Graph",
  defaultPosition: "top-left",  // optional: top-left, top-mid, top-right, bottom-left, bottom-mid, bottom-right
  minSize: { w: 200, h: 150 },  // optional: minimum width and height in pixels
  
  render(container, ctx) {
    // container: HTMLElement you own (cleared between renders)
    // ctx: { traces, byService, rollup, anomalies, settings, serviceFilter, timeWindowMin, lib }
    
    container.innerHTML = '<div>Panel content</div>';
  },
  
  destroy() {
    // optional cleanup: called when panel is closed or plug-in unloads
  }
}
```

**`list()`** — Returns array of all registered panels (built-in and plug-in).

```js
const panels = edgeless.panels.list();
// [
//   { id: 'edgeless.builtin.traces', label: 'Recent Traces' },
//   { id: 'myorg.plugin.map', label: 'Service Map' }
// ]
```

---

### `edgeless.anomalies`

```js
edgeless.anomalies.register(id, def)
edgeless.anomalies.list()
```

**`register(id, def)`** — Register an anomaly detector rule.

- `id` (string) — must start with your plugin id
- `def` (object) — anomaly definition (see below)

Anomaly definition:

```js
{
  label: "High error rate",
  severity: "crit",  // "crit", "warn", or "ok"
  
  detect(ctx) {
    // ctx: { traces, byService, timeWindowMin }
    // return [{ kind, title, detail, service, traceID }, ...] or []
    
    const errors = ctx.traces.filter(t => t.error).length;
    const errorRate = errors / ctx.traces.length;
    
    if (errorRate > 0.5) {
      return [{
        kind: 'error-rate',
        title: `Error rate: ${(errorRate * 100).toFixed(1)}%`,
        detail: `${errors} of ${ctx.traces.length} traces failed`,
        service: 'your-service',
        traceID: ctx.traces[0]?.traceID
      }];
    }
    return [];
  }
}
```

**`list()`** — Returns array of all registered anomaly rules.

---

### `edgeless.themes`

```js
edgeless.themes.register(id, css)
```

**`register(id, css)`** — Register a theme (CSS variable overrides).

- `id` (string) — must start with your plugin id
- `css` (string) — CSS that overrides theme variables

Example:
```js
edgeless.themes.register('myorg.plugin.dark-blue', `
  :root {
    --color-primary: #0066ff;
    --color-text: #e0e0e0;
    --color-bg: #0a0a0a;
  }
`);
```

Available CSS variables (see `index.html` for full list):
- `--color-primary`, `--color-secondary`, `--color-accent`
- `--color-text`, `--color-bg`, `--color-border`
- `--crt-scanline-opacity`, `--crt-glow-intensity`, `--border-radius`

---

### `edgeless.router`

```js
edgeless.router.navigate(hash)
edgeless.router.current()
```

**`navigate(hash)`** — Navigate to a route (like location.hash).

```js
edgeless.router.navigate('#/trace/abc123');
edgeless.router.navigate('#/service/my-service');
```

**`current()`** — Get the current route.

```js
const route = edgeless.router.current();
// { view: 'trace', params: { id: 'abc123' } }
// { view: 'service', params: { name: 'my-service' } }
```

---

### `edgeless.jaeger`

```js
edgeless.jaeger.fetch(path)
edgeless.jaeger.fetchTrace(id)
```

**`fetch(path)`** — Make a proxied request to your Jaeger instance.

- `path` (string) — `/api/...` path relative to Jaeger root

```js
const services = await edgeless.jaeger.fetch('/api/services');
// { data: ['service-1', 'service-2', ...] }
```

**`fetchTrace(id)`** — Fetch a single trace by ID.

```js
const trace = await edgeless.jaeger.fetchTrace('abc123');
// { traceID, spans: [...], ...}
// Returns null if not found
```

---

### `edgeless.lib`

Utility functions for formatting and color generation.

```js
edgeless.lib.fmtDur(microseconds)      // "1.23ms", "456µs", etc.
edgeless.lib.fmtAge(microseconds)      // "5 min ago", "2.3 sec ago"
edgeless.lib.hashColor(string)         // "#abc123"
edgeless.lib.tagsToObj(tags)           // { key: value, ... }
```

Example:
```js
const dur = edgeless.lib.fmtDur(1500000);  // "1.5ms"
const age = edgeless.lib.fmtAge(300000000);  // "5 min ago"
const color = edgeless.lib.hashColor('my-service');  // stable color
const obj = edgeless.lib.tagsToObj([
  { key: 'env', value: 'prod' },
  { key: 'region', value: 'us-west' }
]);
// { env: 'prod', region: 'us-west' }
```

---

### `edgeless.storage`

Persistent key-value storage scoped to your plug-in.

```js
edgeless.storage.get(key)
edgeless.storage.set(key, value)
```

**`get(key)`** — Retrieve a stored value. Returns Promise.

```js
const saved = await edgeless.storage.get('user-prefs');
// null if not found
```

**`set(key, value)`** — Store a value. Returns Promise.

```js
await edgeless.storage.set('user-prefs', { theme: 'dark' });
```

Values are JSON-serializable (objects, arrays, strings, numbers, booleans).

---

### `edgeless.events`

Subscribe to app events.

```js
edgeless.events.on(event, callback)  // returns unsubscribe function
```

Available events:
- `'tick'` — fires every time the dashboard polls Jaeger (default 10s)
- `'trace-selected'` — user clicked a trace
- `'service-selected'` — user selected a service filter

**`on(event, callback)`** — Subscribe to an event.

- `event` (string) — event name
- `callback` (function) — called with event data

Returns unsubscribe function:

```js
const unsubscribe = edgeless.events.on('tick', (data) => {
  console.log('Poll happened', data.timestamp);
});

// Later, stop listening:
unsubscribe();
```

---

## Building a Panel

A panel is a visual component that renders trace data.

### Example 1: Static info panel

```js
export default function activate(edgeless) {
  edgeless.panels.register('myorg.plugin.info.about', {
    label: 'About',
    
    render(container) {
      container.innerHTML = `
        <div style="padding: 12px; font-family: monospace; color: #0f0;">
          <div>Edgeless OTel Command</div>
          <div>App version: ${edgeless.app.version}</div>
          <div>Plug-in API v1 (stable)</div>
        </div>
      `;
    }
  });
}
```

### Example 2: List clickable traces

```js
export default function activate(edgeless) {
  edgeless.panels.register('myorg.plugin.traces.list', {
    label: 'All Traces',
    minSize: { w: 300, h: 200 },
    
    render(container, ctx) {
      const html = ctx.traces.map(trace => `
        <div 
          style="padding: 8px; cursor: pointer; border-bottom: 1px solid #333;"
          onclick="window.clickTrace('${trace.traceID}')"
        >
          <div style="font-weight: bold;">${trace.operationName}</div>
          <div style="font-size: 0.8em; color: #666;">
            ${edgeless.lib.fmtDur(trace.duration)}
          </div>
        </div>
      `).join('');
      
      container.innerHTML = html;
      
      // Make traces clickable
      window.clickTrace = (id) => {
        edgeless.router.navigate(`#/trace/${id}`);
      };
    }
  });
}
```

### Example 3: Fetch and display trace details

```js
export default function activate(edgeless) {
  edgeless.panels.register('myorg.plugin.trace-detail', {
    label: 'Trace Detail',
    
    async render(container, ctx) {
      const route = edgeless.router.current();
      if (route.view !== 'trace') {
        container.innerHTML = '<div style="padding: 12px; color: #666;">Select a trace</div>';
        return;
      }
      
      const trace = await edgeless.jaeger.fetchTrace(route.params.id);
      if (!trace) {
        container.innerHTML = '<div style="color: red;">Trace not found</div>';
        return;
      }
      
      const html = `
        <div style="padding: 12px; font-family: monospace; font-size: 0.9em;">
          <div><strong>Trace ID:</strong> ${trace.traceID}</div>
          <div><strong>Spans:</strong> ${trace.spans.length}</div>
          <div><strong>Duration:</strong> ${edgeless.lib.fmtDur(trace.duration)}</div>
          <div style="margin-top: 8px;">
            ${trace.spans.map(span => `
              <div style="border-left: 3px solid ${edgeless.lib.hashColor(span.operationName)}; padding: 4px 8px; margin: 4px 0;">
                ${span.operationName} (${edgeless.lib.fmtDur(span.duration)})
              </div>
            `).join('')}
          </div>
        </div>
      `;
      
      container.innerHTML = html;
    }
  });
}
```

---

## Building an Anomaly Rule

An anomaly detector runs every poll (default every 10s) and returns flagged issues.

### Example: Error rate spike

```js
export default function activate(edgeless) {
  edgeless.anomalies.register('myorg.plugin.alerts.error-rate', {
    label: 'High error rate',
    severity: 'crit',
    
    detect(ctx) {
      const { traces, byService, timeWindowMin } = ctx;
      
      if (traces.length === 0) return [];
      
      const errorCount = traces.filter(t => t.error).length;
      const errorRate = errorCount / traces.length;
      
      const anomalies = [];
      
      if (errorRate > 0.5) {
        anomalies.push({
          kind: 'error-rate-crit',
          title: `${(errorRate * 100).toFixed(0)}% errors`,
          detail: `${errorCount}/${traces.length} traces failed in last ${timeWindowMin} min`,
          service: 'primary',
          traceID: traces.find(t => t.error)?.traceID
        });
      }
      
      return anomalies;
    }
  });
}
```

**Severity guide:**
- `'crit'` — fire alarm. User should act immediately. Example: all requests failing.
- `'warn'` — yellow light. Notable but not catastrophic. Example: latency spike.
- `'ok'` — everything nominal (rarely used; omit rules that always return `[]`).

---

## Building a Theme

A theme is a set of CSS variable overrides.

```js
export default function activate(edgeless) {
  edgeless.themes.register('myorg.plugin.theme.cyberpunk-purple', `
    :root {
      --color-primary: #ff00ff;
      --color-secondary: #00ffff;
      --color-accent: #ffff00;
      --color-text: #00ff00;
      --color-bg: #0a000a;
      --color-border: #ff00ff;
      --crt-scanline-opacity: 0.15;
      --crt-glow-intensity: 2;
      --border-radius: 2px;
    }
  `);
}
```

Visit **Settings** → **Themes** to switch at runtime. Changes apply instantly.

---

## Local Development Workflow

### Symlink your plug-in

```bash
# macOS / Linux
mkdir -p ~/Library/Application\ Support/edgeless-otel-command/plugins
ln -s /path/to/your/plugin ~/Library/Application\ Support/edgeless-otel-command/plugins/myorg.plugin.name

# Windows
mkdir "%APPDATA%\edgeless-otel-command\plugins"
mklink /D "%APPDATA%\edgeless-otel-command\plugins\myorg.plugin.name" "C:\path\to\your\plugin"
```

### Reload the app

Press **Cmd+R** (macOS) or **Ctrl+Shift+R** (Windows/Linux) to reload all plug-ins without restarting the app.

### View errors

Open **Settings** → **Installed Plug-ins**. Click on your plug-in. Errors appear in a collapsible panel with the full stack trace.

### Debug with DevTools

Press **Cmd+Option+I** (macOS) or **Ctrl+Shift+I** (Windows/Linux) to open the developer console.

All `edgeless.app.log()` calls appear there. You can also use `console.log()` directly in your code.

---

## Publishing to the Community Registry (Coming in v1.3.0)

Community plug-in discovery is coming in v1.3.0. Here is the model:

1. **Create a GitHub repo** for your plug-in
2. **Tag a release** with the plug-in folder zipped (no node_modules, .git, etc.)
3. **Fork** `edgeless-dev/edgeless-otel-plugins` (the registry)
4. **Add an entry** to `plugins.json`:

```json
{
  "id": "myorg.plugin.awesome",
  "name": "Awesome Panel",
  "description": "Does awesome things with traces",
  "repo": "myname/edgeless-plugin-awesome",
  "tags": ["panel", "traces"],
  "minAppVersion": "1.2.0",
  "latestVersion": "1.0.0"
}
```

5. **Open a PR** against the registry
6. **Maintainer reviews** (security, functionality, license)
7. **Merged** → appears in app's "Browse Plugins" browser (v1.3.0)

Once in the registry, users can install via the app without downloading manually.

---

## Trust Model & Responsibilities

Plug-ins run with **full JavaScript access** to the renderer. They cannot:
- Read files outside their own folder
- Call Electron APIs directly
- Access other plug-ins' storage

They **can**:
- Make HTTP requests (including to external APIs)
- Read and modify DOM within their panel container
- Store data in their scoped storage
- Call any `edgeless.*` API method

**Install only from sources you trust.** A malicious plug-in could:
- Make requests to exfiltrate data
- Run compute-heavy code and freeze the UI
- Store/access data via the `storage` API

Before installing a community plug-in, check:
- The repository is public and auditable
- The author has a track record
- The README explains what it does
- The license is permissive (MIT, Apache, etc.)

---

## API Stability Promise

Methods documented here are **stable** and will not break in minor releases (e.g., 1.2.0 → 1.3.0).

Future additions will be marked `edgeless.experimental.*` to signal "subject to change." Breaking changes only happen in major version bumps (1.x → 2.0).

Plug-ins can check the app version:

```js
if (edgeless.app.version.startsWith('1.')) {
  // Use v1 API
}
```

---

## FAQ

**Can I use TypeScript?**

Yes. Compile to JavaScript first, then deploy the `.js` file. No build tools are required by the host — you handle the build step locally.

```bash
npx tsc index.ts --target es2020 --module es2020
# produces index.js
```

**Can plug-ins talk to each other?**

Not directly. Use `edgeless.events.on()` for loose coupling. For example, one plug-in publishes a 'custom-event' via the host, and another listens. This is deferred to v1.3.0. For now, design plug-ins to work independently.

**How do I debug?**

Press **Cmd+Option+I** (macOS) or **Ctrl+Shift+I** (Windows/Linux) to open the developer console. Your `console.log()` calls and `edgeless.app.log()` messages appear there.

For detailed error messages, check **Settings** → **Installed Plug-ins** and click on your plug-in row.

**What if my plug-in crashes during rendering?**

The error is caught, logged, and your panel shows a warning message. The app does not crash. Fix the error, press reload, and try again.

**Can I make HTTP requests to external services?**

Yes, via `fetch()`. Be transparent about it in your README. Example: a plug-in that fetches exchange rates from an API should document that it makes external requests.

**How do I store user preferences?**

Use `edgeless.storage.set()` and `edgeless.storage.get()`. Storage is scoped to your plug-in and persists across app restarts.

```js
// Save
await edgeless.storage.set('user-theme', 'dark');

// Load
const theme = await edgeless.storage.get('user-theme');
```

---

## Reference

- **Architecture:** See `docs/v1.2.0-plugin-architecture.md` for design rationale
- **Example plug-in:** https://github.com/edgeless-dev/edgeless-plugin-example
- **Registry:** https://github.com/edgeless-dev/edgeless-otel-plugins (v1.3.0)
- **Main app:** https://github.com/edgeless-dev/edgeless-otel-command

---

**Last updated:** May 2026 | Edgeless OTel Command v1.2.0
