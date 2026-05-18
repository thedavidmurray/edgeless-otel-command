# Setup Guide

## What You Need

1. **Jaeger all-in-one** running and receiving traces
2. **Any OTel-instrumented service** exporting spans to that Jaeger
3. **This app** pointing at that Jaeger

That is it. No Hermes required. No Edgeless-specific infra. Any service that emits OpenTelemetry to Jaeger will show up.

---

## 1. Start Jaeger

### Docker (recommended)

```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:1.60
```

### Binary

Download from https://www.jaegertracing.io/download/ and run `./jaeger-all-in-one`.

Verify: open http://localhost:16686 and see the Jaeger UI.

---

## 2. Wire Your Service to Jaeger

### Python

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "my-service",   # <-- your service name
    "service.version": "1.0.0",
})

provider = TracerProvider(resource=resource)
exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Use it
tracer = trace.get_tracer("my-app")
with tracer.start_as_current_span("my.operation"):
    do_work()
```

### Node.js

```javascript
const { NodeSDK } = require("@opentelemetry/sdk-node");
const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-grpc");

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({ url: "http://localhost:4317" }),
  serviceName: "my-service",
});
sdk.start();
```

### Go

```go
import (
    "go.opentelemetry.io/otel/sdk/resource"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
)

exp, _ := otlptracegrpc.New(ctx, otlptracegrpc.WithEndpoint("localhost:4317"), otlptracegrpc.WithInsecure())
provider := sdktrace.NewTracerProvider(
    sdktrace.WithBatcher(exp),
    sdktrace.WithResource(resource.NewWithAttributes("my-service")),
)
```

### Java / .NET / Rust / etc.

Any language with an OTLP exporter works. Point at `http://localhost:4317` (gRPC) or `http://localhost:4318` (HTTP).

---

## 3. Install the Dashboard App

### macOS

Download `.dmg` from [Releases](https://github.com/thedavidmurray/edgeless-otel-command/releases), drag to Applications.

### Windows

Download `.exe` installer from Releases, run it.

### Linux

Download `.AppImage`, make executable, run:

```bash
chmod +x EDGELESS_OTEL_Command-x.x.x.AppImage
./EDGELESS_OTEL_Command-x.x.x.AppImage
```

---

## 4. Point App at Your Jaeger (if not localhost:16686)

The app proxies to `http://localhost:16687` by default.

To change:

```bash
# macOS / Linux
export OTEL_DASHBOARD_JAEGER=http://your-jaeger-host:16686

# Windows
set OTEL_DASHBOARD_JAEGER=http://your-jaeger-host:16686
```

Then launch the app.

---

## 5. What You Will See

The dashboard auto-discovers **all services** registered in Jaeger. The left panels default to the service named `edgeless-swarm` if present. If not, it shows the first service alphabetically.

| Panel | What it shows | Agnostic? |
|-------|---------------|-----------|
| **Throughput & Metrics** | Trace/span counts, error rate, active agent | Yes — agent/model labels show "unknown" if your spans do not carry them |
| **Donut chart** | Operation distribution by span count | Yes — auto-colored by hash of op name |
| **Operation Breakdown** | Horizontal bar chart of all operations | Yes |
| **Span Throughput waveform** | Real-time spans/second from poll deltas | Yes |
| **Latency Heatmap** | p50/p95/avg per operation | Yes |
| **Live Trace Log** | Last 40 spans with timestamps | Yes |
| **Anomaly Detection** | Phantom stall, ghost agent, loop detection | Partially hardcoded examples — see below |
| **Services Grid** | All services from `/api/services` | Fully auto-discovered |
| **Recent Traces** | Last 12 traces with root op + status | Yes |
| **Mini Span Tree** | Parent/child hierarchy of last trace | Yes |

---

## 6. Customizing the Anomaly Panel

The three anomaly cards are **demo placeholders** based on our swarm:

- `[PHANTOM STALL] Kilo: 0 min active spans`
- `[GHOST AGENT] Beau: last span >30 min ago`
- `[LOOP DETECT] No loops detected`

To adapt to your own agents/services, edit `index.html` around line 348-363:

```html
<div class="anom-card crit">
  <div class="anom-title glow-red">[YOUR ALERT] YourAgent: description</div>
  <div class="anom-detail">Threshold: your rule</div>
</div>
```

Or replace the static cards with a dynamic query against your own health endpoint / cron status / heartbeat file.

---

## 7. Making Your Spans Richer

If you add these attributes to your spans, the dashboard surfaces more detail:

| Attribute | Shown in |
|-----------|----------|
| `agent.name` | "Active Agent" metric tile |
| `agent.id` | Not displayed (used for grouping) |
| `agent.provider` | Hover tooltip on model tile |
| `model` | "Model" metric tile |
| `hermes.tool.name` | Operation name (if using Hermes) |
| `error` = `true` | Error rate, red sparkline bars, red waveform bars |

Any span with `error=true` turns that interval red in the throughput waveform and increments the error counter.

---

## 8. Multiple Services

The dashboard queries **one** primary service for the main panels (traces, spans, ops, heatmap). It defaults to `edgeless-swarm`. The services grid below shows **all** services.

To change the primary service, edit `index.html`:

```javascript
const SERVICE = 'my-service';  // line ~399
```

Future versions will make this a dropdown.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "JAEGER OFFLINE" | Verify Jaeger is on `localhost:16687` (or set `OTEL_DASHBOARD_JAEGER`) |
| All panels empty but Jaeger online | Check that your service name matches `SERVICE` constant in `index.html` |
| "unknown" agent/model | Your spans do not carry `agent.name` / `model` attributes — purely cosmetic |
| macOS "cannot open because developer cannot be verified" | Right-click app → Open, or `xattr -cr /Applications/EDGELESS\ OTEL\ Command.app` |
| Windows SmartScreen warning | Click "More info" → "Run anyway" |

---

## Architecture

```
Your Service(s) ── OTLP gRPC ──▶ Jaeger (localhost:16687)
                                                │
Electron App ────────────────────────────────▼
  Embedded proxy (port 8766) ─── HTTP ──▶ /api/traces
  BrowserWindow ──────────────────────────── /api/services
```

No data leaves your machine. The proxy only speaks to Jaeger. The app is a pure viewer.
