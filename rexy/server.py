"""FastAPI application: WebSocket /ws + static file serving."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

if TYPE_CHECKING:
    from rexy.repository import TelemetryRepository

_repo: "TelemetryRepository | None" = None


def set_repo(repo: "TelemetryRepository | None") -> None:
    global _repo
    _repo = repo


def _add_distance(frames: list[dict]) -> list[dict]:
    """Append distance_m to each frame using wall-clock ts as time base.

    GT7 does not broadcast current_lap_time_ms; ts is set server-side on
    frame receipt. Frames where dt > 0.1 s (pause, menu, load screen)
    contribute zero distance to prevent teleportation artefacts.
    """
    result = []
    dist = 0.0
    prev_ts: float | None = None
    for f in frames:
        ts = f.get("ts")
        if prev_ts is not None and ts is not None:
            dt = ts - prev_ts
            if 0.0 < dt < 0.1:
                dist += (f.get("speed_mps") or 0.0) * dt
        prev_ts = ts
        result.append({**f, "distance_m": round(dist, 2)})
    return result


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


@app.get("/laps")
async def get_laps():
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    return await _repo.list_laps()


@app.get("/laps/{lap_id}/frames")
async def get_frames(lap_id: int):
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    frames = await _repo.get_frames(lap_id)
    return _add_distance(frames)


@app.get("/analysis")
async def analysis() -> FileResponse:
    return FileResponse(_STATIC / "analysis.html")


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
