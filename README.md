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

## macOS / Windows

Docker Desktop on macOS and Windows runs containers inside a Linux VM that is not on the
same network as the host, so PS5 UDP telemetry cannot reach the container. Run directly
on the host instead.

```shell
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set PS_IP if auto-discovery doesn't work
python -m rexy
```

## Linux / Raspberry Pi (Docker)

```shell
cp .env.example .env
# Edit .env — set PS_IP if auto-discovery doesn't work
make build
make up
make logs
```

## Web UI

Once running, open **<http://localhost:8000>** in a browser from any device on the LAN.

### `/` — Live HUD

Full-viewport engineering display, updated at ~60 Hz:

| Section | Fields |
| --- | --- |
| Speed | km/h (large) |
| Powertrain | RPM bar + shift lights, gear, suggested gear |
| Pedals | Throttle % bar, brake % bar |
| G-forces | Lateral and longitudinal gauge |
| Tyres | FL / FR / RL / RR temperature (colour-coded) |
| Temps | Oil temp, water temp, boost pressure |
| Fuel | Level bar + percentage |
| Lap timer | Running lap time (anchored to server-side lap-start — survives sleep/wake) |
| Lap info | Current lap number, last lap time, best lap time |
| Post-lap overlay | Chart.js traces (speed, throttle, brake, lateral G) rendered automatically after each lap |

### `/compare` — Lap Comparison

Select any two recorded laps for a side-by-side analysis:

| Element | Description |
| --- | --- |
| Lap selector | Filterable list of all recorded laps with time, car code, and date |
| Trace overlay | Speed, throttle, brake, gear, lateral G — distance-aligned x-axis |
| Time delta | Gap graph: cumulative time difference at every metre of track |
| Track map | `position_x` vs `position_z`, colour-coded by speed; two-lap overlay |
| Crosshair sync | Hover any chart — all charts and track map highlight the same distance point |

Laps are recorded automatically to `telemetry.db` (SQLite) on every `on_lap_change` event.

## Configuration

All configuration via `.env`. See [`.env.example`](.env.example) for the full reference.

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
        │    dispatcher loop          rexy/dispatcher.py
        │    writes frames to SQLite on active lap
        │           │
        │           ▼
        │    ws_queue (maxsize=1)
        │           │
        │           ▼
        │    broadcaster loop         rexy/server.py
        │    fans out JSON to all WS clients
        │           │ WebSocket /ws
        │           ▼
        │    Browser — index.html     rexy/static/index.html
        │    live HUD + post-lap charts
        │
        └─── LapRecorder              rexy/recorder.py
             flushes buffered frames to SQLite on lap change
             (/compare reads via REST from the same DB)
```

| Component | File | Responsibility |
| --- | --- | --- |
| Telemetry client | `rexy/client.py` | Wraps `TurismoClient`; serialises frames; wires all game/race event callbacks |
| Dispatcher | `rexy/dispatcher.py` | Drains raw queue; feeds ws_queue and recorder |
| Lap recorder | `rexy/recorder.py` | Buffers frames; flushes to SQLite on lap change |
| Repository | `rexy/repository.py` | All SQLite reads and writes |
| FastAPI server | `rexy/server.py` | WebSocket `/ws`; REST `/laps`, `/laps/{id}/frames`; serves static files |
| Live HUD | `rexy/static/index.html` | Vanilla JS; live gauges + post-lap Chart.js overlay |
| Entrypoint | `rexy/__main__.py` | Wires all components; handles clean shutdown |
