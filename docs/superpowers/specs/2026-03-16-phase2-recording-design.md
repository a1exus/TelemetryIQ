# Phase 2 Design: Lap Recording + Live View

**Date:** 2026-03-16
**Status:** Approved
**Phase:** 2 — Recording

---

## Overview

Phase 2 adds two capabilities to the Phase 1 foundation:

1. **Lap recording** — persist full telemetry per completed lap to SQLite
2. **Live view** — broadcast all telemetry fields over WebSocket at ~60Hz

---

## Architecture

### Queues

| Queue | Type | Purpose |
| --- | --- | --- |
| `raw_queue` | `asyncio.Queue()` — unbounded | Receives every frame from the telemetry callback |
| `ws_queue` | `asyncio.Queue(maxsize=1)` — drop-oldest | Holds the single freshest frame for the WebSocket broadcaster |

`raw_queue` is unbounded because the dispatcher does only in-memory work (no I/O,
no `await` except `queue.get()`). Under normal operation, queue depth stays at 0–2
frames. Growth above a few frames indicates a scheduler stall.

### Data flow

```text
TurismoClient (gt-telem)
    │
    ├── on_frame_handler (sync; runs in gt-telem callback thread)
    │       → frame = telemetry_to_dict(t)   ← custom flat serializer; no as_dict
    │       → frame["ts"] = time.time()
    │       → frame["heartbeat_type"] = env GT7_HEARTBEAT_TYPE
    │       → loop.call_soon_threadsafe(raw_queue.put_nowait, frame)
    │           registered via: tc.register_callback(on_frame_handler)
    │
    ├── GameEvents(tc)  → registers its own _state_tracker with tc internally
    │       on_at_track_handler (sync; no args)  ← fires in TT/practice (cars_on_track=False)
    │           → loop.call_soon_threadsafe(
    │                 lambda: asyncio.create_task(recorder.reset_and_new_lap(1))
    │             )
    │       on_in_race_handler (sync; no args)   ← fires in races (cars_on_track=True, current_lap=0)
    │           → loop.call_soon_threadsafe(
    │                 lambda: asyncio.create_task(recorder.reset_and_new_lap(0))
    │             )
    │               ← lap_number=0 matches current_lap at race start; on_lap_change(1) flushes it
    │               ← on_at_track and on_in_race are mutually exclusive in normal operation
    │       on_race_end_handler (sync; no args)
    │           → loop.call_soon_threadsafe(
    │                 lambda: asyncio.create_task(recorder.close())
    │             )
    │           registered via: game_events.on_at_track.append(on_at_track_handler)
    │                           game_events.on_in_race.append(on_in_race_handler)
    │                           game_events.on_race_end.append(on_race_end_handler)
    │                           game_events.on_in_game_menu.append(on_race_end_handler)
    │
    └── RaceEvents(tc)  → registers its own _state_tracker with tc internally
            on_lap_change_handler (sync; receives new_lap_number: int)
                → loop.call_soon_threadsafe(
                      lambda n=new_lap_number: asyncio.create_task(
                          recorder.flush_and_new_lap(n)
                      )
                  )
                      ← lap_time_ms derived inside flush_and_new_lap from
                        buf[-1]["last_lap_time_ms"] (always present; int from t.last_lap_time_ms)
                registered via: race_events.on_lap_change.append(on_lap_change_handler)

dispatcher task (no I/O; only awaits raw_queue.get())
    └── for each frame:
            ├── try ws_queue.put_nowait(frame)
            │   except QueueFull: ws_queue.get_nowait(); ws_queue.put_nowait(frame)
            │   ← get_nowait() does not yield; safe in single-writer asyncio loop
            └── LapRecorder.on_frame(frame)   ← sync; no await

FastAPI
    ├── GET /     → serves index.html
    └── WS  /ws   → broadcaster task fans out ws_queue frames to connected clients
```

### gt-telem callback threading model (verified from source)

**Critical**: gt-telem runs async callbacks via `asyncio.new_event_loop()` per call in
a thread pool — NOT on the application's event loop:

```python
# turismo_client.py
def _run_async_callback(self, callback, telemetry_value, args):
    loop = asyncio.new_event_loop()   # ← new loop per invocation, NOT the app loop
    asyncio.set_event_loop(loop)
    loop.run_until_complete(callback(telemetry_value))
    loop.close()
```

Phase 2 uses **sync callbacks only** for `on_frame_handler` and all lifecycle handlers
(`on_at_track_handler`, `on_race_end_handler`, `on_lap_change_handler`). Sync callbacks
are called directly from the gt-telem callback thread without a new event loop.

All communication back to the app event loop goes through `call_soon_threadsafe`:

- Frame data: `loop.call_soon_threadsafe(raw_queue.put_nowait, frame)`
- Lifecycle tasks: `loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))`

`client.py` captures the running event loop at startup (`loop = asyncio.get_running_loop()`)
and closes over it in all callback closures.

**`GameEvents` and `RaceEvents` API (verified from source)**:

Both classes take `TurismoClient` as their constructor argument and self-register
their own async `_state_tracker` callback with `TurismoClient.register_callback()`.
User code appends callables to the class-level lists (`on_at_track`, `on_lap_change`, etc.),
which `_state_tracker` invokes on each relevant frame:

```python
tc = TurismoClient(ps_ip, heartbeat_type=heartbeat_type)
game_events = GameEvents(tc)   # internally calls tc.register_callback(GameEvents._state_tracker, ...)
race_events = RaceEvents(tc)   # internally calls tc.register_callback(RaceEvents._state_tracker, ...)

game_events.on_at_track.append(on_at_track_handler)
game_events.on_in_race.append(on_in_race_handler)
game_events.on_race_end.append(on_race_end_handler)
game_events.on_in_game_menu.append(on_race_end_handler)  # menu exit = close recording
race_events.on_lap_change.append(on_lap_change_handler)
tc.register_callback(on_frame_handler)  # raw frames; separate from GameEvents/RaceEvents
```

**Class-level list bug (verified from source)**:

`on_at_track`, `on_lap_change`, and all other event lists are declared as class attributes
on `GameEvents` and `RaceEvents`. This means all instances share the same list. Always
create exactly one `GameEvents` instance and one `RaceEvents` instance per session to
avoid duplicate callback registrations.

**`on_lap_change` callback signature (verified from source)**:

```python
# race_events.py
await invoke_callbacks(self.on_lap_change, t.current_lap)
```

Only `new_lap_number: int` is passed. `lap_time_ms` is NOT available from the event;
it is derived inside `flush_and_new_lap` from `buf[-1]["last_lap_time_ms"]`. This is
reliable: `last_lap_time_ms` is a raw int field present on every telemetry frame and
remains set to the most recently completed lap's time throughout the new lap.

**`telemetry_to_dict` — custom flat serializer (replaces `as_dict`)**:

`Telemetry.as_dict` is a `@property` (not a method call) that returns nested objects
(`Vector3D`, `WheelMetric`) and strips flat per-axis and per-corner fields. It is
unsuitable for JSON serialization or SQLite storage.

`client.py` implements `telemetry_to_dict(t: Telemetry) -> dict` that reads all flat
attributes directly from the `Telemetry` dataclass and adds explicitly decoded fields:

```python
def telemetry_to_dict(t: Telemetry) -> dict:
    return {
        "packet_id": t.packet_id,
        "speed_mps": t.speed_mps, "engine_rpm": t.engine_rpm,
        "current_gear": t.bits & 0b1111,  # decoded from bits
        "suggested_gear": t.bits >> 4,    # decoded from bits
        "throttle": t.throttle, "brake": t.brake,
        "clutch_pedal": t.clutch_pedal, "clutch_engagement": t.clutch_engagement,
        "boost_pressure": t.boost_pressure,
        "fuel_level": t.fuel_level, "fuel_capacity": t.fuel_capacity,
        "oil_pressure": t.oil_pressure, "oil_temp": t.oil_temp, "water_temp": t.water_temp,
        "tire_fl_temp": t.tire_fl_temp, "tire_fr_temp": t.tire_fr_temp,
        "tire_rl_temp": t.tire_rl_temp, "tire_rr_temp": t.tire_rr_temp,
        "tire_fl_sus_height": t.tire_fl_sus_height, "tire_fr_sus_height": t.tire_fr_sus_height,
        "tire_rl_sus_height": t.tire_rl_sus_height, "tire_rr_sus_height": t.tire_rr_sus_height,
        "tire_fl_radius": t.tire_fl_radius, "tire_fr_radius": t.tire_fr_radius,
        "tire_rl_radius": t.tire_rl_radius, "tire_rr_radius": t.tire_rr_radius,
        "wheel_fl_rps": t.wheel_fl_rps, "wheel_fr_rps": t.wheel_fr_rps,
        "wheel_rl_rps": t.wheel_rl_rps, "wheel_rr_rps": t.wheel_rr_rps,
        "current_lap": t.current_lap, "total_laps": t.total_laps,
        "best_lap_time_ms": t.best_lap_time_ms, "last_lap_time_ms": t.last_lap_time_ms,
        "time_of_day_ms": t.time_of_day_ms, "race_start_pos": t.race_start_pos,
        "total_cars": t.total_cars,
        "position_x": t.position_x, "position_y": t.position_y, "position_z": t.position_z,
        "velocity_x": t.velocity_x, "velocity_y": t.velocity_y, "velocity_z": t.velocity_z,
        "ang_vel_x": t.ang_vel_x, "ang_vel_y": t.ang_vel_y, "ang_vel_z": t.ang_vel_z,
        "rotation_x": t.rotation_x, "rotation_y": t.rotation_y, "rotation_z": t.rotation_z,
        "road_plane_x": t.road_plane_x, "road_plane_y": t.road_plane_y,
        "road_plane_z": t.road_plane_z, "road_plane_dist": t.road_plane_dist,
        "body_height": t.body_height, "orientation": t.orientation,
        "min_alert_rpm": t.min_alert_rpm, "max_alert_rpm": t.max_alert_rpm,
        "calc_max_speed": t.calc_max_speed,
        "trans_rpm": t.trans_rpm, "trans_top_speed": t.trans_top_speed,
        "gear1": t.gear1, "gear2": t.gear2, "gear3": t.gear3, "gear4": t.gear4,
        "gear5": t.gear5, "gear6": t.gear6, "gear7": t.gear7, "gear8": t.gear8,
        "car_code": t.car_code,
        # Decoded flags (from t.flags via Telemetry properties)
        "tcs_active": bool(t.flags & (1 << 11)),
        "asm_active": bool(t.flags & (1 << 10)),
        "cars_on_track": bool(t.flags & (1 << 0)),
        "is_paused": bool(t.flags & (1 << 1)),
        "in_gear": bool(t.flags & (1 << 3)),
        "rev_limit": bool(t.flags & (1 << 5)),
        "hand_brake_active": bool(t.flags & (1 << 6)),
        # Heartbeat B only — None for A and ~
        "wheel_rotation_radians": getattr(t, "wheel_rotation_radians", None),
        "filler_float_fb": getattr(t, "filler_float_fb", None),
        "sway": getattr(t, "sway", None),
        "heave": getattr(t, "heave", None),
        "surge": getattr(t, "surge", None),
        # Heartbeat ~ only — None for A and B
        "throttle_filtered": getattr(t, "throttle_filtered", None),
        "brake_filtered": getattr(t, "brake_filtered", None),
        "energy_recovery": getattr(t, "energy_recovery", None),
    }
```

Fields excluded: `iv` (encryption IV), `empty`, `unused1`–`unused8`, `unk_tilde_1/2/3`
(unknowns), `time` (Python `datetime` added in `__post_init__`, not GT7 data).

### Buffer safety — clear before await

`flush_and_new_lap` and similar methods must capture `lap_buffer` contents and clear
the buffer **before** the first `await`. This is the critical invariant:

```python
# CORRECT — buffer cleared before I/O
buf = self.lap_buffer
car = buf[0]["car_code"] if buf else None
lap_time_ms = buf[-1]["last_lap_time_ms"] if buf else None
old_id = self.current_lap_id
self.lap_buffer = []   # ← BEFORE any await
self.seq = 0
await repo.insert_frames(old_id, buf)
...

# WRONG — buffer cleared after I/O; on_frame() appends new-lap frames to buf
# during the await, which then get written as part of the old lap
await repo.insert_frames(self.current_lap_id, self.lap_buffer)
self.lap_buffer = []   # ← too late
```

Because `on_frame()` is synchronous and the event loop is cooperative, appending to
`lap_buffer` can only happen between `await` points. Clearing the buffer before the
first `await` means all subsequent `on_frame()` calls build the new buffer independently.

### LapRecorder state machine

All lifecycle methods are `async def`. The buffer-capture pattern above applies to
every method that reads `lap_buffer` and then awaits.

```text
State: IDLE (initial)
    async reset_and_new_lap(n)
                 → self.current_lap_id = await repo.insert_lap(n, started_at=time.time())
                   ← lastrowid
                   self.lap_buffer = []; self.seq = 0; state = RECORDING
    on_frame()   → no-op (sync)
    flush_and_new_lap() → no-op
    close()      → no-op

State: RECORDING
    async reset_and_new_lap(n)   ← race restart path
                 → buf = self.lap_buffer; car = buf[0]["car_code"] if buf else None
                   old_id = self.current_lap_id
                   self.lap_buffer = []; self.seq = 0   ← BEFORE any await
                   if buf:
                       await repo.insert_frames(old_id, buf)
                       await repo.complete_lap(old_id, lap_time_ms=None,
                           completed_at=time.time(), is_complete=0, car_code=car)
                   self.current_lap_id = await repo.insert_lap(n, started_at=time.time())
                   state = RECORDING
    on_frame(frame)
                 → self.lap_buffer.append(frame); self.seq += 1  ← sync; no await
    async flush_and_new_lap(n)   ← no-op if state == IDLE
                 → buf = self.lap_buffer; car = buf[0]["car_code"] if buf else None
                   lap_time_ms = buf[-1]["last_lap_time_ms"] if buf else None
                   old_id = self.current_lap_id
                   self.lap_buffer = []; self.seq = 0   ← BEFORE any await
                   await repo.insert_frames(old_id, buf)
                   await repo.complete_lap(old_id, lap_time_ms, ..., is_complete=1, car_code=car)
                   self.current_lap_id = await repo.insert_lap(n, ...) ← lastrowid
    async close()
                 → buf = self.lap_buffer; car = buf[0]["car_code"] if buf else None
                   old_id = self.current_lap_id
                   self.lap_buffer = []; self.seq = 0   ← BEFORE any await
                   if buf:
                       await repo.insert_frames(old_id, buf)
                       await repo.complete_lap(old_id, lap_time_ms=None,
                           completed_at=time.time(), is_complete=0, car_code=car)
                   state = IDLE
```

### Shutdown sequence

`__main__.py` manages task lifecycle. On SIGTERM or keyboard interrupt, all tasks are
cancelled before cleanup:

```python
async def main():
    # ... setup ...
    dispatcher_task = asyncio.create_task(run_dispatcher(...))
    broadcaster_task = asyncio.create_task(run_broadcaster(...))
    try:
        await asyncio.gather(dispatcher_task, broadcaster_task, ...)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        dispatcher_task.cancel()
        broadcaster_task.cancel()
        await asyncio.gather(dispatcher_task, broadcaster_task, return_exceptions=True)
        await recorder.close()   # flush partial lap if recording
        await repo.close()       # close aiosqlite connection
```

The `broadcaster` and `dispatcher` loops use `while True` with `await` — they
handle `asyncio.CancelledError` cleanly when cancelled.

**Shutdown ordering with in-flight lifecycle tasks**: lifecycle tasks (`flush_and_new_lap`,
`reset_and_new_lap`) may be pending on the event loop when `recorder.close()` is called.
The state machine handles this safely:

- If `close()` runs before `flush_and_new_lap`: `close()` captures the buffer, writes
  the partial lap (is_complete=0), sets state=IDLE. When `flush_and_new_lap` runs, it
  sees IDLE state and is a no-op. No data is written twice.
- If `flush_and_new_lap` runs first and clears the buffer before its first `await`:
  `close()` sees an empty buffer and does nothing. `flush_and_new_lap` completes the
  old lap (is_complete=1) and inserts a new orphaned lap row (is_complete=0, no frames).
  Acceptable: the orphaned row is cleaned up by the Phase 3 lap selector.

All lifecycle coroutines run on the main event loop and cannot preempt each other —
they interleave only at `await` points.

### WebSocket broadcaster

Single task; concurrent sends via `asyncio.gather` to isolate slow clients:

```python
async def broadcaster(ws_queue, clients):
    while True:
        frame = await ws_queue.get()
        if clients:
            await asyncio.gather(
                *[send_safe(ws, frame) for ws in list(clients)],
                return_exceptions=True
            )

async def send_safe(ws, frame):
    try:
        await ws.send_json(frame)
    except Exception:
        pass  # silently ignored; /ws handler removes client on disconnect
```

`clients` is a `set` maintained by the `/ws` endpoint. The handler adds on connect
and removes in `finally` when the receive loop detects disconnect:

```python
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # raises WebSocketDisconnect on close
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)
```

`send_safe` does not modify `clients`. Removal is the `/ws` handler's responsibility.

---

## Components

| File | Responsibility |
| --- | --- |
| `rexy/client.py` | TurismoClient wrapper; creates `GameEvents`/`RaceEvents`; sync callbacks; `call_soon_threadsafe` for all queue/lifecycle ops; `telemetry_to_dict` serializer; injects `ts` + `heartbeat_type` |
| `rexy/dispatcher.py` | Drains `raw_queue`; drop-oldest to `ws_queue`; calls `LapRecorder.on_frame()` |
| `rexy/recorder.py` | `LapRecorder`: IDLE/RECORDING state machine; all lifecycle `async def`; buffer-before-await pattern |
| `rexy/repository.py` | `TelemetryRepository`: aiosqlite CRUD; `insert_lap` returns `lastrowid`; schema init; version check |
| `rexy/server.py` | FastAPI; `/ws` broadcaster; `clients` set; static files |
| `rexy/static/index.html` | Vanilla JS; all telemetry fields; rAF render loop; WS reconnect |
| `rexy/__main__.py` | Wires components; task lifecycle; shutdown sequence |

---

## Schema

The schema is applied via individual `await db.execute()` calls (not `executescript`),
so `PRAGMA user_version` is executed as a separate statement after table creation:

```sql
-- Applied as separate statements in TelemetryRepository.init()

CREATE TABLE IF NOT EXISTS laps (
    id           INTEGER PRIMARY KEY,
    lap_number   INTEGER NOT NULL,
    started_at   REAL    NOT NULL,   -- time.time() when insert_lap() is called
    completed_at REAL,               -- time.time() when complete_lap() is called; NULL if partial
    lap_time_ms  INTEGER,            -- buf[-1]["last_lap_time_ms"]; NULL for partial laps
    car_code     INTEGER,            -- buf[0]["car_code"] captured before flush; NULL if buf empty
    is_complete  INTEGER DEFAULT 0   -- set to 1 by complete_lap() on successful flush
);

CREATE TABLE IF NOT EXISTS frames (
    lap_id  INTEGER NOT NULL REFERENCES laps(id),
    seq     INTEGER NOT NULL,        -- 0-based; owned and reset by LapRecorder
    ts      REAL    NOT NULL,        -- time.time() injected by client.py
    packet_id INTEGER,               -- gt-telem packet sequence number; useful for gap detection

    -- All heartbeat types (A, B, ~)
    speed_mps REAL, engine_rpm REAL,
    current_gear INTEGER,            -- decoded: bits & 0b1111
    suggested_gear INTEGER,          -- decoded: bits >> 4
    throttle INTEGER, brake INTEGER, -- raw 0-255; frontend converts to %
    clutch_pedal REAL, clutch_engagement REAL,
    boost_pressure REAL, fuel_level REAL, fuel_capacity REAL,
    oil_pressure REAL, oil_temp REAL, water_temp REAL,
    tire_fl_temp REAL, tire_fr_temp REAL, tire_rl_temp REAL, tire_rr_temp REAL,
    tire_fl_sus_height REAL, tire_fr_sus_height REAL,
    tire_rl_sus_height REAL, tire_rr_sus_height REAL,
    tire_fl_radius REAL, tire_fr_radius REAL,   -- for speed cross-checks (Phase 3)
    tire_rl_radius REAL, tire_rr_radius REAL,
    wheel_fl_rps REAL, wheel_fr_rps REAL, wheel_rl_rps REAL, wheel_rr_rps REAL,
    current_lap INTEGER, total_laps INTEGER,
    best_lap_time_ms INTEGER, last_lap_time_ms INTEGER,
    time_of_day_ms INTEGER,          -- in-game time of day
    race_start_pos INTEGER,          -- starting grid position
    total_cars INTEGER,              -- cars in race
    position_x REAL, position_y REAL, position_z REAL,
    velocity_x REAL, velocity_y REAL, velocity_z REAL,   -- for G-force derivation (Phase 3)
    ang_vel_x REAL, ang_vel_y REAL, ang_vel_z REAL,
    rotation_x REAL, rotation_y REAL, rotation_z REAL,
    road_plane_x REAL, road_plane_y REAL, road_plane_z REAL, road_plane_dist REAL,
    body_height REAL, orientation REAL,
    min_alert_rpm REAL, max_alert_rpm REAL,
    -- Decoded flag booleans (stored as 0/1)
    tcs_active INTEGER, asm_active INTEGER,
    cars_on_track INTEGER, is_paused INTEGER, in_gear INTEGER,
    rev_limit INTEGER, hand_brake_active INTEGER,
    calc_max_speed REAL, trans_rpm REAL, trans_top_speed REAL,
    gear1 REAL, gear2 REAL, gear3 REAL, gear4 REAL,
    gear5 REAL, gear6 REAL, gear7 REAL, gear8 REAL,
    car_code INTEGER,

    -- Heartbeat B only — NULL for A and ~
    wheel_rotation_radians REAL,     -- steering wheel input
    filler_float_fb REAL,            -- lateral slip angle (approx.)
    sway REAL, heave REAL, surge REAL,   -- lateral/vertical/longitudinal body motion (G-force proxy)

    -- Heartbeat ~ only — NULL for A and B
    throttle_filtered INTEGER, brake_filtered INTEGER,  -- raw 0-255; same scale as throttle/brake
    energy_recovery REAL,

    PRIMARY KEY (lap_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_laps_is_complete ON laps(is_complete);

PRAGMA user_version = 1;   -- set after CREATE TABLE statements
```

### Heartbeat-to-column mapping

| Column group | A | B | ~ |
| --- | --- | --- | --- |
| All standard fields (`speed_mps` through `car_code`) | populated | populated | populated |
| `wheel_rotation_radians`, `filler_float_fb`, `sway`, `heave`, `surge` | NULL | populated | NULL |
| `throttle_filtered`, `brake_filtered`, `energy_recovery` | NULL | NULL | populated |

### G-forces

`sway`, `heave`, `surge` (Heartbeat B) represent lateral, vertical, and longitudinal
body motion from the motion-rig data. These are displayed directly as G-force proxies
in the live view (Heartbeat B only). For Heartbeat A/~, G-force display is not available.

`velocity_x/y/z` is recorded for all heartbeat types and is reserved for Phase 3
G-force computation (numerical differentiation × 1/g).

---

## Database initialization

`TelemetryRepository.init()` is awaited from `__main__.py` before any other component
starts. Each DDL statement is executed individually via `await db.execute()`:

```python
async def init(self):
    async with aiosqlite.connect(self.db_path) as db:
        row = await db.execute("PRAGMA user_version")
        version = (await row.fetchone())[0]
        if version == 0:
            await db.execute("CREATE TABLE IF NOT EXISTS laps (...)")
            await db.execute("CREATE TABLE IF NOT EXISTS frames (...)")
            await db.execute("CREATE INDEX IF NOT EXISTS ...")
            await db.commit()                            # commit DDL first
            await db.execute("PRAGMA user_version = 1") # set version AFTER commit
            # PRAGMA user_version is non-transactional — setting it before commit
            # would leave version=1 even if commit fails, causing silent skip on
            # next startup with missing tables.
        elif version == 1:
            pass  # schema already at current version
        else:
            raise RuntimeError(f"unsupported schema version: {version}")
```

---

## SQLite persistence

Named Docker volume `telemetry_data` mounted at `/data`:

```yaml
volumes:
  telemetry_data:

services:
  rexy:
    volumes:
      - telemetry_data:/data
```

---

## Environment variables

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `PS_IP` | *(auto-discover)* | No | PlayStation IP address |
| `GT7_HEARTBEAT_TYPE` | `B` | No | Heartbeat type: `A`, `B`, or `~` |
| `DB_PATH` | `/data/telemetry.db` | No | SQLite database file path |

---

## WebSocket message format

Flat JSON containing all fields from `telemetry_to_dict` plus `ts` and `heartbeat_type`.
Field names match the schema columns exactly:

```json
{
  "ts": 1710000000.123,
  "heartbeat_type": "B",
  "packet_id": 4521,
  "speed_mps": 55.3,
  "engine_rpm": 6800.0,
  "current_gear": 4,
  "suggested_gear": 5,
  "throttle": 200,
  "brake": 0,
  "tcs_active": false,
  "asm_active": false,
  "cars_on_track": true,
  "is_paused": false,
  "in_gear": true,
  "rev_limit": false,
  "hand_brake_active": false,
  "car_code": 12345,
  "position_x": 120.4, "position_y": 0.3, "position_z": -45.1,
  "velocity_x": 0.12, "velocity_y": -0.01, "velocity_z": 55.3,
  "wheel_rotation_radians": 0.12,
  "filler_float_fb": -0.03,
  "sway": 0.01,
  "heave": -0.05,
  "surge": 0.22,
  "throttle_filtered": null,
  "brake_filtered": null,
  "energy_recovery": null
}
```

All fields always present. Heartbeat-specific fields are `null` when inactive.
Raw throttle/brake (0–255) transmitted as-is; frontend converts for display.

---

## Live view

### Delivery

- WebSocket at `/ws`; exponential backoff reconnect.
- `ws_queue` `maxsize=1` with drop-oldest (see dispatcher section).
- `requestAnimationFrame` render loop:

```js
let latest = {};
ws.onmessage = e => { latest = JSON.parse(e.data); };
function render() {
    if (latest.speed_mps !== undefined) { /* update DOM */ }
    requestAnimationFrame(render);
}
requestAnimationFrame(render);
```

### Field cards

| Card | Fields | Visible when |
| --- | --- | --- |
| Lap | `current_lap`, current/last/best lap time, `total_laps`, `cars_on_track` | Always |
| Engine | speed (km/h), `engine_rpm`, `current_gear`, `suggested_gear`, throttle %, brake %, `boost_pressure`, fuel % | Always |
| Tires | `tire_*_temp` (°C), `tire_*_sus_height` | Always |
| Thermal | `oil_temp` (°C), `oil_pressure`, `water_temp` (°C) | Always |
| Motion | `wheel_rotation_radians` (steering), `filler_float_fb` (slip), `sway`/`heave`/`surge` (G-force proxy) | `heartbeat_type == "B"` |
| Filtered | `throttle_filtered` %, `brake_filtered` %, `energy_recovery` | `heartbeat_type == "~"` |
| Status | `tcs_active`, `asm_active`, `rev_limit`, `in_gear`, `min/max_alert_rpm` (shift lights), `hand_brake_active` | Always |
| Position | `position_x/y/z`, `velocity_x/y/z`, road plane | Always |
| Race | `race_start_pos`, `total_cars`, `time_of_day_ms`, `car_code` | Always |

Frontend conversions: `speed_mps * 3.6` → km/h; `throttle / 255 * 100` → %;
lap times (`*_ms`) → `m:ss.mmm`; `sway/heave/surge` displayed as-is (motion-rig units).

---

## Error handling

| Scenario | Handling |
| --- | --- |
| Mid-lap unclean crash | Buffer lost; `laps` row `is_complete=0` |
| Clean shutdown (SIGTERM) | Tasks cancelled; `await recorder.close()` in finally; partial `is_complete=0` |
| Race restart (`on_at_track`/`on_in_race` while RECORDING) | `reset_and_new_lap()` flushes partial inline (buffer-before-await pattern) |
| SQLite write failure | Error logged; buffer already cleared; `laps` row `is_complete=0`; no retry |
| WebSocket client disconnect | Removed from `clients` set in `/ws` handler `finally` block |
| Slow WebSocket client | `asyncio.gather` isolates per-client sends |
| `on_lap_change` fires before recording started | `flush_and_new_lap()` no-op in IDLE state |
| In-flight lifecycle task races with shutdown `close()` | State machine guarantees safety: `close()` and `flush_and_new_lap()` interleave at await points but never double-write; see Shutdown sequence section |
| `GameEvents`/`RaceEvents` duplicate instance | Class-level list appended twice; create exactly one instance per session |

---

## Constraints carried forward

- No npm, no build step — `index.html` is a single static file
- Single Docker container, no sidecars
- ARM64 (Raspberry Pi) compatible
- Python 3.10+
