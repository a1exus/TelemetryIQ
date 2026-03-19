# HUD Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `index.html` into a full engineering display (all telemetry fields always visible + post-lap Chart.js overlay), and rename the analysis route from `/analysis` to `/compare`.

**Architecture:** Pure front-end + route rename. No new Python endpoints, no changes to `repository.py`, `recorder.py`, `client.py`, or `__main__.py`. `server.py` changes one route. `index.html` is fully rewritten to split into a top zone (60%: live instruments) and bottom zone (40%: Chart.js last-vs-best-lap charts, populated after each lap transition via `GET /laps` + `GET /laps/{id}/frames`).

**Tech Stack:** Python/FastAPI (existing), vanilla JS, Chart.js 4.4.4 (CDN). No npm, no build step.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Rename | `rexy/static/analysis.html` → `rexy/static/compare.html` | Analysis page served at `/compare` |
| Modify | `rexy/server.py` | Route `GET /analysis` → `GET /compare`; serve `compare.html` |
| Modify | `tests/test_api.py` | Update test to hit `/compare` |
| Modify | `rexy/static/index.html` | Full HUD redesign — live fields + Chart.js bottom zone |
| Modify | `specs.md` | Mark HUD redesign success criterion complete; update roadmap |

---

## Housekeeping: commit pending changes

Before touching code, commit the uncommitted README and specs changes that already exist in the working tree. These track the split of Phase 3 into two sub-items (analysis dashboard done, HUD redesign in progress).

- [ ] **Step 1 — Stage and commit**

```bash
git add README.md specs.md
git commit -m "docs: split Phase 3 goal into analysis dashboard (done) and HUD redesign (in progress)"
```

---

## Task 1 — Rename `/analysis` → `/compare`

**Files:**
- Rename: `rexy/static/analysis.html` → `rexy/static/compare.html`
- Modify: `rexy/server.py:88-90`
- Modify: `tests/test_api.py:63-66`

- [ ] **Step 1 — Replace the failing test**

In `tests/test_api.py`, **delete** `test_analysis_page_served` and **replace it** with `test_compare_page_served`. The file must not contain both functions after this step — the old function references `/analysis` which no longer exists after the route rename, and will fail.

Old function to remove:
```python
def test_analysis_page_served():
    r = TestClient(app).get("/analysis")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
```

Replace with (in the same location at the bottom of the file):
```python
def test_compare_page_served():
    r = TestClient(app).get("/compare")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
```

- [ ] **Step 2 — Run test to confirm it fails**

```bash
source .venv/bin/activate
pytest tests/test_api.py::test_compare_page_served -v
```

Expected: `FAILED` — `/compare` returns 404 because the route doesn't exist yet.

- [ ] **Step 3 — Rename the HTML file**

```bash
git mv rexy/static/analysis.html rexy/static/compare.html
```

- [ ] **Step 4 — Update the route in `server.py`**

Change `rexy/server.py` lines 88–90 from:
```python
@app.get("/analysis")
async def analysis() -> FileResponse:
    return FileResponse(_STATIC / "analysis.html")
```
To:
```python
@app.get("/compare")
async def compare() -> FileResponse:
    return FileResponse(_STATIC / "compare.html")
```

- [ ] **Step 5 — Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass including `test_compare_page_served`.

- [ ] **Step 6 — Commit**

```bash
git add rexy/server.py tests/test_api.py rexy/static/compare.html
git commit -m "feat: rename /analysis route to /compare; serve compare.html"
```

---

## Task 2 — Redesign `index.html`

**Files:**
- Modify: `rexy/static/index.html` (full replacement)

No Python code changes. No new tests — this is a pure UI rewrite.

### Layout overview

```
#app (flex column, height: 100svh, overflow: hidden)
├── #topbar          (flex-shrink: 0)  status + Compare link
├── #top-zone        (flex: 0 0 60%)   all live telemetry fields
│   ├── #shift-bar
│   ├── #instruments  Speed | Gear | RPM
│   ├── #lap-section  running time · delta · last · best
│   ├── #pedals       T / B bars
│   ├── #badges       TCS · ASM · REV · suggested gear · fuel
│   ├── #tires        FL/FR/RL/RR temp + sus height
│   └── #extra        thermal · car state · body motion (HB-B) · filtered (HB-~)
└── #bottom-zone     (flex: 0 0 40%)   Chart.js post-lap overlay
    ├── Chart 1: throttle% (green) + brake% (red) — last lap only
    └── Chart 2: speed km/h — last lap (blue) + best lap (orange)
```

Chart logic:
- Triggered on `d.current_lap` raw increment (before `lapOffset`)
- `GET /laps` → if empty, skip silently (normal on race start before any complete lap)
- Find `lastLap = laps[0]` (server returns newest first); `bestLap = min by lap_time_ms`
- If same id: fetch frames once; else fetch in parallel
- Chart instances created on first non-empty call; data swapped in-place on subsequent laps
- Charts hidden behind placeholder until first data arrives

- [ ] **Step 1 — Write the new `index.html`**

Replace the entire contents of `rexy/static/index.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>TelemetryIQ</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; overflow: hidden;
               font-family: 'Courier New', monospace;
               background: #0d0d0d; color: #e0e0e0; }

  #app { display: flex; flex-direction: column; height: 100svh; overflow: hidden; }

  /* ── Top bar ──────────────────────────────────────────── */
  #topbar { display: flex; justify-content: space-between; align-items: center;
            flex-shrink: 0; padding: 0.3rem 0.5rem;
            border-bottom: 1px solid #1a1a1a; }
  #status { font-size: 0.7rem; padding: 0.12rem 0.4rem; border-radius: 3px;
            background: #1a1a1a; border: 1px solid #333; }
  #status.connected    { border-color: #2a7; color: #2a7; }
  #status.disconnected { border-color: #a33; color: #a33; }
  #compare-link { font-size: 0.7rem; color: #4af; text-decoration: none;
                  padding: 0.12rem 0.4rem; border: 1px solid #1a4a8a; border-radius: 3px; }
  #compare-link:hover { color: #8cf; }

  /* ── Top zone (60%) ───────────────────────────────────── */
  #top-zone { flex: 0 0 60%; display: flex; flex-direction: column;
              gap: 0.3rem; padding: 0.3rem 0.5rem; overflow: hidden; min-height: 0; }

  /* ── Shift bar ────────────────────────────────────────── */
  #shift-bar { display: flex; gap: 3px; height: 1.1rem; flex-shrink: 0; }
  .seg { flex: 1; border-radius: 2px; background: #141414; border: 1px solid #1e1e1e; }
  .seg.grn { background: #1ef060; }
  .seg.amb { background: #ffa020; }
  .seg.red { background: #ff3030; }
  .seg.flash { animation: blink 0.1s step-end infinite; }
  @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0.1; } }

  /* ── Instruments ──────────────────────────────────────── */
  #instruments { display: grid; grid-template-columns: 1fr 1.1fr 1fr;
                 gap: 0.3rem; flex: 1; min-height: 0; max-height: 6rem; }
  .inst { background: #111; border: 1px solid #1e1e1e; border-radius: 5px;
          display: flex; flex-direction: column;
          justify-content: center; align-items: center;
          padding: 0.3rem; min-height: 0; overflow: hidden; }
  .inst-lbl  { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.12em;
               color: #444; flex-shrink: 0; }
  .inst-val  { font-weight: bold; line-height: 1; letter-spacing: -0.03em;
               font-size: clamp(1.8rem, 7vw, 3.5rem); }
  .inst-unit { font-size: 0.6rem; color: #444; text-transform: uppercase;
               letter-spacing: 0.08em; flex-shrink: 0; }
  #current_gear { font-size: clamp(3rem, 13vw, 6rem); color: #e0e0e0; }
  #speed_kph    { color: #4af; }
  #engine_rpm   { color: #ccc; }

  /* ── Lap section ──────────────────────────────────────── */
  #lap-section { background: #111; border: 1px solid #1e1e1e; border-radius: 5px;
                 padding: 0.3rem 0.6rem; flex-shrink: 0; }
  #lap-primary { display: flex; justify-content: space-between; align-items: center; }
  #lap-counter  { font-size: 0.6rem; color: #444; text-transform: uppercase; letter-spacing: 0.1em; }
  #running-time { font-size: clamp(1.2rem, 4vw, 1.7rem); font-weight: bold; color: #e0e0e0; }
  #lap-delta    { font-size: clamp(1.2rem, 4vw, 1.7rem); font-weight: bold; }
  #lap-delta.ahead  { color: #4f4; }
  #lap-delta.behind { color: #f44; }
  #lap-delta.none   { color: #333; }
  #lap-secondary { display: flex; justify-content: space-between; font-size: 0.75rem;
                   margin-top: 0.1rem; }
  .sub-lbl { color: #444; }
  .sub-val { color: #4af; font-weight: bold; margin-left: 0.25rem; }

  /* ── Pedals ───────────────────────────────────────────── */
  #pedals { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem; flex-shrink: 0; }
  .pedal { display: flex; align-items: center; gap: 0.3rem; }
  .pedal-lbl   { font-size: 0.6rem; text-transform: uppercase; color: #444;
                 letter-spacing: 0.08em; width: 1rem; flex-shrink: 0; }
  .pedal-track { flex: 1; height: 0.8rem; background: #1a1a1a;
                 border-radius: 2px; border: 1px solid #1e1e1e; overflow: hidden; }
  .pedal-fill  { height: 100%; width: 0%; border-radius: 2px; }
  #t-fill { background: #4f4; }
  #b-fill { background: #f44; }
  .pedal-pct { font-size: 0.65rem; font-weight: bold; width: 2.5rem;
               text-align: right; flex-shrink: 0; }
  #t-pct { color: #4f4; }
  #b-pct { color: #f44; }

  /* ── Badges ───────────────────────────────────────────── */
  #badges { display: flex; gap: 0.3rem; align-items: center; flex-shrink: 0; }
  .badge { font-size: 0.6rem; padding: 0.1rem 0.4rem; border-radius: 3px;
           border: 1px solid #222; color: #333; letter-spacing: 0.07em;
           text-transform: uppercase; }
  .badge.on { background: #2a1800; border-color: #fa4; color: #fa4; }
  #sugg-gear { font-size: 0.75rem; font-weight: bold; color: #fa4;
               padding: 0.1rem 0.4rem; border: 1px solid #8a4a00;
               background: #2a1500; border-radius: 3px; }
  #fuel-val  { margin-left: auto; font-size: 0.8rem; font-weight: bold; }
  #fuel-val .lbl { color: #444; font-size: 0.6rem; text-transform: uppercase;
                   letter-spacing: 0.08em; margin-right: 0.2rem; }

  /* ── Tires ────────────────────────────────────────────── */
  #tires { display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; flex-shrink: 0; }
  .tire { background: #111; border: 1px solid #1e1e1e; border-radius: 4px;
          display: flex; justify-content: space-between; align-items: center;
          padding: 0.15rem 0.5rem; }
  .tire-pos  { font-size: 0.6rem; color: #444; text-transform: uppercase;
               letter-spacing: 0.08em; }
  .tire-temp { font-size: 0.9rem; font-weight: bold; }
  .tire-sus  { font-size: 0.65rem; color: #666; }

  /* ── Extra fields (always visible) ───────────────────── */
  #extra { display: grid; grid-template-columns: 1fr 1fr; gap: 0.25rem; flex-shrink: 0; }
  .ext-card { background: #111; border: 1px solid #1e1e1e; border-radius: 4px;
              padding: 0.25rem 0.5rem; }
  .ext-card h4 { font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.12em;
                 color: #444; margin-bottom: 0.15rem; }
  .ext-row { display: flex; justify-content: space-between; font-size: 0.7rem; padding: 0.05rem 0; }
  .ext-lbl { color: #555; }
  .ext-val { color: #ccc; font-weight: bold; }
  .hidden { display: none !important; }

  /* ── Bottom zone (40%) ────────────────────────────────── */
  #bottom-zone { flex: 0 0 40%; display: flex; flex-direction: column;
                 gap: 0.25rem; padding: 0.3rem 0.5rem;
                 border-top: 1px solid #1a1a1a; min-height: 0; overflow: hidden; }
  #chart-placeholder { color: #444; font-size: 0.75rem; text-align: center;
                       margin: auto; }
  .chart-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column;
                background: #111; border: 1px solid #1e1e1e; border-radius: 4px;
                padding: 0.3rem 0.4rem; }
  .chart-lbl  { font-size: 0.55rem; text-transform: uppercase; letter-spacing: 0.1em;
                color: #555; margin-bottom: 0.15rem; flex-shrink: 0; }
  canvas { flex: 1; min-height: 0; }
</style>
</head>
<body>
<div id="app">

  <div id="topbar">
    <span id="status" class="disconnected">&#9679; Connecting&#8230;</span>
    <a id="compare-link" href="/compare">Compare &#8599;</a>
  </div>

  <div id="top-zone">

    <div id="shift-bar">
      <div class="seg" id="s0"></div><div class="seg" id="s1"></div>
      <div class="seg" id="s2"></div><div class="seg" id="s3"></div>
      <div class="seg" id="s4"></div><div class="seg" id="s5"></div>
      <div class="seg" id="s6"></div><div class="seg" id="s7"></div>
      <div class="seg" id="s8"></div><div class="seg" id="s9"></div>
      <div class="seg" id="s10"></div><div class="seg" id="s11"></div>
    </div>

    <div id="instruments">
      <div class="inst">
        <div class="inst-lbl">Speed</div>
        <div class="inst-val" id="speed_kph">---</div>
        <div class="inst-unit">km/h</div>
      </div>
      <div class="inst">
        <div class="inst-lbl">Gear</div>
        <div class="inst-val" id="current_gear">-</div>
      </div>
      <div class="inst">
        <div class="inst-lbl">RPM</div>
        <div class="inst-val" id="engine_rpm">----</div>
      </div>
    </div>

    <div id="lap-section">
      <div id="lap-primary">
        <div>
          <div id="lap-counter">Lap <span id="current_lap">--</span> / <span id="total_laps">--</span></div>
          <div id="running-time">--:--.---</div>
        </div>
        <div id="lap-delta" class="none">--</div>
      </div>
      <div id="lap-secondary">
        <span><span class="sub-lbl">LAST</span><span class="sub-val" id="last_lap_time">--:--.---</span></span>
        <span><span class="sub-lbl">BEST</span><span class="sub-val" id="best_lap_time">--:--.---</span></span>
      </div>
    </div>

    <div id="pedals">
      <div class="pedal">
        <span class="pedal-lbl">T</span>
        <div class="pedal-track"><div class="pedal-fill" id="t-fill"></div></div>
        <span class="pedal-pct" id="t-pct">0%</span>
      </div>
      <div class="pedal">
        <span class="pedal-lbl">B</span>
        <div class="pedal-track"><div class="pedal-fill" id="b-fill"></div></div>
        <span class="pedal-pct" id="b-pct">0%</span>
      </div>
    </div>

    <div id="badges">
      <span class="badge" id="tcs-badge">TCS</span>
      <span class="badge" id="asm-badge">ASM</span>
      <span class="badge" id="rev-badge">REV</span>
      <span id="sugg-gear" class="hidden">SG <span id="sugg-gear-val">--</span></span>
      <span id="fuel-val"><span class="lbl">Fuel</span><span id="fuel_pct">--%</span></span>
    </div>

    <div id="tires">
      <div class="tire"><span class="tire-pos">FL</span>
        <span class="tire-temp" id="tfl">--&#176;</span>
        <span class="tire-sus"  id="sfl">--mm</span></div>
      <div class="tire"><span class="tire-pos">FR</span>
        <span class="tire-temp" id="tfr">--&#176;</span>
        <span class="tire-sus"  id="sfr">--mm</span></div>
      <div class="tire"><span class="tire-pos">RL</span>
        <span class="tire-temp" id="trl">--&#176;</span>
        <span class="tire-sus"  id="srl">--mm</span></div>
      <div class="tire"><span class="tire-pos">RR</span>
        <span class="tire-temp" id="trr">--&#176;</span>
        <span class="tire-sus"  id="srr">--mm</span></div>
    </div>

    <div id="extra">
      <div class="ext-card">
        <h4>Thermal</h4>
        <div class="ext-row"><span class="ext-lbl">Oil temp</span><span class="ext-val" id="e-oil-temp">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Oil pres</span><span class="ext-val" id="e-oil-pres">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Water</span>   <span class="ext-val" id="e-water">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Boost</span>   <span class="ext-val" id="e-boost">--</span></div>
      </div>
      <div class="ext-card">
        <h4>Car state</h4>
        <div class="ext-row"><span class="ext-lbl">Car code</span>  <span class="ext-val" id="e-car-code">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Heartbeat</span> <span class="ext-val" id="e-hb">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Start pos</span> <span class="ext-val" id="e-race-start">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Cars</span>      <span class="ext-val" id="e-total-cars">--</span></div>
      </div>
      <div class="ext-card hidden" id="e-card-motion">
        <h4>Body motion (HB-B)</h4>
        <div class="ext-row"><span class="ext-lbl">Steering (rad)</span><span class="ext-val" id="e-steer">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Sway (m/s&#178;)</span> <span class="ext-val" id="e-sway">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Heave</span>            <span class="ext-val" id="e-heave">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Surge</span>            <span class="ext-val" id="e-surge">--</span></div>
      </div>
      <div class="ext-card hidden" id="e-card-filtered">
        <h4>Filtered (HB-~)</h4>
        <div class="ext-row"><span class="ext-lbl">Throttle filt</span><span class="ext-val" id="e-thr-filt">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Brake filt</span>   <span class="ext-val" id="e-brk-filt">--</span></div>
        <div class="ext-row"><span class="ext-lbl">Energy rec</span>   <span class="ext-val" id="e-energy">--</span></div>
      </div>
    </div>

  </div><!-- #top-zone -->

  <div id="bottom-zone">
    <p id="chart-placeholder">Waiting for lap data&#8230;</p>
    <div class="chart-wrap hidden" id="chart-tb-wrap">
      <p class="chart-lbl">Throttle (green) / Brake (red) &#8212; % &#183; last lap</p>
      <canvas id="chart-tb"></canvas>
    </div>
    <div class="chart-wrap hidden" id="chart-spd-wrap">
      <p class="chart-lbl">Speed &#8212; km/h &#183; blue = last &nbsp; orange = best</p>
      <canvas id="chart-spd"></canvas>
    </div>
  </div>

</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script>
'use strict';

let latest = {};
let retryDelay = 1000;
const maxDelay = 30000;

// ── Lap timer ──────────────────────────────────────────────
let prevOnTrack = false;
let prevLap     = null;   // for lap timer reset (lapOffset-adjusted)
let prevRawLap  = null;   // raw d.current_lap — chart trigger, no offset applied
let lapOffset   = 0;
let lapStartTs  = null;

// ── Chart instances ────────────────────────────────────────
const charts = {};  // { tb: Chart|null, spd: Chart|null }

// ── Shift bar ──────────────────────────────────────────────
const SEG_COLORS = ['grn','grn','grn','grn','grn','grn','grn','amb','amb','amb','red','red'];
const segs = Array.from({length: 12}, (_, i) => document.getElementById(`s${i}`));

function updateShiftBar(rpm, lo, hi) {
  const overRev = rpm >= hi;
  const ratio   = hi > lo ? (rpm - lo) / (hi - lo) : 0;
  const filled  = Math.round(Math.max(0, Math.min(1, ratio)) * 12);
  segs.forEach((s, i) => {
    if (!lo || !hi || hi <= lo) { s.className = 'seg'; return; }
    if (overRev) { s.className = 'seg red flash'; }
    else         { s.className = i < filled ? `seg ${SEG_COLORS[i]}` : 'seg'; }
  });
}

// ── Tire temp → color ──────────────────────────────────────
function tireTempColor(t) {
  if (t == null) return '#2a2a2a';
  if (t < 50)   return '#44f';
  if (t < 70)   return '#4af';
  if (t < 85)   return '#4f4';
  if (t < 100)  return '#fa4';
  return '#f44';
}

// ── Formatting ─────────────────────────────────────────────
function fmtMs(ms) {
  if (ms == null || ms === -1) return '--:--.---';
  const t = Math.max(0, ms | 0);
  const m = (t / 60000) | 0;
  const s = ((t % 60000) / 1000) | 0;
  const f = t % 1000;
  return `${m}:${String(s).padStart(2,'0')}.${String(f).padStart(3,'0')}`;
}

function fmtDelta(ms) {
  const sign = ms <= 0 ? '\u2212' : '+';
  const abs  = Math.abs(ms);
  const s    = (abs / 1000) | 0;
  const cs   = ((abs % 1000) / 10) | 0;
  return `${sign}${s}.${String(cs).padStart(2,'0')}`;
}

function set(id, v, fb = '--') {
  const el = document.getElementById(id);
  if (el) el.textContent = (v == null) ? fb : v;
}

// ── Chart helpers ──────────────────────────────────────────
const CHART_OPTS = {
  responsive: true, maintainAspectRatio: false, animation: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { type: 'linear', grid: { color: '#1e1e1e' },
         ticks: { color: '#555', maxTicksLimit: 6 } },
    y: { grid: { color: '#1e1e1e' }, ticks: { color: '#555' } },
  },
  elements: { point: { radius: 0 }, line: { borderWidth: 1.5, tension: 0 } },
};

function mkDs(frames, fn, color) {
  return { data: frames.map(f => ({ x: f.distance_m, y: fn(f) })),
           borderColor: color, fill: false, spanGaps: false };
}

async function updateCharts() {
  let laps;
  try { laps = await fetch('/laps').then(r => r.json()); } catch { return; }
  if (!laps.length) return;  // normal on 0→1 race-start increment

  const lastLap = laps[0];  // server returns newest first
  const bestLap = laps.reduce((b, l) => l.lap_time_ms < b.lap_time_ms ? l : b, laps[0]);

  let framesLast, framesBest;
  if (lastLap.id === bestLap.id) {
    framesLast = framesBest = await fetch(`/laps/${lastLap.id}/frames`).then(r => r.json());
  } else {
    [framesLast, framesBest] = await Promise.all([
      fetch(`/laps/${lastLap.id}/frames`).then(r => r.json()),
      fetch(`/laps/${bestLap.id}/frames`).then(r => r.json()),
    ]);
  }

  // Reveal charts, remove placeholder
  document.getElementById('chart-placeholder')?.remove();
  ['chart-tb-wrap', 'chart-spd-wrap'].forEach(id =>
    document.getElementById(id).classList.remove('hidden'));

  const tbDs = [
    mkDs(framesLast, f => (f.throttle ?? 0) / 255 * 100, '#4f4'),
    mkDs(framesLast, f => (f.brake    ?? 0) / 255 * 100, '#f44'),
  ];
  const spdDs = [
    mkDs(framesLast, f => (f.speed_mps ?? 0) * 3.6, '#4af'),
    mkDs(framesBest, f => (f.speed_mps ?? 0) * 3.6, '#fa4'),
  ];

  if (!charts.tb) {
    charts.tb  = new Chart(document.getElementById('chart-tb'),
      { type: 'line', data: { datasets: tbDs  }, options: CHART_OPTS });
    charts.spd = new Chart(document.getElementById('chart-spd'),
      { type: 'line', data: { datasets: spdDs }, options: CHART_OPTS });
  } else {
    charts.tb.data.datasets  = tbDs;  charts.tb.update();
    charts.spd.data.datasets = spdDs; charts.spd.update();
  }
}

// ── WebSocket ──────────────────────────────────────────────
function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws    = new WebSocket(`${proto}//${location.host}/ws`);
  const sEl   = document.getElementById('status');
  ws.onopen  = () => { sEl.textContent = '\u25cf Connected';
                       sEl.className = 'connected'; retryDelay = 1000; };
  ws.onmessage = e => { latest = JSON.parse(e.data); };
  ws.onclose   = () => {
    sEl.textContent = `\u25cf Reconnecting (${(retryDelay/1000)|0}s)\u2026`;
    sEl.className = 'disconnected';
    setTimeout(() => { retryDelay = Math.min(retryDelay * 2, maxDelay); connect(); }, retryDelay);
  };
}

// ── Render loop ────────────────────────────────────────────
function render() {
  const d = latest;
  if (d.speed_mps !== undefined) {
    const onTrack = !!d.cars_on_track;

    // Lap timer
    if (onTrack && !prevOnTrack) {
      lapOffset  = (d.current_lap ?? 1) - 1;
      lapStartTs = Date.now();
      prevLap    = d.current_lap;
      prevRawLap = d.current_lap;
    } else if (onTrack && d.current_lap !== prevLap && prevLap !== null) {
      lapStartTs = Date.now();
      prevLap    = d.current_lap;
    } else if (onTrack && prevLap === null) {
      lapStartTs = Date.now();
      prevLap    = d.current_lap;
      prevRawLap = d.current_lap;
    }
    if (!onTrack) { lapStartTs = null; prevLap = null; prevRawLap = null; }
    prevOnTrack = onTrack;

    // Chart trigger: raw current_lap increment
    if (onTrack && prevRawLap !== null && d.current_lap !== prevRawLap) {
      prevRawLap = d.current_lap;
      updateCharts();
    }

    const displayLap = onTrack ? Math.max(1, (d.current_lap ?? 1) - lapOffset) : '--';
    const runningMs  = (onTrack && lapStartTs) ? Date.now() - lapStartTs : null;
    const bestMs     = (d.best_lap_time_ms != null && d.best_lap_time_ms !== -1)
                       ? d.best_lap_time_ms : null;
    const deltaMs    = (runningMs != null && bestMs != null) ? runningMs - bestMs : null;

    // Shift bar
    updateShiftBar(d.engine_rpm ?? 0, d.min_alert_rpm, d.max_alert_rpm);

    // Instruments
    set('speed_kph',    (d.speed_mps * 3.6).toFixed(0));
    set('engine_rpm',   d.engine_rpm?.toFixed(0));
    set('current_gear', d.current_gear === 0 ? 'R' : d.current_gear >= 15 ? 'N' : d.current_gear);

    // Lap
    set('current_lap',   displayLap);
    set('total_laps',    d.total_laps);
    set('running-time',  fmtMs(runningMs));
    set('last_lap_time', fmtMs(d.last_lap_time_ms));
    set('best_lap_time', fmtMs(d.best_lap_time_ms));

    const dEl = document.getElementById('lap-delta');
    if (deltaMs != null) {
      dEl.textContent = fmtDelta(deltaMs);
      dEl.className   = deltaMs <= 0 ? 'ahead' : 'behind';
    } else {
      dEl.textContent = '--';
      dEl.className   = 'none';
    }

    // Pedals
    const tPct = (d.throttle ?? 0) / 255 * 100;
    const bPct = (d.brake    ?? 0) / 255 * 100;
    document.getElementById('t-fill').style.width = tPct + '%';
    document.getElementById('b-fill').style.width = bPct + '%';
    set('t-pct', tPct.toFixed(0) + '%');
    set('b-pct', bPct.toFixed(0) + '%');

    // Badges
    document.getElementById('tcs-badge').className = 'badge' + (d.tcs_active ? ' on' : '');
    document.getElementById('asm-badge').className = 'badge' + (d.asm_active ? ' on' : '');
    document.getElementById('rev-badge').className = 'badge' + (d.rev_limit  ? ' on' : '');

    // Suggested gear — hide when null, 0, or sentinel value >= 15
    const sg = d.suggested_gear;
    const showSg = sg != null && sg > 0 && sg < 15;
    document.getElementById('sugg-gear').classList.toggle('hidden', !showSg);
    if (showSg) set('sugg-gear-val', sg);

    // Fuel
    set('fuel_pct', d.fuel_capacity > 0
        ? ((d.fuel_level / d.fuel_capacity) * 100).toFixed(0) + '%' : '--%');

    // Tires — temp (color-coded) + suspension height
    [['fl','tfl','sfl'],['fr','tfr','sfr'],['rl','trl','srl'],['rr','trr','srr']].forEach(([k, tId, sId]) => {
      const t   = d[`tire_${k}_temp`];
      const sus = d[`tire_${k}_sus_height`];
      const tEl = document.getElementById(tId);
      if (tEl) {
        tEl.textContent  = t != null ? t.toFixed(0) + '\u00b0' : '--\u00b0';
        tEl.style.color  = tireTempColor(t);
      }
      set(sId, sus != null ? sus.toFixed(1) + 'mm' : '--mm');
    });

    // Extra — Thermal
    set('e-oil-temp',  d.oil_temp      != null ? d.oil_temp.toFixed(1)      + ' \u00b0C' : null);
    set('e-oil-pres',  d.oil_pressure  != null ? d.oil_pressure.toFixed(2)              : null);
    set('e-water',     d.water_temp    != null ? d.water_temp.toFixed(1)    + ' \u00b0C' : null);
    set('e-boost',     d.boost_pressure != null ? d.boost_pressure.toFixed(2)            : null);

    // Extra — Car state
    set('e-car-code',   d.car_code);
    set('e-hb',         d.heartbeat_type);
    set('e-race-start', d.race_start_pos);
    set('e-total-cars', d.total_cars);

    // Extra — Body motion (HB-B)
    const isB = d.heartbeat_type === 'B';
    document.getElementById('e-card-motion').classList.toggle('hidden', !isB);
    if (isB) {
      set('e-steer', d.wheel_rotation_radians != null ? d.wheel_rotation_radians.toFixed(2) : null);
      set('e-sway',  d.sway  != null ? d.sway.toFixed(3)  : null);
      set('e-heave', d.heave != null ? d.heave.toFixed(3) : null);
      set('e-surge', d.surge != null ? d.surge.toFixed(3) : null);
    }

    // Extra — Filtered inputs (HB-~)
    const isTilde = d.heartbeat_type === '~';
    document.getElementById('e-card-filtered').classList.toggle('hidden', !isTilde);
    if (isTilde) {
      set('e-thr-filt', ((d.throttle_filtered ?? 0) / 255 * 100).toFixed(0) + '%');
      set('e-brk-filt', ((d.brake_filtered    ?? 0) / 255 * 100).toFixed(0) + '%');
      set('e-energy',   d.energy_recovery != null ? d.energy_recovery.toFixed(3) : null);
    }
  }
  requestAnimationFrame(render);
}

connect();
requestAnimationFrame(render);
</script>
</body>
</html>
```

- [ ] **Step 2 — Manual verification checklist**

```bash
source .venv/bin/activate
python -m rexy
```

Open `http://localhost:8000`. Verify:

1. Page fills viewport with no scrollbar at any reasonable window size.
2. Top zone (~60%): shift bar, Speed/Gear/RPM, lap section, pedals, TCS/ASM/REV/fuel badges, tire temps with suspension heights, thermal+car-state cards.
3. Bottom zone (~40%): shows "Waiting for lap data…" placeholder.
4. "Compare ↗" link in topbar navigates to `/compare` (previously `/analysis`).
5. "Details ▾" button is **gone** — no overlay anywhere on the page.
6. After a lap completes in GT7: placeholder disappears; throttle/brake chart and speed chart appear.
7. Speed chart shows two lines (blue = last lap, orange = best lap).
8. Throttle/brake chart shows two lines (green = throttle, red = brake) for the last lap.
9. After subsequent laps: charts update in-place with no flicker (no animation).
10. With Heartbeat B: "Body motion" card appears with steering + sway/heave/surge.
11. With Heartbeat ~: "Filtered" card appears with throttle_filtered/brake_filtered/energy_recovery.

- [ ] **Step 3 — Commit**

```bash
git add rexy/static/index.html
git commit -m "feat: redesign HUD — full engineering display with post-lap Chart.js overlay"
```

---

## Task 3 — Update specs.md

**Files:**
- Modify: `specs.md`

- [ ] **Step 1 — Mark HUD redesign complete in goals list**

In `specs.md`, change:
```markdown
- [ ] Full live engineering display: all telemetry fields visible, post-lap Chart.js overlay
  (Phase 3 — HUD redesign)
```
To:
```markdown
- [x] Full live engineering display: all telemetry fields visible, post-lap Chart.js overlay
  (Phase 3 — HUD redesign)
```

- [ ] **Step 2 — Update roadmap row**

Change:
```markdown
| 3 | Analysis dashboard (`/compare`): REST API, distance-based trace charts, delta graph, track map; HUD redesign: full live display + post-lap overlay | 🔄 In progress |
```
To:
```markdown
| 3 | Analysis dashboard (`/compare`): REST API, distance-based trace charts, delta graph, track map; HUD redesign: full live display + post-lap overlay | ✅ Done |
```

- [ ] **Step 3 — Run full test suite one last time**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4 — Commit**

```bash
git add specs.md
git commit -m "docs: mark Phase 3 HUD redesign complete"
```

---

## Done

At the end of this plan:
- `/compare` serves the lap analysis page (was `/analysis`)
- `index.html` shows all telemetry fields without any overlay/toggle
- Post-lap Chart.js charts appear in the bottom zone after each lap transition
- All existing tests pass
- Phase 3 marked fully complete in `specs.md`
