# Changelog

All notable changes to this project will be documented in this file.

## [Week of 2026-04-07]

### Changed

- **Live HUD redesign**: removed Car State card (debug info) and historical
  charts from bottom zone. HUD is now a pure glanceable driving display —
  speed, gear, RPM, pedals, tires, lap timer. No Chart.js dependency on `/`.
- **Compare page redesign**: replaced A/B two-lap model with N-lap overlay.
  Expanding a session auto-selects all its laps with distinct colours.
  Click to toggle laps on/off. Right-click to set baseline/reference lap
  (rendered as thicker dashed line). Delta chart computed against reference.
  Axis labels added to all charts.
- `cars.json` populated with 559 cars and `tracks.json` with 106 tracks,
  sourced from official gran-turismo.com JS bundles.
- `specs.md` restructured around domain model: vision, use cases, domain
  entities, architecture, decisions, known issues, roadmap.

## [Week of 2026-03-19] — Phase 4 Part 1

### Added

- Session management: each track outing is a first-class session with car and track identity
- `GET /sessions` — all sessions with at least one complete lap, newest first
- `GET /sessions/{id}/laps` — complete laps for a session (lap 0 excluded)
- `cars.json` and `tracks.json` static lookup files bundled at `/static/`
- Session browser sidebar on `/compare`: sessions grouped with nested lap rows,
  most recent expanded by default, delta-to-best shown per lap row

### Changed

- `LapRecorder` no longer requires `session_id` at construction; sessions are created
  automatically on `on_at_track` and `on_in_race` events and closed on `on_in_game_menu`
  and `on_race_end`
- DB schema migrated user_version 1 to 2: sessions table gains `track_id`,
  `car_code`, and `completed_at` columns

## [Week of 2026-03-19]

### Added

- Live engineering HUD: full-viewport driver display with speed, RPM, gear, throttle/brake bars,
  G-force gauge, tyre temps, fuel, boost, and lap timer
- Post-lap Chart.js overlay: speed, throttle, brake, and lateral-G traces rendered after
  each lap completes
- `/compare` lap comparison dashboard: distance-aligned multi-trace overlay, time-delta
  graph, track map with crosshair sync; replaces the old `/analysis` route
- All gt-telem game/race events logged to stdout: `on_running`, `on_paused`, `on_at_track`,
  `on_in_game_menu`, `on_in_race`, `on_race_start`, `on_race_finish`, `on_race_end`,
  `on_lap_change`, `on_track_detected`

### Fixed

- Lap timer anchored to server-recorded `lap_started_at` timestamp — survives browser refreshes
  and sleep/wake reconnects without resetting to zero
- Frame fetch errors and null `lap_time_ms` handled gracefully in the comparison dashboard
- Ctrl-C shutdown no longer hangs: `tc.stop()` now runs in a thread executor with a 3 s
  timeout, preventing the event loop from blocking on gt-telem's internal thread join

## [Week of 2026-03-16]

### Changed

- Rethought product phases: recording (Phase 2) now precedes the analysis dashboard
  (Phase 3); setup comparison added as Phase 4
- Removed lap recording from "out of scope" — it is now the core of Phase 2
- `specs.md` is now the single source of truth for constraints and design decisions;
  no separate design documents
- Updated `plan.md`, `tasks/`, `README.md`, `GEMINI.md`, and `CLAUDE.md` to reflect
  new phases and correct entrypoint (`python -m rexy`)
- Driving line (`position_x/y/z`) added to Phase 3 dashboard requirements

## [Week of 2026-03-15]

### Added

- `PS_IP` env variable for manual PlayStation IP when auto-discovery fails
- `GT7_HEARTBEAT_TYPE` env variable to configure telemetry format
  (`A`, `B`, or `~`)
- `.env.example` with documented configuration options
- README with prerequisites, setup, run instructions, and config reference
- `Makefile` with `build`, `up`, `down`, `logs`, `restart` targets

### Changed

- `TurismoClient` now reads `PS_IP` and `GT7_HEARTBEAT_TYPE` from environment
- Docker Compose wires in `.env` via `env_file` (optional, won't fail if missing)
- Renamed Docker Compose service from `gt7` to `telemetryiq`
- Renamed package directory from `gt7` to `rexy`
- Reverted to `requirements.txt` for dependency management; removed `pyproject.toml`
- Dockerfile reverted to `pip install -r requirements.txt`; entrypoint is
  `python -m rexy`

### Notes

- Docker Desktop on macOS and Windows cannot receive UDP from external devices (PS5).
  Use a Linux host (e.g. Raspberry Pi) on the same LAN, or install via pip on macOS/Windows.

## [Week of 2026-03-09]

### Added

- GT7 telemetry connection via `gt-telem` (`TurismoClient`)
- Live stdout stream of speed, RPM, and gear from GT7
- Error handling for PlayStation not found and PlayStation on standby
- Docker Compose setup with host networking for PlayStation discovery
- `python -m gt7` entrypoint
