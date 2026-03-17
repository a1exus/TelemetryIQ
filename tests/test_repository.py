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


async def test_wal_mode(tmp_path):
    db = str(tmp_path / "wal_test.db")
    r = TelemetryRepository(db)
    await r.init()
    cur = await r.db.execute("PRAGMA journal_mode")
    assert (await cur.fetchone())[0] == "wal"
    await r.close()


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
