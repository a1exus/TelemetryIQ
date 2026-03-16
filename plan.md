# GT7 — Implementation Plan

## Summary

High-level implementation plan for GT7. **What we have now is only the beginning** — Phase 1 is done; Phases 2 and beyond will grow the product. Tasks are tracked in `tasks/`.

## Phases

### Phase 1: Foundation ✅ (current / beginning)

- Set up project structure, tooling, and baseline.
- **Deliverables**: Repo layout, dependencies, Docker Compose, minimal runnable `python -m gt7` that connects to telemetry.
- **Tasks**: See `tasks/01-*.md`.
- **Status**: In place; more will be built on top.

### Phase 2: Core features (to be defined)

- Implement the first real product features (dash, recorder, motion driver, analytics, etc. — TBD in specs).
- **Deliverables**: Working features per updated specs.
- **Tasks**: See `tasks/02-*.md` (add/split as we decide what to build).

### Phase 3: Polish & release (later)

- Testing, docs, performance, and release prep.
- **Deliverables**: Tests passing, docs updated, release checklist done.
- **Tasks**: See `tasks/03-*.md`.

## Dependencies

- Phase 2 depends on Phase 1.
- Phase 3 depends on Phase 2.

## Tech stack

- **Python**: 3.10+
- **Telemetry**: [gt-telem](https://pypi.org/project/gt-telem/) (`pip install gt-telem`)
- **Runtime context**: PC on same network as PlayStation running GT7; telemetry enabled in game.

## Risks & mitigations

| Risk | Mitigation |
|------|-------------|
| PlayStation not found / wrong network | Document network requirements; handle `PlayStationNotFoundError` / `PlayStationOnStandbyError` from gt-telem |
| _Risk_ | _Mitigation_ |

## Revision log

| Date | Change |
|------|--------|
| 2025-03-15 | Initial plan; phases and task references added |
| 2025-03-15 | Aligned with gt-telem; added tech stack and PS discovery error mitigation |
| 2025-03-15 | Clarified: Phase 1 = beginning only; Phase 2/3 = product growth to be defined |
