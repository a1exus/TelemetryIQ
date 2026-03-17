import pytest
from fastapi.testclient import TestClient

from rexy.server import app


def test_ws_connect_and_disconnect():
    """Client can connect to /ws and disconnect cleanly."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            # connected — server should have added to clients set
            pass  # disconnect on context exit
        # After disconnect — no exception means clean removal


def test_ws_multiple_clients():
    """Two clients can connect simultaneously."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws"):
            with client.websocket_connect("/ws"):
                pass
