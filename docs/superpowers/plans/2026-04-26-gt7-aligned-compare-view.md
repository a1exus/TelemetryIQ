# Phase 7: GT7-Aligned Compare View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `rexy/static/compare.html` into three tabs — Driving Line, Inputs, Powertrain — mirroring the organization of GT7 Spec III's in-game Data Logger while keeping all existing TelemetryIQ extras (N-lap overlay, N-lap delta, steering trace, gear trace, session browser, auto-diff banner, session notes, filters, baseline reference).

**Architecture:** Pure frontend refactor of `rexy/static/compare.html`. The data flow, REST API, and database are unchanged. The single HTML file gains a tab navigation strip; existing chart canvases are reorganized across three `tab-panel` containers; one new canvas (`ch-rpm`) is added to Tab 3; speed is rendered to two canvases (`ch-speed` in Tab 1, `ch-speed-pwr` in Tab 3); the track map moves into Tab 1; selected tab persists in URL hash (`#tab=line|inputs|powertrain`).

**Tech Stack:** Vanilla JS, Chart.js 4.4 (already loaded), Canvas API. No new dependencies. No build step.

**Testing approach:** This codebase has no JS test framework — tests are Python-only (FastAPI/repository). Each task's verification is a **manual browser check** with explicit pass criteria. The engineer must have a running dev environment and a SQLite DB containing at least one completed session with ≥3 complete laps. Use `make run` to start the server and open `http://localhost:8000/compare` in a browser.

**Pre-flight:** Engineer must confirm before Task 1:
- `make install` succeeds and `make run` starts the server.
- `telemetry.db` contains at least one session with ≥3 complete laps. If not, generate test data by running the app while playing GT7 (heartbeat type B preferred so steering/sway data is present), or use an existing dev DB.
- `/compare` currently renders the seven existing charts (speed, throttle, brake, gear, sway, steering, delta) plus the track map.

---

### Task 1: Add tab navigation scaffold + hash routing

**Files:**
- Modify: `rexy/static/compare.html`

This task adds the tab nav UI and JS hash routing without moving any charts yet. After this task, all existing charts still render exactly as before — they all live in the (currently sole) "Driving Line" panel. Tabs 2 and 3 exist but are empty placeholders.

- [ ] **Step 1: Verify current behavior**

Open `http://localhost:8000/compare` in a browser. Expand a session in the sidebar; confirm laps select and all seven charts plus the track map render. Note the DOM is currently a flat list of `.chart-wrap` divs inside `<main id="content">`.

- [ ] **Step 2: Add tab nav HTML**

In `rexy/static/compare.html`, replace the contents of `<main id="content">` (currently lines 118–144) with the following structure. Move the existing chart canvases and map into the `#tab-line` panel for now (no functional change):

```html
<main id="content">
  <p id="placeholder">Expand a session to overlay its laps.</p>

  <nav id="tabnav" role="tablist">
    <button class="tab-btn active" data-tab="line"      role="tab">Driving Line</button>
    <button class="tab-btn"        data-tab="inputs"    role="tab">Inputs</button>
    <button class="tab-btn"        data-tab="powertrain" role="tab">Powertrain</button>
  </nav>

  <div id="legend"></div>
  <div id="compare-hdr"></div>
  <div id="setup-diff"></div>

  <section class="tab-panel active" id="tab-line" role="tabpanel">
    <div class="chart-wrap"><p class="chart-lbl">Speed (km/h) &#8212; x: distance (m)</p>
      <canvas id="ch-speed" height="80"></canvas></div>
    <div class="chart-wrap"><p class="chart-lbl">Throttle (%) &#8212; x: distance (m)</p>
      <canvas id="ch-throttle" height="60"></canvas></div>
    <div class="chart-wrap"><p class="chart-lbl">Brake (%) &#8212; x: distance (m)</p>
      <canvas id="ch-brake" height="60"></canvas></div>
    <div class="chart-wrap"><p class="chart-lbl">Gear &#8212; x: distance (m)</p>
      <canvas id="ch-gear" height="50"></canvas></div>
    <div class="chart-wrap"><p class="chart-lbl">Lateral accel &#8212; sway, m/s&#178; (Heartbeat B only)</p>
      <canvas id="ch-sway" height="50"></canvas></div>
    <div class="chart-wrap"><p class="chart-lbl">Steering (rad, Heartbeat B only)</p>
      <canvas id="ch-steer" height="50"></canvas></div>
    <div class="chart-wrap"><p class="chart-lbl">Time Delta &#8212; vs reference lap (s)</p>
      <canvas id="ch-delta" height="60"></canvas></div>
    <div id="map-wrap">
      <p class="chart-lbl">Track Map &#8212; speed colormap (blue=slow &#8594; red=fast)</p>
      <canvas id="map-canvas" width="800" height="500"></canvas>
    </div>
  </section>

  <section class="tab-panel" id="tab-inputs" role="tabpanel"></section>
  <section class="tab-panel" id="tab-powertrain" role="tabpanel"></section>
</main>
```

- [ ] **Step 3: Add tab CSS**

Add the following to the `<style>` block, immediately before the `#placeholder` rule (around line 106 in the original file):

```css
  /* tabs */
  #tabnav { display: none; gap: 0.25rem; flex-shrink: 0; padding: 0; margin: 0;
            border-bottom: 1px solid #222; }
  #tabnav.visible { display: flex; }
  .tab-btn { background: transparent; color: #777; border: 0;
             border-bottom: 2px solid transparent;
             padding: 0.5rem 1rem; font-family: inherit; font-size: 0.75rem;
             letter-spacing: 0.08em; text-transform: uppercase; cursor: pointer; }
  .tab-btn:hover { color: #ccc; }
  .tab-btn.active { color: #4af; border-bottom-color: #4af; }
  .tab-panel { display: none; flex-direction: column; gap: 0.75rem; flex: 1; min-width: 0; }
  .tab-panel.active { display: flex; }
```

The tab nav is hidden until a session is expanded (matches existing behavior of the legend appearing only when laps are selected).

- [ ] **Step 4: Add tab switching JS**

Add the following block to the `<script>` near the top (after the `'use strict';` line):

```javascript
const TAB_IDS = ['line', 'inputs', 'powertrain'];

function readTabFromHash() {
  const m = window.location.hash.match(/tab=([a-z]+)/);
  const t = m && m[1];
  return TAB_IDS.includes(t) ? t : 'line';
}

function activateTab(tabId) {
  if (!TAB_IDS.includes(tabId)) tabId = 'line';
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + tabId);
  });
  // Update hash without scroll
  const newHash = '#tab=' + tabId;
  if (window.location.hash !== newHash) {
    history.replaceState(null, '', newHash);
  }
}

function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
  });
  window.addEventListener('hashchange', () => activateTab(readTabFromHash()));
  activateTab(readTabFromHash());
}

initTabs();
```

- [ ] **Step 5: Show tab nav when laps are selected**

Find the `renderAll()` function (around line 882). Add tab nav visibility toggling alongside the placeholder removal. Replace:

```javascript
function renderAll() {
  const ph = document.getElementById('placeholder');
  if (state.selected.size > 0 && ph) ph.remove();
  updateLegend();
```

With:

```javascript
function renderAll() {
  const ph = document.getElementById('placeholder');
  if (state.selected.size > 0 && ph) ph.remove();
  document.getElementById('tabnav').classList.toggle('visible', state.selected.size > 0);
  updateLegend();
```

- [ ] **Step 6: Verify in browser**

Reload `/compare`. Expected:
- Page loads with placeholder text and no visible tabs.
- Expanding a session shows three tabs (`Driving Line`, `Inputs`, `Powertrain`) with `Driving Line` highlighted.
- All seven charts and the track map render under the `Driving Line` tab (unchanged behavior).
- Clicking `Inputs` or `Powertrain` switches to an empty panel; URL changes to `#tab=inputs` / `#tab=powertrain`.
- Refreshing while on `#tab=inputs` keeps the Inputs tab active on reload.
- Clicking `Driving Line` returns to the chart view.

(History navigation between tabs via Back/Forward is intentionally not supported — `replaceState` is used so tab clicks don't pollute browser history.)

If any check fails, fix before committing.

- [ ] **Step 7: Commit**

```bash
git add rexy/static/compare.html
git commit -m "compare: add tab navigation scaffold with hash routing

Phase 7 step 1/5: introduces three-tab structure (Driving Line, Inputs,
Powertrain) and URL-hash persistence. All existing charts remain in the
Driving Line tab; Inputs and Powertrain are placeholders for follow-up
tasks."
```

---

### Task 2: Distribute charts across the three tabs

**Files:**
- Modify: `rexy/static/compare.html`

This task moves the existing chart canvases into the correct tabs and adds a second speed canvas (`ch-speed-pwr`) so speed renders in both Tab 1 (Driving Line) and Tab 3 (Powertrain), matching GT7's structure.

- [ ] **Step 1: Reorganize canvas placement**

Replace the contents of the three `<section class="tab-panel">` blocks (added in Task 1) with this distribution:

```html
<section class="tab-panel active" id="tab-line" role="tabpanel">
  <div class="chart-wrap"><p class="chart-lbl">Speed (km/h) &#8212; x: distance (m)</p>
    <canvas id="ch-speed" height="80"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Time Delta &#8212; vs reference lap (s)</p>
    <canvas id="ch-delta" height="60"></canvas></div>
  <div id="map-wrap">
    <p class="chart-lbl">Track Map &#8212; speed colormap (blue=slow &#8594; red=fast)</p>
    <canvas id="map-canvas" width="800" height="500"></canvas>
  </div>
</section>

<section class="tab-panel" id="tab-inputs" role="tabpanel">
  <div class="chart-wrap"><p class="chart-lbl">Throttle (%) &#8212; x: distance (m)</p>
    <canvas id="ch-throttle" height="60"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Brake (%) &#8212; x: distance (m)</p>
    <canvas id="ch-brake" height="60"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Lateral accel &#8212; sway, m/s&#178; (Heartbeat B only)</p>
    <canvas id="ch-sway" height="50"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Steering (rad, Heartbeat B only)</p>
    <canvas id="ch-steer" height="50"></canvas></div>
</section>

<section class="tab-panel" id="tab-powertrain" role="tabpanel">
  <div class="chart-wrap"><p class="chart-lbl">Speed (km/h) &#8212; x: distance (m)</p>
    <canvas id="ch-speed-pwr" height="80"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Gear &#8212; x: distance (m)</p>
    <canvas id="ch-gear" height="50"></canvas></div>
</section>
```

- [ ] **Step 2: Update CHART_DEFS to render speed to both canvases**

Find `CHART_DEFS` (around line 506). Replace:

```javascript
const CHART_DEFS = [
  { id: 'ch-speed',    fn: f => f.speed_mps * 3.6,           yLbl: 'km/h' },
  { id: 'ch-throttle', fn: f => f.throttle / 255 * 100,      yLbl: '%'    },
  { id: 'ch-brake',    fn: f => f.brake    / 255 * 100,      yLbl: '%'    },
  { id: 'ch-gear',     fn: f => f.current_gear,               yLbl: ''     },
  { id: 'ch-sway',     fn: f => f.sway,                       yLbl: 'm/s\u00b2' },
  { id: 'ch-steer',    fn: f => f.wheel_rotation_radians,     yLbl: 'rad'  },
];
```

With:

```javascript
const CHART_DEFS = [
  { id: 'ch-speed',     fn: f => f.speed_mps * 3.6,        yLbl: 'km/h' },
  { id: 'ch-speed-pwr', fn: f => f.speed_mps * 3.6,        yLbl: 'km/h' },
  { id: 'ch-throttle',  fn: f => f.throttle / 255 * 100,   yLbl: '%'    },
  { id: 'ch-brake',     fn: f => f.brake    / 255 * 100,   yLbl: '%'    },
  { id: 'ch-gear',      fn: f => f.current_gear,            yLbl: ''     },
  { id: 'ch-sway',      fn: f => f.sway,                    yLbl: 'm/s\u00b2' },
  { id: 'ch-steer',     fn: f => f.wheel_rotation_radians,  yLbl: 'rad'  },
];
```

The existing `updateTraceCharts()` loop already iterates `CHART_DEFS` and looks up canvases by ID, so no further code change is needed: Chart.js renders each canvas independently. Hidden canvases (those in inactive tabs) still render in memory and become visible when their tab is activated.

- [ ] **Step 3: Verify in browser**

Reload `/compare`, expand a session, select multiple laps. Expected:

- **Driving Line tab:** speed trace, time delta, track map.
- **Inputs tab:** throttle, brake, sway (lateral accel), steering. Switching to this tab shows the four input traces with the same lap colors.
- **Powertrain tab:** speed (same data as Tab 1) and gear. Speed in Powertrain tab matches speed in Driving Line tab.
- Lap selection, baseline (right-click), legend, auto-diff banner, session notes, filters all still work.

If a chart appears blank when its tab activates, switch to another tab and back — Chart.js sometimes needs a redraw on visibility change. (Polish in Task 5.)

- [ ] **Step 4: Commit**

```bash
git add rexy/static/compare.html
git commit -m "compare: distribute charts across Driving Line/Inputs/Powertrain tabs

Phase 7 step 2/5: each existing chart now lives in its GT7-aligned tab.
Speed is rendered to two canvases (ch-speed in Tab 1, ch-speed-pwr in
Tab 3) since speed is the universal reference channel that appears in
both views."
```

---

### Task 3: Add RPM trace to Powertrain tab

**Files:**
- Modify: `rexy/static/compare.html`

GT7's View 3 pairs speed with engine RPM. RPM is in heartbeat A (always available); we add it as a new chart between speed and gear in the Powertrain tab.

- [ ] **Step 1: Add RPM canvas to Powertrain tab**

In the `#tab-powertrain` section, insert the RPM chart between the speed and gear charts:

```html
<section class="tab-panel" id="tab-powertrain" role="tabpanel">
  <div class="chart-wrap"><p class="chart-lbl">Speed (km/h) &#8212; x: distance (m)</p>
    <canvas id="ch-speed-pwr" height="80"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Engine RPM &#8212; x: distance (m)</p>
    <canvas id="ch-rpm" height="60"></canvas></div>
  <div class="chart-wrap"><p class="chart-lbl">Gear &#8212; x: distance (m)</p>
    <canvas id="ch-gear" height="50"></canvas></div>
</section>
```

- [ ] **Step 2: Add RPM entry to CHART_DEFS**

Update `CHART_DEFS` to include the new entry. Insert `ch-rpm` after `ch-speed-pwr`:

```javascript
const CHART_DEFS = [
  { id: 'ch-speed',     fn: f => f.speed_mps * 3.6,        yLbl: 'km/h' },
  { id: 'ch-speed-pwr', fn: f => f.speed_mps * 3.6,        yLbl: 'km/h' },
  { id: 'ch-rpm',       fn: f => f.engine_rpm,              yLbl: 'rpm'  },
  { id: 'ch-throttle',  fn: f => f.throttle / 255 * 100,   yLbl: '%'    },
  { id: 'ch-brake',     fn: f => f.brake    / 255 * 100,   yLbl: '%'    },
  { id: 'ch-gear',      fn: f => f.current_gear,            yLbl: ''     },
  { id: 'ch-sway',      fn: f => f.sway,                    yLbl: 'm/s\u00b2' },
  { id: 'ch-steer',     fn: f => f.wheel_rotation_radians,  yLbl: 'rad'  },
];
```

- [ ] **Step 3: Verify in browser**

Reload `/compare`, expand a session, select laps, switch to the Powertrain tab. Expected:
- Three charts visible top-to-bottom: Speed, Engine RPM, Gear.
- RPM trace shows realistic values (typically 2000–9000 rpm, peaking near gear changes).
- RPM trace uses the same lap colors as other charts.
- Gear trace still renders correctly below RPM.

- [ ] **Step 4: Commit**

```bash
git add rexy/static/compare.html
git commit -m "compare: add engine RPM trace to Powertrain tab

Phase 7 step 3/5: completes Tab 3's channel set (speed + RPM + gear),
matching GT7 View 3."
```

---

### Task 4: Tab 1 responsive layout — track map beside speed/delta on desktop

**Files:**
- Modify: `rexy/static/compare.html`

On wide screens (≥1024px), the Driving Line tab should place the track map on the left with speed and delta stacked on the right. On narrow screens, content stacks vertically.

- [ ] **Step 1: Add responsive grid CSS for Tab 1**

Add the following CSS rules to the `<style>` block, immediately after the `.tab-panel` rules added in Task 1:

```css
  /* Tab 1 desktop layout: track map beside stacked traces */
  @media (min-width: 1024px) {
    #tab-line.active {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      grid-template-rows: 1fr 1fr;
      gap: 0.75rem;
    }
    #tab-line #map-wrap {
      grid-column: 1; grid-row: 1 / span 2;
      display: flex; flex-direction: column;
    }
    #tab-line #map-wrap canvas { flex: 1; min-height: 0; }
    #tab-line .chart-wrap:nth-of-type(1) { grid-column: 2; grid-row: 1; }
    #tab-line .chart-wrap:nth-of-type(2) { grid-column: 2; grid-row: 2; }
  }
```

The `nth-of-type` selectors target the speed `.chart-wrap` (1st) and delta `.chart-wrap` (2nd) inside `#tab-line`. The map keeps its native canvas dimensions but stretches to match the right column's combined height.

- [ ] **Step 2: Verify desktop layout**

Reload `/compare` in a browser window ≥1024px wide. On the Driving Line tab with laps selected, expected:
- Track map on the left, occupying full panel height.
- Speed chart top-right.
- Time Delta chart bottom-right.
- Map and traces share the row gracefully; nothing overflows.

- [ ] **Step 3: Verify narrow layout**

Resize the browser to <1024px wide (or test on a tablet). Expected:
- Track map, speed, and delta stack vertically (existing default flex layout).
- Layout reflows smoothly when crossing the 1024px breakpoint.

- [ ] **Step 4: Verify other tabs unaffected**

Switch to Inputs and Powertrain tabs. Expected:
- Both tabs continue to use the default vertical stacking (the grid override applies only to `#tab-line`).

- [ ] **Step 5: Commit**

```bash
git add rexy/static/compare.html
git commit -m "compare: responsive 2-column layout for Driving Line tab on desktop

Phase 7 step 4/5: at >=1024px the track map sits beside speed/delta,
maximising vertical chart space on landscape screens. Below 1024px the
panel stacks vertically as before."
```

---

### Task 5: Polish — crosshair scoping, redraw on tab switch, end-to-end check

**Files:**
- Modify: `rexy/static/compare.html`

Two known rough edges from earlier tasks: (1) `attachCrosshair()` iterates every chart, including those in hidden tabs whose `getBoundingClientRect()` may return zero, causing the synchronized crosshair to drift; (2) charts may need a `resize()` call when their tab becomes active so they pick up correct dimensions. Final task also runs a full end-to-end sanity check.

- [ ] **Step 1: Scope crosshair to active tab's charts and prevent listener accumulation**

The original `attachCrosshair()` adds a fresh `mousemove` listener on every render call, leaking listeners on each re-render. With tabs, this gets worse: hidden canvases' listeners would still fire and dispatch to canvases in other tabs, causing crosshair drift. Replace `attachCrosshair()` (around line 668) with this version, which (a) only attaches once per canvas via a sentinel flag, (b) self-checks the active tab inside the handler, and (c) re-resolves the chart instance at event time since `updateTraceCharts()` re-creates Chart.js instances on every render:

```javascript
function attachCrosshair() {
  Object.values(charts).forEach(ch => {
    const canvas = ch.canvas;
    if (canvas._crosshairAttached) return;
    canvas._crosshairAttached = true;
    canvas.addEventListener('mousemove', e => {
      const activePanel = document.querySelector('.tab-panel.active');
      if (!activePanel || !activePanel.contains(canvas)) return;
      const sourceChart = Object.values(charts).find(c => c.canvas === canvas);
      if (!sourceChart || !sourceChart.scales.x) return;
      const rect = canvas.getBoundingClientRect();
      const xVal = sourceChart.scales.x.getValueForPixel(e.clientX - rect.left);
      if (xVal == null) return;
      Object.values(charts).forEach(target => {
        if (target === sourceChart || !target.scales.x) return;
        if (!activePanel.contains(target.canvas)) return;
        const px = target.scales.x.getPixelForValue(xVal);
        target.canvas.dispatchEvent(new MouseEvent('mousemove', {
          clientX: target.canvas.getBoundingClientRect().left + px,
          clientY: e.clientY, bubbles: true,
        }));
      });
    });
  });
}
```

- [ ] **Step 2: Re-attach crosshair and resize charts on tab switch**

Find `activateTab(tabId)` from Task 1. Append chart resize and crosshair re-attachment at the end of the function, just before the final closing brace:

```javascript
function activateTab(tabId) {
  if (!TAB_IDS.includes(tabId)) tabId = 'line';
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + tabId);
  });
  const newHash = '#tab=' + tabId;
  if (window.location.hash !== newHash) {
    history.replaceState(null, '', newHash);
  }
  // Force visible charts to recompute their canvas size, then rebind crosshair
  Object.values(charts).forEach(ch => { try { ch.resize(); } catch (e) {} });
  setTimeout(attachCrosshair, 0);
}
```

- [ ] **Step 3: End-to-end manual verification**

Reload `/compare` in a fresh browser tab. Run through this checklist:

1. Sidebar loads, sessions render with track names, dates, lap counts.
2. Track filter and Car filter dropdowns populate; selecting a value filters the session list.
3. Expanding a session auto-selects all laps; tab nav becomes visible; Driving Line tab is active by default.
4. Driving Line tab: track map, speed, time delta all render. On a ≥1024px window, track map is on the left.
5. Right-clicking a lap toggles its baseline (REF) state; the time delta updates to use it as reference.
6. Switching to Inputs tab: throttle, brake, sway (when heartbeat B), steering all render. Hovering one chart moves a crosshair line on the others.
7. Switching to Powertrain tab: speed (matching Tab 1), RPM, gear all render with crosshair sync.
8. Setup-diff banner appears when laps from two different sessions are selected; auto-diff lists gear ratio / top speed deltas.
9. Compare header (per-session colour bar + notes) appears with multi-session selection.
10. Inline note edit (`[+ add note]` / `[edit]`) saves via PATCH.
11. Refreshing the page on `#tab=powertrain` lands on the Powertrain tab with correct charts.
12. Pasting `http://localhost:8000/compare#tab=inputs` in a new tab opens the Inputs view directly.

If anything fails, fix before committing. Do not skip checks.

- [ ] **Step 4: Commit**

```bash
git add rexy/static/compare.html
git commit -m "compare: scope crosshair to active tab; resize charts on switch

Phase 7 step 5/5: prevents crosshair drift caused by hidden charts'
zero-size bounding rects, and forces a Chart.js resize after each tab
activation so canvases pick up correct dimensions."
```

---

### Task 6: Update CHANGELOG and project docs

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`

Document the new tabbed compare view so future readers (human and agent) understand the structure.

- [ ] **Step 1: Inspect current CHANGELOG**

```bash
head -40 CHANGELOG.md
```

Note the formatting convention used by previous phases (Keep a Changelog style is referenced in `specs.md`).

- [ ] **Step 2: Add Phase 7 entry to CHANGELOG**

Add an entry under `## [Unreleased]` (or create the section if missing) using the same style as existing entries:

```markdown
## [Unreleased]

### Changed
- `/compare` is now organised into three tabs — Driving Line, Inputs,
  Powertrain — mirroring the structure of GT7 Spec III's in-game Data
  Logger. Selected tab persists in the URL hash. Tab 1 uses a 2-column
  layout on screens ≥1024px (track map left, speed/delta right).

### Added
- Engine RPM trace in the Powertrain tab.
```

- [ ] **Step 3: Update CLAUDE.md compare description**

Find the components table in `CLAUDE.md`. Replace the Compare row:

```markdown
| Compare | `rexy/static/compare.html` | N-lap overlay; session browser; auto-diff banner; session notes; track/car filters; distance-based traces; delta graph; track map |
```

With:

```markdown
| Compare | `rexy/static/compare.html` | Three tabs (Driving Line / Inputs / Powertrain); N-lap overlay; session browser; auto-diff banner; session notes; track/car filters; distance-based traces; N-lap delta graph; track map; tab persisted in URL hash |
```

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md CLAUDE.md
git commit -m "docs: record Phase 7 tabbed compare view

Updates CHANGELOG and CLAUDE.md component table to reflect the new
three-tab analysis dashboard."
```

---

### Task 7: Mark Phase 7 done in specs.md

**Files:**
- Modify: `specs.md`

- [ ] **Step 1: Flip Phase 7 from Planned to Done**

In the Roadmap table in `specs.md`, change:

```markdown
| 7 | GT7-aligned compare view: 3 tabs (Driving Line / Inputs / Powertrain) | Planned |
```

To:

```markdown
| 7 | GT7-aligned compare view: 3 tabs (Driving Line / Inputs / Powertrain) | Done |
```

- [ ] **Step 2: Commit**

```bash
git add specs.md
git commit -m "specs: mark Phase 7 (GT7-aligned compare view) as done"
```

---

## Out of Scope (not to be implemented in this plan)

- **Phase 7b** (separate follow-up plan): Soften the "Positioning vs. the In-Game Data Logger" subsection in `specs.md`. Reframe as "Relationship to the GT7 Data Logger." Convert the differentiation table to an "extends" table.
- Replay download from online rankings (GT7 closed system; no public API).
- Stored setup snapshots tied to laps (no telemetry source for car settings).
- Mobile portrait layout beyond simple vertical stacking.
- Tab keyboard shortcuts (e.g. number keys to switch tabs).
- Splitting `compare.html` into separate JS/CSS files (separate refactor; out of scope for this feature work).
- Adding a JS test framework (the project's test surface is currently Python-only; manual browser verification is the contract for this plan).
