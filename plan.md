# TelemetryIQ — Implementation Plan

## Summary

High-level implementation plan for TelemetryIQ. All phases (1–7) are complete.

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

### Phase 6: Lap Data Export ✅

- `GET /laps/{car_code}/{lap_number}/{lap_id}/export.csv` returns a lap's frames as CSV with `Content-Disposition: attachment`.
- `csv` link on each lap row in `/compare`.
- Narrow scope by design: SQLite is already the de-facto export, and most analysis use cases are covered in-app by Phase 7. MoTeC LD or multi-lap export deferred until a real user request.

### Phase 7: GT7-Aligned Compare View ✅

- Restructured `/compare` into three tabs (Driving Line / Inputs / Powertrain) mirroring GT7 Spec III's in-game Data Logger.
- New engine RPM trace in Powertrain tab.
- Tab selection persisted in URL hash (`#tab=line|inputs|powertrain`).
- Tab 1 desktop layout (≥1024px): track map left, speed/delta stacked right.
- Crosshair listener leak fixed (sentinel-flag attach; active-tab self-check).
- WAI-ARIA tab pattern wired (`role`, `aria-selected`, `aria-controls`, `aria-labelledby`).

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
| 2026-04-26 | Added Phase 7 (GT7-aligned compare view) |
| 2026-04-26 | Phase 6 (per-lap CSV export, narrow scope) shipped |
