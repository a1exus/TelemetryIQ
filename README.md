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

Docker Desktop on macOS and Windows cannot receive UDP from external devices — run directly on the host instead.

```shell
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
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

## Configuration

All configuration is via `.env`. See [`.env.example`](.env.example) for the full reference.

| Variable | Default | Description |
| --- | --- | --- |
| `PS_IP` | _(auto)_ | PlayStation IP address. Leave unset to use automatic discovery. |
| `GT7_HEARTBEAT_TYPE` | `B` | Telemetry format sent by GT7. `A` = standard, `B` = standard + motion data (steering, sway, heave, surge), `~` = standard + filtered inputs + energy recovery. Only one type active per session. |
