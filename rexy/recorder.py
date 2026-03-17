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
            old_id, lap_time_ms, time.time(), 1, car_code=car
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
                old_id, None, time.time(), 0, car_code=car
            )
