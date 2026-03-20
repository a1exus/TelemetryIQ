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
    id           INTEGER PRIMARY KEY,
    started_at   REAL NOT NULL,
    track_id     INTEGER,
    car_code     INTEGER,
    completed_at REAL
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
            await self.db.execute("PRAGMA user_version = 2")
            await self.db.commit()
        elif version == 1:
            await self.db.execute("ALTER TABLE sessions ADD COLUMN track_id INTEGER")
            await self.db.execute("ALTER TABLE sessions ADD COLUMN car_code INTEGER")
            await self.db.execute("ALTER TABLE sessions ADD COLUMN completed_at REAL")
            await self.db.execute("PRAGMA user_version = 2")
            await self.db.commit()
        elif version == 2:
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

    async def insert_frames(self, lap_id: int, frames: list[dict]) -> None:
        if not frames:
            return
        rows = [
            tuple(lap_id if col == "lap_id" else f.get(col) for col in _FRAME_COLS)
            for f in frames
        ]
        await self.db.executemany(_FRAME_INSERT, rows)
        await self.db.commit()

    async def list_laps(self) -> list[dict]:
        """Return all complete laps, newest first."""
        cur = await self.db.execute(
            "SELECT id, lap_number, lap_time_ms, car_code, started_at "
            "FROM laps WHERE is_complete = 1 ORDER BY started_at DESC"
        )
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]

    async def get_frames(self, lap_id: int) -> list[dict]:
        """Return all frames for a lap ordered by seq."""
        cur = await self.db.execute(
            "SELECT * FROM frames WHERE lap_id = ? ORDER BY seq", (lap_id,)
        )
        rows = await cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]

    async def close(self) -> None:
        if self.db:
            await self.db.close()
