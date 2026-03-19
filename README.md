# TelemetryIQ

GT7 telemetry recorder and lap analysis tool — records full telemetry per lap,
streams live data, and enables lap-over-lap comparison of speed, throttle, brake,
G-forces, and more.

## Prerequisites

- Gran Turismo 7 running on PlayStation
- Telemetry enabled in GT7:
  **Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On**
- PlayStation and your machine on the same network

## macOS / Windows

Docker Desktop on macOS and Windows runs containers inside a Linux VM that is not on the
same network as the host, so PS5 UDP telemetry cannot reach the container. Run directly
on the host instead.

```shell
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PS_IP=        # set to your PlayStation's IP, or leave blank for auto-discovery
python -m rexy
```

## Linux / Docker (e.g. Raspberry Pi)

```shell
cp .env.example .env
# Edit .env — set PS_IP if auto-discovery doesn't work
make build
make up
make logs
```

## Web UI

Once running, open **<http://localhost:8000>** in a browser.

| URL | Description |
| --- | --- |
| `/` | Live engineering HUD — speed, RPM, gear, G-forces, throttle/brake, lap timer |
| `/compare` | Lap comparison — select two recorded laps, overlay speed/throttle/brake/G traces, time-delta graph, track map |

Laps are recorded automatically to `telemetry.db` (SQLite). The live timer is anchored to the server-side lap-start timestamp, so it survives browser refreshes and sleep/wake cycles.

## Configuration

All configuration is via `.env`. See [`.env.example`](.env.example) for the full reference.

| Variable | Default | Description |
| --- | --- | --- |
| `PS_IP` | _(auto)_ | PlayStation IP address. Leave unset to use automatic discovery. |
| `GT7_HEARTBEAT_TYPE` | `B` | Telemetry format. `A` = standard, `B` = standard + motion data (steering, sway, heave, surge), `~` = standard + filtered inputs + energy recovery. One type active per session. |
