# Security Policy

## Threat model

TelemetryIQ is designed to run on a **trusted LAN** alongside a PlayStation.
It is not hardened for the open internet. In particular:

- The FastAPI server (default `:8000`) has **no authentication** or access
  control. Anyone on the LAN can read live telemetry, read recorded laps, and
  edit session notes via `PATCH /sessions/{id}`.
- The UDP listener (default `:33740`) accepts anything from any source on the
  network and parses it as gt-telem telemetry.
- SQLite (`telemetry.db`) is a local file with no encryption.

These are intentional design choices — `Authentication / access control` is
explicitly out of scope (see `specs.md`). **Do not expose either port to the
public internet.**

## Reporting a vulnerability

If you find a security issue you believe is sensitive (e.g. a memory-safety
bug in the UDP parser, or a way to compromise the host beyond the documented
threat model above), please **open a private GitHub Security Advisory** for
this repository rather than a public issue:

- <https://github.com/a1exus/TelemetryIQ/security/advisories/new>

Non-sensitive issues (e.g. "the app crashes on malformed UDP packets") can be
filed as a regular GitHub issue.

## Supported versions

Only `main` is supported. The project follows CalVer (`YYYY.MM.DD`) without
maintaining release branches. To get a fix, pull the latest `main`.

## Dependencies

`gt-telem`, `fastapi`, `uvicorn`, `aiosqlite`. Dependency bumps land in
`main` as small PRs. There are no compiled or vendored dependencies.
