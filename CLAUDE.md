# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

TelemetryIQ is a GT7 telemetry recorder and lap analysis tool. GT7 on
PlayStation broadcasts UDP telemetry at ~60 Hz; this app records full telemetry
per lap to SQLite and enables lap-over-lap comparison.

**Phase 1** (complete): CLI receiver that streams telemetry to stdout.
**Phase 2** (in design): Lap recording to SQLite + minimal live view over WebSocket.
**Phase 3** (planned): Full analysis dashboard — live display, two-lap overlay, gap graph, driving line.
**Phase 4** (planned): Car setup tagging, setup comparison, lap export.

## Commands

All Docker-based workflows use `make`:

```bash
make build    # docker compose build
make up       # docker compose up -d
make down     # docker compose down
make logs     # docker compose logs -f
make restart  # down + up
make install  # create .venv and pip install -r requirements.txt (macOS/Windows local dev only)
```

Run directly (macOS/Windows only — Docker Desktop can't receive PS5 UDP):

```bash
source .venv/bin/activate
python -m rexy
```

No test suite exists yet. No Python linter is configured.

## Architecture

### Data Flow (Phase 1, current)

```text
GT7 (PS5, UDP ~60 Hz) → TurismoClient (gt-telem) → stdout poll loop
```

`rexy/__main__.py` is the sole source file. It reads `PS_IP` and
`GT7_HEARTBEAT_TYPE` from the environment, creates a `TurismoClient`, and
polls `tc.telemetry` every second.

### Planned Data Flow (Phase 2+, see `specs.md`)

```text
GT7 (UDP) → rexy/client.py (TurismoClient async callbacks)
         → asyncio.Queue(maxsize=1)   ← drop-oldest, keeps freshest frame
         → rexy/server.py (FastAPI, /ws WebSocket broadcaster)  ← live view
         → SQLite (full telemetry written per lap on on_lap_change)  ← recording
         → browser dashboard (rexy/static/index.html, vanilla JS + Canvas/SVG)
```

Key design choices:

- **Recording before analysis**: SQLite lap storage (Phase 2) is the foundation for comparison (Phase 3).
- **`maxsize=1` queue**: freshness over completeness at ~60 Hz.
- **Single static HTML file**: no npm, no build step.
- **Single container**: no sidecars, no external services.
- **Host networking (`network_mode: host`)**: required on Linux for PS5 UDP
  discovery. Not compatible with macOS or Windows Docker Desktop.

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
