# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

TelemetryIQ is a GT7 telemetry recorder and lap analysis tool. GT7 on
PlayStation broadcasts UDP telemetry at ~60 Hz; this app records full telemetry
per lap to SQLite and enables lap-over-lap comparison.

**Phase 1** (complete): CLI receiver that streams telemetry to stdout.
**Phase 2** (complete): Lap recording to SQLite + live HUD over WebSocket.
**Phase 3** (complete): Analysis dashboard — N-lap overlay, gap graph, track map.
**Phase 4** (complete): Sessions as first-class entities, car/track identity.
**Phase 5** (complete): Setup comparison — auto-diff, session notes, filtering.

## Commands

```bash
make install  # create .venv and pip install -r requirements.txt
make run      # python -m rexy
make test     # pytest tests/ -v
```

## Architecture

### Data Flow

```text
GT7 (UDP ~60 Hz) → TurismoClient (gt-telem, sync callbacks)
    → call_soon_threadsafe → asyncio.Queue(maxsize=1)
    → FastAPI broadcaster → WebSocket /ws → Browser HUD (index.html)
    → LapRecorder → SQLite (telemetry.db)
    → Browser /compare reads via REST from same DB
```

### Components

| Component | File | Responsibility |
| --- | --- | --- |
| Telemetry client | `rexy/client.py` | Wraps `TurismoClient`; sync callbacks dispatch to asyncio via `call_soon_threadsafe`; logs all events to stdout |
| Dispatcher | `rexy/dispatcher.py` | Drains raw_queue; drop-oldest into ws_queue; calls `LapRecorder.on_frame()` |
| FastAPI server | `rexy/server.py` | WebSocket `/ws`; REST API; serves static files |
| Lap recorder | `rexy/recorder.py` | Session lifecycle; lap lifecycle; buffers frames and flushes to SQLite |
| Repository | `rexy/repository.py` | SQLite access; schema DDL with `user_version` migration (currently v3) |
| Live HUD | `rexy/static/index.html` | Vanilla JS; speed/gear/RPM, pedals, tires, lap timer; no charts (analysis is on /compare) |
| Compare | `rexy/static/compare.html` | N-lap overlay; session browser; auto-diff banner; session notes; track/car filters; distance-based traces; delta graph; track map |
| Static data | `rexy/static/cars.json`, `tracks.json` | Car/track name lookups from gran-turismo.com |
| Entrypoint | `rexy/__main__.py` | Wires all components; handles shutdown (`sys.exit(0)` past gt-telem threads) |

### GT7 Telemetry

GT7 listens on port 33739; the client listens on port 33740.
`GT7_HEARTBEAT_TYPE` selects the telemetry mode (only one active per session):

| Value | Data                                                                          |
|-------|-------------------------------------------------------------------------------|
| `A`   | Standard (~296 bytes): speed, RPM, gear, throttle, brake, G-forces, temps, fuel, lap times, etc. |
| `B`   | Motion data (~316 bytes): all of A + steering wheel, sway, heave, surge, slip angle |
| `~`   | Filtered inputs + energy recovery (hybrid/EV)                                 |

## Configuration

Copy `.env.example` → `.env`. Leave `PS_IP` blank for auto-discovery (same LAN required).

## Constraints

See `specs.md` for the authoritative list of constraints and design decisions. Do not duplicate them here.
