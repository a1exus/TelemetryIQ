# HUD Redesign: Live Engineering Display

**Date:** 2026-03-17
**Status:** Approved
**Phase:** 3 completion / Phase 4 preparation

---

## Overview

Redesign `rexy/static/index.html` from a minimal driver HUD into a full
motorsport engineering display. The page runs in a small browser window
alongside GT7 on the same machine. It must fit without scrolling at any
tall-narrow viewport (fully fluid layout, `height: 100svh; overflow: hidden`).
360×900px is the reference target, not a hard constraint.

Also rename the analysis route: `GET /analysis` → `GET /compare`, serving
`compare.html` instead of `analysis.html`.

---

## Section 1: Page Structure

Single fixed-height HTML file, no scroll. Layout splits vertically:

- **Top zone (~60%):** Live instruments — all telemetry fields at ~60 Hz
- **Bottom zone (~40%):** Lap comparison charts — post-lap, updated per lap

The existing "Details" button and overlay (`#secondary`) are **removed**.
All fields previously hidden behind the overlay move into the always-visible
top zone.

Page routes:

- `/` — Live engineering display (this redesign)
- `/compare` — Post-session lap comparison (`analysis.html` → `compare.html`)

The existing hardcoded `/analysis` link in `index.html` is updated to `/compare`.

No build step. No npm. Single static HTML file served by FastAPI.

---

## Section 2: Data Fields

All telemetry fields from the WebSocket stream are displayed, organized by
category. Nothing is hidden.

**Motion:** Speed km/h (`speed_mps×3.6`), `current_gear`, `engine_rpm`,
shift bar (`min_alert_rpm`, `max_alert_rpm`)

**Driver inputs:** `throttle`%, `brake`%,
`wheel_rotation_radians` displayed in radians to 2 decimal places,
labelled "Steering (rad)" (HB-B only)

**Body motion:** `sway`, `surge`, `heave` (HB-B only; labelled as body
motion, not G-force — no G-force field exists in the payload)

**Tires:** `tire_fl/fr/rl/rr_temp` color-coded cold→optimal→hot;
`tire_fl/fr/rl/rr_sus_height` displayed in mm, labelled "Sus (mm)"

**Timing:** Current lap time (client-computed), `last_lap_time_ms`,
`best_lap_time_ms`, delta vs best

**Car state:** `fuel_level`/`fuel_capacity`%, `boost_pressure`,
`oil_pressure`, `oil_temp`, `water_temp`, `tcs_active`, `asm_active`,
`rev_limit`, `suggested_gear` (display `--` when value ≥ 15 or falsy,
as that is the GT7 sentinel for "no suggestion")

`clutch_pedal` and `clutch_engagement` are intentionally excluded — most
GT7 racing uses automatic transmission and these fields are not actionable.

**Filtered inputs:** `throttle_filtered`, `brake_filtered`, `energy_recovery`
(HB-~ only; hidden when `null`)

**Note:** `g_lateral` does not exist in `telemetry_to_dict()`. Use
`sway`/`surge`/`heave` (HB-B) for body motion display only.

**Client-side lap timer:** `Date.now() - lapStartTs`, where `lapStartTs` is
reset on each `current_lap` increment or `cars_on_track` transition.
Preserves existing `index.html` logic.

HB-B and HB-~ fields are shown when non-null and hidden otherwise.

---

## Section 3: Charts

Two stacked Chart.js charts in the bottom zone, updated each lap transition.

**Traces:**

- Blue: last completed lap
- Orange: best lap (same as last on lap 1)

**Channels:**

- Chart 1: `throttle`% + `brake`% (two lines, one chart)
- Chart 2: Speed km/h (`speed_mps × 3.6`)

**X-axis:** distance (metres) from `distance_m`, already computed server-side
by `_add_distance()` in `GET /laps/{id}/frames` responses.

**Trigger:** raw `d.current_lap` increment in the WebSocket frame (before any
client-side `lapOffset` adjustment).

**Data flow on lap transition:**

1. `GET /laps` — index 0 = last completed; minimum `lap_time_ms` across all
   returned rows = best (server filters to `is_complete = 1`, so aborted laps
   are never returned). Tiebreak: if two laps share the minimum, prefer
   index 0 (most recent).
2. If `GET /laps` returns empty, skip silently — charts stay at previous
   state. This is the normal path on the `0 → 1` race-start transition,
   where `current_lap` increments before any lap is committed to the DB.
   Chart instances are not created until the first non-empty response.
3. If last completed and best are the same lap (same `id`), fetch frames
   once and use the same dataset for both traces.
4. Otherwise fetch in parallel: `GET /laps/{lastId}/frames` +
   `GET /laps/{bestId}/frames`
5. Swap dataset arrays, `chart.update()` with no animation

**Empty state:** Charts hidden until first non-empty lap transition; show
"Waiting for lap data…" placeholder.

**Rendering:**
CDN: `https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js`
`animation: false` in chart config. Instances created on first non-empty
lap transition; data swapped in place on subsequent laps.

---

## Files Changed

- **Modify** `rexy/static/index.html` — full redesign; remove Details overlay;
  add Chart.js charts; update `/analysis` link to `/compare`
- **Rename** `rexy/static/analysis.html` → `rexy/static/compare.html`
- **Modify** `rexy/server.py` — route `GET /analysis` → `GET /compare`;
  serve `compare.html`

No new REST endpoints. No new WebSocket events. No changes to
`repository.py`, `recorder.py`, `client.py`, or `__main__.py`.
