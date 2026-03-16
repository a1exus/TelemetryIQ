# TelemetryIQ: Gemini Context & Instructions

This document provides essential context and instructions for AI agents working on the TelemetryIQ project.

## Project Overview

**TelemetryIQ** (internal package name `rexy`) is a real-time telemetry dashboard for Gran Turismo 7 (GT7) on PlayStation. It captures data such as speed, RPM, gear, and G-forces via UDP from the PlayStation and provides a foundation for dashboards, recording, and analytics.

- **Primary Technologies:** Python 3.10+, `gt-telem` (UDP telemetry library), Docker, Docker Compose.
- **Architecture:** A CLI application (`rexy`) that acts as a client connecting to the PlayStation's telemetry stream.
- **Status:** Phase 1 (Foundation) is complete. The project is currently transitioning into Phase 2 (Core Features).

## Directory Structure

- `rexy/`: Core Python source code.
  - `__main__.py`: Entry point for the CLI.
- `lib/`: Reference documentation for GT7 and specific car telemetry.
- `tasks/`: Structured task lists for project phases (01-setup, 02-core-feature, 03-polish-release).
- `specs.md`: Technical specifications and requirements.
- `plan.md`: High-level implementation plan and roadmap.
- `AGENTS.md`: Definitions for custom workspace agents.
- `Makefile`: Common development and operations commands.
- `compose.yaml` & `Dockerfile`: Containerization setup.

## Building and Running

### Local Development (macOS/Linux)
1.  **Environment Setup:**
    ```bash
    make install
    # OR manually:
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e .
    ```
2.  **Configuration:** Copy `.env.example` to `.env` and configure `PS_IP` if necessary.
3.  **Run CLI:**
    ```bash
    rexy
    ```

### Docker (Linux/Raspberry Pi)
- **Build:** `make build`
- **Start:** `make up`
- **Stop:** `make down`
- **Logs:** `make logs`
- **Restart:** `make restart`

## Development Conventions

- **Code Style:** Adhere to standard Python (PEP 8) conventions. Use type hints where possible.
- **Configuration:** Always use environment variables via `.env`. Do not hardcode IPs or sensitive data.
- **Workflow:** Follow the Phase/Task model defined in `plan.md` and the `tasks/` directory. Update tasks as they are completed.
- **Dependencies:** Managed via `pyproject.toml` (hatchling backend). The core dependency is `gt-telem`.
- **Testing:** (TODO) Define testing framework and patterns as Phase 2 progresses.

## Workspace Agents

This project uses custom agents for specialized tasks (see `AGENTS.md`):

- **Explore:** Use for fast, read-only codebase exploration.
  - *Usage:* `Explore: <thoroughness (quick/medium/thorough)> - <what you are looking for>`

## GT7 Connectivity Requirements

- PlayStation and PC must be on the same network.
- UDP Telemetry must be enabled in GT7: **Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On**.
- Handle `PlayStationNotFoundError` and `PlayStationOnStandbyError` gracefully.
