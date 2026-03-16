# GT7 — Specifications

## Overview

- **Project**: GT7 — application using Gran Turismo 7 telemetry
- **Status**: Draft (beginning / foundation only)
- **Last updated**: 2025-03-15
- **Telemetry source**: [gt-telem](https://pypi.org/project/gt-telem/) (Python library for Polyphony Digital’s motion-rig telemetry in GT6/GTS/GT7)

**This is just the beginning.** Current scope is the foundation: connect to telemetry, run in Docker, minimal CLI. The full product (dash, recorder, motion rig, analytics, etc.) will be defined and built in later phases.

## Current state (foundation)

What exists today:

- Connect to GT7 via gt-telem (`TurismoClient`), basic error handling for PS not found/standby
- Docker Compose + Dockerfile, host network for discovery
- Minimal `python -m gt7` entrypoint that streams speed/rpm/gear to stdout
- Specs, plan, and task scaffolding in `plan.md` and `tasks/`

## Goals (product direction — to be refined)

- [ ] _Define primary goal 1 (e.g. dash, recorder, motion rig driver, analytics)_
- [ ] _Define primary goal 2_

## Scope

### In scope

- Connect to GT7 telemetry via gt-telem (PlayStation and PC on same network; telemetry enabled in GT7).
- _Feature / area 1_
- _Feature / area 2_

### Out of scope

- _Explicitly excluded_

## Requirements

### Functional

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Connect to GT7 telemetry (TurismoClient, sync/async or callbacks) | Must |
| F2 | _Requirement_ | Should |
| F3 | _Requirement_ | Could |

### Non-functional

| ID | Requirement | Priority |
|----|-------------|----------|
| NF1 | Python 3.10+ (gt-telem requirement) | Must |
| NF2 | _Performance / latency / UX_ | Should |

## Constraints & assumptions

- **Constraints**: gt-telem (LGPLv3), Python ≥3.10; GT7 running on PlayStation; same network for PS and PC.
- **Assumptions**: Telemetry enabled in GT7; optional use of heartbeat types (A=default, B=motion data, ~=extended) per [gt-telem docs](https://pypi.org/project/gt-telem/).

## Success criteria

- [ ] _Measurable outcome 1_
- [ ] _Measurable outcome 2_

## Roadmap / Later

- _Add next big goals: e.g. live dash UI, telemetry recorder, motion-rig driver, replay/analytics, multi-client, …_
- _Prioritise and break into phases in `plan.md` and `tasks/` as we go._

## References

- [gt-telem on PyPI](https://pypi.org/project/gt-telem/) — install: `pip install gt-telem`
- gt-telem: PlayStation discovery, sync/async callbacks, game/race/driver events, heartbeat types A / B / ~
