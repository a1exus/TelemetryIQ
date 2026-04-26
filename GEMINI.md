# TelemetryIQ: Gemini Context & Instructions

This document provides essential context and instructions for AI agents working on the TelemetryIQ project.

## Project Overview

**TelemetryIQ** (package name `rexy`) is a GT7 telemetry recorder and
lap analysis tool. It captures UDP telemetry from PlayStation via
`gt-telem`, records full telemetry per lap to SQLite, streams live data
over WebSocket, and enables lap-over-lap comparison.

- **Primary Technologies:** Python 3.10+, `gt-telem`, FastAPI, SQLite (`aiosqlite`).
- **Status:** Phases 1–5 and 7 complete. Phase 6 (lap data export) planned.
- **Specs:** `specs.md` is the authoritative source for requirements.
  Phase designs and plans are in `docs/superpowers/`.

## Architecture & Flow

```text
PlayStation (GT7, ~60Hz UDP)
        │
        ▼
  TurismoClient (gt-telem) — sync callbacks in thread pool
        │
        ▼ call_soon_threadsafe
        │
  raw_queue (unbounded) — receives every frame from callback
        │
        ▼
  dispatcher task — drains raw_queue; no-I/O state updates
        │
        ├── LapRecorder — buffer-before-await; writes per-lap SQLite frames
        │
        └── ws_queue (maxsize=1, drop-oldest) — holds freshest frame
                │
                ▼
          FastAPI broadcaster task — fans out ws_queue to clients
                │
                ▼ WebSocket /ws (JSON)
                │
          Browser — Vanilla JS Dashboard (WS reconnection w/ exp. backoff)
```

## Key Files & Responsibilities

- `rexy/__main__.py`: App entrypoint; wires tasks; handles shutdown.
- `rexy/client.py`: Wraps `TurismoClient`; sync callbacks;
  `call_soon_threadsafe` for queue/lifecycle ops.
- `rexy/dispatcher.py`: Drains `raw_queue`; drop-oldest to `ws_queue`; calls `LapRecorder.on_frame()`.
- `rexy/recorder.py`: `LapRecorder`: session/lap lifecycle;
  buffers frames and flushes to SQLite.
- `rexy/repository.py`: `TelemetryRepository`: `aiosqlite` connection;
  schema migrations via `user_version` (v3); CRUD for sessions, laps, frames.
- `rexy/server.py`: FastAPI server; `/ws` broadcaster; REST API
  (`/sessions`, `/sessions/{id}/laps`, `/laps`, `/laps/.../frames`,
  `PATCH /sessions/{id}`); serves static files.
- `rexy/static/index.html`: Live HUD — speed, RPM, gear, pedals,
  tires, lap timer.
- `rexy/static/compare.html`: N-lap overlay analysis organised into
  three tabs (Driving Line / Inputs / Powertrain) aligned with GT7's
  in-game Data Logger; selected tab persisted in URL hash. Includes
  session browser, auto-diff, session notes, track/car filters, trace
  charts, delta, track map.
- `rexy/static/cars.json`, `tracks.json`: Car/track name lookups (559 cars, 106 tracks from gran-turismo.com).
- `specs.md`: Authoritative source for requirements, architecture, and telemetry fields.
- `plan.md`: High-level roadmap and phase definitions.
- `tasks/`: Individual task files per phase (e.g., `01-*.md`, `02-*.md`, `03-*.md`).
- `docs/superpowers/`: Detailed phase designs, deep-dive specs, and architectural decisions.

## Configuration (.env)

| Variable | Description | Default |
| --- | --- | --- |
| `PS_IP` | PlayStation IP address (optional if auto-discovery works) | (None) |
| `GT7_HEARTBEAT_TYPE` | `A` (standard), `B` (motion), or `~` (filtered + energy) | `B` |
| `DB_PATH` | SQLite database path | `./telemetry.db` |

## Development & Operations

### Common Commands (Makefile)

Run `make` or `make help` for usage.

- `make install`: Create `.venv` and install dependencies.
- `make run`: Start TelemetryIQ (auto-discovers PlayStation on LAN).
- `make test`: Run tests.
- `PS_IP=192.168.1.42 make run`: Set PlayStation IP manually.

## GT7 Connectivity Requirements

- PlayStation and host must be on the same LAN subnet.
- UDP Telemetry must be enabled in GT7: **Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On**.
- Handle `PlayStationNotFoundError` and `PlayStationOnStandbyError` gracefully.

## Project Standards

- **Design Doc:** `specs.md` is the only design document. Do not create new ones.
- **Changelog:** Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) in `CHANGELOG.md`.
- **Out of Scope:** The `./lib` directory is for reference only; do not modify.
- **Dependencies:** Python 3.10+ is required.

## Workspace Agents

- **Explore:** Fast read-only codebase exploration.
  Usage: `Explore: <thoroughness> - <what you are looking for>`
- **Directives:** When implementing a phase, read the corresponding
  `tasks/*.md` file and update the status when complete.
