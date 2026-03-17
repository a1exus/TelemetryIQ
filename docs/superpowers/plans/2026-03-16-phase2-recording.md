# Phase 2 Recording Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 1 polling loop with an event-driven pipeline: gt-telem callbacks → asyncio queue → SQLite lap recorder + WebSocket live view served by FastAPI.

**Architecture:** A single sync callback from gt-telem's background thread deposits frames onto `raw_queue` via `call_soon_threadsafe`. An asyncio dispatcher fans out to a drop-oldest `ws_queue` (live view) and a `LapRecorder` (SQLite). `GameEvents` and `RaceEvents` callbacks drive the IDLE/RECORDING state machine. FastAPI serves the dashboard at `GET /` and the WebSocket at `/ws`.

**Tech Stack:** Python 3.12 · gt-telem 1.2.1 · FastAPI 0.110+ · aiosqlite 0.19+ · uvicorn[standard] · pytest 8+ · pytest-asyncio 0.23+

**Spec:** `docs/superpowers/specs/2026-03-16-phase2-recording-design.md`

---

## File Map

| Action | Path | Responsibility |
| --- | --- | --- |
| Modify | `requirements.txt` | Add fastapi, uvicorn, aiosqlite, pytest, pytest-asyncio |
| Create | `pytest.ini` | `asyncio_mode = auto` for pytest-asyncio |
| Modify | `Makefile` | Fix `make install`; add `make test` |
| Modify | `.env.example` | Add `DB_PATH` |
| Modify | `compose.yaml` | Add `telemetry_data` volume |
| Create | `rexy/repository.py` | `TelemetryRepository`: aiosqlite CRUD, schema init |
| Create | `rexy/recorder.py` | `LapRecorder`: IDLE/RECORDING state machine |
| Create | `rexy/dispatcher.py` | `run_dispatcher`: raw_queue → ws_queue + recorder |
| Create | `rexy/client.py` | `telemetry_to_dict`, `setup_client`: gt-telem wiring |
| Create | `rexy/server.py` | FastAPI app, WebSocket endpoint, `run_broadcaster` |
| Create | `rexy/static/index.html` | Live telemetry dashboard — vanilla JS, all field cards |
| Modify | `rexy/__main__.py` | Wire all components; async entrypoint; graceful shutdown |
| Create | `tests/__init__.py` | Empty — marks tests as a package |
| Create | `tests/test_repository.py` | Repository unit tests with `:memory:` SQLite |
| Create | `tests/test_recorder.py` | LapRecorder state machine tests with mock repo |
| Create | `tests/test_dispatcher.py` | Dispatcher queue fanout tests |

---

## Chunk 1: Foundation

### Task 1: Dependencies, config, and project structure

**Files:**
- Modify: `requirements.txt`
- Create: `pytest.ini`
- Modify: `Makefile`
- Modify: `.env.example`
- Modify: `compose.yaml`
- Create: `tests/__init__.py`

- [ ] **Step 1: Update `requirements.txt`**

```
gt-telem>=1.2.1
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
aiosqlite>=0.19.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: Update `Makefile`**

```makefile
.PHONY: build up down logs restart install test

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest tests/ -v

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose down && docker compose up -d
```

- [ ] **Step 4: Update `.env.example`** — add `DB_PATH` line

```
# ...existing content...

# SQLite database path (inside container).
# Default: /data/telemetry.db — persisted in Docker volume telemetry_data.
DB_PATH=/data/telemetry.db
```

- [ ] **Step 5: Update `compose.yaml`** — add volume

```yaml
volumes:
  telemetry_data:

services:
  telemetryiq:
    build: .
    image: telemetryiq:latest
    network_mode: host
    env_file:
      - path: .env
        required: false
    volumes:
      - telemetry_data:/data
    restart: unless-stopped
```

- [ ] **Step 6: Create `tests/__init__.py`** — empty file

- [ ] **Step 7: Install and verify**

```bash
make install
.venv/bin/python -c "import fastapi, aiosqlite, uvicorn, pytest; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini Makefile .env.example compose.yaml tests/__init__.py
git commit -m "feat: add phase 2 dependencies and project setup"
```

---

### Task 2: TelemetryRepository

**Files:**
- Create: `rexy/repository.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_repository.py`:

```python
import pytest
from rexy.repository import TelemetryRepository


@pytest.fixture
async def repo():
    r = TelemetryRepository(":memory:")
    await r.init()
    yield r
    await r.close()


async def test_schema_version(repo):
    cur = await repo.db.execute("PRAGMA user_version")
    assert (await cur.fetchone())[0] == 1


async def test_wal_mode(repo):
    cur = await repo.db.execute("PRAGMA journal_mode")
    assert (await cur.fetchone())[0] == "wal"


async def test_tables_exist(repo):
    cur = await repo.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in await cur.fetchall()}
    assert {"sessions", "laps", "frames"} <= tables


async def test_insert_session(repo):
    sid = await repo.insert_session(started_at=1000.0)
    assert isinstance(sid, int) and sid > 0
    cur = await repo.db.execute("SELECT started_at FROM sessions WHERE id=?", (sid,))
    assert (await cur.fetchone())[0] == 1000.0


async def test_insert_lap(repo):
    sid = await repo.insert_session(1000.0)
    lid = await repo.insert_lap(1, sid, track_id=42, started_at=1001.0)
    assert isinstance(lid, int) and lid > 0
    cur = await repo.db.execute(
        "SELECT session_id, track_id, lap_number, is_complete FROM laps WHERE id=?", (lid,)
    )
    assert (await cur.fetchone()) == (sid, 42, 1, 0)


async def test_insert_lap_null_track(repo):
    sid = await repo.insert_session(1000.0)
    lid = await repo.insert_lap(1, sid, track_id=None, started_at=1001.0)
    cur = await repo.db.execute("SELECT track_id FROM laps WHERE id=?", (lid,))
    assert (await cur.fetchone())[0] is None


async def test_complete_lap(repo):
    sid = await repo.insert_session(1000.0)
    lid = await repo.insert_lap(1, sid, None, 1001.0)
    await repo.complete_lap(
        lid, lap_time_ms=85432, completed_at=1090.0, is_complete=1, car_code=999
    )
    cur = await repo.db.execute(
        "SELECT lap_time_ms, is_complete, car_code FROM laps WHERE id=?", (lid,)
    )
    assert (await cur.fetchone()) == (85432, 1, 999)


async def test_insert_frames(repo):
    sid = await repo.insert_session(1000.0)
    lid = await repo.insert_lap(1, sid, None, 1001.0)
    frames = [
        {k: None for k in _all_frame_keys()} | {"seq": 0, "ts": 1001.0, "speed_mps": 10.0},
        {k: None for k in _all_frame_keys()} | {"seq": 1, "ts": 1001.016, "speed_mps": 10.1},
    ]
    await repo.insert_frames(lid, frames)
    cur = await repo.db.execute("SELECT COUNT(*) FROM frames WHERE lap_id=?", (lid,))
    assert (await cur.fetchone())[0] == 2


async def test_insert_frames_empty(repo):
    sid = await repo.insert_session(1000.0)
    lid = await repo.insert_lap(1, sid, None, 1001.0)
    await repo.insert_frames(lid, [])  # must not raise


async def test_init_idempotent(tmp_path):
    db = str(tmp_path / "t.db")
    r1 = TelemetryRepository(db)
    await r1.init()
    await r1.close()
    r2 = TelemetryRepository(db)
    await r2.init()  # second init on version=1 must not raise
    await r2.close()


def _all_frame_keys():
    """Return all non-lap_id frame column names for building test dicts."""
    from rexy.repository import _FRAME_COLS
    return [c for c in _FRAME_COLS if c != "lap_id"]
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_repository.py -v
```

Expected: `ImportError: No module named 'rexy.repository'`

- [ ] **Step 3: Create `rexy/repository.py`**

```python
from __future__ import annotations

import aiosqlite

# All columns in the frames table, in INSERT order.
# lap_id is first; remaining columns match telemetry_to_dict keys + "seq".
_FRAME_COLS: tuple[str, ...] = (
    "lap_id", "seq", "ts", "packet_id",
    "speed_mps", "engine_rpm", "current_gear", "suggested_gear",
    "throttle", "brake", "clutch_pedal", "clutch_engagement",
    "boost_pressure", "fuel_level", "fuel_capacity",
    "oil_pressure", "oil_temp", "water_temp",
    "tire_fl_temp", "tire_fr_temp", "tire_rl_temp", "tire_rr_temp",
    "tire_fl_sus_height", "tire_fr_sus_height", "tire_rl_sus_height", "tire_rr_sus_height",
    "tire_fl_radius", "tire_fr_radius", "tire_rl_radius", "tire_rr_radius",
    "wheel_fl_rps", "wheel_fr_rps", "wheel_rl_rps", "wheel_rr_rps",
    "current_lap", "total_laps", "best_lap_time_ms", "last_lap_time_ms",
    "time_of_day_ms", "race_start_pos", "total_cars",
    "position_x", "position_y", "position_z",
    "velocity_x", "velocity_y", "velocity_z",
    "ang_vel_x", "ang_vel_y", "ang_vel_z",
    "rotation_x", "rotation_y", "rotation_z",
    "road_plane_x", "road_plane_y", "road_plane_z", "road_plane_dist",
    "body_height", "orientation",
    "min_alert_rpm", "max_alert_rpm",
    "tcs_active", "asm_active", "cars_on_track", "is_paused",
    "in_gear", "rev_limit", "hand_brake_active",
    "calc_max_speed", "trans_rpm", "trans_top_speed",
    "gear1", "gear2", "gear3", "gear4", "gear5", "gear6", "gear7", "gear8",
    "car_code",
    "wheel_rotation_radians", "filler_float_fb", "sway", "heave", "surge",
    "throttle_filtered", "brake_filtered", "energy_recovery",
)

_FRAME_PLACEHOLDERS = ",".join("?" * len(_FRAME_COLS))
_FRAME_INSERT = (
    f"INSERT INTO frames ({','.join(_FRAME_COLS)}) VALUES ({_FRAME_PLACEHOLDERS})"
)

_DDL_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY,
    started_at REAL NOT NULL
)
"""

_DDL_LAPS = """
CREATE TABLE IF NOT EXISTS laps (
    id           INTEGER PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES sessions(id),
    lap_number   INTEGER NOT NULL,
    track_id     INTEGER,
    started_at   REAL    NOT NULL,
    completed_at REAL,
    lap_time_ms  INTEGER,
    car_code     INTEGER,
    is_complete  INTEGER DEFAULT 0
)
"""

_DDL_FRAMES = """
CREATE TABLE IF NOT EXISTS frames (
    lap_id                 INTEGER NOT NULL REFERENCES laps(id),
    seq                    INTEGER NOT NULL,
    ts                     REAL    NOT NULL,
    packet_id              INTEGER,
    speed_mps              REAL, engine_rpm REAL, current_gear INTEGER, suggested_gear INTEGER,
    throttle               INTEGER, brake INTEGER, clutch_pedal REAL, clutch_engagement REAL,
    boost_pressure         REAL, fuel_level REAL, fuel_capacity REAL,
    oil_pressure           REAL, oil_temp REAL, water_temp REAL,
    tire_fl_temp           REAL, tire_fr_temp REAL, tire_rl_temp REAL, tire_rr_temp REAL,
    tire_fl_sus_height     REAL, tire_fr_sus_height REAL,
    tire_rl_sus_height     REAL, tire_rr_sus_height REAL,
    tire_fl_radius         REAL, tire_fr_radius REAL,
    tire_rl_radius         REAL, tire_rr_radius REAL,
    wheel_fl_rps           REAL, wheel_fr_rps REAL, wheel_rl_rps REAL, wheel_rr_rps REAL,
    current_lap            INTEGER, total_laps INTEGER,
    best_lap_time_ms       INTEGER, last_lap_time_ms INTEGER,
    time_of_day_ms         INTEGER, race_start_pos INTEGER, total_cars INTEGER,
    position_x             REAL, position_y REAL, position_z REAL,
    velocity_x             REAL, velocity_y REAL, velocity_z REAL,
    ang_vel_x              REAL, ang_vel_y REAL, ang_vel_z REAL,
    rotation_x             REAL, rotation_y REAL, rotation_z REAL,
    road_plane_x           REAL, road_plane_y REAL, road_plane_z REAL, road_plane_dist REAL,
    body_height            REAL, orientation REAL,
    min_alert_rpm          REAL, max_alert_rpm REAL,
    tcs_active             INTEGER, asm_active INTEGER, cars_on_track INTEGER,
    is_paused              INTEGER, in_gear INTEGER, rev_limit INTEGER, hand_brake_active INTEGER,
    calc_max_speed         REAL, trans_rpm REAL, trans_top_speed REAL,
    gear1 REAL, gear2 REAL, gear3 REAL, gear4 REAL,
    gear5 REAL, gear6 REAL, gear7 REAL, gear8 REAL,
    car_code               INTEGER,
    wheel_rotation_radians REAL, filler_float_fb REAL,
    sway REAL, heave REAL, surge REAL,
    throttle_filtered      INTEGER, brake_filtered INTEGER, energy_recovery REAL,
    PRIMARY KEY (lap_id, seq)
)
"""


class TelemetryRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL")
        cur = await self.db.execute("PRAGMA user_version")
        version = (await cur.fetchone())[0]
        if version == 0:
            await self.db.execute(_DDL_SESSIONS)
            await self.db.execute(_DDL_LAPS)
            await self.db.execute(_DDL_FRAMES)
            await self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_laps_is_complete ON laps(is_complete)"
            )
            await self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_laps_complete_track "
                "ON laps(is_complete, track_id, lap_time_ms)"
            )
            await self.db.commit()
            await self.db.execute("PRAGMA user_version = 1")
        elif version == 1:
            pass
        else:
            raise RuntimeError(f"unsupported schema version: {version}")

    async def insert_session(self, started_at: float) -> int:
        cur = await self.db.execute(
            "INSERT INTO sessions (started_at) VALUES (?)", (started_at,)
        )
        await self.db.commit()
        return cur.lastrowid

    async def insert_lap(
        self,
        lap_number: int,
        session_id: int,
        track_id: int | None,
        started_at: float,
    ) -> int:
        cur = await self.db.execute(
            "INSERT INTO laps (lap_number, session_id, track_id, started_at) VALUES (?,?,?,?)",
            (lap_number, session_id, track_id, started_at),
        )
        await self.db.commit()
        return cur.lastrowid

    async def complete_lap(
        self,
        lap_id: int,
        lap_time_ms: int | None,
        completed_at: float,
        is_complete: int,
        car_code: int | None,
    ) -> None:
        await self.db.execute(
            "UPDATE laps SET lap_time_ms=?, completed_at=?, is_complete=?, car_code=? WHERE id=?",
            (lap_time_ms, completed_at, is_complete, car_code, lap_id),
        )
        await self.db.commit()

    async def insert_frames(self, lap_id: int, frames: list[dict]) -> None:
        if not frames:
            return
        rows = [
            tuple(lap_id if col == "lap_id" else f.get(col) for col in _FRAME_COLS)
            for f in frames
        ]
        await self.db.executemany(_FRAME_INSERT, rows)
        await self.db.commit()

    async def close(self) -> None:
        if self.db:
            await self.db.close()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_repository.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add rexy/repository.py tests/test_repository.py
git commit -m "feat: add TelemetryRepository with SQLite schema and CRUD"
```

---

## Chunk 2: Core Logic

### Task 3: LapRecorder

**Files:**
- Create: `rexy/recorder.py`
- Create: `tests/test_recorder.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recorder.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from rexy.recorder import LapRecorder, State


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.insert_lap = AsyncMock(return_value=7)
    repo.insert_frames = AsyncMock()
    repo.complete_lap = AsyncMock()
    return repo


@pytest.fixture
def recorder(mock_repo):
    return LapRecorder(repo=mock_repo, session_id=1)


# --- IDLE state ---

async def test_initial_state_is_idle(recorder):
    assert recorder.state == State.IDLE


async def test_on_frame_idle_noop(recorder, mock_repo):
    recorder.on_frame({"speed_mps": 10.0})
    assert recorder.lap_buffer == []


async def test_flush_idle_noop(recorder, mock_repo):
    await recorder.flush_and_new_lap(2)
    mock_repo.insert_frames.assert_not_called()
    mock_repo.insert_lap.assert_not_called()


async def test_close_idle_noop(recorder, mock_repo):
    await recorder.close()
    mock_repo.insert_frames.assert_not_called()


# --- IDLE → RECORDING ---

async def test_reset_transitions_to_recording(recorder):
    await recorder.reset_and_new_lap(1)
    assert recorder.state == State.RECORDING


async def test_reset_inserts_lap_row(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    mock_repo.insert_lap.assert_called_once()
    args = mock_repo.insert_lap.call_args[0]
    assert args[0] == 1        # lap_number
    assert args[1] == 1        # session_id
    assert args[2] is None     # track_id (not set yet)


async def test_reset_stores_lap_id(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    assert recorder.current_lap_id == 7  # mock returns 7


# --- RECORDING ---

async def test_on_frame_appends_to_buffer(recorder):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"speed_mps": 10.0, "last_lap_time_ms": -1})
    recorder.on_frame({"speed_mps": 11.0, "last_lap_time_ms": -1})
    assert len(recorder.lap_buffer) == 2


async def test_on_frame_injects_seq(recorder):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"speed_mps": 1.0, "last_lap_time_ms": -1})
    recorder.on_frame({"speed_mps": 2.0, "last_lap_time_ms": -1})
    assert recorder.lap_buffer[0]["seq"] == 0
    assert recorder.lap_buffer[1]["seq"] == 1


async def test_on_frame_does_not_mutate_input(recorder):
    await recorder.reset_and_new_lap(1)
    frame = {"speed_mps": 5.0, "last_lap_time_ms": -1}
    recorder.on_frame(frame)
    assert "seq" not in frame  # original dict untouched


# --- flush_and_new_lap ---

async def test_flush_clears_buffer_before_await(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 99, "last_lap_time_ms": 85000})

    captured = []

    async def capture(lap_id, frames):
        captured.append(list(recorder.lap_buffer))  # snapshot during await

    mock_repo.insert_frames.side_effect = capture
    await recorder.flush_and_new_lap(2)
    assert captured[0] == []  # buffer was empty when insert_frames ran


async def test_flush_derives_lap_time_from_buffer(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 5, "last_lap_time_ms": 85432})
    await recorder.flush_and_new_lap(2)
    args = mock_repo.complete_lap.call_args[0]
    assert args[1] == 85432  # lap_time_ms positional arg


async def test_flush_minus_one_sentinel_becomes_none(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await recorder.flush_and_new_lap(2)
    args = mock_repo.complete_lap.call_args[0]
    assert args[1] is None  # -1 → None


async def test_flush_marks_lap_complete(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 5, "last_lap_time_ms": 85000})
    await recorder.flush_and_new_lap(2)
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 1  # is_complete=1


async def test_flush_starts_new_lap(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 5, "last_lap_time_ms": 85000})
    await recorder.flush_and_new_lap(2)
    assert mock_repo.insert_lap.call_count == 2  # once on reset, once on flush


async def test_flush_empty_buffer_still_inserts_lap(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    # No frames
    await recorder.flush_and_new_lap(2)
    mock_repo.insert_frames.assert_not_called()
    mock_repo.complete_lap.assert_called_once()


# --- close ---

async def test_close_flushes_partial_lap(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await recorder.close()
    mock_repo.insert_frames.assert_called_once()
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 0  # is_complete=0 (partial)


async def test_close_empty_buffer_no_write(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    await recorder.close()
    mock_repo.insert_frames.assert_not_called()
    mock_repo.complete_lap.assert_not_called()


async def test_close_sets_state_to_idle(recorder):
    await recorder.reset_and_new_lap(1)
    await recorder.close()
    assert recorder.state == State.IDLE


# --- set_track_id ---

async def test_set_track_id(recorder):
    recorder.set_track_id(42)
    assert recorder.current_track_id == 42


async def test_track_id_passed_to_insert_lap(recorder, mock_repo):
    recorder.set_track_id(42)
    await recorder.reset_and_new_lap(1)
    args = mock_repo.insert_lap.call_args[0]
    assert args[2] == 42  # track_id


# --- race restart (RECORDING → reset_and_new_lap) ---

async def test_reset_while_recording_flushes_partial(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await recorder.reset_and_new_lap(1)  # restart
    mock_repo.insert_frames.assert_called_once()
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 0  # is_complete=0


async def test_reset_while_recording_stays_recording(recorder):
    await recorder.reset_and_new_lap(1)
    await recorder.reset_and_new_lap(1)
    assert recorder.state == State.RECORDING
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_recorder.py -v
```

Expected: `ImportError: No module named 'rexy.recorder'`

- [ ] **Step 3: Create `rexy/recorder.py`**

```python
from __future__ import annotations

import time
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rexy.repository import TelemetryRepository


class State(Enum):
    IDLE = auto()
    RECORDING = auto()


class LapRecorder:
    def __init__(self, repo: TelemetryRepository, session_id: int) -> None:
        self._repo = repo
        self._session_id = session_id
        self.state = State.IDLE
        self.current_lap_id: int | None = None
        self.current_track_id: int | None = None
        self.lap_buffer: list[dict] = []
        self.seq: int = 0

    # --- sync methods (safe to call from asyncio event loop without await) ---

    def set_track_id(self, track_id: int) -> None:
        self.current_track_id = track_id

    def on_frame(self, frame: dict) -> None:
        if self.state != State.RECORDING:
            return
        # Create new dict to avoid mutating the frame shared with ws_queue
        self.lap_buffer.append({**frame, "seq": self.seq})
        self.seq += 1

    # --- async lifecycle methods ---

    async def reset_and_new_lap(self, lap_number: int) -> None:
        if self.state == State.RECORDING:
            await self._flush_partial()
        self.current_lap_id = await self._repo.insert_lap(
            lap_number, self._session_id, self.current_track_id, started_at=time.time()
        )
        self.lap_buffer = []
        self.seq = 0
        self.state = State.RECORDING

    async def flush_and_new_lap(self, new_lap_number: int) -> None:
        if self.state != State.RECORDING:
            return
        # Capture before any await — critical invariant
        buf = self.lap_buffer
        car = buf[0].get("car_code") if buf else None
        raw = buf[-1].get("last_lap_time_ms") if buf else None
        lap_time_ms = None if (raw is None or raw == -1) else raw
        old_id = self.current_lap_id
        self.lap_buffer = []  # clear BEFORE first await
        self.seq = 0

        if buf:
            await self._repo.insert_frames(old_id, buf)
        await self._repo.complete_lap(
            old_id, lap_time_ms, time.time(), is_complete=1, car_code=car
        )
        self.current_lap_id = await self._repo.insert_lap(
            new_lap_number, self._session_id, self.current_track_id, started_at=time.time()
        )

    async def close(self) -> None:
        if self.state != State.RECORDING:
            return
        await self._flush_partial()
        self.state = State.IDLE

    # --- private ---

    async def _flush_partial(self) -> None:
        buf = self.lap_buffer
        car = buf[0].get("car_code") if buf else None
        old_id = self.current_lap_id
        self.lap_buffer = []  # clear BEFORE first await
        self.seq = 0
        if buf:
            await self._repo.insert_frames(old_id, buf)
            await self._repo.complete_lap(
                old_id, None, time.time(), is_complete=0, car_code=car
            )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_recorder.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add rexy/recorder.py tests/test_recorder.py
git commit -m "feat: add LapRecorder IDLE/RECORDING state machine"
```

---

### Task 4: Dispatcher

**Files:**
- Create: `rexy/dispatcher.py`
- Create: `tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dispatcher.py`:

```python
import asyncio
from unittest.mock import MagicMock

import pytest

from rexy.dispatcher import run_dispatcher


async def _run_once(raw_queue, ws_queue, recorder):
    """Drive dispatcher for one frame then cancel."""
    task = asyncio.create_task(run_dispatcher(raw_queue, ws_queue, recorder))
    await asyncio.sleep(0)  # yield to let dispatcher process pending items
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_frame_forwarded_to_ws_queue():
    raw_queue = asyncio.Queue()
    ws_queue = asyncio.Queue(maxsize=1)
    recorder = MagicMock()
    recorder.on_frame = MagicMock()

    await raw_queue.put({"speed_mps": 10.0})
    await _run_once(raw_queue, ws_queue, recorder)

    assert not ws_queue.empty()
    frame = ws_queue.get_nowait()
    assert frame["speed_mps"] == 10.0


async def test_frame_forwarded_to_recorder():
    raw_queue = asyncio.Queue()
    ws_queue = asyncio.Queue(maxsize=1)
    recorder = MagicMock()
    recorder.on_frame = MagicMock()

    frame = {"speed_mps": 10.0}
    await raw_queue.put(frame)
    await _run_once(raw_queue, ws_queue, recorder)

    recorder.on_frame.assert_called_once_with(frame)


async def test_drop_oldest_when_ws_queue_full():
    raw_queue = asyncio.Queue()
    ws_queue = asyncio.Queue(maxsize=1)
    recorder = MagicMock()
    recorder.on_frame = MagicMock()

    # Pre-fill ws_queue with old frame
    ws_queue.put_nowait({"speed_mps": 5.0})

    # Put newer frame in raw_queue
    await raw_queue.put({"speed_mps": 20.0})
    await _run_once(raw_queue, ws_queue, recorder)

    frame = ws_queue.get_nowait()
    assert frame["speed_mps"] == 20.0  # old frame was dropped


async def test_cancelled_error_exits_cleanly():
    raw_queue = asyncio.Queue()
    ws_queue = asyncio.Queue(maxsize=1)
    recorder = MagicMock()
    recorder.on_frame = MagicMock()

    task = asyncio.create_task(run_dispatcher(raw_queue, ws_queue, recorder))
    await asyncio.sleep(0)
    task.cancel()
    # Must not raise anything other than CancelledError
    with pytest.raises(asyncio.CancelledError):
        await task
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_dispatcher.py -v
```

Expected: `ImportError: No module named 'rexy.dispatcher'`

- [ ] **Step 3: Create `rexy/dispatcher.py`**

```python
from __future__ import annotations

import asyncio

from rexy.recorder import LapRecorder


async def run_dispatcher(
    raw_queue: asyncio.Queue,
    ws_queue: asyncio.Queue,
    recorder: LapRecorder,
) -> None:
    while True:
        frame = await raw_queue.get()
        # Drop-oldest into ws_queue: get_nowait does not yield — safe in single-writer loop
        try:
            ws_queue.put_nowait(frame)
        except asyncio.QueueFull:
            ws_queue.get_nowait()
            ws_queue.put_nowait(frame)
        recorder.on_frame(frame)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_dispatcher.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Run all tests to check no regressions**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add rexy/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: add dispatcher with drop-oldest ws_queue fanout"
```

---

## Chunk 3: Serving Layer

### Task 5: client.py — telemetry serializer and gt-telem wiring

**Files:**
- Create: `rexy/client.py`

No automated tests — requires a live PlayStation and gt-telem hardware. Verified via `make up` in Task 9.

- [ ] **Step 1: Create `rexy/client.py`**

```python
"""GT7 telemetry client: serializer, sync callbacks, event wiring."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from gt_telem import TurismoClient
from gt_telem.events.game_events import GameEvents
from gt_telem.events.race_events import RaceEvents
from gt_telem.models.telemetry import Telemetry

if TYPE_CHECKING:
    from rexy.recorder import LapRecorder


def telemetry_to_dict(t: Telemetry) -> dict:
    """Flat dict of all telemetry fields, suitable for JSON and SQLite.

    Does NOT use Telemetry.as_dict — that property returns nested Vector3D/
    WheelMetric objects and strips the flat per-axis and per-corner fields we need.
    """
    return {
        "packet_id": t.packet_id,
        "speed_mps": t.speed_mps,
        "engine_rpm": t.engine_rpm,
        "current_gear": t.bits & 0b1111,
        "suggested_gear": t.bits >> 4,
        "throttle": t.throttle,
        "brake": t.brake,
        "clutch_pedal": t.clutch_pedal,
        "clutch_engagement": t.clutch_engagement,
        "boost_pressure": t.boost_pressure,
        "fuel_level": t.fuel_level,
        "fuel_capacity": t.fuel_capacity,
        "oil_pressure": t.oil_pressure,
        "oil_temp": t.oil_temp,
        "water_temp": t.water_temp,
        "tire_fl_temp": t.tire_fl_temp,
        "tire_fr_temp": t.tire_fr_temp,
        "tire_rl_temp": t.tire_rl_temp,
        "tire_rr_temp": t.tire_rr_temp,
        "tire_fl_sus_height": t.tire_fl_sus_height,
        "tire_fr_sus_height": t.tire_fr_sus_height,
        "tire_rl_sus_height": t.tire_rl_sus_height,
        "tire_rr_sus_height": t.tire_rr_sus_height,
        "tire_fl_radius": t.tire_fl_radius,
        "tire_fr_radius": t.tire_fr_radius,
        "tire_rl_radius": t.tire_rl_radius,
        "tire_rr_radius": t.tire_rr_radius,
        "wheel_fl_rps": t.wheel_fl_rps,
        "wheel_fr_rps": t.wheel_fr_rps,
        "wheel_rl_rps": t.wheel_rl_rps,
        "wheel_rr_rps": t.wheel_rr_rps,
        "current_lap": t.current_lap,
        "total_laps": t.total_laps,
        "best_lap_time_ms": t.best_lap_time_ms,
        "last_lap_time_ms": t.last_lap_time_ms,
        "time_of_day_ms": t.time_of_day_ms,
        "race_start_pos": t.race_start_pos,
        "total_cars": t.total_cars,
        "position_x": t.position_x,
        "position_y": t.position_y,
        "position_z": t.position_z,
        "velocity_x": t.velocity_x,
        "velocity_y": t.velocity_y,
        "velocity_z": t.velocity_z,
        "ang_vel_x": t.ang_vel_x,
        "ang_vel_y": t.ang_vel_y,
        "ang_vel_z": t.ang_vel_z,
        "rotation_x": t.rotation_x,
        "rotation_y": t.rotation_y,
        "rotation_z": t.rotation_z,
        "road_plane_x": t.road_plane_x,
        "road_plane_y": t.road_plane_y,
        "road_plane_z": t.road_plane_z,
        "road_plane_dist": t.road_plane_dist,
        "body_height": t.body_height,
        "orientation": t.orientation,
        "min_alert_rpm": t.min_alert_rpm,
        "max_alert_rpm": t.max_alert_rpm,
        "calc_max_speed": t.calc_max_speed,
        "trans_rpm": t.trans_rpm,
        "trans_top_speed": t.trans_top_speed,
        "gear1": t.gear1,
        "gear2": t.gear2,
        "gear3": t.gear3,
        "gear4": t.gear4,
        "gear5": t.gear5,
        "gear6": t.gear6,
        "gear7": t.gear7,
        "gear8": t.gear8,
        "car_code": t.car_code,
        # Decoded flags — bit positions from Telemetry source
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


def setup_client(
    tc: TurismoClient,
    raw_queue: asyncio.Queue,
    recorder: LapRecorder,
    loop: asyncio.AbstractEventLoop,
    heartbeat_type: str,
) -> None:
    """Register all gt-telem callbacks. Call before tc.start().

    All callbacks are sync and communicate back to the asyncio loop via
    call_soon_threadsafe — gt-telem runs callbacks in its own thread pool.

    GameEvents and RaceEvents use class-level lists; create exactly one instance
    of each per process to avoid duplicate callback registrations.
    """
    game_events = GameEvents(tc)
    race_events = RaceEvents(tc)

    def on_frame_handler(t: Telemetry) -> None:
        frame = telemetry_to_dict(t)
        frame["ts"] = time.time()
        frame["heartbeat_type"] = heartbeat_type
        loop.call_soon_threadsafe(raw_queue.put_nowait, frame)

    def on_at_track_handler() -> None:
        # TT / practice: cars_on_track=False; current_lap not available here
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.reset_and_new_lap(1))
        )

    def on_in_race_handler() -> None:
        # Race start: cars_on_track=True, current_lap=0; on_lap_change(1) flushes it
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.reset_and_new_lap(0))
        )

    def on_race_end_handler() -> None:
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.close())
        )

    def on_lap_change_handler(new_lap_number: int) -> None:
        loop.call_soon_threadsafe(
            lambda n=new_lap_number: asyncio.create_task(recorder.flush_and_new_lap(n))
        )

    def on_track_detected_handler(track_id: int) -> None:
        loop.call_soon_threadsafe(recorder.set_track_id, track_id)

    game_events.on_at_track.append(on_at_track_handler)
    game_events.on_in_race.append(on_in_race_handler)
    game_events.on_race_end.append(on_race_end_handler)
    game_events.on_in_game_menu.append(on_race_end_handler)
    race_events.on_lap_change.append(on_lap_change_handler)
    race_events.on_track_detected.append(on_track_detected_handler)
    tc.register_callback(on_frame_handler)
```

- [ ] **Step 2: Verify import is clean**

```bash
.venv/bin/python -c "from rexy.client import telemetry_to_dict, setup_client; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add rexy/client.py
git commit -m "feat: add telemetry_to_dict serializer and gt-telem callback wiring"
```

---

### Task 6: server.py — FastAPI, WebSocket, broadcaster

**Files:**
- Create: `rexy/server.py`
- Create: `rexy/static/` (directory)

- [ ] **Step 1: Create static directory placeholder**

```bash
mkdir -p rexy/static
touch rexy/static/.gitkeep
```

`index.html` is added in Task 8. The static directory must exist before `server.py` imports.

- [ ] **Step 2: Write a failing smoke test**

Add to a new `tests/test_server.py`:

```python
import pytest
from fastapi.testclient import TestClient

from rexy.server import app


def test_ws_connect_and_disconnect():
    """Client can connect to /ws and disconnect cleanly."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            # connected — server should have added to clients set
            pass  # disconnect on context exit
        # After disconnect — no exception means clean removal


def test_ws_multiple_clients():
    """Two clients can connect simultaneously."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws"):
            with client.websocket_connect("/ws"):
                pass
```

- [ ] **Step 3: Run test — verify it fails**

```bash
.venv/bin/pytest tests/test_server.py -v
```

Expected: `ImportError: No module named 'rexy.server'`

- [ ] **Step 4: Create `rexy/server.py`**

```python
"""FastAPI application: WebSocket /ws + static file serving."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()
clients: set[WebSocket] = set()

_STATIC = Path(__file__).parent / "static"


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC), name="static")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)


async def run_broadcaster(ws_queue: asyncio.Queue, clients: set[WebSocket]) -> None:
    while True:
        frame = await ws_queue.get()
        if clients:
            await asyncio.gather(
                *[_send_safe(ws, frame) for ws in list(clients)],
                return_exceptions=True,
            )


async def _send_safe(ws: WebSocket, frame: dict) -> None:
    try:
        await ws.send_json(frame)
    except Exception:
        pass  # client removed by /ws handler on its next receive attempt
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_server.py -v
```

Expected: PASS

- [ ] **Step 6: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add rexy/server.py rexy/static/.gitkeep tests/test_server.py
git commit -m "feat: add FastAPI server with WebSocket broadcaster"
```

---

## Chunk 4: Assembly

### Task 7: \_\_main\_\_.py — wire everything together

**Files:**
- Modify: `rexy/__main__.py`

- [ ] **Step 1: Replace `rexy/__main__.py`**

```python
"""TelemetryIQ entrypoint — wires all Phase 2 components."""
from __future__ import annotations

import asyncio
import os
import time

import uvicorn
from gt_telem import TurismoClient
from gt_telem.errors.playstation_errors import (
    PlayStationNotFoundError,
    PlayStationOnStandbyError,
)

from rexy.client import setup_client
from rexy.dispatcher import run_dispatcher
from rexy.recorder import LapRecorder
from rexy.repository import TelemetryRepository
from rexy.server import app, clients, run_broadcaster


async def _main() -> None:
    ps_ip = os.environ.get("PS_IP") or None
    heartbeat_type = os.environ.get("GT7_HEARTBEAT_TYPE", "B")
    db_path = os.environ.get("DB_PATH", "/data/telemetry.db")

    # Database — must init before anything else
    repo = TelemetryRepository(db_path)
    await repo.init()
    session_id = await repo.insert_session(started_at=time.time())

    # Recorder and queues
    recorder = LapRecorder(repo=repo, session_id=session_id)
    raw_queue: asyncio.Queue = asyncio.Queue()
    ws_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    loop = asyncio.get_running_loop()

    # GT7 client — raises on PS not found / standby
    try:
        tc = TurismoClient(ps_ip=ps_ip, heartbeat_type=heartbeat_type)
    except PlayStationOnStandbyError:
        print("PlayStation is on standby. Turn it on and restart.")
        raise SystemExit(1)
    except PlayStationNotFoundError:
        print("PlayStation not found. Ensure PC and PS are on the same LAN.")
        raise SystemExit(1)

    setup_client(tc, raw_queue, recorder, loop, heartbeat_type)
    tc.start()

    # Async tasks
    dispatcher_task = asyncio.create_task(run_dispatcher(raw_queue, ws_queue, recorder))
    broadcaster_task = asyncio.create_task(run_broadcaster(ws_queue, clients))

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        tc.stop()
        dispatcher_task.cancel()
        broadcaster_task.cancel()
        await asyncio.gather(dispatcher_task, broadcaster_task, return_exceptions=True)
        await recorder.close()
        await repo.close()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import is clean**

```bash
.venv/bin/python -c "from rexy.__main__ import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run all tests — no regressions**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add rexy/__main__.py
git commit -m "feat: wire all Phase 2 components in async entrypoint"
```

---

### Task 8: index.html — live telemetry dashboard

**Files:**
- Create: `rexy/static/index.html`

- [ ] **Step 1: Create `rexy/static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TelemetryIQ</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Courier New', monospace; background: #0d0d0d; color: #e0e0e0;
         padding: 1rem; font-size: 13px; }
  #header { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
  #status { font-size: 12px; padding: 0.25rem 0.5rem; border-radius: 3px;
            background: #1a1a1a; border: 1px solid #333; }
  #status.connected { border-color: #2a7; color: #2a7; }
  #status.disconnected { border-color: #a33; color: #a33; }
  h1 { font-size: 1rem; color: #888; letter-spacing: 0.1em; }
  #dashboard { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
               gap: 0.75rem; }
  .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 4px;
          padding: 0.75rem; }
  .card h2 { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.12em;
             color: #666; margin-bottom: 0.5rem; border-bottom: 1px solid #222;
             padding-bottom: 0.35rem; }
  .row { display: flex; justify-content: space-between; padding: 0.12rem 0;
         border-bottom: 1px solid #1e1e1e; }
  .row:last-child { border-bottom: none; }
  .lbl { color: #666; }
  .val { color: #e0e0e0; font-weight: bold; text-align: right; }
  .val.highlight { color: #4af; }
  .val.warn { color: #fa4; }
  .val.active { color: #4f4; }
  .hidden { display: none; }
</style>
</head>
<body>
<div id="header">
  <h1>TelemetryIQ</h1>
  <span id="status" class="disconnected">● Connecting…</span>
</div>
<div id="dashboard">

  <div class="card" id="card-lap">
    <h2>Lap</h2>
    <div class="row"><span class="lbl">Lap / Total</span>
      <span class="val"><span id="current_lap">--</span> / <span id="total_laps">--</span></span></div>
    <div class="row"><span class="lbl">Last</span>
      <span class="val highlight" id="last_lap_time">--:--.---</span></div>
    <div class="row"><span class="lbl">Best</span>
      <span class="val highlight" id="best_lap_time">--:--.---</span></div>
    <div class="row"><span class="lbl">Cars on track</span>
      <span class="val" id="cars_on_track">--</span></div>
  </div>

  <div class="card" id="card-engine">
    <h2>Engine</h2>
    <div class="row"><span class="lbl">Speed</span>
      <span class="val highlight" id="speed_kph">-- km/h</span></div>
    <div class="row"><span class="lbl">RPM</span>
      <span class="val" id="engine_rpm">----</span></div>
    <div class="row"><span class="lbl">Gear / Suggested</span>
      <span class="val"><span id="current_gear">-</span> / <span id="suggested_gear">-</span></span></div>
    <div class="row"><span class="lbl">Throttle</span>
      <span class="val active" id="throttle_pct">--%</span></div>
    <div class="row"><span class="lbl">Brake</span>
      <span class="val warn" id="brake_pct">--%</span></div>
    <div class="row"><span class="lbl">Boost</span>
      <span class="val" id="boost_pressure">--</span></div>
    <div class="row"><span class="lbl">Fuel</span>
      <span class="val" id="fuel_pct">--%</span></div>
  </div>

  <div class="card" id="card-tires">
    <h2>Tires</h2>
    <div class="row"><span class="lbl">Temp FL/FR</span>
      <span class="val"><span id="tire_fl_temp">--</span> / <span id="tire_fr_temp">--</span> °C</span></div>
    <div class="row"><span class="lbl">Temp RL/RR</span>
      <span class="val"><span id="tire_rl_temp">--</span> / <span id="tire_rr_temp">--</span> °C</span></div>
    <div class="row"><span class="lbl">Sus FL/FR (mm)</span>
      <span class="val"><span id="tire_fl_sus_height">--</span> / <span id="tire_fr_sus_height">--</span></span></div>
    <div class="row"><span class="lbl">Sus RL/RR (mm)</span>
      <span class="val"><span id="tire_rl_sus_height">--</span> / <span id="tire_rr_sus_height">--</span></span></div>
  </div>

  <div class="card" id="card-thermal">
    <h2>Thermal</h2>
    <div class="row"><span class="lbl">Oil Temp</span>
      <span class="val" id="oil_temp">-- °C</span></div>
    <div class="row"><span class="lbl">Oil Pressure</span>
      <span class="val" id="oil_pressure">--</span></div>
    <div class="row"><span class="lbl">Water Temp</span>
      <span class="val" id="water_temp">-- °C</span></div>
  </div>

  <div class="card hidden" id="card-motion">
    <h2>Motion (Heartbeat B)</h2>
    <div class="row"><span class="lbl">Steering (rad)</span>
      <span class="val" id="wheel_rotation_radians">--</span></div>
    <div class="row"><span class="lbl">Slip angle</span>
      <span class="val" id="filler_float_fb">--</span></div>
    <div class="row"><span class="lbl">Sway (lat G)</span>
      <span class="val" id="sway">--</span></div>
    <div class="row"><span class="lbl">Heave (vert G)</span>
      <span class="val" id="heave">--</span></div>
    <div class="row"><span class="lbl">Surge (lon G)</span>
      <span class="val" id="surge">--</span></div>
  </div>

  <div class="card hidden" id="card-filtered">
    <h2>Filtered (Heartbeat ~)</h2>
    <div class="row"><span class="lbl">Throttle filt</span>
      <span class="val active" id="throttle_filtered_pct">--%</span></div>
    <div class="row"><span class="lbl">Brake filt</span>
      <span class="val warn" id="brake_filtered_pct">--%</span></div>
    <div class="row"><span class="lbl">Energy recovery</span>
      <span class="val" id="energy_recovery">--</span></div>
  </div>

  <div class="card" id="card-status">
    <h2>Status</h2>
    <div class="row"><span class="lbl">TCS</span>
      <span class="val" id="tcs_active">--</span></div>
    <div class="row"><span class="lbl">ASM</span>
      <span class="val" id="asm_active">--</span></div>
    <div class="row"><span class="lbl">Rev limit</span>
      <span class="val" id="rev_limit">--</span></div>
    <div class="row"><span class="lbl">Shift (RPM)</span>
      <span class="val"><span id="min_alert_rpm">----</span> – <span id="max_alert_rpm">----</span></span></div>
    <div class="row"><span class="lbl">Hand brake</span>
      <span class="val" id="hand_brake_active">--</span></div>
    <div class="row"><span class="lbl">Car code</span>
      <span class="val" id="car_code">--</span></div>
  </div>

  <div class="card" id="card-position">
    <h2>Position</h2>
    <div class="row"><span class="lbl">X / Y / Z</span>
      <span class="val" style="font-size:11px">
        <span id="position_x">--</span>,
        <span id="position_y">--</span>,
        <span id="position_z">--</span></span></div>
    <div class="row"><span class="lbl">Vel X/Y/Z</span>
      <span class="val" style="font-size:11px">
        <span id="velocity_x">--</span>,
        <span id="velocity_y">--</span>,
        <span id="velocity_z">--</span></span></div>
    <div class="row"><span class="lbl">Road plane dist</span>
      <span class="val" id="road_plane_dist">--</span></div>
  </div>

  <div class="card" id="card-race">
    <h2>Race</h2>
    <div class="row"><span class="lbl">Start pos / Cars</span>
      <span class="val"><span id="race_start_pos">--</span> / <span id="total_cars">--</span></span></div>
    <div class="row"><span class="lbl">Time of day</span>
      <span class="val" id="time_of_day_ms">--</span></div>
    <div class="row"><span class="lbl">Heartbeat</span>
      <span class="val" id="heartbeat_type">--</span></div>
  </div>

</div>
<script>
  let latest = {};
  let retryDelay = 1000;
  const maxDelay = 30000;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    const statusEl = document.getElementById('status');

    ws.onopen = () => {
      statusEl.textContent = '● Connected';
      statusEl.className = 'connected';
      retryDelay = 1000;
    };
    ws.onmessage = e => { latest = JSON.parse(e.data); };
    ws.onclose = () => {
      statusEl.textContent = `● Reconnecting (${(retryDelay/1000).toFixed(0)}s)…`;
      statusEl.className = 'disconnected';
      setTimeout(() => {
        retryDelay = Math.min(retryDelay * 2, maxDelay);
        connect();
      }, retryDelay);
    };
  }

  function fmtMs(ms) {
    if (ms === null || ms === undefined || ms === -1) return '--:--.---';
    const t = Math.max(0, Math.floor(ms));
    const m = Math.floor(t / 60000);
    const s = Math.floor((t % 60000) / 1000);
    const f = t % 1000;
    return `${m}:${String(s).padStart(2,'0')}.${String(f).padStart(3,'0')}`;
  }

  function fmtBool(v) { return v ? 'YES' : 'no'; }

  function set(id, v, fallback = '--') {
    const el = document.getElementById(id);
    if (el) el.textContent = (v === null || v === undefined) ? fallback : v;
  }

  function render() {
    const d = latest;
    if (d.speed_mps !== undefined) {
      // Lap
      set('current_lap', d.current_lap);
      set('total_laps', d.total_laps);
      set('last_lap_time', fmtMs(d.last_lap_time_ms));
      set('best_lap_time', fmtMs(d.best_lap_time_ms));
      set('cars_on_track', fmtBool(d.cars_on_track));

      // Engine
      set('speed_kph', (d.speed_mps * 3.6).toFixed(1) + ' km/h');
      set('engine_rpm', d.engine_rpm?.toFixed(0));
      set('current_gear', d.current_gear === 0 ? 'R' : (d.current_gear >= 15 ? 'N' : d.current_gear));
      set('suggested_gear', (d.suggested_gear >= 15 || !d.suggested_gear) ? '--' : d.suggested_gear);
      set('throttle_pct', ((d.throttle ?? 0) / 255 * 100).toFixed(0) + '%');
      set('brake_pct', ((d.brake ?? 0) / 255 * 100).toFixed(0) + '%');
      set('boost_pressure', d.boost_pressure?.toFixed(2));
      set('fuel_pct', d.fuel_capacity > 0
        ? ((d.fuel_level / d.fuel_capacity) * 100).toFixed(0) + '%' : '--');

      // Tires
      set('tire_fl_temp', d.tire_fl_temp?.toFixed(1));
      set('tire_fr_temp', d.tire_fr_temp?.toFixed(1));
      set('tire_rl_temp', d.tire_rl_temp?.toFixed(1));
      set('tire_rr_temp', d.tire_rr_temp?.toFixed(1));
      set('tire_fl_sus_height', d.tire_fl_sus_height?.toFixed(1));
      set('tire_fr_sus_height', d.tire_fr_sus_height?.toFixed(1));
      set('tire_rl_sus_height', d.tire_rl_sus_height?.toFixed(1));
      set('tire_rr_sus_height', d.tire_rr_sus_height?.toFixed(1));

      // Thermal
      set('oil_temp', d.oil_temp?.toFixed(1) + ' °C');
      set('oil_pressure', d.oil_pressure?.toFixed(2));
      set('water_temp', d.water_temp?.toFixed(1) + ' °C');

      // Motion (B only)
      const isB = d.heartbeat_type === 'B';
      document.getElementById('card-motion').classList.toggle('hidden', !isB);
      if (isB) {
        set('wheel_rotation_radians', d.wheel_rotation_radians?.toFixed(3));
        set('filler_float_fb', d.filler_float_fb?.toFixed(3));
        set('sway', d.sway?.toFixed(3));
        set('heave', d.heave?.toFixed(3));
        set('surge', d.surge?.toFixed(3));
      }

      // Filtered (~ only)
      const isTilde = d.heartbeat_type === '~';
      document.getElementById('card-filtered').classList.toggle('hidden', !isTilde);
      if (isTilde) {
        set('throttle_filtered_pct', ((d.throttle_filtered ?? 0) / 255 * 100).toFixed(0) + '%');
        set('brake_filtered_pct', ((d.brake_filtered ?? 0) / 255 * 100).toFixed(0) + '%');
        set('energy_recovery', d.energy_recovery?.toFixed(3));
      }

      // Status
      set('tcs_active', fmtBool(d.tcs_active));
      set('asm_active', fmtBool(d.asm_active));
      set('rev_limit', fmtBool(d.rev_limit));
      set('min_alert_rpm', d.min_alert_rpm?.toFixed(0));
      set('max_alert_rpm', d.max_alert_rpm?.toFixed(0));
      set('hand_brake_active', fmtBool(d.hand_brake_active));
      set('car_code', d.car_code);

      // Position
      set('position_x', d.position_x?.toFixed(1));
      set('position_y', d.position_y?.toFixed(1));
      set('position_z', d.position_z?.toFixed(1));
      set('velocity_x', d.velocity_x?.toFixed(2));
      set('velocity_y', d.velocity_y?.toFixed(2));
      set('velocity_z', d.velocity_z?.toFixed(2));
      set('road_plane_dist', d.road_plane_dist?.toFixed(3));

      // Race
      set('race_start_pos', d.race_start_pos);
      set('total_cars', d.total_cars);
      set('time_of_day_ms', fmtMs(d.time_of_day_ms));
      set('heartbeat_type', d.heartbeat_type);
    }
    requestAnimationFrame(render);
  }

  connect();
  requestAnimationFrame(render);
</script>
</body>
</html>
```

- [ ] **Step 2: Verify static file is served**

```bash
.venv/bin/python -c "
import asyncio
from fastapi.testclient import TestClient
from rexy.server import app
with TestClient(app) as c:
    r = c.get('/')
    print(r.status_code)
    assert r.status_code == 200
    print('OK')
"
```

Expected: `200\nOK`

- [ ] **Step 3: Run all tests**

```bash
.venv/bin/pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add rexy/static/index.html rexy/static/.gitkeep
git commit -m "feat: add live telemetry dashboard with all field cards"
```

---

### Task 9: Dockerfile + integration verification

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Update `Dockerfile`** — add `/data` directory

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default DB location for Docker volume mount
RUN mkdir -p /data

CMD ["python", "-m", "rexy"]
```

- [ ] **Step 2: Run the full test suite**

```bash
.venv/bin/pytest tests/ -v --tb=short
```

Expected: all PASS. Fix any failures before proceeding.

- [ ] **Step 3: Verify Docker build succeeds**

```bash
make build
```

Expected: image builds without errors

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: create /data directory in container for SQLite volume mount"
```

- [ ] **Step 5: Final commit — update tasks/02-core-feature.md**

Mark Phase 2 task complete:

```markdown
# Task: Telemetry recording

**Phase**: 2 — Recording
**Status**: Complete ✅
```

```bash
git add tasks/02-core-feature.md
git commit -m "docs: mark Phase 2 telemetry recording task complete"
```

---

## Integration verification (requires GT7 + PlayStation)

After `make up` on Linux/Raspberry Pi or `python -m rexy` on macOS with gt-telem installed on host:

1. Open `http://<host>:8000` — dashboard loads with "Connecting…" status
2. Turn on GT7 — status changes to "● Connected", all fields populate at ~60Hz
3. Complete a lap — `laps` table gets a row with `is_complete=1`
4. Inspect DB: `docker exec <container> sqlite3 /data/telemetry.db "SELECT id, lap_number, lap_time_ms, is_complete FROM laps;"`
5. `docker compose down && docker compose up` — `laps` data persists from Docker volume
