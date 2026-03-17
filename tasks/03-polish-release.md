# Task: Analysis dashboard

**Phase**: 3 — Analysis dashboard
**Status**: Not started

## Objective

Build the full analysis dashboard on top of Phase 2's recorded laps.

## Acceptance criteria

- [ ] Full live telemetry display (all fields from `specs.md` F4)
- [ ] Lap selector — choose any two recorded laps to compare
- [ ] Two-lap overlay: throttle, brake, speed, RPM traces on a shared X axis (distance through lap)
- [ ] Gap graph: time delta between two laps at each point
- [ ] Driving line: `position_x/y/z` plotted as a 2D track map
- [ ] Dashboard readable on a phone screen while sitting in a racing seat
- [ ] WebSocket auto-reconnects with exponential backoff

## Notes

- X axis for comparison should be distance-through-lap, not wall-clock time.
- Driving line needs the two `position_x/z` traces overlaid on the same track map.
- See `specs.md` for full requirements and telemetry field reference.
