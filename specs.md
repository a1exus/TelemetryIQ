# TelemetryIQ — Specifications

## Vision

TelemetryIQ is a telemetry recorder and lap analysis tool for Gran Turismo 7.
GT7 on PlayStation broadcasts UDP telemetry at ~60 Hz; TelemetryIQ records
full telemetry per lap to SQLite and enables lap-over-lap comparison — modelled
on professional motorsport tools (MoTeC i2, AiM Race Studio) and the official
[GT7 Data Logger](https://www.gran-turismo.com/us/news/00_5736734.html).

**Last updated:** 2026-04-26

### Core Use Cases

The GT7 Data Logger article defines two primary analysis workflows. These are
the north star for TelemetryIQ.

#### 1. Compare and Improve Driving Techniques

**Scenario:** Same car, same settings, different laps (or different drivers).
**Question:** "Where am I losing time?"

- **Speed + Gap graph**: where time is gained/lost per corner
- **Driving line overlay**: braking points, apex proximity, corner exit
- **Throttle/Brake traces**: coasting (neither accelerating nor braking),
  late/early braking, hesitant throttle application
- **Lateral G**: cornering commitment and consistency

> *Article example:* Slower driver braked earlier at Tsukuba Turn 1, lost
> speed at corner entry, relied on momentum through apex. Faster driver braked
> later, hit slightly lower minimum speed, but got on throttle earlier — gained
> 0.5s by corner exit. Key insight: "braking later and reducing the amount of
> time spent coasting."

**Status:** Fully supported via `/compare`.

#### 2. Compare and Improve Car Settings

**Scenario:** Same driver, same track, different car setup.
**Question:** "Did this setup change help?"

- Compare laps before/after a setup change (e.g. front downforce, tire type)
- Look for: understeer reduction, earlier throttle application, cleaner
  cornering, tighter driving line
- Speed + Gap graph shows net effect per corner

> *Article example:* Increasing front downforce allowed later braking, cleaner
> turn-in without understeer, earlier throttle — 0.3s improvement.

**Status:** Complete. Session notes let the user record what they changed.
Gear ratio, top speed, and max speed changes auto-detected between sessions.

### Positioning vs. the In-Game Data Logger

GT7's Spec III Data Logger inspired TelemetryIQ and shares its two analysis
workflows. TelemetryIQ is not a replacement — it is what you reach for when
the in-game tool runs out of room.

| Capability | GT7 Data Logger | TelemetryIQ |
| --- | --- | --- |
| Lap overlay | Two laps | N laps |
| Where viewable | TV / console only | Any LAN device (phone, tablet, laptop) |
| Persistent history | Tied to game session | SQLite across all sessions, indefinitely |
| Setup change tracking | Implicit via stored setups | Free-text notes + auto-detected gear ratio / top speed diffs |
| Live HUD while driving | On-screen | LAN-accessible WebSocket HUD on any device |
| Cross-session filtering | N/A | Track/car filters in the session browser |
| Data export | None documented | SQLite, plus planned export (Phase 6) |

What GT7 has that TelemetryIQ does not: replay download from online rankings.
This is the one workflow where the in-game tool wins outright — TelemetryIQ
has no access to other players' telemetry.

---

## Domain Model

The data model follows motorsport industry conventions.

### Session

A single track visit. Created when the driver enters a track (`on_at_track`)
or starts a race (`on_in_race`); closed when they return to the menu
(`on_in_game_menu`) or the race ends (`on_race_end`).

| Field | Type | Source |
| --- | --- | --- |
| `id` | integer (PK) | auto |
| `started_at` | real (epoch) | server clock |
| `completed_at` | real (epoch) | server clock (on close) |
| `track_id` | integer | `on_track_detected` event |
| `car_code` | integer | first complete lap's telemetry |

### Lap

One lap within a session. Created when a lap begins; completed when the next
lap starts (`on_lap_change`). Lap 0 is the formation/out lap and is excluded
from analysis UI.

| Field | Type | Source |
| --- | --- | --- |
| `id` | integer (PK) | auto |
| `session_id` | integer (FK) | owning session |
| `lap_number` | integer | `on_lap_change` event |
| `track_id` | integer | session's track_id |
| `started_at` | real (epoch) | server clock |
| `completed_at` | real (epoch) | server clock (on next lap) |
| `lap_time_ms` | integer | `last_lap_time_ms` from telemetry |
| `car_code` | integer | first frame's `car_code` |
| `is_complete` | integer (0/1) | 1 if lap ended normally |

### Frame

A single telemetry sample (~60 per second). Stored per lap, ordered by `seq`.

| Field | Type | Source |
| --- | --- | --- |
| `lap_id` | integer (FK) | owning lap |
| `seq` | integer | sequential counter per lap |
| `ts` | real (epoch) | server clock at frame receipt |
| All telemetry fields | various | gt-telem (see Telemetry Reference) |

### Channels (Trace Data)

Standard motorsport analysis set used in the overlay view:

| Channel | Field(s) | Unit | Notes |
| --- | --- | --- | --- |
| Speed | `speed_mps * 3.6` | km/h | |
| Throttle | `throttle / 255 * 100` | % | |
| Brake | `brake / 255 * 100` | % | |
| Gear | `current_gear` | — | |
| Lateral G | `sway` | m/s² | Heartbeat B only — lateral body acceleration; charted as the lateral-G channel |
| Steering | `wheel_rotation_radians` | rad | Heartbeat B only |
| Time delta | computed | s | N-lap: one trace per non-baseline lap, vs the baseline lap |

### Derived Data

| Field | Formula | Notes |
| --- | --- | --- |
| `distance_m` | `d[i] = d[i-1] + speed_mps[i] * dt` | Computed server-side per frame. `dt = ts[i] - ts[i-1]`. Frames with `dt > 0.1s` contribute zero distance (pause/menu). |
| Time delta | Interpolate both laps onto shared distance grid; delta = cumulative time difference at each point | Positive = faster lap ahead |

### Overlay (Comparison)

Selecting two laps renders them as an overlay: all channel charts share a
distance-based x-axis with a synchronized crosshair, plus a time delta trace
and a two-color track map.

### Static Lookup Data

| File | Content | Source | Count |
| --- | --- | --- | --- |
| `rexy/static/cars.json` | `car_code` → car name | [gran-turismo.com/carlist](https://www.gran-turismo.com/us/gt7/carlist/) | 559 |
| `rexy/static/tracks.json` | `track_id` → track name | [gran-turismo.com/tracklist](https://www.gran-turismo.com/us/gt7/tracklist/) + gt-telem | 106 |

See `AGENTS.md` for refresh instructions when GT7 adds new cars/tracks.

### Setup Notes

Free-text notes per session enabling the "Compare Car Settings" use case.
The driver records what they changed (e.g. "front DF +5, softer rear springs")
after each garage visit. Notes appear in the session browser and in the
comparison view header when overlaying laps from different sessions.

| Field | Type | Source |
| --- | --- | --- |
| `sessions.notes` | text (nullable) | User input via UI |

Design rationale: GT7 does not export setup files — there is no API or file
to read car settings programmatically. Manual free-text is the only reliable
option. One field covers 90% of the value; structured fields (dropdown per
setting category) can be added later if usage warrants it.

Automatic detection: gear ratios (`gear1`–`gear8`) are in telemetry and can
be compared across sessions without user input. Flag gear ratio changes
automatically in the comparison view.

---

## Architecture

### Data Flow

```text
PlayStation (GT7, ~60 Hz UDP)
        |
        v
  TurismoClient (gt-telem)
  callback-driven: telemetry frames + game/race/driver events
        |
        +---> asyncio.Queue (maxsize=1, drop-oldest)
        |         |
        |         v
        |     FastAPI broadcaster loop
        |     fans out JSON to all WebSocket clients
        |         | WebSocket /ws (JSON)
        |         v
        |     Browser --- index.html (live HUD)
        |
        +---> LapRecorder
              buffers frames; flushes to SQLite on lap change
              manages session lifecycle (open/close)
                  |
                  v
              SQLite (telemetry.db)
                  ^
                  |
              REST API (read-only queries)
                  | GET /sessions, /sessions/{id}/laps,
                  | /laps, /laps/{car}/{lap}/{id}/frames
                  v
              Browser --- compare.html (analysis dashboard)
```

### Components

| Component | File | Responsibility |
| --- | --- | --- |
| Telemetry client | `rexy/client.py` | Wraps `TurismoClient`; sync callbacks dispatch to asyncio via `call_soon_threadsafe`; pushes frames to queue; logs all gt-telem events to stdout |
| Dispatcher | `rexy/dispatcher.py` | Drains raw_queue; drop-oldest into ws_queue; calls `LapRecorder.on_frame()` |
| FastAPI server | `rexy/server.py` | WebSocket `/ws`; broadcaster loop; REST API; serves static files |
| Lap recorder | `rexy/recorder.py` | Session lifecycle (`start_session`/`close_session`); lap lifecycle (`reset_and_new_lap`/`flush_and_new_lap`); buffers frames; flushes to SQLite |
| Repository | `rexy/repository.py` | SQLite access; schema DDL with `user_version` migration (v3); CRUD for sessions, laps, frames |
| Live HUD | `rexy/static/index.html` | All telemetry fields; WS reconnect with exponential backoff; post-lap Chart.js overlay |
| Analysis dashboard | `rexy/static/compare.html` | Session browser sidebar; distance-based trace charts; time delta; track map; synchronized crosshair |
| Static data | `rexy/static/cars.json`, `tracks.json` | Car/track name lookups |
| Entrypoint | `rexy/__main__.py` | Wires client + server + recorder; graceful shutdown |

### REST API

| Method | Path | Returns |
| --- | --- | --- |
| `GET` | `/sessions` | `[{id, started_at, completed_at, track_id, car_code, notes, lap_count, best_lap_time_ms}]` |
| `GET` | `/sessions/{id}/laps` | `[{id, lap_number, lap_time_ms}]` — complete laps, `lap_number > 0` |
| `GET` | `/laps` | `[{id, lap_number, lap_time_ms, car_code, started_at}]` |
| `GET` | `/laps/{car_code}/{lap_number}/{lap_id}/frames` | `[{seq, ...all fields..., distance_m}]` |
| `PATCH` | `/sessions/{id}` | Update session notes. Body: `{"notes": "..."}`. Returns `{"ok": true}` or 404/422. |

### Rendering Stack

| Concern | Approach |
| --- | --- |
| Trace charts | [Chart.js](https://www.chartjs.org/) via CDN — Canvas, 5K+ points, zoom/pan |
| Synchronized crosshair | Shared `mousemove` handler updating all chart instances |
| Track map | Raw Canvas API — `position_x` vs `position_z`, color-coded by speed |
| UI state | Vanilla JS — single `state` object |

No npm, no build step. All dependencies loaded from CDN.

### Schema Migrations

SQLite `user_version` PRAGMA tracks the schema version. On startup:

| Version | Action |
| --- | --- |
| 0 | Fresh install: create all tables at current schema, set `user_version = 3` |
| 1 | Migrate: `ALTER TABLE sessions ADD COLUMN track_id/car_code/completed_at/notes`, set `user_version = 3` |
| 2 | Migrate: `ALTER TABLE sessions ADD COLUMN notes TEXT`, set `user_version = 3` |
| 3 | Current — no-op |

---

## Constraints

### In Scope

- GT7 telemetry ingestion via gt-telem on the same LAN as PlayStation
- Real-time WebSocket broadcast of all telemetry fields
- Lap recording to SQLite with session grouping
- Lap comparison with distance-based charts, delta graph, track map
- Heartbeat type configurable (`A` / `B` / `~`) via environment variable
- Single-page dashboards served by FastAPI (no separate web server)
- Accessible from any device on the LAN (phone, tablet, laptop)
- No external services — single Python process + SQLite

### Out of Scope

- Authentication / access control
- Multiple simultaneous GT7 sources
- Native desktop app
- `./lib` directory

### Assumptions

- PlayStation and host are on the same LAN subnet
- `PS_IP` set if auto-discovery doesn't work
- `GT7_HEARTBEAT_TYPE=B` default (standard + motion); switch to `~` for
  energy recovery (hybrid/EV cars)

### Platform Notes

Runs on any platform with Python 3.10+ and LAN access to the PlayStation.
`make install && make run` is all you need. Run `make help` for options.

---

## Decisions

Non-obvious design choices and why they were made.

| Decision | Why | Alternatives rejected |
| --- | --- | --- |
| `maxsize=1` queue (drop-oldest) | At ~60 Hz, freshness > completeness for live display | Unbounded queue (memory leak), larger buffer (stale frames) |
| Server-side `lap_started_at` | Lap timer must survive browser sleep/wake reconnects | Client-side timer (resets on reconnect), game timer (GT7 doesn't broadcast running lap time) |
| `set_track_id()` stays sync | Called via `call_soon_threadsafe` from gt-telem thread | Async method (breaks `call_soon_threadsafe` pattern) |
| `sys.exit(0)` after `asyncio.run()` | gt-telem spawns non-daemon threads that prevent clean exit | `tc.stop()` alone (blocks), daemon threads (not our code) |
| Sessions as first-class DB entities | Own car/track identity; deriving from laps loses boundary info | Derive from laps (anti-pattern) |
| Static `cars.json` / `tracks.json` | No runtime network calls, no CORS, works offline | Fetch from GT7 website at runtime (CORS, fragile) |
| `user_version` PRAGMA for migrations | SQLite built-in, no external tool needed | Alembic (overkill), migration table (reinventing) |
| Distance from wall-clock `ts` | GT7 doesn't broadcast lap elapsed time; server `ts` at ~60 Hz is accurate to one frame interval | Game-provided timer (doesn't exist in telemetry) |

---

## Critical Implementation Patterns

Non-obvious patterns the codebase depends on. Touch these only with care.

### gt-telem callback threading

gt-telem runs async callbacks via a fresh `asyncio.new_event_loop()` per
call in a thread pool — **not** on the application's event loop. The app
uses sync callbacks only and dispatches back to the captured app loop via
`call_soon_threadsafe`:

- `loop = asyncio.get_running_loop()` is captured at startup in `client.py`.
- Frame data: `loop.call_soon_threadsafe(raw_queue.put_nowait, frame)`.
- Lifecycle tasks: `loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))`.
- Sync state updates: `loop.call_soon_threadsafe(recorder.set_track_id, tid)`.

`GameEvents` and `RaceEvents` declare their event lists (`on_at_track`,
`on_lap_change`, etc.) as **class attributes**, so all instances share the
same list. Create exactly one `GameEvents` and one `RaceEvents` per session
to avoid duplicate callback registrations.

`on_lap_change` passes only `new_lap_number: int` — `lap_time_ms` is NOT
provided. `flush_and_new_lap` derives it from `buf[-1]["last_lap_time_ms"]`,
which is reliable: `last_lap_time_ms` is present on every frame and remains
the most recently completed lap throughout the next lap.

### Buffer-before-await invariant

Every `LapRecorder` method that reads `lap_buffer` and then awaits MUST
capture the buffer contents and clear `self.lap_buffer = []` BEFORE the
first `await`. Otherwise, frames received during the await for the new lap
get appended to the old lap's buffer.

```python
# CORRECT
buf = self.lap_buffer
self.lap_buffer = []   # ← BEFORE any await
await repo.insert_frames(old_id, buf)
```

`on_frame()` is synchronous and only appends between awaits, so clearing
first is sufficient.

### Race-restart path

If `reset_and_new_lap()` is called while RECORDING (e.g. `on_at_track`
during a race restart), it flushes the partial lap inline (writes frames,
marks `is_complete=0`) before opening the new lap.

### Lap-time `-1` sentinel

GT7 telemetry uses `-1` for `last_lap_time_ms` and `best_lap_time_ms` when
no valid lap time exists yet. Both are normalized to NULL on insert
(`None if raw == -1 else raw`). The frontend renders missing values as
`--:--.---`.

### SQLite persistence

`TelemetryRepository` holds a **persistent aiosqlite connection** opened
in `init()` and closed in `close()`. `async with aiosqlite.connect(...)`
would drop the connection after `init()` returns and break every
subsequent query.

`PRAGMA journal_mode=WAL` is set during `init()` so the FastAPI read path
doesn't block the writer.

`PRAGMA user_version` is **non-transactional**: set it AFTER the DDL
`commit()` for fresh installs and migrations. Setting it before commit
risks `version=N` persisting while DDL fails, causing silent skip on the
next startup with missing tables.

Indexes:

- `idx_laps_is_complete` — filter complete laps.
- `idx_laps_complete_track(is_complete, track_id, lap_time_ms)` —
  "best laps on track" comparison query.

### Queue sizing

`raw_queue` is **unbounded**: the dispatcher does only in-memory work
(no I/O, no `await` except `queue.get()`). Depth normally stays at 0–2.
Growth above a few frames indicates a scheduler stall.

`ws_queue` has `maxsize=1` with drop-oldest: at ~60 Hz, a slow WS client
must not back-pressure the recording path.

### Telemetry serialization

`Telemetry.as_dict` (gt-telem) is a `@property` that returns nested
`Vector3D` / `WheelMetric` objects and strips the flat per-axis /
per-corner fields. It's unsuitable for JSON or SQLite. `client.py`
provides a custom `telemetry_to_dict()` that:

- Reads all flat dataclass attributes directly.
- Decodes `current_gear = bits & 0b1111`, `suggested_gear = bits >> 4`.
- Decodes flag booleans from `flags` (TCS active, ASM active, cars on
  track, paused, in gear, rev limit, handbrake).
- Excludes `iv` (encryption IV), `empty`, `unused1`–`unused8`,
  `unk_tilde_*`, and `time` (the Python `datetime` added in
  `__post_init__`).

### `g_lateral` is not in the payload

There is no G-force field in gt-telem. Lateral motion is `sway`
(m/s², body acceleration) — heartbeat B only. The Channels table charts
`sway` as the lateral-G channel; on heartbeat A there is no lateral-G
display.

### Shutdown sequence

`__main__.py` cancels the dispatcher and broadcaster tasks, then awaits
`recorder.close()` (which flushes any partial lap as `is_complete=0`) and
`repo.close()`. After `asyncio.run()` returns, `sys.exit(0)` is required
because gt-telem spawns non-daemon threads that block process exit (also
recorded in Decisions).

`recorder.close()` and any in-flight `flush_and_new_lap()` may interleave
at await points but never double-write — the buffer-before-await pattern
guarantees one of them sees an empty buffer. An orphan lap row
(`is_complete=0`, no frames) is acceptable and filtered out by
`is_complete=1` queries.

### Auto-diff field rules

The `/compare` auto-diff banner reads the **first frame** of each lap
(these fields are constant per car setup). Compared fields:

| Field | Display | Notes |
| --- | --- | --- |
| `gear1`–`gear8` | `"G3: 1.355 → 1.290"` | Skip pairs where both are 0 (unused gears); round to 3 decimals |
| `trans_top_speed` | `"Top speed setting: 320 → 340"` | Rounded to integer |
| `calc_max_speed` | `"Calc max speed: 280 → 295"` | Rounded to integer |

The banner only shows when laps are from **different sessions** (same
session = same setup) and at least one field differs.

### Static lookup fallbacks

If `cars.json` lacks a `car_code`, the UI displays `"Car {code}"`. If
`tracks.json` lacks a `track_id`, it displays `"Track {id}"`. Both files
may be committed as `{}` initially without blocking implementation; see
`AGENTS.md` for refresh instructions.

### HUD field exclusions

The live HUD intentionally hides:

- `clutch_pedal` and `clutch_engagement` — most GT7 racing uses automatic
  transmission; these aren't actionable.
- `suggested_gear` when the value is `≥ 15` or falsy — GT7's "no
  suggestion" sentinel; render `--` instead.

### Error handling outcomes

| Scenario | Outcome |
| --- | --- |
| Mid-lap process crash | Buffer lost; lap row stays `is_complete=0`. |
| Clean shutdown (SIGTERM / Ctrl-C) | Tasks cancelled; partial lap flushed with `is_complete=0`. |
| Race restart while recording | `reset_and_new_lap()` flushes partial inline (buffer-before-await). |
| SQLite write failure | Error logged; buffer already cleared; lap row stays `is_complete=0`; no retry. |
| WebSocket client disconnect | Removed from `clients` set in `/ws` handler `finally`. |
| Slow WebSocket client | `asyncio.gather` isolates per-client sends. |
| `on_lap_change` before recording started | `flush_and_new_lap` is a no-op in the IDLE state. |
| `on_track_detected` after first lap starts | `current_track_id` is None for that lap; subsequent laps populated correctly. |
| Lap counter jumps after laptop sleep | Lap numbers may skip; data for skipped laps is lost (see Known Issues). |

---

## Known Issues

| Issue | Impact | Notes |
| --- | --- | --- |
| Lap counter jumps after laptop sleep | Lap numbers may skip (e.g. 2 -> 6) | GT7 continues counting during sleep; first `on_lap_change` after wake reports current GT7 lap. Data for skipped laps is lost. |
| gt-telem non-daemon threads | App hangs on Ctrl-C without `sys.exit(0)` | Mitigated by `sys.exit(0)` after `asyncio.run()`; `tc.stop()` in executor with 3s timeout. |

---

## Roadmap

| Phase | What | Status |
| --- | --- | --- |
| 1 | Telemetry connection, packaging | Done |
| 2 | Lap recording to SQLite; live HUD | Done |
| 3 | Analysis dashboard: trace charts, delta, track map | Done |
| 4 | Sessions with car/track identity; session browser UI | Done |
| 5 | Setup comparison: auto-diff, session notes, filtering | Done |
| 6 | Lap data export | Planned |
| 7 | GT7-aligned compare view: 3 tabs (Driving Line / Inputs / Powertrain) | Done |

---

## Phase 7 Design — GT7-Aligned Compare View

### Goal

Restructure `/compare` to mirror the three-view organization of GT7's Spec III
in-game Data Logger. Adopt the shape of GT7's analysis flow while keeping
TelemetryIQ-specific extras (N-lap overlay, steering/gear traces, session
notes, cross-session filtering).

### Three Tabs

`/compare` becomes three tabs. The selected tab is persisted in the URL hash
(`#tab=line | inputs | powertrain`) so links are shareable. Default on load:
`line`.

**Tab 1 — Driving Line** *(GT7 View 1: speed/gap + driving line)*

| Element | Notes |
| --- | --- |
| Track map | Color-coded by speed; existing implementation |
| Speed trace | Distance-based x-axis |
| Time delta trace | N-lap mode: one line per non-baseline lap, computed against the baseline. Existing behavior, preserved |

Layout:

- Desktop (≥1024px): track map on the left, speed + delta stacked on the right.
- Narrow (<1024px): track map, speed, delta stacked vertically.

**Tab 2 — Inputs** *(GT7 View 2: throttle/brake + lateral G)*

| Element | Notes |
| --- | --- |
| Throttle trace | |
| Brake trace | |
| Lateral G trace | |
| Steering trace | Heartbeat B only; hidden when unavailable |

Layout: stacked traces, full width.

**Tab 3 — Powertrain** *(GT7 View 3: speed + RPM)*

| Element | Notes |
| --- | --- |
| Speed trace | Same channel as Tab 1; included here as the universal reference, mirroring GT7 |
| RPM trace | |
| Gear trace | Stepped trace; same width as RPM, half the height |

Layout: stacked traces, full width.

### Components Outside Tabs

Session browser, lap pickers, auto-diff banner, session notes, track/car
filters, and the synchronized crosshair stay outside the tab area and apply
to whichever tab is active. Switching tabs does not reset lap selection or
crosshair position.

### Naming

Tab names are descriptive ("Driving Line", "Inputs", "Powertrain") rather
than GT7's literal "View 1/2/3". The descriptive form is self-explanatory
and matches the way GT7's own announcement article describes each view.

### Out of Scope (Phase 7)

- Replay download from online rankings — GT7 closed system; no public API.
- Stored setup snapshots tied to laps — no telemetry source for car settings;
  free-text session notes remain the workaround.
- Mobile portrait optimization beyond vertical stacking.
- Tab keyboard shortcuts.

### Follow-up — Phase 7b

After Phase 7 lands, soften the "Positioning vs. the In-Game Data Logger"
subsection above. Reframe it as "Relationship to the GT7 Data Logger",
emphasizing TelemetryIQ as a faithful extension rather than an alternative.
The current differentiation table becomes an "extends" table.

---

## Telemetry Reference

### Heartbeat A — standard (all types include these)

| Field | Description |
| --- | --- |
| `speed_mps` | Speed in m/s |
| `engine_rpm` | Engine RPM |
| `current_gear` / `suggested_gear` | Current and suggested gear (from `bits`) |
| `throttle` | Throttle input (raw, 0-255) |
| `brake` | Brake input (raw, 0-255) |
| `clutch_pedal` / `clutch_engagement` | Clutch position and engagement |
| `boost_pressure` | Turbo boost pressure |
| `fuel_level` / `fuel_capacity` | Fuel level and capacity |
| `oil_pressure` / `oil_temp` | Oil pressure and temperature |
| `water_temp` | Water temperature |
| `tire_fl/fr/rl/rr_temp` | Tire surface temperatures |
| `tire_fl/fr/rl/rr_sus_height` | Suspension heights per corner |
| `tire_fl/fr/rl/rr_radius` | Tire radii per corner |
| `wheel_fl/fr/rl/rr_rps` | Wheel rotations per second |
| `current_lap` / `total_laps` | Lap counter |
| `best_lap_time_ms` / `last_lap_time_ms` | Lap times in ms |
| `position_x/y/z` | 3D position on track |
| `velocity_x/y/z` | Velocity vector |
| `ang_vel_x/y/z` | Angular velocity |
| `rotation_x/y/z` | Vehicle rotation |
| `road_plane_x/y/z/dist` | Road surface normal + distance |
| `body_height` / `orientation` | Body height and heading |
| `min_alert_rpm` / `max_alert_rpm` | Shift light RPM range |
| `car_code` | Car identifier (maps to `cars.json`) |
| `calc_max_speed` | Calculated top speed |
| `trans_rpm` / `trans_top_speed` | Transmission data |
| `gear1`-`gear8` | Gear ratios |
| `flags` | TCS active, ASM active, cars on track, paused, in gear, rev limit, handbrake |

### Heartbeat B — adds motion data

| Field | Description |
| --- | --- |
| `wheel_rotation_radians` | Steering wheel input |
| `filler_float_fb` | Lateral slip angle (approx.) |
| `sway` | Lateral body motion |
| `heave` | Vertical body motion |
| `surge` | Longitudinal body motion |

### Heartbeat ~ — adds filtered inputs + energy recovery

| Field | Description |
| --- | --- |
| `throttle_filtered` | Smoothed throttle input |
| `brake_filtered` | Smoothed brake input |
| `energy_recovery` | Regenerative braking value (hybrid/EV) |

### Events (gt-telem callbacks)

| Category | Events | Used by TelemetryIQ |
| --- | --- | --- |
| Game | `on_running`, `on_paused`, `on_at_track`, `on_in_game_menu`, `on_in_race`, `on_race_end` | All: logged to stdout; `on_at_track`/`on_in_race` open session; `on_in_game_menu`/`on_race_end` close session |
| Race | `on_race_start`, `on_race_finish`, `on_lap_change`, `on_track_detected` | `on_lap_change` flushes lap; `on_track_detected` sets session track_id |
| Race (unused) | `on_best_lap_time`, `on_last_lap_time` | Available but not wired |
| Driver (unused) | `on_gear_change`, `on_flash_lights`, `on_handbrake`, `on_suggested_gear`, `on_tcs`, `on_asm`, `on_rev_limit`, `on_brake`, `on_throttle`, `on_shift_light_low`, `on_shift_light_high` | Available but not wired |

---

## References

- [GT7 Data Logger article](https://www.gran-turismo.com/us/news/00_5736734.html)
  — **north star** for analysis dashboard design
- [GT7 Car List (official)](https://www.gran-turismo.com/us/gt7/carlist/)
  — source for `cars.json`
- [GT7 Track List (official)](https://www.gran-turismo.com/us/gt7/tracklist/)
  — source for `tracks.json`
- [gt-telem on PyPI](https://pypi.org/project/gt-telem/)
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/)
