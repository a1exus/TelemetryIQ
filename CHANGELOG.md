# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## v0.5.0 — Phase 4.2: Setup Comparison (2026-04-07)

### Added

- **Auto-diff banner** in `/compare`: automatically detects gear ratio, top
  speed, and max speed changes when comparing laps from different sessions
- **Session notes**: free-text note per session with inline edit in sidebar;
  shown in comparison header when overlaying laps from different sessions
- **Session filtering**: filter sidebar by track and/or car for faster
  navigation when you have many sessions
- `PATCH /sessions/{id}` endpoint for saving/clearing session notes
- Schema migration v2→v3: `notes TEXT` column on sessions table

### Changed

- **Live HUD redesigned**: removed Car State card (debug info) and historical
  charts from bottom zone — HUD is now a pure glanceable driving display
  (speed, gear, RPM, pedals, tires, lap timer). Chart.js removed from `/`.
- **Compare page redesigned**: replaced A/B two-lap selection with N-lap
  overlay. Expanding a session auto-selects all its laps with distinct
  colours. Click to toggle, right-click to set baseline/reference (thicker
  dashed line). Delta chart computed against reference. Axis labels added.
- `cars.json` populated (559 cars) and `tracks.json` (106 tracks) from
  official gran-turismo.com
- `specs.md` restructured around domain model with GT7 Data Logger use cases
  as north star

---

## v0.4.0 — Phase 4.1: Sessions (2026-03-19)

### Added

- **Sessions as first-class entities**: each track outing is a session with
  car and track identity
- `GET /sessions` — all sessions with at least one complete lap, newest first
- `GET /sessions/{id}/laps` — complete laps for a session (lap 0 excluded)
- `cars.json` and `tracks.json` static lookup files bundled at `/static/`
- Session browser sidebar on `/compare`: sessions grouped with nested lap
  rows, most recent expanded by default, delta-to-best per lap, best-lap
  indicator

### Changed

- `LapRecorder` no longer requires `session_id` at construction; sessions
  created automatically on `on_at_track`/`on_in_race` and closed on
  `on_in_game_menu`/`on_race_end`
- DB schema migrated user_version 1→2: sessions table gains `track_id`,
  `car_code`, `completed_at` columns

---

## v0.3.0 — Phase 3: Analysis Dashboard (2026-03-19)

### Added

- **Live engineering HUD** at `/`: full-viewport driver display with speed,
  RPM, gear, throttle/brake bars, shift lights, tyre temps, fuel, boost,
  lap timer with delta-to-best
- **Post-lap Chart.js overlay**: speed, throttle, brake traces rendered after
  each completed lap
- **`/compare` analysis dashboard**: distance-aligned multi-trace overlay
  (speed, throttle, brake, gear, lateral G, steering), time-delta graph,
  track map with crosshair sync
- `GET /laps` and `GET /laps/{car_code}/{lap_number}/{lap_id}/frames`
  REST endpoints
- All gt-telem game/race events logged to stdout: `on_running`, `on_paused`,
  `on_at_track`, `on_in_game_menu`, `on_in_race`, `on_race_start`,
  `on_race_finish`, `on_race_end`, `on_lap_change`, `on_track_detected`

### Fixed

- Lap timer anchored to server-recorded `lap_started_at` — survives browser
  refreshes and sleep/wake reconnects
- Ctrl-C shutdown no longer hangs: `tc.stop()` in executor with 3s timeout;
  `sys.exit(0)` to force-exit past gt-telem non-daemon threads
- Frame fetch errors and null `lap_time_ms` handled gracefully

---

## v0.2.0 — Phase 2: Recording + Live View (2026-03-16)

### Added

- **Full telemetry recording** to SQLite per lap on `on_lap_change` event
- **Live dashboard** at `/` with all telemetry field cards over WebSocket
- `TelemetryRepository` with SQLite schema, WAL journal mode, session/lap/
  frame CRUD
- `LapRecorder` state machine (IDLE/RECORDING) with async lock
- FastAPI server with WebSocket `/ws` broadcaster and static file serving
- `telemetry_to_dict` serialiser covering all gt-telem fields (A, B, ~)

### Changed

- Architecture: callback-driven `TurismoClient` with `asyncio.Queue`
  (maxsize=1, drop-oldest) for freshness over completeness

---

## v0.1.0 — Phase 1: Foundation (2026-03-15)

### Added

- GT7 telemetry connection via `gt-telem` (`TurismoClient`)
- Live stdout stream of speed, RPM, and gear
- `PS_IP` and `GT7_HEARTBEAT_TYPE` environment variables
- `.env.example` with documented configuration options
- Docker Compose with `network_mode: host` for PS5 UDP discovery
- `Makefile` with `build`, `up`, `down`, `logs`, `restart` targets
- Error handling for PlayStation not found / on standby

### Notes

- Docker Desktop on macOS/Windows cannot receive UDP from PS5 — use Linux
  host or run directly via pip on macOS/Windows
