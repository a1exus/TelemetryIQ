# TelemetryIQ — Implementation Plan

## Summary

High-level implementation plan for TelemetryIQ. Phase 1 is done; Phases 2–4 build toward a full lap analysis tool. Tasks are tracked in `tasks/`.

## Phases

### Phase 1: Foundation ✅

- **Deliverables**: Repo layout, dependencies, Docker Compose, `python -m rexy` connects to GT7 telemetry and streams to stdout.
- **Tasks**: See `tasks/01-*.md`.

### Phase 2: Recording

- Persist full telemetry per lap to SQLite on `on_lap_change` event.
- Minimal live view via WebSocket (speed, RPM, gear, lap time) — enough to confirm the connection is working.
- **Tasks**: See `tasks/02-*.md`.

### Phase 3: Analysis Dashboard

- Full live telemetry display (all fields).
- Lap selector; two-lap overlay comparison (throttle, brake, speed, RPM traces).
- Gap graph; driving line from `position_x/y/z`.
- **Tasks**: See `tasks/03-*.md`.

### Phase 4: Setup Comparison

- Car setup tagging per recorded lap.
- Setup-vs-setup comparison on the same track.
- Lap data export.
- **Tasks**: See `tasks/04-*.md`.

## Dependencies

- Phase 2 depends on Phase 1.
- Phase 3 depends on Phase 2 (needs recorded laps to compare).
- Phase 4 depends on Phase 3.

## Tech stack

- **Python**: 3.10+
- **Telemetry**: [gt-telem](https://pypi.org/project/gt-telem/)
- **Runtime context**: PC/Raspberry Pi on same LAN as PlayStation running GT7; telemetry enabled in game.

## Risks & mitigations

| Risk                                               | Mitigation                                                                    |
|----------------------------------------------------|-------------------------------------------------------------------------------|
| PlayStation not found / wrong network              | Handle `PlayStationNotFoundError` / `PlayStationOnStandbyError` from gt-telem |
| macOS / Windows Docker Desktop can't receive PS5 UDP | Run gt-telem on host directly (documented in README)                        |

## Revision log

| Date | Change |
|------|--------|
| 2025-03-15 | Initial plan |
| 2025-03-15 | Aligned with gt-telem; added tech stack and PS discovery error mitigation |
| 2026-03-16 | Rethought phases: recording first, analysis second, setup comparison fourth |
