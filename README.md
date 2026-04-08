# TelemetryIQ

GT7 telemetry recorder and lap analysis tool. Gran Turismo 7 broadcasts UDP telemetry
at ~60 Hz; TelemetryIQ records every frame per lap to SQLite, streams live data to a
browser HUD, and enables lap-over-lap comparison of speed, throttle, brake, G-forces,
and more.

## Prerequisites

- Gran Turismo 7 running on PlayStation
- Telemetry enabled in GT7:
  **Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On**
- PlayStation and your machine on the same LAN

## Quick Start

```shell
make install
make run
```

Run `make help` for all options (e.g. `PS_IP=192.168.1.42 make run`).

## Web UI

Once running, open **<http://localhost:8000>** in a browser from any device on the LAN.

### `/` — Live HUD

Glanceable driving display, updated at ~60 Hz. Designed to be readable in a
0.5-second glance at speed.

| Section | Fields |
| --- | --- |
| Speed | km/h (large) |
| Powertrain | RPM, gear, shift lights (green → amber → red → flash) |
| Pedals | Throttle % bar + value, brake % bar + value |
| Tyres | FL / FR / RL / RR temperature (colour-coded: blue → green → amber → red) + suspension height |
| Temps | Oil temp, oil pressure, water temp, boost pressure |
| Badges | TCS, ASM, REV limit indicators; suggested gear; fuel % |
| Lap timer | Running lap time (anchored to server-side `lap_started_at` — survives sleep/wake) |
| Lap info | Current lap / total, last lap time, best lap time, delta to best |

### `/compare` — Lap Analysis

N-lap overlay analysis modelled on MoTeC i2 / AiM Race Studio:

| Element | Description |
| --- | --- |
| Session browser | Sessions listed newest-first with car name, track name, lap count, best time. Filter by track and car. Expanding a session auto-selects all its laps for overlay. |
| N-lap overlay | All selected laps overlaid on every chart with distinct colours. Click any lap in the sidebar to toggle it on/off. |
| Baseline/reference | Best lap auto-set as reference (thicker dashed line, `[REF]` tag). Right-click any lap to change reference. Delta chart computed against it. |
| Session notes | Free-text note per session (e.g. "front DF +5"). Inline edit in sidebar. Shown in comparison header when overlaying laps from different sessions. |
| Auto-diff banner | Automatically detects gear ratio, top speed, and max speed changes between sessions — no user input needed. |
| Trace channels | Speed (km/h), throttle (%), brake (%), gear, lateral accel (m/s²), steering (rad) — all distance-aligned x-axis with labelled axes |
| Time delta | Gap graph: cumulative time difference vs reference lap at every metre of track |
| Track map | `position_x` vs `position_z` with lap-coloured paths |
| Crosshair sync | Hover any chart — all charts highlight the same distance point |

Laps are recorded automatically to `telemetry.db` (SQLite) on every `on_lap_change` event.

## Configuration

All configuration via environment variables. Pass inline or `export` before running.

| Variable | Default | Description |
| --- | --- | --- |
| `PS_IP` | _(auto)_ | PlayStation IP. Leave unset for automatic discovery (same LAN required). |
| `GT7_HEARTBEAT_TYPE` | `B` | Telemetry format: `A` = standard (~296 bytes), `B` = standard + motion data (steering, sway, heave, surge), `~` = standard + filtered inputs + energy recovery (hybrid/EV). One type active per session. |
| `DB_PATH` | `./telemetry.db` | SQLite database path. |

## Telemetry fields recorded

Every frame written to SQLite includes:

- **Motion**: speed, position (x/y/z), velocity (x/y/z), angular velocity, rotation, road plane
- **Powertrain**: RPM, gear, throttle, brake, clutch, boost, fuel level/capacity,
  gear ratios (1–8), transmission RPM/top speed
- **Temperatures**: oil temp/pressure, water temp, tyre temps (FL/FR/RL/RR)
- **Suspension**: tyre suspension heights (FL/FR/RL/RR), tyre radii, wheel RPS (FL/FR/RL/RR)
- **Driver aids**: TCS active, ASM active, rev limit, handbrake
- **Race state**: current lap, total laps, best/last lap time ms, race start position, total cars, time of day
- **Car**: car code, calculated max speed
- **Heartbeat B only**: steering wheel angle, sway, heave, surge, lateral slip angle
- **Heartbeat ~ only**: filtered throttle/brake, energy recovery (hybrid/EV)

## Stdout event log

Game state transitions are printed to stdout for observability:

```text
[gt-telem] event: on_at_track
[gt-telem] event: on_track_detected → track_id=40
[gt-telem] event: on_lap_change → lap 2
[gt-telem] event: on_in_game_menu
```

## Architecture

```text
PlayStation (GT7, ~60 Hz UDP)
        │
        ▼
  TurismoClient (gt-telem)          rexy/client.py
  fires sync callbacks per frame + game/race events
        │
        ├─── asyncio.Queue (maxsize=1, drop-oldest)
        │           │
        │           ▼
        │    FastAPI broadcaster      rexy/server.py
        │    fans out JSON to all WS clients
        │           │ WebSocket /ws
        │           ▼
        │    Browser — index.html     rexy/static/index.html
        │    live driving HUD
        │
        └─── LapRecorder              rexy/recorder.py
             session lifecycle (start/close on game events)
             buffers frames; flushes to SQLite on lap change
             (/compare reads via REST from the same DB)
```

| Component | File | Responsibility |
| --- | --- | --- |
| Telemetry client | `rexy/client.py` | Wraps `TurismoClient`; serialises frames; wires all game/race event callbacks |
| Dispatcher | `rexy/dispatcher.py` | Drains raw_queue; drop-oldest into ws_queue; calls `LapRecorder.on_frame()` |
| Lap recorder | `rexy/recorder.py` | Session lifecycle; buffers frames; flushes to SQLite on lap change |
| Repository | `rexy/repository.py` | All SQLite reads and writes; schema migrations via `user_version` |
| FastAPI server | `rexy/server.py` | WebSocket `/ws`; REST `/laps`, `/sessions`, `/sessions/{id}/laps`, `PATCH /sessions/{id}`, `/laps/{car_code}/{lap_number}/{lap_id}/frames`; serves static files |
| Live HUD | `rexy/static/index.html` | Vanilla JS; glanceable driving display |
| Lap analysis | `rexy/static/compare.html` | N-lap overlay with session browser, auto-diff banner, session notes, track/car filters, baseline reference, trace charts, delta, track map |
| Static data | `rexy/static/cars.json`, `tracks.json` | Car/track name lookups (559 cars, 106 tracks from gran-turismo.com) |
| Entrypoint | `rexy/__main__.py` | Wires all components; handles clean shutdown |
