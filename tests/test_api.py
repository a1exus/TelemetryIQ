"""Tests for Phase 3 REST API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rexy.server import app, set_repo


class FakeRepo:
    async def list_laps(self):
        return [{"id": 1, "lap_number": 1, "lap_time_ms": 90000,
                 "car_code": 42, "started_at": 0.0}]

    async def list_sessions(self):
        return [{"id": 1, "started_at": 1000.0, "completed_at": 2000.0,
                 "track_id": 40, "car_code": 3520, "lap_count": 2, "best_lap_time_ms": 101887}]

    async def list_session_laps(self, session_id: int):
        if session_id != 1:
            return []
        return [
            {"id": 10, "lap_number": 1, "lap_time_ms": 102341},
            {"id": 11, "lap_number": 2, "lap_time_ms": 101887},
        ]

    async def get_frames(self, lap_id: int):
        if lap_id != 1:
            return []
        return [
            {"seq": 0, "ts": 0.0,   "speed_mps": 0.0},
            {"seq": 1, "ts": 0.016, "speed_mps": 10.0},
            {"seq": 2, "ts": 0.033, "speed_mps": 20.0},
        ]


@pytest.fixture(autouse=True)
def inject_repo():
    set_repo(FakeRepo())
    yield
    set_repo(None)


def test_get_laps():
    r = TestClient(app).get("/laps")
    assert r.status_code == 200
    laps = r.json()
    assert len(laps) == 1
    assert laps[0]["lap_time_ms"] == 90000


def test_get_laps_503_before_repo_set():
    set_repo(None)
    r = TestClient(app).get("/laps")
    assert r.status_code == 503


def test_get_frames_adds_distance():
    r = TestClient(app).get("/laps/42/1/1/frames")
    assert r.status_code == 200
    frames = r.json()
    assert frames[0]["distance_m"] == 0.0
    # frame 1: dt=0.016 s, speed=10 m/s → d ≈ 0.16 m
    assert frames[1]["distance_m"] == pytest.approx(0.16, abs=0.01)
    # frame 2: dt≈0.017 s, speed=20 m/s → cumulative ≈ 0.50 m
    assert frames[2]["distance_m"] == pytest.approx(0.5, abs=0.02)


def test_get_frames_unknown_lap_returns_empty():
    r = TestClient(app).get("/laps/42/1/999/frames")
    assert r.status_code == 200
    assert r.json() == []


def test_compare_page_served():
    r = TestClient(app).get("/compare")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_get_sessions():
    r = TestClient(app).get("/sessions")
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) == 1
    assert sessions[0]["best_lap_time_ms"] == 101887


def test_get_sessions_503_before_repo_set():
    set_repo(None)
    r = TestClient(app).get("/sessions")
    assert r.status_code == 503


def test_get_session_laps():
    r = TestClient(app).get("/sessions/1/laps")
    assert r.status_code == 200
    laps = r.json()
    assert len(laps) == 2
    assert laps[0]["lap_number"] == 1


def test_get_session_laps_unknown_session_returns_empty():
    r = TestClient(app).get("/sessions/999/laps")
    assert r.status_code == 200
    assert r.json() == []
