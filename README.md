# TelemetryIQ

Live telemetry dashboard for Gran Turismo 7 — speed, RPM, G-forces, lap times,
inputs, and more, streamed in real time from your PlayStation.

## Prerequisites

- Gran Turismo 7 running on PlayStation
- Telemetry enabled in GT7:
  **Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On**
- **Linux host** on the same network as the PlayStation (e.g. Raspberry Pi).
  Docker Desktop on macOS cannot receive UDP from external devices — the
  container runs in a VM and the PS5 can't reach it.
- Docker + Docker Compose

## Setup

1. Copy the example env file and configure it:

   ```shell
   cp .env.example .env
   ```

2. Edit `.env` — at minimum, set `PS_IP` if auto-discovery doesn't work:

   ```ini
   PS_IP=192.168.1.xxx
   ```

   See `.env.example` for all options and descriptions.

## Run

```bash
docker compose up --build
```

To run in the background:

```bash
docker compose up --build -d
docker compose logs -f
```

To stop:

```bash
docker compose down
```

## Configuration

All configuration is via `.env`. See [`.env.example`](.env.example) for the full reference.

| Variable | Default | Description |
| --- | --- | --- |
| `PS_IP` | _(auto)_ | PlayStation IP address. Leave unset to use automatic discovery. |
| `GT7_HEARTBEAT_TYPE` | `B` | Telemetry format sent by GT7. `A` = standard, `B` = standard + motion data (steering, sway, heave, surge), `~` = standard + filtered inputs + energy recovery. Only one type active per session. |
