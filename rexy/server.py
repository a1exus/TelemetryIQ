"""FastAPI application: WebSocket /ws + static file serving."""
from __future__ import annotations

import asyncio
import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
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


@app.patch("/sessions/{session_id}")
async def patch_session(session_id: int, request: Request):
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    body = await request.json()
    if "notes" not in body:
        raise HTTPException(status_code=422, detail="missing 'notes' key")
    notes = body["notes"]
    if notes is not None and not isinstance(notes, str):
        raise HTTPException(status_code=422, detail="notes must be string or null")
    if notes == "":
        notes = None
    rows = await _repo.update_session_notes(session_id, notes)
    if rows == 0:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


@app.get("/laps/{car_code}/{lap_number}/{lap_id}/frames")
async def get_frames(car_code: int, lap_number: int, lap_id: int):
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    frames = await _repo.get_frames(lap_id)
    return _add_distance(frames)


@app.get("/laps/{car_code}/{lap_number}/{lap_id}/export.csv")
async def export_lap_csv(car_code: int, lap_number: int, lap_id: int) -> Response:
    from fastapi import HTTPException
    if _repo is None:
        raise HTTPException(status_code=503, detail="repository not ready")
    frames = _add_distance(await _repo.get_frames(lap_id))
    body = io.StringIO()
    if frames:
        writer = csv.DictWriter(body, fieldnames=list(frames[0].keys()))
        writer.writeheader()
        writer.writerows(frames)
    filename = f"lap-{car_code}-{lap_number}-{lap_id}.csv"
    return Response(
        content=body.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/compare")
async def compare() -> FileResponse:
    return FileResponse(_STATIC / "compare.html")


async def run_broadcaster(ws_queue: asyncio.Queue, clients: set[WebSocket]) -> None:
    try:
        while True:
            frame = await ws_queue.get()
            if clients:
                await asyncio.gather(
                    *[_send_safe(ws, frame) for ws in list(clients)],
                    return_exceptions=True,
                )
    except asyncio.CancelledError:
        pass


async def _send_safe(ws: WebSocket, frame: dict) -> None:
    try:
        await ws.send_json(frame)
    except Exception:
        pass  # client removed by /ws handler on its next receive attempt
