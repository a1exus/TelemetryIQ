# Changelog

All notable changes to this project will be documented in this file.

## [Week of 2026-03-15]

### Added

- `PS_IP` env variable for manual PlayStation IP when auto-discovery fails
- `GT7_HEARTBEAT_TYPE` env variable to configure telemetry format
  (`A`, `B`, or `~`)
- `.env.example` with documented configuration options
- README with prerequisites, setup, run instructions, and config reference

### Changed

- `TurismoClient` now reads `PS_IP` and `GT7_HEARTBEAT_TYPE` from environment
- Docker Compose wires in `.env` via `env_file` (optional, won't fail if missing)
- Renamed Docker Compose service from `gt7` to `telemetryiq`

## [Week of 2026-03-09]

### Added

- GT7 telemetry connection via `gt-telem` (`TurismoClient`)
- Live stdout stream of speed, RPM, and gear from GT7
- Error handling for PlayStation not found and PlayStation on standby
- Docker Compose setup with host networking for PlayStation discovery
- `python -m gt7` entrypoint
