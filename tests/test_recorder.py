import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from rexy.recorder import LapRecorder, State


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.insert_session = AsyncMock(return_value=1)
    repo.insert_lap = AsyncMock(return_value=7)
    repo.insert_frames = AsyncMock()
    repo.complete_lap = AsyncMock()
    repo.complete_session = AsyncMock()
    repo.update_session_track = AsyncMock()
    repo.update_session_car = AsyncMock()
    return repo


@pytest.fixture
def recorder(mock_repo):
    return LapRecorder(repo=mock_repo)


@pytest.fixture
async def active_recorder(mock_repo):
    """Recorder with an active session (session_id=1)."""
    rec = LapRecorder(repo=mock_repo)
    await rec.start_session()
    return rec


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

async def test_reset_transitions_to_recording(active_recorder):
    await active_recorder.reset_and_new_lap(1)
    assert active_recorder.state == State.RECORDING


async def test_reset_inserts_lap_row(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    mock_repo.insert_lap.assert_called_once()
    args = mock_repo.insert_lap.call_args[0]
    assert args[0] == 1        # lap_number
    assert args[1] == 1        # session_id
    assert args[2] is None     # track_id (not set yet)


async def test_reset_stores_lap_id(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    assert active_recorder.current_lap_id == 7  # mock returns 7


# --- RECORDING ---

async def test_on_frame_appends_to_buffer(active_recorder):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"speed_mps": 10.0, "last_lap_time_ms": -1})
    active_recorder.on_frame({"speed_mps": 11.0, "last_lap_time_ms": -1})
    assert len(active_recorder.lap_buffer) == 2


async def test_on_frame_injects_seq(active_recorder):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"speed_mps": 1.0, "last_lap_time_ms": -1})
    active_recorder.on_frame({"speed_mps": 2.0, "last_lap_time_ms": -1})
    assert active_recorder.lap_buffer[0]["seq"] == 0
    assert active_recorder.lap_buffer[1]["seq"] == 1


async def test_on_frame_does_not_mutate_input(active_recorder):
    await active_recorder.reset_and_new_lap(1)
    frame = {"speed_mps": 5.0, "last_lap_time_ms": -1}
    active_recorder.on_frame(frame)
    assert "seq" not in frame  # original dict untouched


# --- flush_and_new_lap ---

async def test_flush_clears_buffer_before_await(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 99, "last_lap_time_ms": 85000})

    captured = []

    async def capture(lap_id, frames):
        captured.append(list(active_recorder.lap_buffer))  # snapshot during await

    mock_repo.insert_frames.side_effect = capture
    await active_recorder.flush_and_new_lap(2)
    assert captured[0] == []  # buffer was empty when insert_frames ran


async def test_flush_derives_lap_time_from_buffer(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": 85432})
    await active_recorder.flush_and_new_lap(2)
    args = mock_repo.complete_lap.call_args[0]
    assert args[1] == 85432  # lap_time_ms positional arg


async def test_flush_minus_one_sentinel_becomes_none(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await active_recorder.flush_and_new_lap(2)
    args = mock_repo.complete_lap.call_args[0]
    assert args[1] is None  # -1 → None


async def test_flush_marks_lap_complete(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": 85000})
    await active_recorder.flush_and_new_lap(2)
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 1  # is_complete=1


async def test_flush_starts_new_lap(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": 85000})
    await active_recorder.flush_and_new_lap(2)
    assert mock_repo.insert_lap.call_count == 2  # once on reset, once on flush


async def test_flush_empty_buffer_still_inserts_lap(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    # No frames
    await active_recorder.flush_and_new_lap(2)
    mock_repo.insert_frames.assert_not_called()
    mock_repo.complete_lap.assert_called_once()


async def test_flush_calls_update_session_car_when_car_known(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 42, "last_lap_time_ms": 85000})
    await active_recorder.flush_and_new_lap(2)
    mock_repo.update_session_car.assert_called_once_with(1, 42)


async def test_flush_skips_update_session_car_when_no_car(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    # No frames — car is None
    await active_recorder.flush_and_new_lap(2)
    mock_repo.update_session_car.assert_not_called()


# --- close ---

async def test_close_flushes_partial_lap(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await active_recorder.close()
    mock_repo.insert_frames.assert_called_once()
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 0  # is_complete=0 (partial)


async def test_close_empty_buffer_no_write(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    await active_recorder.close()
    mock_repo.insert_frames.assert_not_called()
    mock_repo.complete_lap.assert_not_called()


async def test_close_sets_state_to_idle(active_recorder):
    await active_recorder.reset_and_new_lap(1)
    await active_recorder.close()
    assert active_recorder.state == State.IDLE


# --- set_track_id ---

async def test_set_track_id(recorder):
    recorder.set_track_id(42)
    assert recorder.current_track_id == 42


async def test_set_track_id_dispatches_update_when_session_active(active_recorder, mock_repo):
    active_recorder.set_track_id(42)
    # Let the event loop run the created task
    await asyncio.sleep(0)
    mock_repo.update_session_track.assert_called_once_with(1, 42)


async def test_set_track_id_no_update_when_no_session(recorder, mock_repo):
    recorder.set_track_id(42)
    await asyncio.sleep(0)
    mock_repo.update_session_track.assert_not_called()


async def test_track_id_passed_to_insert_lap(active_recorder, mock_repo):
    active_recorder.set_track_id(42)
    await active_recorder.reset_and_new_lap(1)
    args = mock_repo.insert_lap.call_args[0]
    assert args[2] == 42  # track_id


# --- session lifecycle ---

async def test_start_session_sets_session_id(recorder, mock_repo):
    assert recorder._session_id is None
    await recorder.start_session()
    assert recorder._session_id == 1
    mock_repo.insert_session.assert_called_once()


async def test_close_session_calls_complete_session(active_recorder, mock_repo):
    await active_recorder.close_session()
    mock_repo.complete_session.assert_called_once_with(1, completed_at=pytest.approx(time.time(), abs=5))
    assert active_recorder._session_id is None


async def test_close_session_flushes_partial_if_recording(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await active_recorder.close_session()
    mock_repo.insert_frames.assert_called_once()
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 0  # is_complete=0 (partial)
    assert active_recorder.state == State.IDLE


async def test_close_session_noop_when_no_session(recorder, mock_repo):
    await recorder.close_session()
    mock_repo.complete_session.assert_not_called()


async def test_reset_no_session_is_noop(recorder, mock_repo):
    await recorder.reset_and_new_lap(1)
    assert recorder.state == State.IDLE
    mock_repo.insert_lap.assert_not_called()


async def test_flush_no_session_is_noop(recorder, mock_repo):
    await recorder.flush_and_new_lap(2)
    mock_repo.insert_lap.assert_not_called()
    mock_repo.insert_frames.assert_not_called()


# --- race restart (RECORDING → reset_and_new_lap) ---

async def test_reset_while_recording_flushes_partial(active_recorder, mock_repo):
    await active_recorder.reset_and_new_lap(1)
    active_recorder.on_frame({"car_code": 5, "last_lap_time_ms": -1})
    await active_recorder.reset_and_new_lap(1)  # restart
    mock_repo.insert_frames.assert_called_once()
    args = mock_repo.complete_lap.call_args[0]
    assert args[3] == 0  # is_complete=0


async def test_reset_while_recording_stays_recording(active_recorder):
    await active_recorder.reset_and_new_lap(1)
    await active_recorder.reset_and_new_lap(1)
    assert active_recorder.state == State.RECORDING
