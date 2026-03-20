"""TelemetryIQ entrypoint — wires all Phase 2 components."""
from __future__ import annotations

import asyncio
import os
import sys
import time

import uvicorn
from gt_telem import TurismoClient
from gt_telem.errors.playstation_errors import (
    PlayStationNotFoundError,
    PlayStationOnStandbyError,
)

from rexy.client import setup_client
from rexy.dispatcher import run_dispatcher
from rexy.recorder import LapRecorder
from rexy.repository import TelemetryRepository
from rexy.server import app, clients, run_broadcaster, set_repo


async def _main() -> None:
    ps_ip = os.environ.get("PS_IP") or None
    heartbeat_type = os.environ.get("GT7_HEARTBEAT_TYPE", "B")
    db_path = os.environ.get("DB_PATH", os.path.join(os.getcwd(), "telemetry.db"))

    # Database — must init before anything else
    repo = TelemetryRepository(db_path)
    await repo.init()
    set_repo(repo)
    session_id = await repo.insert_session(started_at=time.time())

    # Recorder and queues
    recorder = LapRecorder(repo=repo, session_id=session_id)
    raw_queue: asyncio.Queue = asyncio.Queue()
    ws_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    loop = asyncio.get_running_loop()

    # GT7 client — raises on PS not found / standby
    try:
        tc = TurismoClient(ps_ip=ps_ip, heartbeat_type=heartbeat_type)
    except PlayStationOnStandbyError:
        print("PlayStation is on standby. Turn it on and restart.")
        raise SystemExit(1)
    except PlayStationNotFoundError:
        print("PlayStation not found. Ensure PC and PS are on the same LAN.")
        raise SystemExit(1)

    setup_client(tc, raw_queue, recorder, loop, heartbeat_type)
    tc.start()

    # Async tasks
    dispatcher_task = asyncio.create_task(run_dispatcher(raw_queue, ws_queue, recorder))
    broadcaster_task = asyncio.create_task(run_broadcaster(ws_queue, clients))

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        dispatcher_task.cancel()
        broadcaster_task.cancel()
        await asyncio.gather(dispatcher_task, broadcaster_task, return_exceptions=True)
        try:
            await asyncio.wait_for(loop.run_in_executor(None, tc.stop), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        await recorder.close()
        await repo.close()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    # gt-telem starts non-daemon threads; force exit so we don't hang.
    sys.exit(0)


if __name__ == "__main__":
    main()
