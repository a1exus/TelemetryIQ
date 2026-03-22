# Phase 4 Part 1 — Session Browser & Car/Track Identity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sessions as first-class DB entities with car/track identity, expose them via two new REST endpoints, and redesign the `/compare` sidebar into a session browser with nested lap rows and delta-to-best.

**Architecture:** The existing `sessions` table gains `track_id`, `car_code`, and `completed_at` via a SQLite migration (user_version 1→2). `LapRecorder` becomes session-lifecycle-aware: it creates a session row on `on_at_track`/`on_in_race` events and silently skips recording when no session is active. Two new REST endpoints expose session and lap data. The `/compare` sidebar is rebuilt in vanilla JS to show sessions grouped with nested lap rows, most recent expanded by default.

**Tech Stack:** Python 3.11+, aiosqlite, FastAPI, vanilla JS, SQLite WAL mode, pytest + pytest-asyncio

---

## File Map

| File | Change |
|------|--------|
| `rexy/repository.py` | Migration v1→v2; new `update_session_track`, `update_session_car`, `complete_session`, `list_sessions`, `list_session_laps` methods |
| `rexy/recorder.py` | Remove `session_id` from `__init__`; add `start_session()`, `close_session()`; guard on `_session_id`; update `set_track_id` and `flush_and_new_lap` |
| `rexy/client.py` | Wire `start_session`/`close_session` into `on_at_track`, `on_in_race`, `on_in_game_menu`, `on_race_end` |
| `rexy/__main__.py` | Remove `insert_session` call; update `LapRecorder` instantiation |
| `rexy/server.py` | Add `GET /sessions` and `GET /sessions/{id}/laps` endpoints |
| `rexy/static/cars.json` | Create (empty `{}`) |
| `rexy/static/tracks.json` | Create (empty `{}`) |
| `rexy/static/compare.html` | Replace flat lap list with session-grouped sidebar |
| `pytest.ini` | Configure asyncio_mode = auto |
| `tests/__init__.py` | Create (empty, makes tests/ a package) |
| `tests/test_repository.py` | Migration tests, session method tests |

---

### Task 1: Test Infrastructure

pytest and pytest-asyncio are already in `requirements.txt`. Just need `pytest.ini` for asyncio mode and an empty `tests/` package.

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/test_repository.py` (stub)

- [ ] **Step 1: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Create tests/__init__.py**

Empty file.

- [ ] **Step 3: Create stub test file**

Create `tests/test_repository.py`:
```python
# Tests for TelemetryRepository — migration and session methods
```

- [ ] **Step 4: Run pytest to verify setup**

Run: `python -m pytest tests/ -v`
Expected: `no tests ran`, exit 0

- [ ] **Step 5: Commit**

```bash
git add pytest.ini tests/__init__.py tests/test_repository.py
git commit -m "test: set up pytest infrastructure with asyncio_mode=auto"
```

---

### Task 2: DB Migration v1 → v2

The `sessions` table gains `track_id INTEGER`, `car_code INTEGER`, and `completed_at REAL`.

**Files:**
- Modify: `rexy/repository.py:124-127`
- Modify: `tests/test_repository.py`

- [ ] **Step 1: Write failing migration tests**

Replace the stub in `tests/test_repository.py`:

```python
import os
import tempfile

import aiosqlite
import pytest

from rexy.repository import TelemetryRepository


async def _make_v1_db(path: str) -> None:
    """Create a version-1 database (sessions table without new columns)."""
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE sessions (
                id         INTEGER PRIMARY KEY,
                started_at REAL NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE laps (
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
        """)
        await db.execute("""
            CREATE TABLE frames (
                lap_id INTEGER NOT NULL,
                seq    INTEGER NOT NULL,
                ts     REAL    NOT NULL,
                PRIMARY KEY (lap_id, seq)
            )
        """)
        await db.commit()
        await db.execute("PRAGMA user_version = 1")


async def test_migration_v1_to_v2_adds_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        await _make_v1_db(path)
        repo = TelemetryRepository(path)
        await repo.init()
        await repo.close()

        async with aiosqlite.connect(path) as db:
            cur = await db.execute("PRAGMA user_version")
            version = (await cur.fetchone())[0]
            assert version == 2

            cur = await db.execute("PRAGMA table_info(sessions)")
            cols = {row[1] for row in await cur.fetchall()}
            assert "track_id" in cols
            assert "car_code" in cols
            assert "completed_at" in cols
    finally:
        os.unlink(path)


async def test_migration_v2_is_noop():
    """Running init() on a v2 DB must not raise."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        await _make_v1_db(path)
        repo = TelemetryRepository(path)
        await repo.init()   # v1 -> v2
        await repo.close()

        repo2 = TelemetryRepository(path)
        await repo2.init()  # v2 -> v2 (noop)
        await repo2.close()
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run to verify tests fail**

Run: `python -m pytest tests/test_repository.py::test_migration_v1_to_v2_adds_columns -v`
Expected: FAIL — `assert "track_id" in cols`

- [ ] **Step 3: Implement migration in repository.py**

In `rexy/repository.py`, replace:
```python
        elif version == 1:
            pass
        else:
            raise RuntimeError(f"unsupported schema version: {version}")
```

With:
```python
        elif version == 1:
            await self.db.execute("ALTER TABLE sessions ADD COLUMN track_id INTEGER")
            await self.db.execute("ALTER TABLE sessions ADD COLUMN car_code INTEGER")
            await self.db.execute("ALTER TABLE sessions ADD COLUMN completed_at REAL")
            await self.db.commit()
            await self.db.execute("PRAGMA user_version = 2")
        elif version == 2:
            pass
        else:
            raise RuntimeError(f"unsupported schema version: {version}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_repository.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add rexy/repository.py tests/test_repository.py pytest.ini tests/__init__.py
git commit -m "feat: sessions schema migration v1->v2 (track_id, car_code, completed_at)"
```

---

### Task 3: New Repository Session Methods

Five new methods on `TelemetryRepository`.

**Files:**
- Modify: `rexy/repository.py`
- Modify: `tests/test_repository.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_repository.py`:

```python
async def _make_v2_repo() -> tuple[TelemetryRepository, str]:
    """Create an initialized v2 repo. Caller must close() and unlink path."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = f.name
    f.close()
    repo = TelemetryRepository(path)
    await repo.init()
    return repo, path


async def test_update_session_track():
    repo, path = await _make_v2_repo()
    try:
        sid = await repo.insert_session(started_at=1000.0)
        await repo.update_session_track(sid, 40)
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("SELECT track_id FROM sessions WHERE id=?", (sid,))
            row = await cur.fetchone()
        assert row[0] == 40
    finally:
        await repo.close()
        os.unlink(path)


async def test_update_session_car_only_updates_if_null():
    repo, path = await _make_v2_repo()
    try:
        sid = await repo.insert_session(started_at=1000.0)
        await repo.update_session_car(sid, 3520)
        await repo.update_session_car(sid, 9999)  # second call: should be ignored
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("SELECT car_code FROM sessions WHERE id=?", (sid,))
            row = await cur.fetchone()
        assert row[0] == 3520  # first write wins
    finally:
        await repo.close()
        os.unlink(path)


async def test_complete_session():
    repo, path = await _make_v2_repo()
    try:
        sid = await repo.insert_session(started_at=1000.0)
        await repo.complete_session(sid, completed_at=2000.0)
        async with aiosqlite.connect(path) as db:
            cur = await db.execute("SELECT completed_at FROM sessions WHERE id=?", (sid,))
            row = await cur.fetchone()
        assert row[0] == 2000.0
    finally:
        await repo.close()
        os.unlink(path)


async def test_list_sessions_excludes_empty_sessions():
    repo, path = await _make_v2_repo()
    try:
        sid = await repo.insert_session(started_at=1000.0)
        # No laps yet -> should not appear
        result = await repo.list_sessions()
        assert result == []

        # Add one complete lap
        lid = await repo.insert_lap(1, sid, None, 1000.0)
        await repo.complete_lap(lid, 101887, 1101.887, 1, car_code=3520)

        result = await repo.list_sessions()
        assert len(result) == 1
        assert result[0]["id"] == sid
        assert result[0]["lap_count"] == 1
        assert result[0]["best_lap_time_ms"] == 101887
    finally:
        await repo.close()
        os.unlink(path)


async def test_list_session_laps_excludes_lap0_and_incomplete():
    repo, path = await _make_v2_repo()
    try:
        sid = await repo.insert_session(started_at=1000.0)

        # Lap 0 (complete) -- must be excluded from UI
        lid0 = await repo.insert_lap(0, sid, None, 1000.0)
        await repo.complete_lap(lid0, 105000, 1105.0, 1, car_code=3520)

        # Lap 1 (complete) -- must be included
        lid1 = await repo.insert_lap(1, sid, None, 1105.0)
        await repo.complete_lap(lid1, 101887, 1207.0, 1, car_code=3520)

        # Lap 2 (incomplete) -- must be excluded
        lid2 = await repo.insert_lap(2, sid, None, 1207.0)
        await repo.complete_lap(lid2, None, 1300.0, 0, car_code=3520)

        laps = await repo.list_session_laps(sid)
        assert len(laps) == 1
        assert laps[0]["lap_number"] == 1
        assert laps[0]["lap_time_ms"] == 101887
    finally:
        await repo.close()
        os.unlink(path)
```

- [ ] **Step 2: Run to verify tests fail**

Run: `python -m pytest tests/test_repository.py -k "test_update_session or test_complete_session or test_list_session" -v`
Expected: FAIL — `AttributeError: 'TelemetryRepository' object has no attribute 'update_session_track'`

- [ ] **Step 3: Add five new methods to repository.py**

Add after the `complete_lap` method:

```python
    async def update_session_track(self, session_id: int, track_id: int) -> None:
        await self.db.execute(
            "UPDATE sessions SET track_id=? WHERE id=?", (track_id, session_id)
        )
        await self.db.commit()

    async def update_session_car(self, session_id: int, car_code: int) -> None:
        await self.db.execute(
            "UPDATE sessions SET car_code=? WHERE id=? AND car_code IS NULL",
            (car_code, session_id),
        )
        await self.db.commit()

    async def complete_session(self, session_id: int, completed_at: float) -> None:
        await self.db.execute(
            "UPDATE sessions SET completed_at=? WHERE id=?", (completed_at, session_id)
        )
        await self.db.commit()

    async def list_sessions(self) -> list[dict]:
        """Return all sessions with at least one complete lap, newest first."""
        cur = await self.db.execute(
            """
            SELECT s.id, s.started_at, s.completed_at, s.track_id, s.car_code,
                   COUNT(l.id) AS lap_count,
                   MIN(l.lap_time_ms) AS best_lap_time_ms
            FROM sessions s
            JOIN laps l ON l.session_id = s.id AND l.is_complete = 1
            GROUP BY s.id
            HAVING COUNT(l.id) > 0
            ORDER BY s.started_at DESC
            """
        )
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]

    async def list_session_laps(self, session_id: int) -> list[dict]:
        """Return complete laps with lap_number > 0 for a session, ordered by lap_number."""
        cur = await self.db.execute(
            "SELECT id, lap_number, lap_time_ms FROM laps "
            "WHERE session_id=? AND is_complete=1 AND lap_number > 0 "
            "ORDER BY lap_number",
            (session_id,),
        )
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]
```

- [ ] **Step 4: Run all repository tests**

Run: `python -m pytest tests/test_repository.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add rexy/repository.py tests/test_repository.py
git commit -m "feat: add session repository methods (update track/car, complete, list)"
```

---

### Task 4: LapRecorder Session Lifecycle

**Files:**
- Modify: `rexy/recorder.py`

Changes:
1. `__init__` drops `session_id` param; sets `self._session_id = None`
2. `reset_and_new_lap` / `flush_and_new_lap` skip silently when `_session_id is None`
3. New `start_session()`: calls `repo.insert_session`, sets `_session_id`
4. New `close_session()`: flushes partial lap, calls `repo.complete_session`, clears `_session_id`
5. `set_track_id` dispatches `create_task(update_session_track(...))` if session is active
6. `flush_and_new_lap` calls `update_session_car` after completing the old lap

- [ ] **Step 1: Rewrite recorder.py**

Replace the full content of `rexy/recorder.py`:

```python
from __future__ import annotations

import asyncio
import time
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rexy.repository import TelemetryRepository


class State(Enum):
    IDLE = auto()
    RECORDING = auto()


class LapRecorder:
    def __init__(self, repo: TelemetryRepository) -> None:
        self._repo = repo
        self._session_id: int | None = None
        self._lock = asyncio.Lock()
        self.state = State.IDLE
        self.current_lap_id: int | None = None
        self.current_track_id: int | None = None
        self.current_lap_started_at: float | None = None
        self.lap_buffer: list[dict] = []
        self.seq: int = 0

    # --- sync methods (safe to call from asyncio event loop without await) ---

    def set_track_id(self, track_id: int) -> None:
        self.current_track_id = track_id
        if self._session_id is not None:
            asyncio.create_task(
                self._repo.update_session_track(self._session_id, track_id)
            )

    def on_frame(self, frame: dict) -> None:
        if self.state != State.RECORDING:
            return
        # Create new dict to avoid mutating the frame shared with ws_queue
        self.lap_buffer.append({**frame, "seq": self.seq})
        self.seq += 1

    # --- async lifecycle methods ---

    async def start_session(self) -> None:
        self._session_id = await self._repo.insert_session(started_at=time.time())

    async def close_session(self) -> None:
        if self._session_id is None:
            return
        async with self._lock:
            if self.state == State.RECORDING:
                await self._flush_partial()
                self.state = State.IDLE
        await self._repo.complete_session(self._session_id, completed_at=time.time())
        self._session_id = None

    async def reset_and_new_lap(self, lap_number: int) -> None:
        if self._session_id is None:
            return
        async with self._lock:
            if self.state == State.RECORDING:
                await self._flush_partial()
            self.current_lap_started_at = time.time()
            self.current_lap_id = await self._repo.insert_lap(
                lap_number, self._session_id, self.current_track_id,
                started_at=self.current_lap_started_at,
            )
            self.lap_buffer = []
            self.seq = 0
            self.state = State.RECORDING

    async def flush_and_new_lap(self, new_lap_number: int) -> None:
        if self._session_id is None:
            return
        async with self._lock:
            if self.state != State.RECORDING:
                return
            buf = self.lap_buffer
            car = buf[0].get("car_code") if buf else None
            raw = buf[-1].get("last_lap_time_ms") if buf else None
            lap_time_ms = None if (raw is None or raw == -1) else raw
            old_id = self.current_lap_id
            self.lap_buffer = []
            self.seq = 0

            if buf:
                await self._repo.insert_frames(old_id, buf)
            await self._repo.complete_lap(old_id, lap_time_ms, time.time(), 1, car_code=car)
            if car is not None:
                await self._repo.update_session_car(self._session_id, car)

            self.current_lap_started_at = time.time()
            self.current_lap_id = await self._repo.insert_lap(
                new_lap_number, self._session_id, self.current_track_id,
                started_at=self.current_lap_started_at,
            )

    async def close(self) -> None:
        """Flush partial lap on shutdown (does not complete the session)."""
        async with self._lock:
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
            await self._repo.complete_lap(old_id, None, time.time(), 0, car_code=car)
```

- [ ] **Step 2: Run repository tests (verify no import regressions)**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add rexy/recorder.py
git commit -m "feat: LapRecorder session lifecycle (start_session, close_session, session guard)"
```

---

### Task 5: Wire Events in client.py and __main__.py

**Files:**
- Modify: `rexy/client.py`
- Modify: `rexy/__main__.py`

`on_at_track` and `on_in_race` must call `start_session()` then the lap method sequentially — chain them in a single coroutine to avoid a race between `_session_id` being set and the lap insert.

- [ ] **Step 1: Update on_at_track_handler**

Replace:
```python
    def on_at_track_handler() -> None:
        print("[gt-telem] event: on_at_track", flush=True)
        # TT / practice: cars_on_track=False; current_lap not available here
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.reset_and_new_lap(1))
        )
```

With:
```python
    def on_at_track_handler() -> None:
        print("[gt-telem] event: on_at_track", flush=True)

        async def _start_and_lap() -> None:
            await recorder.start_session()
            await recorder.reset_and_new_lap(1)

        loop.call_soon_threadsafe(lambda: asyncio.create_task(_start_and_lap()))
```

- [ ] **Step 2: Update on_in_race_handler**

Replace:
```python
    def on_in_race_handler() -> None:
        print("[gt-telem] event: on_in_race", flush=True)
        # Race start: cars_on_track=True, current_lap=0; on_lap_change(1) flushes it
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.reset_and_new_lap(0))
        )
```

With:
```python
    def on_in_race_handler() -> None:
        print("[gt-telem] event: on_in_race", flush=True)

        async def _start_and_lap() -> None:
            await recorder.start_session()
            await recorder.reset_and_new_lap(0)

        loop.call_soon_threadsafe(lambda: asyncio.create_task(_start_and_lap()))
```

- [ ] **Step 3: Update on_in_game_menu_handler**

Replace:
```python
    def on_in_game_menu_handler() -> None:
        print("[gt-telem] event: on_in_game_menu", flush=True)
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.close())
        )
```

With:
```python
    def on_in_game_menu_handler() -> None:
        print("[gt-telem] event: on_in_game_menu", flush=True)
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.close_session())
        )
```

- [ ] **Step 4: Update on_race_end_handler**

Replace:
```python
    def on_race_end_handler() -> None:
        print("[gt-telem] event: on_race_end", flush=True)
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.close())
        )
```

With:
```python
    def on_race_end_handler() -> None:
        print("[gt-telem] event: on_race_end", flush=True)
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.close_session())
        )
```

- [ ] **Step 5: Update __main__.py**

Remove:
```python
    session_id = await repo.insert_session(started_at=time.time())
```

Change:
```python
    recorder = LapRecorder(repo=repo, session_id=session_id)
```
To:
```python
    recorder = LapRecorder(repo=repo)
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add rexy/client.py rexy/__main__.py
git commit -m "feat: wire session start/close to on_at_track, on_in_race, on_in_game_menu, on_race_end"
```

---

### Task 6: New API Endpoints

**Files:**
- Modify: `rexy/server.py`

- [ ] **Step 1: Add both session endpoints after the existing get_laps endpoint**

In `rexy/server.py`, add after the `get_laps` function (after line 76):

```python
@app.get("/sessions")
async def get_sessions():
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    return await _repo.list_sessions()


@app.get("/sessions/{session_id}/laps")
async def get_session_laps(session_id: int):
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    return await _repo.list_session_laps(session_id)
```

- [ ] **Step 2: Verify endpoints manually**

Start the app: `python -m rexy`

```bash
curl http://localhost:8000/sessions
# Expected: [] (empty) or list of session objects

curl http://localhost:8000/sessions/1/laps
# Expected: [] or list of lap objects
```

- [ ] **Step 3: Commit**

```bash
git add rexy/server.py
git commit -m "feat: add GET /sessions and GET /sessions/{id}/laps endpoints"
```

---

### Task 7: Static Data Files

**Files:**
- Create: `rexy/static/cars.json`
- Create: `rexy/static/tracks.json`

- [ ] **Step 1: Create empty cars.json**

Create `rexy/static/cars.json` with content `{}`.

- [ ] **Step 2: Create empty tracks.json**

Create `rexy/static/tracks.json` with content `{}`.

- [ ] **Step 3: Verify static file serving**

```bash
curl http://localhost:8000/static/cars.json
# Expected: {}
curl http://localhost:8000/static/tracks.json
# Expected: {}
```

- [ ] **Step 4: Commit**

```bash
git add rexy/static/cars.json rexy/static/tracks.json
git commit -m "feat: add empty cars.json and tracks.json static data files"
```

---

### Task 8: UI — Session-Grouped Sidebar

Replace the flat lap list in `/compare` with a session browser. The charts, track map, and delta graph are unchanged.

**Files:**
- Modify: `rexy/static/compare.html`

**What changes:**
- CSS: add `.session-item`, `.session-hdr`, `.session-arrow`, `.session-track`, `.session-date`, `.session-meta`, `.session-laps`, `.session-laps.open`, `.lap-row`, `.lap-num-col`, `.lap-time-col`, `.lap-delta-col`, `.lap-star`, `.lap-row-btns`; remove `.lap-item`, `.lap-num`, `.lap-time`, `.lap-meta`
- JS: replace `loadLapList()` and the `state` declaration with the session browser functions below. `fetchFrames`, `selectLap`, `updateButtonStates` are replaced with updated versions.

Note: All dynamic text (track names, car names, lap numbers, times) is set via `textContent` or numeric formatting, never via `innerHTML`, to avoid XSS.

- [ ] **Step 1: Add new CSS classes to the style block**

Append inside `<style>`, after `.btn-b.active` and before `#sidebar-msg`:

```css
  .session-item  { border-bottom: 1px solid #1a1a1a; }
  .session-hdr   { cursor: pointer; user-select: none; padding: 0.45rem 0.5rem;
                   line-height: 1.4; }
  .session-hdr:hover { background: #181818; }
  .session-arrow { color: #555; font-size: 0.75rem; margin-right: 0.25rem; }
  .session-track { font-size: 0.8rem; font-weight: bold; }
  .session-date  { float: right; color: #555; font-size: 0.7rem; }
  .session-meta  { font-size: 0.65rem; color: #555; margin-top: 0.1rem; }
  .session-laps  { display: none; }
  .session-laps.open { display: block; }
  .lap-row       { display: flex; align-items: center; gap: 0.25rem;
                   padding: 0.22rem 0.5rem; font-size: 0.72rem; }
  .lap-row:hover { background: #141414; }
  .lap-num-col   { width: 3.4rem; color: #555; }
  .lap-time-col  { width: 6rem; color: #4af; }
  .lap-delta-col { width: 5rem; color: #888; }
  .lap-star      { color: #fa4; }
  .lap-row-btns  { margin-left: auto; display: flex; gap: 0.2rem; }
```

- [ ] **Step 2: Remove old CSS classes**

Remove from `<style>` the rules for `.lap-item`, `.lap-num`, `.lap-time`, `.lap-meta` (replaced by session CSS).

- [ ] **Step 3: Replace sidebar JS**

In the `<script>` block, replace from `const state = { lapA: null, lapB: null, cache: {} };` through `loadLapList();` with the following. Note: `fmtMs` already exists in the file and must NOT be duplicated.

```javascript
// ── Session browser ────────────────────────────────────────────────────────────
const state = { lapA: null, lapB: null, cache: {}, sessions: [], cars: {}, tracks: {}, lapCache: new Map() };

function fmtDate(unix) {
  const d = new Date(unix * 1000);
  return d.toISOString().slice(0, 16).replace('T', ' ');
}

function fmtDelta(deltaMs) {
  if (deltaMs === 0) return '\u2605';
  const sign = deltaMs > 0 ? '+' : '\u2212';
  return sign + (Math.abs(deltaMs) / 1000).toFixed(3) + 's';
}

async function fetchSessionLaps(sessionId) {
  if (state.lapCache.has(sessionId)) return state.lapCache.get(sessionId);
  const laps = await fetch('/sessions/' + sessionId + '/laps').then(r => r.json());
  state.lapCache.set(sessionId, laps);
  return laps;
}

async function populateLaps(lapsDiv, session) {
  const laps = await fetchSessionLaps(session.id);
  while (lapsDiv.firstChild) lapsDiv.removeChild(lapsDiv.firstChild);
  if (!laps.length) {
    const msg = document.createElement('p');
    msg.style.cssText = 'color:#555;font-size:0.7rem;padding:0.3rem 0.5rem';
    msg.textContent = 'No complete laps';
    lapsDiv.appendChild(msg);
    return;
  }
  const best = session.best_lap_time_ms;
  laps.forEach(lap => {
    const lapWithCar = Object.assign({}, lap, { car_code: session.car_code });
    const isBest = lap.lap_time_ms === best;

    const row = document.createElement('div');
    row.className = 'lap-row';
    row.dataset.lapId = String(lap.id);

    const numEl = document.createElement('span');
    numEl.className = 'lap-num-col';
    numEl.textContent = 'Lap ' + lap.lap_number;

    const timeEl = document.createElement('span');
    timeEl.className = 'lap-time-col';
    timeEl.textContent = fmtMs(lap.lap_time_ms);

    const deltaEl = document.createElement('span');
    deltaEl.className = 'lap-delta-col' + (isBest ? ' lap-star' : '');
    deltaEl.textContent = fmtDelta(lap.lap_time_ms - best);

    const btnsEl = document.createElement('span');
    btnsEl.className = 'lap-row-btns';

    const btnA = document.createElement('button');
    btnA.className = 'btn-a';
    btnA.textContent = 'A';
    btnA.addEventListener('click', () => selectLap(lapWithCar, 'A'));

    const btnB = document.createElement('button');
    btnB.className = 'btn-b';
    btnB.textContent = 'B';
    btnB.addEventListener('click', () => selectLap(lapWithCar, 'B'));

    btnsEl.appendChild(btnA);
    btnsEl.appendChild(btnB);
    row.appendChild(numEl);
    row.appendChild(timeEl);
    row.appendChild(deltaEl);
    row.appendChild(btnsEl);
    lapsDiv.appendChild(row);
  });
}

function renderSidebar() {
  const sidebar = document.getElementById('sidebar');
  while (sidebar.firstChild) sidebar.removeChild(sidebar.firstChild);

  if (!state.sessions.length) {
    const msg = document.createElement('p');
    msg.id = 'sidebar-msg';
    msg.textContent = 'No sessions yet.';
    sidebar.appendChild(msg);
    return;
  }

  state.sessions.forEach((session, idx) => {
    const trackName = session.track_id != null
      ? (state.tracks[String(session.track_id)] || 'Track ' + session.track_id)
      : 'Unknown Track';
    const carName = session.car_code != null
      ? (state.cars[String(session.car_code)] || 'Car ' + session.car_code)
      : 'Unknown Car';
    const lapWord = session.lap_count !== 1 ? ' laps' : ' lap';

    const wrapper = document.createElement('div');
    wrapper.className = 'session-item';

    // Header line 1: arrow + track + date
    const hdr = document.createElement('div');
    hdr.className = 'session-hdr';

    const line1 = document.createElement('div');
    const arrowEl = document.createElement('span');
    arrowEl.className = 'session-arrow';
    arrowEl.textContent = idx === 0 ? '\u25bc' : '\u25b6';
    const trackEl = document.createElement('span');
    trackEl.className = 'session-track';
    trackEl.textContent = trackName;
    const dateEl = document.createElement('span');
    dateEl.className = 'session-date';
    dateEl.textContent = fmtDate(session.started_at);
    line1.appendChild(arrowEl);
    line1.appendChild(trackEl);
    line1.appendChild(dateEl);

    // Header line 2: car + lap count + best time
    const metaEl = document.createElement('div');
    metaEl.className = 'session-meta';
    metaEl.textContent = carName + ' \u00b7 ' + session.lap_count + lapWord + ' \u00b7 best ' + fmtMs(session.best_lap_time_ms);

    hdr.appendChild(line1);
    hdr.appendChild(metaEl);

    const lapsDiv = document.createElement('div');
    lapsDiv.className = 'session-laps' + (idx === 0 ? ' open' : '');

    hdr.addEventListener('click', async () => {
      const open = lapsDiv.classList.toggle('open');
      arrowEl.textContent = open ? '\u25bc' : '\u25b6';
      if (open && !lapsDiv.children.length) await populateLaps(lapsDiv, session);
    });

    wrapper.appendChild(hdr);
    wrapper.appendChild(lapsDiv);
    sidebar.appendChild(wrapper);

    if (idx === 0) populateLaps(lapsDiv, session);
  });
}

async function fetchFrames(lap) {
  if (state.cache[lap.id]) return state.cache[lap.id];
  const frames = await fetch('/laps/' + lap.car_code + '/' + lap.lap_number + '/' + lap.id + '/frames').then(r => r.json());
  state.cache[lap.id] = frames;
  return frames;
}

async function selectLap(lap, slot) {
  const frames = await fetchFrames(lap);
  if (slot === 'A') state.lapA = { id: lap.id, frames };
  else              state.lapB = { id: lap.id, frames };
  updateButtonStates();
  renderAll();
}

function updateButtonStates() {
  document.querySelectorAll('.btn-a').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.btn-b').forEach(b => b.classList.remove('active'));
  if (state.lapA) {
    const el = document.querySelector('.lap-row[data-lap-id="' + state.lapA.id + '"] .btn-a');
    if (el) el.classList.add('active');
  }
  if (state.lapB) {
    const el = document.querySelector('.lap-row[data-lap-id="' + state.lapB.id + '"] .btn-b');
    if (el) el.classList.add('active');
  }
}

async function loadSidebar() {
  const [sessionsRes, carsRes, tracksRes] = await Promise.all([
    fetch('/sessions'),
    fetch('/static/cars.json'),
    fetch('/static/tracks.json'),
  ]);
  state.sessions = await sessionsRes.json();
  state.cars     = await carsRes.json();
  state.tracks   = await tracksRes.json();
  renderSidebar();
}

loadSidebar();
```

- [ ] **Step 4: Verify in browser**

Navigate to `http://localhost:8000/compare`.
- With empty DB: sidebar shows "No sessions yet."
- After driving a session: first session is expanded, lap rows visible with time, delta (★ for best), A/B buttons.
- Clicking A/B loads frames and renders charts as before.
- Clicking a collapsed session header expands it and loads its laps.

- [ ] **Step 5: Commit**

```bash
git add rexy/static/compare.html
git commit -m "feat: redesign /compare sidebar as session browser with nested lap rows"
```

---

### Task 9: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add Phase 4 Part 1 entry at the top of CHANGELOG.md**

Prepend before the existing `## [Week of 2026-03-19]` entry:

```markdown
## [Week of 2026-03-19] — Phase 4 Part 1

### Added

- Session management: each track outing is a first-class session with car and track identity
- `GET /sessions` — all sessions with at least one complete lap, newest first
- `GET /sessions/{id}/laps` — complete laps for a session (lap 0 excluded)
- `cars.json` and `tracks.json` static lookup files bundled at `/static/`
- Session browser sidebar on `/compare`: sessions grouped with nested lap rows,
  most recent expanded by default, delta-to-best shown per lap row

### Changed

- `LapRecorder` no longer requires `session_id` at construction; sessions are created
  automatically on `on_at_track` and `on_in_race` events and closed on `on_in_game_menu`
  and `on_race_end`
- DB schema migrated user_version 1 to 2: sessions table gains `track_id`,
  `car_code`, and `completed_at` columns

```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for Phase 4 Part 1"
```
