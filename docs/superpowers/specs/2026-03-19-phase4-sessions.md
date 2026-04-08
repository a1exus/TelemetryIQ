# Phase 4 — Sessions: Session Browser & Car/Track Identity

**Date:** 2026-03-19
**Status:** Approved for planning

## Overview

Introduce proper session management to TelemetryIQ. Each trip to the track becomes a
first-class session entity with car and track identity. The `/compare` sidebar is
redesigned from a flat lap list to a session browser. Car and track names are resolved
from static JSON files bundled with the app.

This is Phase 4 Part 1. Manual setup annotation (tyre compound, suspension notes) is
Phase 4 Part 2 and is explicitly out of scope here.

## Goals

- Every outing on track is recorded as a distinct session with car code, track ID, and timestamps
- The `/compare` sidebar shows sessions grouped with laps nested, most recent expanded
- Car names and track names are resolved from `cars.json` and `tracks.json`
- Lap list shows delta to session best per lap
- No new Python dependencies

## Schema Changes

The existing `sessions` table gains three columns via migration:

```sql
ALTER TABLE sessions ADD COLUMN track_id     INTEGER;
ALTER TABLE sessions ADD COLUMN car_code     INTEGER;
ALTER TABLE sessions ADD COLUMN completed_at REAL;
```

`user_version` bumped from 1 → 2. In `repository.py`:

- `elif version == 1:` — run the three `ALTER TABLE` statements, commit, then
  `await self.db.execute("PRAGMA user_version = 2")` (literal, not a bind parameter —
  SQLite does not support `?` in PRAGMA statements; follow the existing v0→v1 pattern)
- `elif version == 2: pass` — steady state after migration
- Any other version raises `RuntimeError`

The `laps` table is unchanged.

## Session Lifecycle

Sessions are created and closed by track events, not by app startup.

| Event | Action |
| --- | --- |
| App start | No session created. `LapRecorder._session_id = None`. |
| `on_at_track` | Call `await recorder.start_session()` which creates a session row and sets `self._session_id`. Then start lap 1. |
| `on_in_race` | Same as `on_at_track`, start lap 0 instead. |
| `on_track_detected(track_id)` | Call `recorder.set_track_id(track_id)` (sync) — sets `self.current_track_id` and fires `asyncio.create_task(repo.update_session_track(...))` if session active. |
| Lap flush | After writing lap frames, call `repo.update_session_car(self._session_id, car_code)` using `car_code` from `self.lap_buffer[0]`. Only updates if session `car_code` is null. |
| `on_in_game_menu` | Call `await recorder.close_session()` which calls `repo.complete_session(self._session_id, completed_at=now)` then sets `self._session_id = None`. Close current lap first. |
| `on_race_end` | Same as `on_in_game_menu`. |

While `recorder._session_id is None`, frame recording and lap inserts are silently skipped.

### LapRecorder changes

- `__init__` no longer accepts or requires `session_id`. Initialises `self._session_id = None`.
- New method: `async def start_session() -> None` — calls `repo.insert_session()`, sets `self._session_id`.
- `set_track_id(track_id: int) -> None` remains sync (called via `call_soon_threadsafe`).
  It sets `self.current_track_id` and, if `self._session_id` is not None, dispatches
  `asyncio.create_task(self._repo.update_session_track(self._session_id, track_id))`.
- New method: `async def close_session() -> None` — calls `repo.complete_session`, sets `self._session_id = None`.

`__main__.py` removes the `insert_session` call and stops passing `session_id` to `LapRecorder`.

## Static Data Files

Two JSON files bundled at `rexy/static/`:

**`cars.json`** — mapping of GT7 car code (integer key as string) to display name:
```json
{"3520": "Porsche 911 GT3 (992)", "1234": "Toyota GR Supra RZ '20", ...}
```

**`tracks.json`** — mapping of GT7 track ID (integer key as string) to display name:
```json
{"40": "Suzuka Circuit", "12": "Nürburgring GP", ...}
```

Both files are scraped from `https://www.gran-turismo.com/us/gt7/carlist` and the
equivalent track list page and committed to the repo as static assets. No runtime
network calls are made by either server or client to resolve names.

Both files may be committed as empty objects (`{}`) initially and populated separately
— this does not block implementation. The UI falls back to `"Car {code}"` /
`"Track {id}"` when a code is not found.

If a code is not found in the JSON, the client falls back to `"Car {code}"` /
`"Track {id}"`.

## API

### New endpoints

#### `GET /sessions`

Returns all sessions that have at least one complete lap, newest first.

```json
[
  {
    "id": 12,
    "started_at": 1742394000.0,
    "completed_at": 1742397600.0,
    "track_id": 40,
    "car_code": 3520,
    "lap_count": 6,
    "best_lap_time_ms": 101887
  }
]
```

`lap_count` and `best_lap_time_ms` are computed by an aggregate query joining `sessions`
to `laps` (WHERE `laps.is_complete = 1`), grouped by `sessions.id`. Sessions with zero
complete laps are excluded via `HAVING COUNT(laps.id) > 0`.

#### `GET /sessions/{session_id}/laps`

Returns complete laps (`is_complete = 1` AND `lap_number > 0`) for a session, ordered by
lap number ascending. Lap 0 (out lap / formation lap in races) is excluded from the UI.
`track_id` is intentionally omitted — it lives on the session, not the lap list.

```json
[
  {"id": 268, "lap_number": 1, "lap_time_ms": 102341},
  {"id": 269, "lap_number": 2, "lap_time_ms": 101887},
  {"id": 270, "lap_number": 3, "lap_time_ms": 102104}
]
```

### Unchanged

- `GET /laps/{car_code}/{lap_number}/{lap_id}/frames`
- `GET /laps` (kept for compatibility, not used by new UI)

## UI — `/compare` Sidebar

### Data loading

1. On page load: `fetch('/sessions')` + `fetch('/static/cars.json')` + `fetch('/static/tracks.json')` in parallel.
2. Render session list. Most recent session expanded by default: `fetch('/sessions/{id}/laps')` for the first session only.
3. On session header click: toggle expanded state. If expanding for the first time, fetch laps.

### Session header (collapsed)

```
▶  Suzuka Circuit               2026-03-19 14:32
   Porsche 911 GT3 (992)  ·  6 laps  ·  best 1:41.887
```

### Session header (expanded)

```
▼  Suzuka Circuit               2026-03-19 14:32
   Porsche 911 GT3 (992)  ·  6 laps  ·  best 1:41.887

   Lap 1   1:42.341   +0.454s      [A] [B]
   Lap 2   1:41.887 ★              [A] [B]
   Lap 3   1:42.104   +0.217s      [A] [B]
```

Delta is `lap_time_ms - best_lap_time_ms` for the session, formatted as `+X.XXXs`.
Best lap row shows ★ and no delta.

### Slot assignment

A/B buttons work identically to the current implementation. Clicking A or B on a lap row
calls `fetchFrames(lap)` using `GET /laps/{car_code}/{lap_number}/{lap_id}/frames` and
loads the result into `state.lapA` or `state.lapB`. The rest of the compare page
(charts, track map, delta graph) is unchanged.

### Fallbacks

- Session with unknown `track_id` (null or not in `tracks.json`): show `"Unknown Track"`
- Session with unknown `car_code` (null or not in `cars.json`): show `"Unknown Car"`
- Session with no `completed_at`: show `"In progress"` instead of duration

## Out of Scope

- Tyre compound, suspension notes, or any other manual setup annotation (Phase 4 Part 2)
- Track name scraping detail (tracks.json populated as part of implementation)
- Export of lap data
- Driver profiles or multi-driver support
