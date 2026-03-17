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
TurismoClient (gt-telem, async callbacks on asyncio event loop)
    │
    ├── on_telemetry_frame (~60Hz)
    │       └── raw_queue.put_nowait(frame)
    │           ← frame dict includes "heartbeat_type" and "ts" injected by client.py
    │
    ├── on_at_track
    │       └── await LapRecorder.reset_and_new_lap(lap_number=1)
    │
    ├── on_race_end / on_in_game_menu
    │       └── await LapRecorder.close()
    │
    ├── on_lap_change
    │       └── await LapRecorder.flush_and_new_lap(new_lap_number, lap_time_ms)
    │               # capture before any await:
    │               buf = self.lap_buffer; car = buf[0]["car_code"] if buf else None
    │               old_id = self.current_lap_id
    │               # clear buffer BEFORE first await:
    │               self.lap_buffer = []; self.seq = 0
    │               # then do I/O:
    │               1. await repo.insert_frames(old_id, buf) — executemany, 1 tx
    │               2. await repo.complete_lap(old_id, lap_time_ms,
    │                     completed_at=time.time(), is_complete=1, car_code=car)
    │               3. self.current_lap_id = await repo.insert_lap(
    │                     new_lap_number, started_at=time.time())
    │                  ← insert_lap() returns lastrowid
    │
    └── on shutdown (SIGTERM → __main__.py finally block)
            └── await LapRecorder.close()

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

### Buffer safety — clear before await

`flush_and_new_lap` and similar methods must capture `lap_buffer` contents and clear
the buffer **before** the first `await`. This is the critical invariant:

```python
# CORRECT — buffer cleared before I/O
buf = self.lap_buffer
car = buf[0]["car_code"] if buf else None
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
    async flush_and_new_lap(n, ms)
                 → buf/car/old_id captured; buffer cleared BEFORE first await (see above)
                   await insert_frames(old_id, buf)
                   await complete_lap(old_id, ms, ..., is_complete=1, car_code=car)
                   self.current_lap_id = await insert_lap(n, ...) ← lastrowid
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

### Lifecycle method wiring in client.py

`client.py` registers gt-telem callbacks as `async def` and calls `LapRecorder`
lifecycle methods directly:

```python
async def on_at_track():
    await recorder.reset_and_new_lap(lap_number=1)

async def on_lap_change(lap_number, lap_time_ms):
    await recorder.flush_and_new_lap(lap_number, lap_time_ms)

async def on_race_end():
    await recorder.close()
```

The dispatcher task only calls `LapRecorder.on_frame()` (sync). It never calls
lifecycle methods.

### gt-telem callback API and threading

Phase 2 uses async callbacks exclusively. Prerequisites to verify before implementation:

1. Exact callback registration API for the installed gt-telem version
   (Phase 1 used `tc.telemetry` polling — callbacks are a different code path).
2. Async callbacks are scheduled on the running event loop, not via `asyncio.run()`
   in a thread. If they run in a thread, `await` inside callbacks raises `RuntimeError`.
   In that case, use `asyncio.run_coroutine_threadsafe(coro, loop)` for all lifecycle
   calls, and add a threading lock around `lap_buffer` access.

| Callback | Category | Trigger |
| --- | --- | --- |
| `on_telemetry_frame` | Telemetry | Every ~60Hz frame |
| `on_at_track` | GameEvents | Car loaded at track |
| `on_race_end` | GameEvents | Race ends |
| `on_in_game_menu` | GameEvents | Paused to menu |
| `on_lap_change` | RaceEvents | Lap counter increments |

### `heartbeat_type` injection

`client.py` injects two fields into every frame dict before queuing:

```python
frame["heartbeat_type"] = os.environ.get("GT7_HEARTBEAT_TYPE", "B")
frame["ts"] = time.time()
```

No other component reads `GT7_HEARTBEAT_TYPE`.

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
| `rexy/client.py` | TurismoClient wrapper; async callbacks; injects `ts` + `heartbeat_type`; pushes to `raw_queue`; calls LapRecorder lifecycle |
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
    lap_time_ms  INTEGER,            -- from gt-telem event; NULL for partial laps
    car_code     INTEGER,            -- buf[0]["car_code"] captured before flush; NULL if buf empty
    is_complete  INTEGER DEFAULT 0   -- set to 1 by complete_lap() on successful flush
);

CREATE TABLE IF NOT EXISTS frames (
    lap_id  INTEGER NOT NULL REFERENCES laps(id),
    seq     INTEGER NOT NULL,        -- 0-based; owned and reset by LapRecorder
    ts      REAL    NOT NULL,        -- time.time() injected by client.py

    -- All heartbeat types (A, B, ~)
    speed_mps REAL, engine_rpm REAL, gear INTEGER,
    throttle INTEGER, brake INTEGER,     -- raw 0-255; frontend converts to %
    clutch_pedal REAL,
    boost_pressure REAL, fuel_level REAL, fuel_capacity REAL,
    oil_pressure REAL, oil_temp REAL, water_temp REAL,
    tire_fl_temp REAL, tire_fr_temp REAL, tire_rl_temp REAL, tire_rr_temp REAL,
    tire_fl_sus_height REAL, tire_fr_sus_height REAL,
    tire_rl_sus_height REAL, tire_rr_sus_height REAL,
    wheel_fl_rps REAL, wheel_fr_rps REAL, wheel_rl_rps REAL, wheel_rr_rps REAL,
    current_lap INTEGER, total_laps INTEGER,
    best_lap_time_ms INTEGER, last_lap_time_ms INTEGER,
    position_x REAL, position_y REAL, position_z REAL,
    ang_vel_x REAL, ang_vel_y REAL, ang_vel_z REAL,
    rotation_x REAL, rotation_y REAL, rotation_z REAL,
    road_plane_x REAL, road_plane_y REAL, road_plane_z REAL, road_plane_dist REAL,
    min_alert_rpm REAL, max_alert_rpm REAL,
    flags INTEGER, bits INTEGER,
    car_code INTEGER,                -- always present in all heartbeat types
    calc_max_speed REAL, trans_rpm REAL, trans_top_speed REAL,

    -- Heartbeat B only — NULL for A and ~
    wheel_rotation_radians REAL,     -- gt-telem field name for steering wheel input
    filler_float_fb REAL,            -- gt-telem field name for lateral slip angle (approx.)
    sway REAL, heave REAL, surge REAL,

    -- Heartbeat ~ only — NULL for A and B
    throttle_filtered REAL, brake_filtered REAL, energy_recovery REAL,

    PRIMARY KEY (lap_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_laps_is_complete ON laps(is_complete);

PRAGMA user_version = 1;   -- set after CREATE TABLE statements
```

### Heartbeat-to-column mapping

| Column group | A | B | ~ |
| --- | --- | --- | --- |
| All standard fields incl. `car_code` | populated | populated | populated |
| `wheel_rotation_radians`, `filler_float_fb`, `sway`, `heave`, `surge` | NULL | populated | NULL |
| `throttle_filtered`, `brake_filtered`, `energy_recovery` | NULL | NULL | populated |

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

Flat JSON. All `frames` schema field names plus `ts` and `heartbeat_type`:

```json
{
  "ts": 1710000000.123,
  "heartbeat_type": "B",
  "speed_mps": 55.3,
  "engine_rpm": 6800.0,
  "gear": 4,
  "throttle": 200,
  "brake": 0,
  "car_code": 12345,
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
Raw throttle/brake (0-255) transmitted as-is; frontend converts for display.

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
| Lap | lap#, current/last/best lap time, total laps, race state | Always |
| Engine | speed (km/h), RPM, gear, throttle %, brake %, boost, fuel % | Always |
| Tires | temp FL/FR/RL/RR (°C), suspension height FL/FR/RL/RR | Always |
| Thermal | oil temp (°C), oil pressure, water temp (°C) | Always |
| Motion | Steering (`wheel_rotation_radians`), Slip angle (`filler_float_fb`), sway/heave/surge | `heartbeat_type == "B"` |
| Filtered | throttle filtered %, brake filtered %, energy recovery | `heartbeat_type == "~"` |
| Status | TCS, ASM, shift lights, suggested gear | Always |
| Position | X/Y/Z, road plane normal + dist | Always |

Frontend conversions: speed `* 3.6` → km/h; throttle/brake `/ 255 * 100` → %;
lap times → `m:ss.mmm`.

---

## Error handling

| Scenario | Handling |
| --- | --- |
| Mid-lap unclean crash | Buffer lost; `laps` row `is_complete=0` |
| Clean shutdown (SIGTERM) | Tasks cancelled; `await recorder.close()` in finally; partial `is_complete=0` |
| Race restart (`on_at_track` while RECORDING) | `reset_and_new_lap()` flushes partial inline (buffer-before-await pattern) |
| SQLite write failure | Error logged; buffer already cleared; `laps` row `is_complete=0`; no retry |
| WebSocket client disconnect | Removed from `clients` set in `/ws` handler `finally` block |
| Slow WebSocket client | `asyncio.gather` isolates per-client sends |
| `on_lap_change` before `on_at_track` | `flush_and_new_lap()` no-op in IDLE state |

---

## Constraints carried forward

- No npm, no build step — `index.html` is a single static file
- Single Docker container, no sidecars
- ARM64 (Raspberry Pi) compatible
- Python 3.10+
