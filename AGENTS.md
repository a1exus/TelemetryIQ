---
description: Defines custom agents available for subagent calls in this workspace
applyTo: '**'
---

# Agents

This file defines the custom agents available for use in this workspace.

## Explore

**Description**: Fast read-only codebase exploration and Q&A subagent. Prefer over manually chaining multiple search and file-reading operations to avoid cluttering the main conversation. Safe to call in parallel. Specify thoroughness: quick, medium, or thorough.

**Argument Hint**: Describe WHAT you're looking for and desired thoroughness (quick/medium/thorough)

## Refreshing Static Data (cars.json / tracks.json)

Car and track name lookups use static JSON files bundled in `rexy/static/`.
These map telemetry IDs to human-readable names and should be refreshed when
GT7 adds new cars or tracks via game updates.

### Source: gran-turismo.com (official)

Both pages are JavaScript SPAs. Data lives in chunked JS assets, not in the
initial HTML. **Do not use Playwright** — fetch the JS bundles directly.

#### Cars (`rexy/static/cars.json`)

1. Fetch the carlist page HTML:
   `https://www.gran-turismo.com/us/gt7/carlist/`
2. Extract the JS bundle path from the `<script>` tag (e.g. `/common/dist/gt7/carlist/assets/index-XXXXX.js`).
3. In that bundle, find the `cars.gb-XXXXX.js` chunk filename.
4. Fetch `https://www.gran-turismo.com/common/dist/gt7/carlist/assets/cars.gb-XXXXX.js`.
5. Parse entries: `id:"carNNN"` → `nameLong:"..."`. The number `NNN` is the `car_code` from telemetry.
6. Write `{"NNN": "Car Name", ...}` sorted by integer key.

#### Tracks (`rexy/static/tracks.json`)

Track IDs in telemetry are **integer** IDs assigned by `gt-telem`'s track
detector (position-based). The official site uses different hex content IDs.

1. Start from `gt-telem`'s bundled `track_names.csv`
   (installed at `gt_telem/data/track_names.csv`) — this is the
   authoritative mapping of integer track_id → name.
2. Fetch the official tracklist page HTML:
   `https://www.gran-turismo.com/gb/gt7/tracklist/`
3. Extract `tracks.gb-XXXXX.js` chunk from the bundle (same pattern as cars).
4. Cross-reference official names to fix accents (e.g. Nurburgring → Nürburgring, Autodromo → Autódromo).
5. Write `{"integer_id": "Official Name", ...}` sorted by integer key.

**Note:** New tracks added by game updates may not appear in `gt-telem`'s
`track_names.csv` until the library is updated. In that case, add new integer
ID mappings after confirming the ID from telemetry logs.
