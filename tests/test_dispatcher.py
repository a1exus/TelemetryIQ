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
