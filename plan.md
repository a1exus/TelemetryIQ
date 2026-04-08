# TelemetryIQ — Implementation Plan

## Summary

High-level implementation plan for TelemetryIQ. All five phases are complete. Phase 6 (lap data export) is planned.

## Phases

### Phase 1: Foundation ✅

- **Deliverables**: Repo layout, dependencies, `python -m rexy` connects to GT7 telemetry and streams to stdout.
- **Tasks**: See `tasks/01-*.md`.

### Phase 2: Recording ✅

- Full telemetry recording per lap to SQLite on `on_lap_change` event.
- Live HUD via WebSocket; FastAPI server with broadcaster.
- **Tasks**: See `tasks/02-*.md`.

### Phase 3: Analysis Dashboard ✅

- N-lap overlay comparison (speed, throttle, brake, gear, lateral G, steering traces).
- Distance-based x-axis, time delta graph, track map, crosshair sync.
- **Tasks**: See `tasks/03-*.md`.

### Phase 4: Sessions ✅

- Sessions as first-class entities with car/track identity.
- Session browser sidebar on `/compare`.
- `GET /sessions`, `GET /sessions/{id}/laps` endpoints.

### Phase 5: Setup Comparison ✅

- Auto-diff banner detecting gear ratio, top speed, max speed changes between sessions.
- Session notes (free-text per session) with inline editing.
- Track/car filtering in session browser.
- `PATCH /sessions/{id}` endpoint for notes.

### Phase 6: Lap Data Export (planned)

- Export lap data for external analysis tools.

## Tech stack

- **Python**: 3.10+
- **Telemetry**: [gt-telem](https://pypi.org/project/gt-telem/)
- **Runtime context**: PC/Raspberry Pi on same LAN as PlayStation running GT7; telemetry enabled in game.

## Risks & mitigations

| Risk                                  | Mitigation                                                                    |
|---------------------------------------|-------------------------------------------------------------------------------|
| PlayStation not found / wrong network | Handle `PlayStationNotFoundError` / `PlayStationOnStandbyError` from gt-telem |

## Revision log

| Date | Change |
|------|--------|
| 2025-03-15 | Initial plan |
| 2025-03-15 | Aligned with gt-telem; added tech stack and PS discovery error mitigation |
| 2026-03-16 | Rethought phases: recording first, analysis second, setup comparison fourth |
| 2026-04-07 | Updated all phases to reflect completion; added Phases 4–6 |
