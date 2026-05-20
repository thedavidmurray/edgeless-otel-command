// EDGELESS :: OTEL COMMAND — Dashboard logic (v1.1.0)
// Renderer-side. Talks to Jaeger via the embedded proxy at /jaeger/*.

'use strict';

// ── Global state ───────────────────────────────────────────────────
const state = {
  settings: {},
  jaeger: '/jaeger',           // proxied prefix (rewritten by main.js)
  services: [],                // ['edgeless-swarm', 'claude-code', ...]
  serviceFilter: null,         // null = all
  timeWindowMin: 60,           // 60 min default
  view: 'overview',            // 'overview' | 'trace' | 'service' | 'anomalies' | 'settings'
  selectedTraceId: null,
  selectedService: null,
  serviceTraces: {},           // { svcName: [trace, ...] }
  anomalies: [],               // current active anomalies
  anomalyLog: [],              // historical anomalies (last 100)
  history: [],                 // [{ t, traces, spans, err }] for sparkline
  lastTrace: null,             // last trace fetched (for mini-tree)
};

// ── Formatters ─────────────────────────────────────────────────────
const fmtDur = (us) => {
  if (us > 1e6) return (us / 1e6).toFixed(1) + 's';
  if (us > 1e3) return (us / 1e3).toFixed(0) + 'ms';
  return us + 'us';
};
const fmtTime = (d) => d.toISOString().split('T')[1].split('.')[0];
const fmtAge = (us) => {
  const ageSec = (Date.now() * 1000 - us) / 1e6;
  if (ageSec < 60) return Math.round(ageSec) + 's ago';
  if (ageSec < 3600) return Math.round(ageSec / 60) + 'm ago';
  return Math.round(ageSec / 3600) + 'h ago';
};
const hashColor = (str) => {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
  return `hsl(${Math.abs(h % 360)}, 70%, 60%)`;
};

// ── Data fetching ──────────────────────────────────────────────────
async function fetchServices() {
  const r = await fetch(`${state.jaeger}/api/services`);
  if (!r.ok) throw new Error('Jaeger unreachable');
  const d = await r.json();
  return d.data || [];
}

async function fetchTracesFor(service, limit = 100) {
  // Time window: state.timeWindowMin minutes back from now (microseconds)
  const nowUs = Date.now() * 1000;
  const startUs = nowUs - state.timeWindowMin * 60 * 1e6;
  const url = `${state.jaeger}/api/traces?service=${encodeURIComponent(service)}&limit=${limit}&start=${startUs}&end=${nowUs}`;
  const r = await fetch(url);
  if (!r.ok) return [];
  const d = await r.json();
  return d.data || [];
}

async function fetchTraceById(id) {
  const r = await fetch(`${state.jaeger}/api/traces/${id}`);
  if (!r.ok) return null;
  const d = await r.json();
  return (d.data || [])[0] || null;
}

// ── Analytics ──────────────────────────────────────────────────────
function tagsToObj(spanTags) {
  const o = {};
  for (const t of spanTags || []) o[t.key] = t.value;
  return o;
}

function analyze(allTracesByService) {
  // Aggregate traces across selected services
  const traces = [];
  for (const [svc, arr] of Object.entries(allTracesByService)) {
    if (state.serviceFilter && svc !== state.serviceFilter) continue;
    traces.push(...arr);
  }
  const ops = {};
  const opDur = {};
  const spans = [];
  let err = 0;
  let total = 0;
  for (const t of traces) {
    for (const s of t.spans || []) {
      total++;
      const op = s.operationName || 'unknown';
      ops[op] = (ops[op] || 0) + 1;
      opDur[op] = opDur[op] || [];
      opDur[op].push(s.duration || 0);
      const tags = tagsToObj(s.tags);
      if (tags.error === true || tags.error === 'true') err++;
      for (const log of s.logs || []) {
        for (const f of log.fields || []) {
          if (f.key === 'event' && String(f.value || '').toLowerCase().includes('exception')) err++;
        }
      }
      // Resolve service via processID -> process.serviceName
      const proc = (t.processes && t.processes[s.processID]) || {};
      const svc = proc.serviceName || 'unknown';
      spans.push({
        traceID: t.traceID,
        op, dur: s.duration, tags, startTime: s.startTime,
        spanID: s.spanID, references: s.references || [],
        service: svc, logs: s.logs || [],
      });
    }
  }
  const sortedOps = Object.entries(ops).sort((a, b) => b[1] - a[1]);
  const latency = {};
  for (const [op, durs] of Object.entries(opDur)) {
    const sorted = durs.sort((a, b) => a - b);
    latency[op] = {
      n: sorted.length,
      p50: sorted[Math.floor(sorted.length * 0.5)],
      p95: sorted[Math.floor(sorted.length * 0.95)] || sorted[sorted.length - 1],
      p99: sorted[Math.floor(sorted.length * 0.99)] || sorted[sorted.length - 1],
      avg: sorted.reduce((a, b) => a + b, 0) / sorted.length,
    };
  }
  return { ops: sortedOps, latency, err, total, spans, traces };
}

// Per-service rollup
function serviceRollup(allTracesByService) {
  const rollup = {};
  for (const [svc, traces] of Object.entries(allTracesByService)) {
    let totalSpans = 0, errSpans = 0, lastSpanUs = 0;
    const durs = [];
    for (const t of traces) {
      for (const s of t.spans || []) {
        totalSpans++;
        const tags = tagsToObj(s.tags);
        if (tags.error === true || tags.error === 'true') errSpans++;
        if (s.startTime > lastSpanUs) lastSpanUs = s.startTime;
        durs.push(s.duration || 0);
      }
    }
    durs.sort((a, b) => a - b);
    rollup[svc] = {
      traces: traces.length,
      spans: totalSpans,
      err: errSpans,
      errPct: totalSpans ? (errSpans / totalSpans * 100) : 0,
      p95: durs[Math.floor(durs.length * 0.95)] || 0,
      lastSpanUs,
    };
  }
  return rollup;
}

// Real anomaly detection
function detectAnomalies(allTracesByService, rollup) {
  const out = [];
  const thresholds = state.settings.anomalyThresholds || {
    ghostAgentMin: 30, phantomStallMin: 30,
    loopThreshold: 5, loopWindowSec: 300,
  };
  const nowUs = Date.now() * 1000;
  const ghostThresholdUs = thresholds.ghostAgentMin * 60 * 1e6;
  const loopWindowUs = thresholds.loopWindowSec * 1e6;

  // Ghost agent: service silent > N min (but only flag known service names, not Jaeger itself)
  for (const [svc, r] of Object.entries(rollup)) {
    if (svc === 'jaeger-all-in-one') continue;
    if (r.lastSpanUs === 0) {
      out.push({
        severity: 'warn', kind: 'GHOST_AGENT',
        title: `${svc}: no spans in window`,
        detail: `Service registered with Jaeger but emitted nothing in the last ${state.timeWindowMin}m`,
        service: svc, ts: Date.now(),
      });
      continue;
    }
    const ageUs = nowUs - r.lastSpanUs;
    if (ageUs > ghostThresholdUs) {
      out.push({
        severity: 'warn', kind: 'GHOST_AGENT',
        title: `${svc}: last span ${Math.round(ageUs / 6e7)}m ago`,
        detail: `Threshold ${thresholds.ghostAgentMin}m. Check if the producer cron is alive.`,
        service: svc, ts: Date.now(),
      });
    }
  }

  // Loop detect: per service, if same operation appears > N times within window
  for (const [svc, traces] of Object.entries(allTracesByService)) {
    const opTimes = {};
    for (const t of traces) {
      for (const s of t.spans || []) {
        const op = s.operationName || 'unknown';
        opTimes[op] = opTimes[op] || [];
        opTimes[op].push(s.startTime);
      }
    }
    for (const [op, times] of Object.entries(opTimes)) {
      times.sort((a, b) => a - b);
      // sliding window
      let i = 0;
      for (let j = 0; j < times.length; j++) {
        while (times[j] - times[i] > loopWindowUs) i++;
        const count = j - i + 1;
        if (count >= thresholds.loopThreshold) {
          out.push({
            severity: 'crit', kind: 'LOOP_DETECT',
            title: `${svc}/${op}: ${count} calls in ${Math.round((times[j] - times[i]) / 1e6)}s`,
            detail: `Threshold ${thresholds.loopThreshold} in ${thresholds.loopWindowSec}s. Likely a runaway.`,
            service: svc, ts: Date.now(),
          });
          break; // one alert per op
        }
      }
    }
  }

  // Phantom stall: a span open (no end) for > N min, where "open" = startTime + duration is in the future
  // (Most spans in Jaeger are already complete; this catches sentinel "span never closed" cases.)
  const phantomThresholdUs = thresholds.phantomStallMin * 60 * 1e6;
  for (const [svc, traces] of Object.entries(allTracesByService)) {
    for (const t of traces) {
      for (const s of t.spans || []) {
        const startedAgo = nowUs - s.startTime;
        const recordedDur = s.duration || 0;
        // If duration ≈ "age since start" within 1s, span is likely still open being polled.
        // We treat "stale open" as a span whose start is way in the past but reported duration is tiny.
        if (startedAgo > phantomThresholdUs && recordedDur < 1e6 && recordedDur > 0) {
          out.push({
            severity: 'crit', kind: 'PHANTOM_STALL',
            title: `${svc}/${s.operationName}: ${Math.round(startedAgo / 6e7)}m old, ${fmtDur(recordedDur)} dur`,
            detail: `Possible never-closed span. Trace: ${t.traceID.slice(0, 16)}`,
            service: svc, ts: Date.now(),
            traceID: t.traceID,
          });
          return out; // limit to one per scan
        }
      }
    }
  }

  if (out.length === 0) {
    out.push({
      severity: 'ok', kind: 'ALL_CLEAR',
      title: 'No anomalies detected',
      detail: `Last check: ${fmtTime(new Date())}`,
      ts: Date.now(),
    });
  }
  return out;
}

// ── Rendering: overview ────────────────────────────────────────────
function renderMetrics(a) {
  document.getElementById('m-traces').textContent = a.traces.length;
  document.getElementById('m-spans').textContent = a.total;
  const errPct = a.total ? (a.err / a.total * 100).toFixed(1) + '%' : '0.0%';
  document.getElementById('m-err').textContent = errPct;
  document.getElementById('m-ops').textContent = a.ops.length;
  document.getElementById('trace-count').textContent = a.traces.length;
  document.getElementById('span-count').textContent = a.total;
  document.getElementById('err-rate').textContent = errPct;

  let agent = '-', model = '-';
  if (a.spans.length) {
    const last = a.spans[a.spans.length - 1].tags;
    agent = last['hermes.agent.name'] || last['agent.name'] || '-';
    model = last['hermes.model'] || last['model'] || '-';
  }
  document.getElementById('m-agent').textContent = agent;
  document.getElementById('m-model').textContent = model;

  // Sparklines per metric
  const buckets = new Array(12).fill(0);
  for (const t of a.traces) {
    const s = (t.spans && t.spans[0]) ? t.spans[0].startTime : 0;
    const age = Date.now() * 1000 - s;
    const idx = Math.min(11, Math.floor(age / (300 * 1e6)));
    if (idx >= 0 && idx < 12) buckets[idx] += (t.spans || []).length;
  }
  const max = Math.max(...buckets, 1);
  ['traces', 'spans', 'err', 'ops', 'agent', 'model'].forEach((key, i) => {
    const el = document.getElementById('spark-' + key);
    if (!el) return;
    el.innerHTML = '';
    for (let j = 11; j >= 0; j--) {
      const h = (buckets[j] / max * 100);
      const bar = document.createElement('div');
      bar.className = 'm-bar' + ((key === 'err' && i % 3 === 0) ? ' err' : '');
      bar.style.height = Math.max(2, h) + '%';
      bar.style.opacity = .4 + (j / 11) * .6;
      el.appendChild(bar);
    }
  });

  const slowOps = Object.entries(a.latency).filter(([op, lat]) => lat.p95 > 1e6).length;
  const slowPct = a.ops.length ? Math.round(slowOps / a.ops.length * 100) : 0;
  const successPct = a.total ? (100 - (a.err / a.total * 100)) : 100;
  document.getElementById('gauge-success').style.width = successPct + '%';
  document.getElementById('gauge-success-pct').textContent = successPct.toFixed(0) + '%';
  document.getElementById('gauge-slow').style.width = slowPct + '%';
  document.getElementById('gauge-slow-pct').textContent = slowPct + '%';
}

function renderDonut(a) {
  const ops = a.ops.slice(0, 6);
  const total = a.total || 1;
  const colors = ops.map(([op]) => hashColor(op));
  const grad = [];
  let acc = 0;
  for (let i = 0; i < ops.length; i++) {
    const pct = (ops[i][1] / total * 100);
    grad.push(`${colors[i]} ${acc.toFixed(2)}% ${(acc + pct).toFixed(2)}%`);
    acc += pct;
  }
  const donut = document.getElementById('donut-ops');
  donut.style.background = `conic-gradient(${grad.join(', ')}, var(--bg-panel) ${acc.toFixed(2)}% 100%)`;
  donut.setAttribute('data-pct', ops.length ? Math.round(ops[0][1] / total * 100) + '%' : '-');

  const leg = document.getElementById('donut-legend');
  leg.innerHTML = '';
  for (let i = 0; i < ops.length; i++) {
    const [op, cnt] = ops[i];
    const row = document.createElement('div');
    row.className = 'leg clickable';
    row.title = `Filter to ${op}`;
    row.innerHTML = `<div class="leg-dot" style="background:${colors[i]}"></div><div class="leg-name">${op}</div><div class="leg-val">${cnt}</div>`;
    leg.appendChild(row);
  }
}

function renderSparkline(a) {
  const box = document.getElementById('spark-box');
  box.innerHTML = '';
  const buckets = new Array(20).fill(0);
  const errBuckets = new Array(20).fill(0);
  const now = Date.now() * 1000;
  for (const t of a.traces) {
    const s = (t.spans && t.spans[0]) ? (t.spans[0].startTime || 0) : 0;
    const age = now - s;
    const idx = Math.min(19, Math.floor(age / (300 * 1e6)));
    if (idx >= 0 && idx < 20) {
      buckets[idx] += (t.spans || []).length;
      for (const sp of t.spans || []) {
        const tags = tagsToObj(sp.tags);
        if (tags.error === true) errBuckets[idx]++;
      }
    }
  }
  const max = Math.max(...buckets, 1);
  for (let i = 19; i >= 0; i--) {
    const h = (buckets[i] / max * 100);
    const bar = document.createElement('div');
    bar.className = 'spark-bar' + (errBuckets[i] ? ' err' : '');
    bar.style.height = Math.max(2, h) + '%';
    bar.title = `T-${(19 - i) * 5}min: ${buckets[i]} spans${errBuckets[i] ? ' ' + errBuckets[i] + ' errors' : ''}`;
    box.appendChild(bar);
  }
}

function renderOpChart(a) {
  const chart = document.getElementById('op-chart');
  chart.innerHTML = '';
  const max = a.ops[0] ? a.ops[0][1] : 1;
  for (const [op, cnt] of a.ops.slice(0, 12)) {
    const row = document.createElement('div');
    row.className = 'bar-row clickable';
    row.title = `Click to drill into "${op}"`;
    row.addEventListener('click', () => navigate(`#/op/${encodeURIComponent(op)}`));
    const label = document.createElement('div');
    label.className = 'bar-label'; label.textContent = op;
    const track = document.createElement('div');
    track.className = 'bar-track';
    const fill = document.createElement('div');
    fill.className = 'bar-fill';
    const lat = a.latency[op];
    if (lat && lat.p95 > 500000) fill.classList.add('slow');
    else if (lat && lat.p95 > 100000) fill.classList.add('med');
    fill.style.width = (cnt / max * 100) + '%';
    const val = document.createElement('span');
    val.className = 'bar-val'; val.textContent = cnt;
    track.appendChild(fill); track.appendChild(val);
    row.appendChild(label); row.appendChild(track);
    chart.appendChild(row);
  }
}

function renderHeatmap(a) {
  const grid = document.getElementById('heatmap');
  grid.innerHTML = '';
  const head = document.createElement('div');
  head.className = 'heatmap-cell heatmap-rowhead'; head.textContent = 'OPERATION';
  grid.appendChild(head);
  for (const h of ['P50', 'P95', 'AVG']) {
    const el = document.createElement('div');
    el.className = 'heatmap-cell heatmap-head'; el.textContent = h;
    grid.appendChild(el);
  }
  const ops = a.ops.slice(0, 12);
  for (const [op] of ops) {
    const lat = a.latency[op];
    const rh = document.createElement('div');
    rh.className = 'heatmap-cell heatmap-rowhead clickable';
    rh.textContent = op;
    rh.addEventListener('click', () => navigate(`#/op/${encodeURIComponent(op)}`));
    grid.appendChild(rh);
    for (const v of [lat.p50, lat.p95, lat.avg]) {
      const el = document.createElement('div');
      el.className = 'heatmap-cell';
      el.textContent = fmtDur(v);
      const intensity = Math.min(1, v / 500000);
      if (intensity > 0.8) el.style.background = 'rgba(255,77,77,' + (intensity * 0.3) + ')';
      else if (intensity > 0.3) el.style.background = 'rgba(255,176,0,' + (intensity * 0.3) + ')';
      else el.style.background = 'rgba(0,229,255,' + (intensity * 0.2) + ')';
      if (intensity > 0.5) el.style.color = '#fff';
      grid.appendChild(el);
    }
  }
}

function renderLog(a) {
  const log = document.getElementById('trace-log');
  const entries = a.spans.slice(-40).reverse();
  log.innerHTML = entries.map(s => {
    const ts = fmtTime(new Date((s.startTime || 0) / 1000));
    const hasErr = s.tags && s.tags.error;
    const sev = hasErr ? 'err' : 'ok';
    const sevText = hasErr ? 'ERR' : 'OK';
    return `<div class="log-entry clickable" data-trace="${s.traceID}"><span class="log-time">${ts}</span><span class="log-sev ${sev}">${sevText}</span><span class="log-op glow-cyan">${s.op}</span><span class="log-dur">${fmtDur(s.dur)}</span><span class="log-id">${s.traceID.slice(0, 16)}</span></div>`;
  }).join('');
  // Wire click handlers
  log.querySelectorAll('.log-entry').forEach(el => {
    el.addEventListener('click', () => navigate(`#/trace/${el.dataset.trace}`));
  });
}

function renderTraces(a) {
  const tbody = document.getElementById('trace-tbody');
  tbody.innerHTML = '';
  const recent = a.traces.slice(-12).reverse();
  for (const t of recent) {
    const spans = t.spans || [];
    const dur = spans.length
      ? Math.max(...spans.map(s => s.startTime + s.duration)) - Math.min(...spans.map(s => s.startTime))
      : 0;
    let hasErr = false;
    for (const s of spans) {
      const tags = tagsToObj(s.tags);
      if (tags.error === true) hasErr = true;
    }
    const tr = document.createElement('tr');
    tr.className = 'clickable';
    tr.dataset.trace = t.traceID;
    tr.innerHTML = `
      <td class="log-id">${t.traceID.slice(0, 16)}...</td>
      <td class="glow-cyan">${spans[0] ? spans[0].operationName : '-'}</td>
      <td>${fmtDur(dur)}</td>
      <td>${spans.length}</td>
      <td>${hasErr ? '<span class="glow-red">ERROR</span>' : '<span class="glow-cyan">CLEAN</span>'}</td>
    `;
    tr.addEventListener('click', () => navigate(`#/trace/${t.traceID}`));
    tbody.appendChild(tr);
  }
  state.lastTrace = recent[0] || null;
}

function renderMiniTree(a) {
  const tree = document.getElementById('mini-tree');
  tree.innerHTML = '';
  if (!a.traces.length) return;
  const t = a.traces[a.traces.length - 1];
  const spans = (t.spans || []).slice(0, 8);
  const spanMap = {};
  for (const s of spans) spanMap[s.spanID] = s;
  const children = {};
  for (const s of spans) {
    let parent = null;
    for (const ref of s.references || []) {
      if (ref.refType === 'CHILD_OF') parent = ref.spanID;
    }
    if (parent && spanMap[parent]) {
      children[parent] = children[parent] || [];
      children[parent].push(s);
    }
  }
  const roots = spans.filter(s => {
    for (const ref of s.references || []) if (ref.refType === 'CHILD_OF') return false;
    return true;
  });
  for (const r of roots) {
    const node = document.createElement('div');
    node.className = 'tree-node root clickable';
    node.dataset.trace = t.traceID;
    node.innerHTML = `<span class="glow-cyan">${r.operationName}</span><span class="tree-dur">${fmtDur(r.duration)}</span>`;
    node.addEventListener('click', () => navigate(`#/trace/${t.traceID}`));
    tree.appendChild(node);
    for (const c of (children[r.spanID] || [])) {
      const child = document.createElement('div');
      child.className = 'tree-node';
      child.innerHTML = `<span class="glow-dim">${c.operationName}</span><span class="tree-dur">${fmtDur(c.duration)}</span>`;
      tree.appendChild(child);
    }
  }
}

function renderAnomalies() {
  const container = document.getElementById('anomaly-content');
  container.innerHTML = '';
  for (const a of state.anomalies) {
    const sev = a.severity === 'crit' ? 'crit'
              : a.severity === 'warn' ? 'warn' : 'ok';
    const glow = a.severity === 'crit' ? 'glow-red'
               : a.severity === 'warn' ? 'glow-amber' : 'glow-cyan';
    const card = document.createElement('div');
    card.className = `anom-card ${sev}` + (a.traceID ? ' clickable' : '');
    card.innerHTML = `
      <div class="anom-title ${glow}">[${a.kind}] ${a.title}</div>
      <div class="anom-detail">${a.detail}</div>
    `;
    if (a.traceID) {
      card.addEventListener('click', () => navigate(`#/trace/${a.traceID}`));
    } else if (a.service) {
      card.classList.add('clickable');
      card.addEventListener('click', () => navigate(`#/service/${encodeURIComponent(a.service)}`));
    }
    container.appendChild(card);
  }
  const lc = document.getElementById('last-check');
  if (lc) lc.textContent = fmtTime(new Date());
}

function renderServices(rollup) {
  const grid = document.getElementById('svc-grid');
  grid.innerHTML = '';
  const known = {
    'edgeless-swarm':    { detail: 'Hermes swarm' },
    'jaeger-all-in-one': { detail: 'Collector' },
    'claude-code':       { detail: 'Claude Code sessions' },
    'ingestion.youtube': { detail: 'YouTube pipeline' },
    'ingestion.rss':     { detail: 'RSS pipeline' },
  };
  for (const svc of state.services) {
    const r = rollup[svc] || { spans: 0, err: 0, errPct: 0, p95: 0, lastSpanUs: 0 };
    const info = known[svc] || { detail: 'Service' };
    const isLive = r.lastSpanUs > 0 && (Date.now() * 1000 - r.lastSpanUs) < 5 * 60 * 1e6;
    const box = document.createElement('div');
    box.className = 'svc-box clickable';
    box.title = `Click to drill into ${svc}`;
    box.addEventListener('click', () => navigate(`#/service/${encodeURIComponent(svc)}`));
    box.innerHTML = `
      <div class="svc-header"><div class="svc-dot ${isLive ? 'on' : 'off'}"></div><div class="svc-name">${svc}</div></div>
      <div class="svc-detail">${info.detail}</div>
      <div class="svc-detail">${r.spans} spans · err ${r.errPct.toFixed(1)}% · p95 ${fmtDur(r.p95)}</div>
      <div class="svc-detail">${r.lastSpanUs ? 'last ' + fmtAge(r.lastSpanUs) : 'no recent spans'}</div>
    `;
    grid.appendChild(box);
  }
}

// ── Waveform (real spans/sec from history) ─────────────────────────
function initWaveform() {
  const wf = document.getElementById('waveform');
  wf.innerHTML = '';
  for (let i = 0; i < 40; i++) {
    const bar = document.createElement('div');
    bar.className = 'wave-bar';
    bar.style.height = '4px';
    bar.style.opacity = '.4';
    wf.appendChild(bar);
  }
}

function updateWaveform() {
  const wf = document.getElementById('waveform');
  const bars = wf.querySelectorAll('.wave-bar');
  if (!state.history.length || bars.length === 0) return;
  const rates = [];
  for (let i = 1; i < state.history.length; i++) {
    const dt = (state.history[i].t - state.history[i - 1].t) / 1000;
    const ds = state.history[i].spans - state.history[i - 1].spans;
    rates.push({ rate: dt > 0 ? ds / dt : 0, err: state.history[i].err });
  }
  if (!rates.length) return;
  const maxRate = Math.max(...rates.map(r => r.rate), 0.1);
  const visible = rates.slice(-40);
  for (let i = 0; i < bars.length; i++) {
    const idx = visible.length - bars.length + i;
    if (idx >= 0) {
      const r = visible[idx];
      const h = Math.max(4, (r.rate / maxRate) * 100);
      bars[i].style.height = h + '%';
      bars[i].style.opacity = Math.min(1, 0.3 + (r.rate / maxRate) * 0.7);
      if (r.err > 0) bars[i].style.background = 'var(--red)';
      else if (r.rate > maxRate * 0.8) bars[i].style.background = 'var(--amber)';
      else bars[i].style.background = 'var(--cyan)';
    } else {
      bars[i].style.height = '4px';
      bars[i].style.opacity = '.2';
      bars[i].style.background = 'var(--cyan)';
    }
  }
}

// ── Rendering: trace detail view (drill-down) ──────────────────────
async function renderTraceDetail(traceId) {
  const modal = document.getElementById('detail-modal');
  const body = document.getElementById('detail-body');
  modal.classList.add('open');
  body.innerHTML = '<div class="detail-loading">Loading trace…</div>';
  const trace = await fetchTraceById(traceId);
  if (!trace) {
    body.innerHTML = `<div class="detail-loading">Trace not found: ${traceId}</div>`;
    return;
  }
  const spans = trace.spans || [];
  const procs = trace.processes || {};
  const start = Math.min(...spans.map(s => s.startTime));
  const end = Math.max(...spans.map(s => s.startTime + s.duration));
  const total = end - start;
  const rootSpan = spans.find(s => !(s.references || []).some(r => r.refType === 'CHILD_OF')) || spans[0];
  const rootSvc = (procs[rootSpan.processID] || {}).serviceName || '?';
  let errCount = 0;
  for (const s of spans) {
    const tags = tagsToObj(s.tags);
    if (tags.error === true) errCount++;
  }

  // Header
  let html = `
    <div class="detail-head">
      <div class="detail-meta">
        <div><span class="dim">trace</span> <span class="glow-cyan">${trace.traceID}</span></div>
        <div><span class="dim">root</span> <span class="glow-cyan">${rootSvc} · ${rootSpan.operationName}</span></div>
        <div><span class="dim">spans</span> ${spans.length} · <span class="dim">duration</span> ${fmtDur(total)} · <span class="dim">errors</span> ${errCount}</div>
      </div>
      <div class="detail-actions">
        <button class="btn" id="open-jaeger-btn">Open in Jaeger UI</button>
      </div>
    </div>
    <div class="waterfall">
  `;

  // Sort spans by startTime for waterfall
  const sorted = [...spans].sort((a, b) => a.startTime - b.startTime);
  // Compute depth
  const depth = {};
  const sMap = {};
  for (const s of sorted) sMap[s.spanID] = s;
  const computeDepth = (s) => {
    if (depth[s.spanID] != null) return depth[s.spanID];
    let parent = null;
    for (const ref of s.references || []) {
      if (ref.refType === 'CHILD_OF') parent = ref.spanID;
    }
    if (parent && sMap[parent]) depth[s.spanID] = computeDepth(sMap[parent]) + 1;
    else depth[s.spanID] = 0;
    return depth[s.spanID];
  };

  for (const s of sorted) {
    const d = computeDepth(s);
    const offsetPct = total > 0 ? ((s.startTime - start) / total * 100) : 0;
    const widthPct = total > 0 ? Math.max(0.3, (s.duration / total * 100)) : 100;
    const tags = tagsToObj(s.tags);
    const hasErr = tags.error === true;
    const svc = (procs[s.processID] || {}).serviceName || '?';
    const color = hashColor(svc);
    html += `
      <div class="wf-row" data-span="${s.spanID}">
        <div class="wf-label" style="padding-left:${d * 12}px">
          <span class="wf-svc" style="border-left:3px solid ${color}">${svc}</span>
          <span class="${hasErr ? 'glow-red' : ''}">${s.operationName}</span>
        </div>
        <div class="wf-bar-track">
          <div class="wf-bar ${hasErr ? 'err' : ''}" style="margin-left:${offsetPct}%; width:${widthPct}%" title="${fmtDur(s.duration)}"></div>
        </div>
        <div class="wf-dur">${fmtDur(s.duration)}</div>
      </div>
      <div class="wf-detail" id="wf-detail-${s.spanID}" style="display:none">
        <div class="wf-detail-section"><div class="dim">TAGS</div>${
          Object.entries(tags).map(([k, v]) => `<div class="kv"><span class="k">${k}</span><span class="v">${typeof v === 'object' ? JSON.stringify(v) : v}</span></div>`).join('') || '<div class="dim">none</div>'
        }</div>
        <div class="wf-detail-section"><div class="dim">LOGS (${(s.logs || []).length})</div>${
          (s.logs || []).slice(0, 10).map(l => {
            const lf = {};
            for (const f of l.fields || []) lf[f.key] = f.value;
            return `<div class="kv"><span class="k">${fmtTime(new Date(l.timestamp / 1000))}</span><span class="v">${Object.entries(lf).map(([k, v]) => `${k}=${v}`).join(' ')}</span></div>`;
          }).join('') || '<div class="dim">none</div>'
        }</div>
      </div>
    `;
  }
  html += `</div>`;
  body.innerHTML = html;

  // Span click expand
  body.querySelectorAll('.wf-row').forEach(row => {
    row.addEventListener('click', () => {
      const d = document.getElementById('wf-detail-' + row.dataset.span);
      if (d) d.style.display = d.style.display === 'none' ? 'block' : 'none';
    });
  });
  // Jaeger UI button
  const btn = document.getElementById('open-jaeger-btn');
  if (btn) {
    btn.addEventListener('click', () => {
      const jaegerUrl = (state.settings.jaegerUrl || 'http://localhost:16687').replace(/\/$/, '');
      window.edgeless && window.edgeless.openExternal
        ? window.edgeless.openExternal(`${jaegerUrl}/trace/${trace.traceID}`)
        : window.open(`${jaegerUrl}/trace/${trace.traceID}`);
    });
  }
}

// ── Rendering: service detail view ─────────────────────────────────
async function renderServiceDetail(svcName) {
  const modal = document.getElementById('detail-modal');
  const body = document.getElementById('detail-body');
  modal.classList.add('open');
  body.innerHTML = '<div class="detail-loading">Loading service…</div>';

  const traces = state.serviceTraces[svcName] || await fetchTracesFor(svcName, 100);
  // Operations + latencies for this service
  const ops = {}, opDur = {};
  for (const t of traces) {
    for (const s of t.spans || []) {
      const proc = (t.processes && t.processes[s.processID]) || {};
      if (proc.serviceName !== svcName) continue;
      const op = s.operationName || 'unknown';
      ops[op] = (ops[op] || 0) + 1;
      opDur[op] = opDur[op] || [];
      opDur[op].push(s.duration || 0);
    }
  }
  const sortedOps = Object.entries(ops).sort((a, b) => b[1] - a[1]);

  let html = `
    <div class="detail-head">
      <div class="detail-meta">
        <div><span class="dim">service</span> <span class="glow-cyan">${svcName}</span></div>
        <div><span class="dim">window</span> ${state.timeWindowMin}m · <span class="dim">traces</span> ${traces.length} · <span class="dim">operations</span> ${sortedOps.length}</div>
      </div>
    </div>
    <div class="detail-section">
      <div class="dim">OPERATIONS</div>
      <table class="trace-table">
        <thead><tr><th>OPERATION</th><th>COUNT</th><th>P50</th><th>P95</th><th>P99</th><th>AVG</th></tr></thead>
        <tbody>
  `;
  for (const [op, cnt] of sortedOps) {
    const durs = opDur[op].sort((a, b) => a - b);
    const p50 = durs[Math.floor(durs.length * 0.5)];
    const p95 = durs[Math.floor(durs.length * 0.95)] || durs[durs.length - 1];
    const p99 = durs[Math.floor(durs.length * 0.99)] || durs[durs.length - 1];
    const avg = durs.reduce((a, b) => a + b, 0) / durs.length;
    html += `<tr><td>${op}</td><td>${cnt}</td><td>${fmtDur(p50)}</td><td>${fmtDur(p95)}</td><td>${fmtDur(p99)}</td><td>${fmtDur(avg)}</td></tr>`;
  }
  html += `</tbody></table></div>
    <div class="detail-section">
      <div class="dim">RECENT TRACES</div>
      <table class="trace-table">
        <thead><tr><th>TRACE</th><th>ROOT OP</th><th>DURATION</th><th>SPANS</th></tr></thead>
        <tbody>
  `;
  for (const t of traces.slice(0, 30)) {
    const spans = t.spans || [];
    const dur = spans.length ? Math.max(...spans.map(s => s.startTime + s.duration)) - Math.min(...spans.map(s => s.startTime)) : 0;
    html += `<tr class="clickable" data-trace="${t.traceID}"><td>${t.traceID.slice(0, 16)}…</td><td>${(spans[0] && spans[0].operationName) || '-'}</td><td>${fmtDur(dur)}</td><td>${spans.length}</td></tr>`;
  }
  html += `</tbody></table></div>`;
  body.innerHTML = html;

  body.querySelectorAll('tr.clickable').forEach(tr => {
    tr.addEventListener('click', () => navigate(`#/trace/${tr.dataset.trace}`));
  });
}

// ── Settings panel ─────────────────────────────────────────────────
function renderSettings() {
  const modal = document.getElementById('detail-modal');
  const body = document.getElementById('detail-body');
  modal.classList.add('open');
  const s = state.settings;
  body.innerHTML = `
    <div class="detail-head">
      <div class="detail-meta"><div class="glow-cyan">SETTINGS</div></div>
    </div>
    <div class="settings-form">
      <div class="form-row">
        <label>Jaeger URL</label>
        <input type="text" id="set-jaeger" value="${s.jaegerUrl || ''}" />
        <button class="btn" id="set-jaeger-test">Test</button>
      </div>
      <div class="form-row">
        <label>Refresh interval (ms)</label>
        <input type="number" id="set-refresh" value="${s.refreshIntervalMs || 10000}" min="1000" />
      </div>
      <div class="form-row">
        <label>Time window (min)</label>
        <select id="set-window">
          <option value="5">5 min</option>
          <option value="15">15 min</option>
          <option value="60">1 hour</option>
          <option value="360">6 hours</option>
          <option value="1440">24 hours</option>
        </select>
      </div>
      <hr/>
      <div class="form-row"><label>Ghost agent (min)</label><input type="number" id="set-ghost" value="${s.anomalyThresholds.ghostAgentMin}" /></div>
      <div class="form-row"><label>Phantom stall (min)</label><input type="number" id="set-phantom" value="${s.anomalyThresholds.phantomStallMin}" /></div>
      <div class="form-row"><label>Loop threshold (calls)</label><input type="number" id="set-loop-n" value="${s.anomalyThresholds.loopThreshold}" /></div>
      <div class="form-row"><label>Loop window (sec)</label><input type="number" id="set-loop-w" value="${s.anomalyThresholds.loopWindowSec}" /></div>
      <div class="form-row form-actions">
        <button class="btn primary" id="set-save">Save</button>
        <span id="set-status" class="dim"></span>
      </div>
      <hr/>
      <div class="form-row" style="grid-template-columns: 1fr;">
        <label>Manage panels (show/hide)</label>
      </div>
      <div class="panel-toggles" id="panel-toggles"></div>
      <hr/>
      <div class="form-row" style="grid-template-columns: 1fr;">
        <label>Installed plug-ins</label>
      </div>
      <div class="plugin-list" id="plugin-list"><div class="dim">Loading…</div></div>
      <div class="form-row form-actions">
        <button class="btn" id="plugin-reload">Reload plug-ins (Cmd+R)</button>
      </div>
      <hr/>
      <div class="form-row" style="grid-template-columns: 1fr;">
        <label>Browse community plug-ins</label>
      </div>
      <div class="plugin-browse" id="plugin-browse">
        <div class="dim">Fetching registry…</div>
      </div>
      <div class="form-row form-actions">
        <button class="btn" id="plugin-refresh-registry">Refresh registry</button>
      </div>
    </div>
  `;
  document.getElementById('set-window').value = String(state.timeWindowMin);

  // Plug-in list rendering
  const renderPluginList = async () => {
    const list = document.getElementById('plugin-list');
    if (!list) return;
    if (!window.edgeless || !window.edgeless.pluginsList) {
      list.innerHTML = '<div class="dim">Plug-in API unavailable.</div>';
      return;
    }
    const plugins = await window.edgeless.pluginsList();
    if (plugins.length === 0) {
      list.innerHTML = '<div class="dim">No plug-ins installed.</div>';
      return;
    }
    list.innerHTML = plugins.map(p => {
      const failed = !!p.error;
      const statusBadge = failed
        ? `<span class="glow-red">FAILED</span>`
        : (p.enabled ? `<span class="glow-cyan">ON</span>` : `<span class="dim">OFF</span>`);
      return `
        <div class="plugin-row${failed ? ' failed' : ''}">
          <div>
            <div class="name">${escapeHtml(p.name || p.id)}</div>
            <div class="meta">${escapeHtml(p.id)} · v${escapeHtml(p.version || '?')} · by ${escapeHtml(p.author || 'unknown')}</div>
          </div>
          <div>${statusBadge}</div>
          <button class="btn" data-action="toggle" data-id="${escapeHtml(p.id)}" data-enabled="${!p.enabled}">${p.enabled ? 'Disable' : 'Enable'}</button>
          <button class="btn" data-action="remove" data-id="${escapeHtml(p.id)}">Remove</button>
          ${failed ? `<div class="err">${escapeHtml(p.error)}</div>` : ''}
        </div>`;
    }).join('');
    list.querySelectorAll('button[data-action="toggle"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        await window.edgeless.pluginsToggle(btn.dataset.id, btn.dataset.enabled === 'true');
        renderPluginList();
      });
    });
    list.querySelectorAll('button[data-action="remove"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm(`Remove plug-in "${btn.dataset.id}"? This deletes its folder.`)) return;
        await window.edgeless.pluginsRemove(btn.dataset.id);
        renderPluginList();
      });
    });
  };
  renderPluginList();

  // Panel show/hide toggles
  const renderPanelToggles = async () => {
    const host = document.getElementById('panel-toggles');
    if (!host) return;
    // Discover built-in panel IDs from DOM, plus any plug-in panel IDs from the registry
    const builtins = Array.from(document.querySelectorAll('main .panel[data-panel-id]'))
      .filter(el => !el.dataset.pluginPanel)
      .map(el => ({ id: el.dataset.panelId, label: el.dataset.label || el.dataset.panelId, type: 'built-in' }));
    const pluginPanels = Object.keys(pluginRegistry.panels).map(id => ({
      id,
      label: pluginRegistry.panels[id].def.label || id,
      type: 'plug-in',
    }));
    const all = [...builtins, ...pluginPanels];
    const hidden = new Set((state.settings && state.settings.hiddenPanels) || []);
    host.innerHTML = all.map(p => `
      <label class="panel-toggle">
        <input type="checkbox" data-panel-id="${escapeHtml(p.id)}" ${hidden.has(p.id) ? '' : 'checked'} />
        <span class="pt-label">${escapeHtml(p.label)}</span>
        <span class="pt-type ${p.type === 'plug-in' ? 'glow-cyan' : 'dim'}">${p.type}</span>
      </label>
    `).join('') || '<div class="dim">No panels detected.</div>';
    host.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', async () => {
        const pid = cb.dataset.panelId;
        const next = new Set((state.settings.hiddenPanels) || []);
        if (cb.checked) next.delete(pid);
        else next.add(pid);
        state.settings.hiddenPanels = [...next];
        if (window.edgeless && window.edgeless.setSettings) {
          await window.edgeless.setSettings({ hiddenPanels: state.settings.hiddenPanels });
        }
        // Apply immediately to DOM
        const el = document.querySelector(`main .panel[data-panel-id="${CSS.escape(pid)}"]`);
        if (el) el.dataset.hidden = cb.checked ? 'false' : 'true';
      });
    });
  };
  renderPanelToggles();

  document.getElementById('plugin-reload').addEventListener('click', () => {
    location.reload();
  });

  // Browse community plug-ins
  const renderBrowse = async () => {
    const host = document.getElementById('plugin-browse');
    if (!host) return;
    if (!window.edgeless || !window.edgeless.pluginsFetchRegistry) {
      host.innerHTML = '<div class="dim">Browse unavailable in this build.</div>';
      return;
    }
    host.innerHTML = '<div class="dim">Fetching registry…</div>';
    const res = await window.edgeless.pluginsFetchRegistry();
    if (!res.ok) {
      host.innerHTML = `<div class="glow-red">Registry fetch failed: ${escapeHtml(res.error)}</div>`;
      return;
    }
    const installed = new Set((await window.edgeless.pluginsList()).map(p => p.id));
    const reg = res.registry;
    const plugins = (reg.plugins || []);
    if (!plugins.length) {
      host.innerHTML = '<div class="dim">No plug-ins in registry yet.</div>';
      return;
    }
    host.innerHTML = plugins.map(p => {
      const isInstalled = installed.has(p.id);
      const tags = (p.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join(' ');
      return `
        <div class="browse-card">
          <div class="bc-head">
            <div>
              <div class="name">${escapeHtml(p.name)}</div>
              <div class="meta">${escapeHtml(p.id)} · v${escapeHtml(p.latestVersion)} · by ${escapeHtml(p.author || 'unknown')}</div>
            </div>
            <div class="bc-actions">
              <button class="btn" data-action="repo" data-repo="${escapeHtml(p.repo)}">View repo</button>
              ${isInstalled
                ? '<span class="glow-cyan">INSTALLED</span>'
                : `<button class="btn primary" data-action="install" data-repo="${escapeHtml(p.repo)}" data-id="${escapeHtml(p.id)}">Install</button>`}
            </div>
          </div>
          <div class="bc-desc">${escapeHtml(p.description)}</div>
          <div class="bc-tags">${tags}</div>
        </div>`;
    }).join('');
    host.querySelectorAll('button[data-action="repo"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = `https://github.com/${btn.dataset.repo}`;
        window.edgeless.openExternal ? window.edgeless.openExternal(url) : window.open(url);
      });
    });
    host.querySelectorAll('button[data-action="install"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const original = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Installing…';
        const result = await window.edgeless.pluginsInstallFromRepo({
          repo: btn.dataset.repo,
          id: btn.dataset.id,
        });
        if (result.ok) {
          btn.textContent = '✓ Installed · reload to enable';
          renderPluginList();
        } else {
          btn.textContent = `Failed: ${result.error.slice(0, 30)}`;
          btn.title = result.error;
          setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 4000);
        }
      });
    });
  };
  renderBrowse();
  document.getElementById('plugin-refresh-registry').addEventListener('click', renderBrowse);

  document.getElementById('set-jaeger-test').addEventListener('click', async () => {
    const url = document.getElementById('set-jaeger').value.trim();
    const status = document.getElementById('set-status');
    status.textContent = 'testing…';
    const res = await (window.edgeless && window.edgeless.testJaeger
      ? window.edgeless.testJaeger(url)
      : Promise.resolve({ ok: false, error: 'IPC unavailable' }));
    status.textContent = res.ok ? `✓ connected · ${res.services} services` : `✗ ${res.error}`;
    status.className = res.ok ? 'glow-cyan' : 'glow-red';
  });

  document.getElementById('set-save').addEventListener('click', async () => {
    const patch = {
      jaegerUrl: document.getElementById('set-jaeger').value.trim(),
      refreshIntervalMs: Number(document.getElementById('set-refresh').value),
      anomalyThresholds: {
        ghostAgentMin: Number(document.getElementById('set-ghost').value),
        phantomStallMin: Number(document.getElementById('set-phantom').value),
        loopThreshold: Number(document.getElementById('set-loop-n').value),
        loopWindowSec: Number(document.getElementById('set-loop-w').value),
      },
      firstRunComplete: true,
    };
    state.timeWindowMin = Number(document.getElementById('set-window').value);
    const result = await (window.edgeless && window.edgeless.setSettings
      ? window.edgeless.setSettings(patch)
      : Promise.resolve({ ok: false }));
    if (result && result.ok) {
      state.settings = result.settings;
      document.getElementById('set-status').textContent = '✓ saved · restart app to apply new Jaeger URL';
      document.getElementById('set-status').className = 'glow-cyan';
    }
  });
}

// First-run wizard (shows when firstRunComplete === false)
function renderFirstRun() {
  const modal = document.getElementById('detail-modal');
  const body = document.getElementById('detail-body');
  modal.classList.add('open', 'no-close');
  body.innerHTML = `
    <div class="detail-head">
      <div class="detail-meta">
        <div class="glow-cyan">FIRST-RUN SETUP</div>
        <div class="dim">Tell us where your Jaeger instance lives. The app will test the connection and remember it.</div>
      </div>
    </div>
    <div class="settings-form">
      <div class="form-row">
        <label>Jaeger URL</label>
        <input type="text" id="fr-jaeger" value="${state.settings.jaegerUrl || 'http://localhost:16687'}" />
        <button class="btn" id="fr-test">Test</button>
      </div>
      <div class="form-row form-actions">
        <span id="fr-status" class="dim">Click test to verify, then continue.</span>
      </div>
      <div class="form-row form-actions">
        <button class="btn primary" id="fr-save" disabled>Continue</button>
      </div>
    </div>
  `;
  document.getElementById('fr-test').addEventListener('click', async () => {
    const url = document.getElementById('fr-jaeger').value.trim();
    const status = document.getElementById('fr-status');
    status.textContent = 'testing…'; status.className = 'dim';
    const res = await (window.edgeless && window.edgeless.testJaeger
      ? window.edgeless.testJaeger(url) : Promise.resolve({ ok: false, error: 'IPC unavailable' }));
    if (res.ok) {
      status.textContent = `✓ connected · ${res.services} services detected`;
      status.className = 'glow-cyan';
      document.getElementById('fr-save').disabled = false;
    } else {
      status.textContent = `✗ ${res.error}`;
      status.className = 'glow-red';
    }
  });
  document.getElementById('fr-save').addEventListener('click', async () => {
    const url = document.getElementById('fr-jaeger').value.trim();
    const res = await window.edgeless.setSettings({ jaegerUrl: url, firstRunComplete: true });
    if (res.ok) {
      state.settings = res.settings;
      modal.classList.remove('open', 'no-close');
      tick();
    }
  });
}

// ── Modal helpers ──────────────────────────────────────────────────
function closeModal() {
  const modal = document.getElementById('detail-modal');
  if (modal.classList.contains('no-close')) return;
  modal.classList.remove('open');
  // If we were on a non-overview view, navigate back
  if (state.view !== 'overview') navigate('#/overview');
}

// ── Router ─────────────────────────────────────────────────────────
function parseHash() {
  const h = (location.hash || '#/overview').replace(/^#/, '');
  const parts = h.split('/').filter(Boolean);
  if (parts[0] === 'trace' && parts[1]) return { view: 'trace', id: decodeURIComponent(parts[1]) };
  if (parts[0] === 'service' && parts[1]) return { view: 'service', name: decodeURIComponent(parts[1]) };
  if (parts[0] === 'op' && parts[1]) return { view: 'op', op: decodeURIComponent(parts[1]) };
  if (parts[0] === 'anomalies') return { view: 'anomalies' };
  if (parts[0] === 'settings') return { view: 'settings' };
  return { view: 'overview' };
}

function navigate(hash) {
  if (location.hash !== hash) location.hash = hash;
  else handleRoute();
}

async function handleRoute() {
  const r = parseHash();
  state.view = r.view;
  state.selectedTraceId = r.id || null;
  state.selectedService = r.name || null;

  const overlay = document.getElementById('detail-modal');
  if (r.view === 'overview') {
    overlay.classList.remove('open');
  } else if (r.view === 'trace') {
    await renderTraceDetail(r.id);
  } else if (r.view === 'service') {
    await renderServiceDetail(r.name);
  } else if (r.view === 'op') {
    // filter the overview to that op (simple: highlight + scroll). For now, jump to service detail.
    overlay.classList.remove('open');
    // future: per-op view
  } else if (r.view === 'settings') {
    renderSettings();
  }
  updateBreadcrumb(r);
}

function updateBreadcrumb(r) {
  const bc = document.getElementById('breadcrumb');
  if (!bc) return;
  let parts = ['<span class="bc-link" data-href="#/overview">Overview</span>'];
  if (r.view === 'trace') parts.push(`<span class="bc-sep">›</span><span class="bc-cur">Trace ${r.id.slice(0, 12)}…</span>`);
  if (r.view === 'service') parts.push(`<span class="bc-sep">›</span><span class="bc-cur">${r.name}</span>`);
  if (r.view === 'settings') parts.push('<span class="bc-sep">›</span><span class="bc-cur">Settings</span>');
  if (r.view === 'op') parts.push(`<span class="bc-sep">›</span><span class="bc-cur">op:${r.op}</span>`);
  bc.innerHTML = parts.join(' ');
  bc.querySelectorAll('.bc-link').forEach(a => a.addEventListener('click', () => navigate(a.dataset.href)));
}

// ── Header controls ────────────────────────────────────────────────
function renderServiceSelector() {
  const sel = document.getElementById('svc-select');
  if (!sel) return;
  const current = state.serviceFilter || '__all__';
  sel.innerHTML = `<option value="__all__">All services</option>` +
    state.services.map(s => `<option value="${s}"${s === current ? ' selected' : ''}>${s}</option>`).join('');
  sel.value = current;
  sel.onchange = () => {
    state.serviceFilter = sel.value === '__all__' ? null : sel.value;
    tick();
  };
}

function renderTimeWindow() {
  const sel = document.getElementById('window-select');
  if (!sel) return;
  sel.value = String(state.timeWindowMin);
  sel.onchange = () => {
    state.timeWindowMin = Number(sel.value);
    tick();
  };
}

const VALID_LAYOUTS = ['default', 'focus', 'wide', 'compact', 'stack'];
const LAYOUT_KEY = 'edgeless-otel-layout';

function applyLayout(name) {
  if (!VALID_LAYOUTS.includes(name)) name = 'default';
  const main = document.querySelector('main');
  if (main) main.setAttribute('data-layout', name);
  const sel = document.getElementById('layout-select');
  if (sel) sel.value = name;
  try { localStorage.setItem(LAYOUT_KEY, name); } catch (e) {}
}

function initLayout() {
  let saved;
  try { saved = localStorage.getItem(LAYOUT_KEY); } catch (e) {}
  applyLayout(saved || 'default');
  const sel = document.getElementById('layout-select');
  if (sel) sel.onchange = () => applyLayout(sel.value);
}

// ── Theme system (kept from v1.0) ──────────────────────────────────
const THEME_KEY = 'edgeless-otel-theme';

function applyTheme(name) {
  document.documentElement.setAttribute('data-theme', name);
  document.querySelectorAll('#theme-switcher .theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === name);
  });
  try { localStorage.setItem(THEME_KEY, name); } catch (e) {}
}

function initTheme() {
  let saved;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
  applyTheme(saved || state.settings.defaultTheme || 'phosphor');
  document.querySelectorAll('#theme-switcher .theme-btn').forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });
}

// ── Main tick ──────────────────────────────────────────────────────
async function tick() {
  try {
    document.getElementById('jaeger-status').textContent = 'POLLING';
    // 1. Fetch services
    const services = await fetchServices();
    state.services = services;
    document.getElementById('svc-count').textContent = services.length;
    renderServiceSelector();

    // 2. Fetch traces per service (parallel) within the time window
    const fetched = await Promise.all(services.map(async (s) => [s, await fetchTracesFor(s, 100)]));
    const byService = {};
    for (const [svc, traces] of fetched) byService[svc] = traces;
    state.serviceTraces = byService;

    // 3. Aggregate + render overview
    const a = analyze(byService);
    const rollup = serviceRollup(byService);
    renderMetrics(a);
    renderDonut(a);
    renderSparkline(a);
    renderOpChart(a);
    renderHeatmap(a);
    renderLog(a);
    renderTraces(a);
    renderMiniTree(a);
    renderServices(rollup);

    // 4. Anomalies (built-in + plug-in rules)
    const builtinAnomalies = detectAnomalies(byService, rollup);
    const pluginAnomalies = runPluginAnomalies(a, rollup);
    // Merge: drop the "ALL_CLEAR" placeholder if any real anomalies exist
    const real = [...builtinAnomalies.filter(x => x.severity !== 'ok'), ...pluginAnomalies];
    state.anomalies = real.length ? real : builtinAnomalies;
    renderAnomalies();

    // 4b. Plug-in panels
    renderPluginPanels(a, rollup);
    // Track anomalies in history
    for (const an of state.anomalies) {
      if (an.severity === 'ok') continue;
      // Dedupe by kind+title; only push if not already in last 5
      const recent = state.anomalyLog.slice(-5);
      if (!recent.some(x => x.kind === an.kind && x.title === an.title)) {
        state.anomalyLog.push(an);
        if (state.anomalyLog.length > 100) state.anomalyLog.shift();
      }
    }

    // 5. History + waveform
    state.history.push({ t: Date.now(), traces: a.traces.length, spans: a.total, err: a.err });
    if (state.history.length > 50) state.history.shift();
    updateWaveform();

    document.getElementById('jaeger-status').textContent = 'ONLINE';
  } catch (e) {
    document.getElementById('jaeger-status').textContent = 'OFFLINE';
    console.error('[tick]', e);
  }
}

// ── Plug-in host API ───────────────────────────────────────────────
// `window.edgelessHost` is what plug-in `index.js` files receive as
// `edgeless` when their `activate(edgeless)` function is called. It is
// strictly smaller and more stable than the internal renderer state.
const pluginRegistry = {
  panels: {},         // { panelId: { plugin, def } }
  anomalies: {},      // { ruleId:  { plugin, def } }
  themes: {},         // { themeId: cssText }
  failed: {},         // { pluginId: errorMessage }
  enabled: [],        // [{ id, name, version, ... }]
  eventBus: new EventTarget(),
};

function makeHostApi(plugin) {
  const ns = plugin.id;
  const log = (msg, level = 'info') => {
    const fn = console[level] || console.log;
    fn(`[plugin ${plugin.id}] ${msg}`);
  };
  // Storage key prefix scopes per-plugin
  const storageKey = (k) => `plugin:${plugin.id}:${k}`;
  return {
    app: {
      version: '1.2.0',
      log,
    },
    panels: {
      register(id, def) {
        if (!id.startsWith(ns)) {
          throw new Error(`panel id "${id}" must start with plugin id "${ns}"`);
        }
        if (!def || typeof def.render !== 'function') {
          throw new Error('panel def requires render(container, ctx)');
        }
        pluginRegistry.panels[id] = {
          plugin,
          def: {
            ...def,
            render: wrapPanelRender(plugin, def.render),
          },
        };
        log(`registered panel: ${id}`);
      },
      list() {
        return Object.keys(pluginRegistry.panels).map(id => ({
          id,
          label: pluginRegistry.panels[id].def.label,
          plugin: pluginRegistry.panels[id].plugin.id,
        }));
      },
    },
    anomalies: {
      register(id, def) {
        if (!id.startsWith(ns)) {
          throw new Error(`anomaly id "${id}" must start with plugin id "${ns}"`);
        }
        if (typeof def.detect !== 'function') throw new Error('anomaly def requires detect(ctx)');
        pluginRegistry.anomalies[id] = { plugin, def };
        log(`registered anomaly rule: ${id}`);
      },
      list() {
        return Object.keys(pluginRegistry.anomalies);
      },
    },
    themes: {
      register(id, css) {
        if (!id.startsWith(ns)) throw new Error(`theme id "${id}" must start with "${ns}"`);
        pluginRegistry.themes[id] = css;
        // Inject into a dedicated <style> tag so we can un-register cleanly
        let el = document.getElementById('plugin-theme-' + id);
        if (!el) {
          el = document.createElement('style');
          el.id = 'plugin-theme-' + id;
          document.head.appendChild(el);
        }
        el.textContent = `[data-theme="${id}"] { ${css} }`;
        log(`registered theme: ${id}`);
      },
    },
    router: {
      navigate: (hash) => navigate(hash),
      current: () => parseHash(),
    },
    jaeger: {
      fetch: (apiPath) => fetch(state.jaeger + apiPath).then(r => r.json()),
      fetchTrace: (id) => fetchTraceById(id),
    },
    lib: {
      fmtDur, fmtAge, hashColor, tagsToObj,
    },
    storage: {
      async get(key) {
        try { return JSON.parse(localStorage.getItem(storageKey(key))); }
        catch { return null; }
      },
      async set(key, value) {
        localStorage.setItem(storageKey(key), JSON.stringify(value));
      },
    },
    events: {
      on(event, cb) {
        const handler = (e) => cb(e.detail);
        pluginRegistry.eventBus.addEventListener(event, handler);
        return () => pluginRegistry.eventBus.removeEventListener(event, handler);
      },
    },
  };
}

function wrapPanelRender(plugin, renderFn) {
  return (container, ctx) => {
    try {
      return renderFn(container, ctx);
    } catch (e) {
      container.innerHTML = `<div class="plugin-error">⚠ ${plugin.id}: ${escapeHtml(e.message)}</div>`;
      console.error(`[plugin ${plugin.id}] render error:`, e);
    }
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

async function loadPlugin(plugin) {
  if (!plugin.enabled) return;
  if (plugin.error) {
    pluginRegistry.failed[plugin.id] = plugin.error;
    return;
  }
  try {
    const entryUrl = `/plugins/${plugin.id}/index.js?v=${plugin.version}`;
    const mod = await import(entryUrl);
    const activate = mod.default || mod.activate;
    if (typeof activate !== 'function') {
      throw new Error('no default export — expected `export default function activate(edgeless)`');
    }
    activate(makeHostApi(plugin));
    pluginRegistry.enabled.push(plugin);
  } catch (e) {
    pluginRegistry.failed[plugin.id] = e.message;
    console.error(`[plugin ${plugin.id}] load failed:`, e);
  }
}

async function loadAllPlugins() {
  if (!window.edgeless || !window.edgeless.pluginsList) return;
  const list = await window.edgeless.pluginsList();
  for (const p of list) await loadPlugin(p);
  // Emit a one-time "plugins-ready" event for the dashboard
  pluginRegistry.eventBus.dispatchEvent(new CustomEvent('plugins-ready', { detail: { count: pluginRegistry.enabled.length } }));
}

// Build ctx passed to plug-in panels and anomaly rules on each tick
function buildPluginCtx(a, rollup) {
  return {
    traces: a.traces,
    services: state.services,
    byService: state.serviceTraces,
    rollup,
    anomalies: state.anomalies,
    settings: { ...state.settings },
    serviceFilter: state.serviceFilter,
    timeWindowMin: state.timeWindowMin,
    lib: { fmtDur, fmtAge, hashColor, tagsToObj },
  };
}

// Run all registered plug-in anomaly rules
function runPluginAnomalies(a, rollup) {
  const out = [];
  const ctx = {
    traces: a.traces,
    byService: state.serviceTraces,
    rollup,
    timeWindowMin: state.timeWindowMin,
  };
  for (const [id, entry] of Object.entries(pluginRegistry.anomalies)) {
    try {
      const found = entry.def.detect(ctx) || [];
      for (const f of found) {
        out.push({
          severity: f.severity || entry.def.severity || 'warn',
          kind: f.kind || id,
          title: f.title || entry.def.label,
          detail: f.detail || '',
          service: f.service,
          traceID: f.traceID,
          ts: Date.now(),
        });
      }
    } catch (e) {
      console.error(`[plugin ${entry.plugin.id}] anomaly rule "${id}" failed:`, e);
    }
  }
  return out;
}

// Render registered plug-in panels into the main grid. Each panel
// gets data-panel-id matching its registration id, so the panel
// visibility toggles + layout system treat plug-ins identically to
// built-ins.
function renderPluginPanels(a, rollup) {
  const host = document.querySelector('main');
  if (!host) return;
  const ctx = buildPluginCtx(a, rollup);
  const hidden = new Set((state.settings && state.settings.hiddenPanels) || []);
  for (const [id, entry] of Object.entries(pluginRegistry.panels)) {
    let panel = host.querySelector(`[data-panel-id="${CSS.escape(id)}"]`);
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'panel';
      panel.dataset.panelId = id;
      panel.dataset.pluginPanel = id;
      panel.setAttribute('data-label', entry.def.label || id);
      const inner = document.createElement('div');
      inner.className = 'panel-content';
      panel.appendChild(inner);
      host.appendChild(panel);
    }
    // Apply hide-state from settings
    panel.dataset.hidden = hidden.has(id) ? 'true' : 'false';
    const inner = panel.querySelector('.panel-content');
    entry.def.render(inner, ctx);
  }
  // Also apply hide-state to built-ins
  host.querySelectorAll('.panel[data-panel-id]').forEach(p => {
    const pid = p.dataset.panelId;
    if (pluginRegistry.panels[pid]) return; // already handled above
    p.dataset.hidden = hidden.has(pid) ? 'true' : 'false';
  });
}

// ── Bootstrap ──────────────────────────────────────────────────────
async function init() {
  // Load settings
  if (window.edgeless && window.edgeless.getSettings) {
    state.settings = await window.edgeless.getSettings();
  } else {
    state.settings = {
      jaegerUrl: 'http://localhost:16687',
      anomalyThresholds: { ghostAgentMin: 30, phantomStallMin: 30, loopThreshold: 5, loopWindowSec: 300 },
      firstRunComplete: true,
    };
  }
  initTheme();
  initLayout();
  initWaveform();
  renderTimeWindow();

  // First-run check
  if (!state.settings.firstRunComplete) {
    renderFirstRun();
    return;
  }

  // Wire modal close + ESC + back button
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
  document.getElementById('detail-close').addEventListener('click', closeModal);
  document.getElementById('detail-modal').addEventListener('click', (e) => {
    if (e.target.id === 'detail-modal') closeModal();
  });

  // Wire settings gear
  document.getElementById('settings-btn').addEventListener('click', () => navigate('#/settings'));

  // Wire router
  window.addEventListener('hashchange', handleRoute);
  handleRoute();

  // Clock
  setInterval(() => {
    document.getElementById('clock').textContent = fmtTime(new Date());
  }, 1000);

  // Load plug-ins BEFORE first tick so they show on the first render
  await loadAllPlugins();

  // Initial fetch + interval
  await tick();
  setInterval(tick, state.settings.refreshIntervalMs || 10000);
}

init();
