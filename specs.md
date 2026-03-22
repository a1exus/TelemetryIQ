# TelemetryIQ — Specifications

## Overview

- **Project**: TelemetryIQ — real-time Gran Turismo 7 telemetry dashboard
- **Status**: Active — Phase 4 Part 1 (sessions) complete
- **Last updated**: 2026-03-22
- **Telemetry source**: [gt-telem](https://pypi.org/project/gt-telem/) (Python
  library for Polyphony Digital's motion-rig telemetry in GT6/GTS/GT7)

## Current state (through Phase 4 Part 1)

- GT7 telemetry connection via gt-telem (`TurismoClient`); heartbeat type and
  PS IP configurable via `.env`
- Error handling for PlayStation not found / on standby
- Docker Compose with `network_mode: host`
- `requirements.txt` declares dependencies (`gt-telem`)
- Makefile for common dev/ops tasks (`build`, `up`, `down`, `logs`, `restart`)
- Full telemetry recording to SQLite per lap (on `on_lap_change`)
- Live HUD at `/` with all telemetry fields, post-lap Chart.js overlay
- Lap comparison dashboard at `/compare` with distance-based trace charts,
  time delta, track map, synchronized crosshair
- **Sessions as first-class entities**: `on_at_track`/`on_in_race` opens a
  session; `on_in_game_menu`/`on_race_end` closes it. Sessions carry
  `track_id` and `car_code`.
- Session-browser sidebar in `/compare` with nested lap rows, delta-to-best,
  best-lap indicator
- REST API: `GET /laps`, `GET /sessions`, `GET /sessions/{id}/laps`,
  `GET /laps/{car_code}/{lap_number}/{lap_id}/frames`
- Static car/track name lookup via `cars.json` (559 cars) and `tracks.json`
  (106 tracks), sourced from official gran-turismo.com
- All gt-telem events logged to stdout for observability
- Server-side lap start timestamp (`lap_started_at`) for accurate lap timer
  across sleep/wake reconnects

## Goals

- [x] Connect to GT7 telemetry and stream data (Phase 1)
- [x] Record telemetry per lap to persistent storage + minimal live view (Phase 2)
- [x] Lap comparison dashboard: REST API for lap/frame data; distance-based
  trace charts; time delta; track map (Phase 3 — `/compare`)
- [x] Full live engineering display: all telemetry fields visible, post-lap Chart.js overlay
  (Phase 3 — HUD redesign)
- [x] Sessions as first-class entities with car/track identity (Phase 4.1)
- [ ] Car setup tagging, setup-vs-setup comparison, lap export (Phase 4.2)

## Scope

### In scope

- GT7 telemetry ingestion via gt-telem on a host on the same LAN as PlayStation
- Real-time WebSocket broadcast of all telemetry fields to a browser dashboard
- All telemetry fields exposed: speed, RPM, gear, throttle/brake (raw +
  filtered), G-forces (lateral, longitudinal, vertical), steering, boost,
  oil/water temp, tire temps, tire suspension heights, fuel, lap times
  (current/last/best), lap counter, race state, TCS/ASM, shift lights,
  suggested gear, energy recovery, car code, position (3D), road plane
- Heartbeat type configurable (`A` / `B` / `~`) via `.env`
- Single-page dashboard served by the same FastAPI process (no separate web
  server)
- Dashboard accessible from any device on the LAN (phone, tablet, laptop)

### Out of scope

- Authentication / access control
- Multiple simultaneous GT7 sources
- Native desktop app
- `./lib` directory

## Architecture

```text
PlayStation (GT7, ~60Hz UDP)
        │
        ▼
  TurismoClient (gt-telem)
  callback-driven, fires on every telemetry frame + race/driver events
        │
        ▼
  asyncio.Queue (maxsize=1, drop-oldest)
  keeps only the latest frame — freshness over completeness
        │
        ▼
  FastAPI broadcaster loop
  drains queue, fans out JSON to all connected WebSocket clients
        │ WebSocket /ws  (JSON)
        ▼
  Browser — index.html (vanilla JS + Canvas/SVG gauges)
  accessible from any device on the LAN
```

## Components

| Component | File | Responsibility |
| --- | --- | --- |
| Telemetry client | `rexy/client.py` | Wraps `TurismoClient`; registers sync callbacks that dispatch to asyncio via `call_soon_threadsafe`; pushes frames to queue; logs all gt-telem events to stdout |
| FastAPI server | `rexy/server.py` | WebSocket `/ws` endpoint; broadcaster loop; REST API (`/laps`, `/sessions`, `/sessions/{id}/laps`, `/laps/{car_code}/{lap_number}/{lap_id}/frames`); serves static files |
| Lap recorder | `rexy/recorder.py` | Session lifecycle (`start_session`/`close_session`); lap lifecycle (`reset_and_new_lap`/`flush_and_new_lap`); buffers frames and flushes to SQLite |
| Repository | `rexy/repository.py` | SQLite access layer; schema DDL with `user_version` migration (currently v2); all CRUD for sessions, laps, frames |
| Live dashboard | `rexy/static/index.html` | Vanilla JS; renders all telemetry fields; WS reconnect w/ exponential backoff; post-lap Chart.js overlay |
| Compare dashboard | `rexy/static/compare.html` | Session browser sidebar; distance-based trace charts; time delta; track map; synchronized crosshair |
| Static data | `rexy/static/cars.json`, `tracks.json` | Car code → name and track ID → name lookups (from gran-turismo.com) |
| Entrypoint | `rexy/__main__.py` | Wires client + server + recorder; starts both; handles graceful shutdown (`sys.exit(0)` to force-exit past gt-telem threads) |

## Running

All platforms use Docker Compose to start the container. The difference
is whether gt-telem runs inside the container or on the host:

| Step | macOS / Windows | Linux / Raspberry Pi |
| --- | --- | --- |
| Install gt-telem on host | `pip install gt-telem` (**required**) | — (skip; inside container) |
| Start container | `docker compose up` | `docker compose up` |
| Open dashboard | `http://localhost:8000` | `http://<host-ip>:8000` |

**Why macOS and Windows need a host-side install:** Docker Desktop on macOS
and Windows runs containers inside a Linux VM. That VM is not on the same
network as the host, so PS5 UDP telemetry cannot reach the container. gt-telem
must run on the host directly to receive PS5 packets. Linux hosts use
`network_mode: host` which gives the container direct access to the host's
network interface — no host-side install needed.

## Requirements

### Functional

| ID | Requirement | Priority |
| --- | --- | --- |
| F1 | Connect to GT7 via `TurismoClient`; support heartbeat types `A`, `B`, `~` | Must |
| F2 | Broadcast all telemetry fields over WebSocket at ~60Hz | Must |
| F3 | Serve live dashboard at `http://<host>:8000` | Must |
| F4 | Dashboard displays: speed, RPM, gear, throttle, brake, G-forces (lat/lon/vert), steering, shift lights, suggested gear, TCS/ASM indicators, boost, fuel, tire temps (FL/FR/RL/RR), tire suspension heights, oil/water temp, lap times (current/last/best), lap counter, race state, energy recovery, car code, driving line (track position via `position_x/y/z`) | Must |
| F5 | Dashboard auto-reconnects on WebSocket disconnect (exponential backoff) | Must |
| F6 | PS IP and heartbeat type configurable via `.env` without code changes | Must |
| F7 | Dashboard accessible from any device on the same LAN | Should |
| F8 | Handle race/driver events (lap change, best lap, TCS trigger, etc.) | Should |

### Non-functional

| ID | Requirement | Priority |
| --- | --- | --- |
| NF1 | Python 3.10+ (gt-telem requirement) | Must |
| NF2 | End-to-end latency (PS5 → browser) under 500ms | Should |
| NF3 | No npm / no build step — dashboard is a single static HTML file | Must |
| NF4 | Runs on Raspberry Pi (ARM64); Docker image must support ARM | Must |
| NF5 | Single Docker container; no additional services required | Must |

## Constraints & assumptions

- **Constraints**:
  - `./lib` — out of scope
  - Do not create separate design documents; update `specs.md` directly
- **Assumptions**:
  - PlayStation and host are on the same LAN subnet
  - `PS_IP` set in `.env` if auto-discovery (UDP broadcast) doesn't work
  - `GT7_HEARTBEAT_TYPE=B` default (standard + motion data); switch to `~` for
    filtered inputs + energy recovery (hybrid/EV cars)

## Telemetry fields reference (gt-telem)

### Heartbeat A — standard (all types include these)

| Field | Description |
| --- | --- |
| `speed_mps` | Speed in m/s |
| `engine_rpm` | Engine RPM |
| `gear` | Current gear |
| `throttle` | Throttle input (raw, 0–255) |
| `brake` | Brake input (raw, 0–255) |
| `clutch_pedal` | Clutch pedal position |
| `boost_pressure` | Turbo boost pressure |
| `fuel_level` / `fuel_capacity` | Fuel level and capacity |
| `oil_pressure` / `oil_temp` | Oil pressure and temperature |
| `water_temp` | Water temperature |
| `tire_fl/fr/rl/rr_temp` | Tire surface temperatures |
| `tire_fl/fr/rl/rr_sus_height` | Suspension heights per corner |
| `wheel_fl/fr/rl/rr_rps` | Wheel rotations per second |
| `current_lap` / `total_laps` | Lap counter |
| `best_lap_time_ms` / `last_lap_time_ms` | Lap times in ms |
| `position_x/y/z` | 3D position on track |
| `ang_vel_x/y/z` | Angular velocity |
| `rotation_x/y/z` | Vehicle rotation |
| `road_plane_x/y/z/dist` | Road surface normal + distance |
| `min_alert_rpm` / `max_alert_rpm` | Shift light RPM range |
| `flags` / `bits` | Race flags and status bits |
| `car_code` | Car identifier |
| `calc_max_speed` | Calculated top speed |
| `trans_rpm` / `trans_top_speed` | Transmission data |
| `gear1`–`gear8` | Gear ratios |

### Heartbeat B — adds motion data

| Field | Description |
| --- | --- |
| `wheel_rotation_radians` | Steering wheel input |
| `filler_float_fb` | Lateral slip angle (approx.) |
| `sway` | Lateral body motion |
| `heave` | Vertical body motion |
| `surge` | Longitudinal body motion |

### Heartbeat ~ — adds filtered inputs + energy recovery

| Field | Description |
| --- | --- |
| `throttle_filtered` | Smoothed throttle input |
| `brake_filtered` | Smoothed brake input |
| `energy_recovery` | Regenerative braking value (hybrid/EV) |

### Events (gt-telem callbacks)

| Category | Events |
| --- | --- |
| Game | `on_running`, `on_in_game_menu`, `on_at_track`, `on_in_race`, `on_paused`, `on_race_end` |
| Race | `on_race_start`, `on_race_finish`, `on_lap_change`, `on_best_lap_time`, `on_last_lap_time`, `on_track_detected` |
| Driver | `on_gear_change`, `on_flash_lights`, `on_handbrake`, `on_suggested_gear`, `on_tcs`, `on_asm`, `on_rev_limit`, `on_brake`, `on_throttle`, `on_shift_light_low`, `on_shift_light_high` |

## Success criteria

### Phase 1–2

- [ ] Browser dashboard loads at `http://<host>:8000` from any device on LAN
- [ ] All telemetry fields update live at ~60Hz with no perceptible lag
- [ ] WebSocket reconnects automatically after disconnect
- [ ] Dashboard readable on a phone screen while sitting in a racing seat
- [ ] `docker compose up` is the only command needed on Linux/Raspberry Pi

### Phase 3

- [x] Lap list shows all recorded laps with lap time and car code
- [x] Selecting one lap renders all trace channels with distance as x-axis
- [x] Selecting two laps renders an overlay with a time delta (gap) trace
- [x] Synchronized crosshair: hovering one chart highlights the same distance on all charts
- [x] Track map renders `position_x` vs `position_z`, color-coded by speed;
      two-lap overlay in distinct colors
- [x] Distance computed from wall-clock `ts` per frame (GT7 does not broadcast
      current lap time; `ts` is set server-side on frame receipt and is accurate
      to within one frame interval at ~60 Hz; dt > 0.1 s frames are skipped)

## Phase 3 — Analysis Dashboard

### Overview

A lap analysis view served from the same FastAPI process. Reads recorded laps from SQLite
via REST; does not use the WebSocket feed. Modelled on professional motorsport tools
(MoTeC i2, AiM Race Studio): distance-based x-axis, synchronized crosshair, time delta
graph, and a color-coded track map.

### Data flow

```text
Browser (analysis view)
    │  GET /laps                  — list recorded laps
    │  GET /laps/{id}/frames      — full frame data for one lap
    ▼
FastAPI (rexy/server.py)
    │
    ▼
SQLite (rexy/repository.py)      — read-only queries
```

Live gauges continue to use the existing WebSocket feed. Analysis and live are separate views, not separate servers.

### REST endpoints (new)

| Method | Path | Returns |
| --- | --- | --- |
| `GET` | `/laps` | `[{id, lap_number, lap_time_ms, car_code, started_at}]` |
| `GET` | `/laps/{car_code}/{lap_number}/{lap_id}/frames` | `[{seq, …all telemetry fields…, distance_m}]` |
| `GET` | `/sessions` | `[{id, started_at, completed_at, track_id, car_code, lap_count, best_lap_time_ms}]` |
| `GET` | `/sessions/{id}/laps` | `[{id, lap_number, lap_time_ms}]` (complete laps, lap_number > 0) |

`distance_m` is computed server-side per frame:
`d[i] = d[i-1] + speed_mps[i] * dt`
where `dt = ts[i] - ts[i-1]` and `ts` is the server-side wall-clock timestamp set on
frame receipt. GT7 does not broadcast a running lap timer (`current_lap_time_ms` is not
in the telemetry stream); `ts` at ~60 Hz is accurate to within one frame interval.
Frames where `dt > 0.1 s` (pause, menu, load screen) contribute zero distance to
prevent teleportation artefacts.

### Trace channels

Standard motorsport analysis set, rendered in this order:

| Channel | Field(s) | Unit |
| --- | --- | --- |
| Speed | `speed_mps × 3.6` | km/h |
| Throttle | `throttle / 255 × 100` | % |
| Brake | `brake / 255 × 100` | % |
| Gear | `gear` | — |
| Lateral G | `g_lateral` | g |
| Steering | `wheel_rotation_radians` (Heartbeat B only) | rad |
| Time delta | computed (see below) | s |

### Time delta (gap graph)

Computed only when two laps are selected. For each distance point in the faster lap,
interpolate the time the slower lap was at the same distance. Delta = cumulative time
difference at each point. Positive = faster lap is ahead; negative = slower lap is ahead.

Requires linear interpolation of both laps onto a shared distance grid.

### Track map

- Plot `position_x` vs `position_z` (Y is altitude; drop it for the 2D map).
- Color-code the path by the selected channel (default: speed). Use a continuous colormap (cool → warm = slow → fast).
- Two-lap overlay: render each lap as a separate colored path with opacity.
- Rendered on a `<canvas>` element; no library required.

### Rendering stack

| Concern | Approach |
| --- | --- |
| Trace charts | [Chart.js](https://www.chartjs.org/) via CDN — Canvas-backed, handles 5K+ points, zoom/pan plugin |
| Synchronized crosshair | Chart.js `crosshair` plugin or shared `mousemove` handler updating all chart instances |
| Track map | Raw Canvas API |
| UI state | Vanilla JS — single `state` object (`{lapA, lapB, activeChannel}`) |

No npm, no build step. All dependencies loaded from CDN in `index.html`.

### Constraints

- No new Python dependencies for Phase 3 — SQLite reads use the existing `repository.py` pattern.
- `GET /laps/{id}/frames` may return ~5 000 rows; response must be streamed or paginated
  if response time exceeds 200ms in practice.
- Track map must not re-fetch on channel change — cache frame data in JS after first fetch.

## Phase 4 Part 1 — Sessions

### Overview

Sessions are first-class entities that group laps recorded during a single
track visit. A session starts when `on_at_track` or `on_in_race` fires and
closes when `on_in_game_menu` or `on_race_end` fires. Each session carries
`track_id` (from `on_track_detected`) and `car_code` (from the first complete
lap's telemetry).

### Schema (user_version = 2)

Sessions table gained `track_id INTEGER`, `car_code INTEGER`, and
`completed_at REAL` columns. Fresh installs create the full schema at v2;
existing v1 databases are migrated via `ALTER TABLE ADD COLUMN`.

### Session lifecycle

- `LapRecorder.__init__` takes only `repo` (no `session_id`); `_session_id`
  starts as `None`.
- `start_session()` guards against re-entry (no-op if `_session_id` is set).
- `close_session()` flushes any partial lap, clears `_session_id` inside the
  lock, then calls `complete_session()`.
- `set_track_id()` remains sync (safe for `call_soon_threadsafe`); dispatches
  `asyncio.create_task` internally to update the session's `track_id`.
- `flush_and_new_lap()` writes `car_code` to the session on first complete lap.

### UI

The `/compare` sidebar is a session browser: sessions listed newest-first,
most recent auto-expanded. Each session row shows car name, track name,
lap count, and best lap time. Expanding a session lazily fetches its laps via
`GET /sessions/{id}/laps`. Each lap row shows delta-to-best and a ★ for the
session's best lap. Lap 0 (formation/out lap) is excluded.

### Static data

`rexy/static/cars.json` (559 cars) and `rexy/static/tracks.json` (106 tracks)
provide car_code → name and track_id → name lookups. Sourced from official
gran-turismo.com JS bundles. See `AGENTS.md` for refresh instructions.

## Roadmap

| Phase | Description | Status |
| --- | --- | --- |
| 1 | Foundation: telemetry connection, Docker, packaging | ✅ Done |
| 2 | Recording: persist full telemetry per lap to SQLite (on `on_lap_change`); minimal live view (speed, RPM, gear, lap time) via WebSocket | ✅ Done |
| 3 | Analysis dashboard (`/compare`): REST API, distance-based trace charts, delta graph, track map; HUD redesign: full live display + post-lap overlay | ✅ Done |
| 4.1 | Sessions as first-class entities; car/track identity; session-browser UI | ✅ Done |
| 4.2 | Car setup tagging per lap; setup-vs-setup comparison on same track; lap data export | 📋 Planned |

## Core Use Cases (from GT7 Data Logger)

The official [GT7 Data Logger article](https://www.gran-turismo.com/us/news/00_5736734.html)
defines two primary analysis workflows. These are the north star for
TelemetryIQ's `/compare` feature.

### 1. Compare and Improve Driving Techniques

**Scenario:** Same car, same settings, different laps (or different drivers).
**Question:** "Where am I losing time?"

Key analysis:

- **Speed + Gap graph**: identify where time is gained/lost per corner
- **Driving line overlay**: see braking points, apex proximity, corner exit
- **Throttle/Brake traces**: spot coasting (neither accelerating nor braking),
  late/early braking, hesitant throttle application
- **Lateral G**: cornering commitment and consistency

The article example: slower driver braked earlier at Tsukuba Turn 1, lost
speed at corner entry, relied on momentum through apex. Faster driver braked
later, hit slightly lower minimum speed, but got on throttle earlier — gained
0.5s by corner exit.

**Status:** Fully supported today via `/compare` (speed, gap, driving line,
throttle/brake/lateral G traces, synchronized crosshair).

### 2. Compare and Improve Car Settings

**Scenario:** Same driver, same track, different car setup.
**Question:** "Did this setup change help?"

Key analysis:
- Compare laps before/after a setup change (e.g. front downforce, tire type)
- Look for: understeer reduction, earlier throttle application, cleaner
  cornering, tighter driving line
- Speed + Gap graph shows net effect per corner

The article example: increasing front downforce allowed later braking, cleaner
turn-in without understeer, earlier throttle — 0.3s improvement.

**Status:** Visualization exists. Missing: setup tagging per session/lap so
the user can identify *which* setup produced each lap. Planned for Phase 4.2.

## Decisions

Non-obvious design choices and why they were made. Prevents future reversals.

| Decision | Why | Alternatives rejected |
| --- | --- | --- |
| `maxsize=1` queue (drop-oldest) | At ~60 Hz, freshness matters more than completeness for live display | Unbounded queue (memory leak), larger buffer (stale frames) |
| Server-side `lap_started_at` timestamp | Lap timer must survive browser sleep/wake reconnects; client-side `Date.now()` resets on reconnect | Client-side timer (breaks on reconnect), game-provided timer (GT7 doesn't broadcast running lap time) |
| `set_track_id()` stays sync | Called via `call_soon_threadsafe` from gt-telem thread; making it async would require `asyncio.run_coroutine_threadsafe` | Async method (breaks `call_soon_threadsafe` pattern) |
| `sys.exit(0)` after `asyncio.run()` | gt-telem spawns non-daemon threads that prevent clean Python exit | `tc.stop()` alone (blocks on thread join), daemon threads (not our code) |
| Sessions as first-class DB entities | Sessions own car/track identity; deriving from laps is fragile and loses boundary info | Derive session from laps (anti-pattern, loses start/end events) |
| Static `cars.json` / `tracks.json` | No runtime network calls, no CORS issues, works offline | Fetch from GT7 website at runtime (CORS, fragile, requires network) |
| `user_version` PRAGMA for migrations | SQLite built-in, no external migration tool needed; value is an integer, incremented per schema change | Alembic (overkill), migration table (reinventing the wheel) |

## Known Issues

| Issue | Impact | Notes |
| --- | --- | --- |
| Lap counter jumps after laptop sleep | Lap numbers may skip (e.g. 2 → 6) | GT7 continues counting internally during sleep; first `on_lap_change` after wake reports the current GT7 lap number. Data for skipped laps is lost. Needs event log data to confirm. |
| gt-telem non-daemon threads | App hangs on Ctrl-C without `sys.exit(0)` | Mitigated by `sys.exit(0)` after `asyncio.run()`; `tc.stop()` runs in executor with 3s timeout. |

## References

- [GT7 Data Logger article](https://www.gran-turismo.com/us/news/00_5736734.html)
  — **north star** for what the analysis dashboard should do
- [GT7 Car List (official)](https://www.gran-turismo.com/us/gt7/carlist/)
  — source for `cars.json`
- [GT7 Track List (official)](https://www.gran-turismo.com/us/gt7/tracklist/)
  — source for `tracks.json`
- [gt-telem on PyPI](https://pypi.org/project/gt-telem/)
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/)
