"""FastAPI application: WebSocket /ws + static file serving."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
