# Phase 4 — Session Browser & Car/Track Identity

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

`user_version` bumped from 1 → 2. Migration runs on startup if `user_version == 1`.

The `laps` table is unchanged.

## Session Lifecycle

Sessions are created and closed by track events, not by app startup.

| Event | Action |
| --- | --- |
| App start | No session created. `LapRecorder._session_id = None`. |
| `on_at_track` | Create new session row (`started_at = now`). Set `recorder._session_id`. Start lap 1. |
| `on_in_race` | Create new session row. Set `recorder._session_id`. Start lap 0. |
| `on_track_detected(track_id)` | `UPDATE sessions SET track_id = ? WHERE id = recorder._session_id` |
| Lap flush | `UPDATE sessions SET car_code = ?` using `car_code` from the flushed lap's frames (first non-null value). Only set if not already set. |
| `on_in_game_menu` | `UPDATE sessions SET completed_at = now`. Set `recorder._session_id = None`. Close current lap. |
| `on_race_end` | Same as `on_in_game_menu`. |

While `recorder._session_id is None`, frame recording and lap inserts are silently skipped.

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
equivalent track list page. They are committed to the repo as static assets. No
runtime network calls are made by either server or client to resolve names.

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

`lap_count` and `best_lap_time_ms` are computed by the query (aggregate over laps).
Sessions with zero complete laps are excluded.

#### `GET /sessions/{session_id}/laps`

Returns complete laps for a session, ordered by lap number ascending.

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
