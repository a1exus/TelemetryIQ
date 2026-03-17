# TelemetryIQ: Gemini Context & Instructions

This document provides essential context and instructions for AI agents working on the TelemetryIQ project.

## Project Overview

**TelemetryIQ** (package name `rexy`) is a GT7 telemetry recorder and lap analysis tool. It captures UDP telemetry from PlayStation via `gt-telem`, records full telemetry per lap to SQLite, streams live data over WebSocket, and enables lap-over-lap comparison.

- **Primary Technologies:** Python 3.10+, `gt-telem`, FastAPI, SQLite (`aiosqlite`), Docker Compose.
- **Status:** Phase 2 (Recording) implementation in progress. Phase 1 (Foundation) complete.
- **Specs:** `specs.md` is the authoritative source for requirements. Detailed phase designs and "Superpower" plans are in `docs/superpowers/`.

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

- `rexy/__main__.py`: App entrypoint; creates session row; wires tasks; handles shutdown.
- `rexy/client.py`: Wraps `TurismoClient`; sync callbacks; `call_soon_threadsafe` for queue/lifecycle ops; `telemetry_to_dict` serializer.
- `rexy/dispatcher.py`: Drains `raw_queue`; drop-oldest to `ws_queue`; calls `LapRecorder.on_frame()`.
- `rexy/recorder.py`: `LapRecorder`: IDLE/RECORDING state machine; buffer-before-await pattern for lap flushes.
- `rexy/repository.py`: `TelemetryRepository`: persistent `aiosqlite` connection; CRUD for sessions, laps, and frames.
- `rexy/server.py`: FastAPI server; `/ws` broadcaster task; maintains client set.
- `rexy/static/index.html`: Single-page vanilla JS/Canvas dashboard; rAF render loop.
- `specs.md`: Authoritative source for requirements, architecture, and telemetry fields.
- `plan.md`: High-level roadmap and phase definitions.
- `tasks/`: Individual task files per phase (e.g., `01-*.md`, `02-*.md`).
- `docs/superpowers/`: Detailed phase designs, deep-dive specs, and architectural decisions.

## Configuration (.env)

| Variable | Description | Default |
| --- | --- | --- |
| `PS_IP` | PlayStation IP address (optional if auto-discovery works) | (None) |
| `GT7_HEARTBEAT_TYPE` | `A` (standard), `B` (motion), or `~` (filtered + energy) | `B` |

## Development & Operations

### Common Commands (Makefile)

- `make install`: Set up local venv and install package in editable mode.
- `make build`: Build Docker images.
- `make up`: Start containers in background.
- `make restart`: Restart containers (down + up).
- `make logs`: Follow container logs.
- `make down`: Stop and remove containers.

### Platform-Specific Running

- **macOS / Windows (Host-side):** Docker Desktop cannot receive PS5 UDP. `gt-telem` must run on the host directly.
  ```bash
  source .venv/bin/activate && python -m rexy
  ```
- **Linux / Raspberry Pi (Docker):** Uses `network_mode: host` for direct UDP access.
  ```bash
  make build && make up && make logs
  ```

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

- **Explore:** Fast read-only codebase exploration. Usage: `Explore: <thoroughness (quick/medium/thorough)> - <what you are looking for>`
- **Directives:** When implementing a phase, ensure you've read the corresponding `tasks/*.md` file and updated the status when complete.
