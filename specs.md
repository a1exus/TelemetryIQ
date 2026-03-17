# TelemetryIQ — Specifications

## Overview

- **Project**: TelemetryIQ — real-time Gran Turismo 7 telemetry dashboard
- **Status**: Active — Phase 2 (live dashboard) in design
- **Last updated**: 2026-03-16
- **Telemetry source**: [gt-telem](https://pypi.org/project/gt-telem/) (Python
  library for Polyphony Digital's motion-rig telemetry in GT6/GTS/GT7)

## Current state (foundation — Phase 1 complete)

- GT7 telemetry connection via gt-telem (`TurismoClient`); heartbeat type and
  PS IP configurable via `.env`
- Error handling for PlayStation not found / on standby
- Docker Compose with `network_mode: host`
- `requirements.txt` declares dependencies (`gt-telem`)
- Makefile for common dev/ops tasks (`build`, `up`, `down`, `logs`, `restart`)

## Goals

- [x] Connect to GT7 telemetry and stream data (Phase 1)
- [ ] Record telemetry per lap to persistent storage + minimal live view (Phase 2)
- [ ] Lap analysis dashboard: full live display + two-lap comparison overlays + gap graph + driving line (Phase 3)
- [ ] Car setup tagging, setup-vs-setup comparison, lap export (Phase 4)

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
| Telemetry client | `rexy/client.py` | Wraps `TurismoClient`; registers async callbacks (gt-telem supports both sync and async); pushes to queue. Tune `max_callback_workers` for thread pool sizing. |
| FastAPI server | `rexy/server.py` | WebSocket `/ws` endpoint; broadcaster loop; serves static files |
| Dashboard | `rexy/static/index.html` | Vanilla JS; renders all telemetry fields; WS reconnect w/ exponential backoff |
| Entrypoint | `rexy/__main__.py` | Wires client + server; starts both |

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

- [ ] Browser dashboard loads at `http://<host>:8000` from any device on LAN
- [ ] All telemetry fields update live at ~60Hz with no perceptible lag
- [ ] WebSocket reconnects automatically after disconnect
- [ ] Dashboard readable on a phone screen while sitting in a racing seat
- [ ] `docker compose up` is the only command needed on Linux/Raspberry Pi

## Roadmap

| Phase | Description | Status |
| --- | --- | --- |
| 1 | Foundation: telemetry connection, Docker, packaging | ✅ Done |
| 2 | Recording: persist full telemetry per lap to SQLite (on `on_lap_change`); minimal live view (speed, RPM, gear, lap time) via WebSocket | 🔄 In design |
| 3 | Analysis dashboard: full live telemetry display; lap selector; two-lap overlay comparison (throttle, brake, speed, RPM traces); gap graph; driving line (`position_x/y/z`) | 📋 Planned |
| 4 | Car setup tagging per lap; setup-vs-setup comparison on same track; lap data export | 📋 Planned |

## References

- [gt-telem on PyPI](https://pypi.org/project/gt-telem/)
- [GT7 Data Logger article](https://www.gran-turismo.com/us/news/00_5736734.html)
  — reference for what a telemetry dashboard should show
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/)
