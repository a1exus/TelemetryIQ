# Task: Telemetry recording

**Phase**: 2 — Recording
**Status**: Complete ✅

## Objective

Persist full telemetry per lap to SQLite and provide a minimal live view over WebSocket.

## Acceptance criteria

- [x] On `on_lap_change` event, completed lap telemetry is written to SQLite
- [x] SQLite schema stores all telemetry fields with timestamp and lap number
- [x] WebSocket endpoint (`/ws`) broadcasts live frames (speed, RPM, gear, lap time) at ~60Hz
- [x] Minimal browser page confirms live data is flowing
- [x] `docker compose up` is the only command needed on Linux/Raspberry Pi

## Notes

- Use gt-telem async callbacks; push frames to `asyncio.Queue(maxsize=1)` for the WebSocket broadcaster.
- SQLite is the storage target — no external services.
- Lap boundary is `on_lap_change` from `RaceEvents`.
- See `specs.md` for full telemetry field reference.
