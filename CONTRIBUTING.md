# Contributing to TelemetryIQ

Thanks for your interest. This is a small, single-maintainer project aimed at
GT7 sim racers — the bar for changes is correctness and clarity over scope.

## Project status

TelemetryIQ is **feature-complete** as of 2026-04-26 (Phases 1–7 shipped). Bug
fixes, doc improvements, dependency bumps, and refreshes of `cars.json` /
`tracks.json` are always welcome. **New features** — please open an issue
first to discuss scope before opening a PR; otherwise the change is likely to
be closed or significantly reshaped.

## Dev setup

You need:

- Python 3.10+ (see `pyproject.toml`)
- A LAN-connected PlayStation running GT7 with UDP telemetry enabled
  (Settings → Options → Machine → BD-ROM / PS5 Activity → GT7 UDP Telemetry → On)

```bash
make install   # creates .venv and installs deps
make run       # starts TelemetryIQ; auto-discovers PS on LAN
make test      # runs the pytest suite
```

If auto-discovery doesn't work, set `PS_IP=<your.ps.ip> make run`. See
`make help` for all environment variables.

## Code style

- Python: standard library plus the dependencies already in `pyproject.toml`.
  Don't add new dependencies without a clear case.
- `from __future__ import annotations` at the top of new modules.
- Type hints on public functions; `# type: ignore` only when truly necessary.
- Errors: wrap with `f"context: {original}"`-style messages or `raise ... from`;
  no bare `panic` / `sys.exit` in library code.
- Frontend: vanilla JS, no npm, no build step. Chart.js comes via CDN.

`specs.md` is the **single durable design document**. Architectural changes
need a corresponding update there. Do not create parallel design docs under
`docs/superpowers/specs/` (that directory is intentionally absent).

## Submitting a PR

1. Open an issue first if you're proposing a new feature or non-trivial
   refactor.
2. Branch from `main`. Keep commits small and focused.
3. Run `make test` and confirm all tests pass before pushing.
4. If your change is user-visible, add a `CHANGELOG.md` entry under a new or
   appropriate `## YYYY.MM.DD` section.
5. If the change touches architecture, the data model, or REST API, update
   `specs.md` in the same PR.
6. Use the PR template; fill in the summary and the test plan.

Commits use imperative-mood subjects, ≤72 chars on the first line, with body
detail when the "why" isn't obvious from the diff.

## Reporting bugs

Use the GitHub issue templates (`.github/ISSUE_TEMPLATE/`). For bugs, include
the heartbeat type (`A`/`B`/`~`), Python version, OS, and any relevant stdout
log lines from `make run`.

## License

By contributing you agree your changes are released under the MIT license
(see `LICENSE`).
