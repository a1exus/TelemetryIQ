# TelemetryIQ

Live telemetry dashboard for Gran Turismo 7 — speed, RPM, G-forces, lap times,
inputs, and more, streamed in real time from your PlayStation.

## Prerequisites

- Gran Turismo 7 running on PlayStation
- Telemetry enabled in GT7:
  **Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On**
- PlayStation and your machine on the same network

## macOS (pip via brew)

Docker Desktop on macOS cannot receive UDP from external devices — use pip instead.

```shell
brew install pipx
pipx install .
rexy
```

For development (editable install):

```shell
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
rexy
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
