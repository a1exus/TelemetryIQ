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
