# Citizen Preset Codec Hardening (AI-OPS-38)

Date:
- 2026-02-22

Goal:
- Keep alignment preset links stable and auditable by moving `#preset=v1` logic into a reusable, test-backed module.

## What shipped

1. Shared codec module
- Added `ui/citizen/preset_codec.js` with pure helpers for:
  - payload encode/decode
  - hash read (`#preset=...`)
  - share URL build
- Module exports both browser global (`window.CitizenPresetCodec`) and Node/CommonJS (`module.exports`) for local tests.

2. Citizen UI wiring
- `ui/citizen/index.html` now imports `./preset_codec.js`.
- Existing preset functions (`encodePresetPayload`, `decodePresetPayload`, `readPresetFromHash`, `buildAlignmentPresetShareUrl`) delegate to shared codec with concern-aware config.

3. Runtime parity (local + GH Pages)
- `scripts/graph_ui_server.py` now serves `/citizen/preset_codec.js`.
- `scripts/graph_ui_server.py` now redirects `/citizen` -> `/citizen/` so relative citizen assets resolve deterministically.
- `just explorer-gh-pages-build` now copies `ui/citizen/preset_codec.js` to `docs/gh-pages/citizen/preset_codec.js`.

4. Test lane
- Added deterministic Node tests:
  - `tests/test_citizen_preset_codec.js`
- Added shortcut:
  - `just citizen-test-preset-codec`

## Validation evidence

- Codec tests:
  - `docs/etl/sprints/AI-OPS-38/evidence/citizen_preset_codec_tests_postroute_20260222T204230Z.txt`
- Marker checks:
  - `docs/etl/sprints/AI-OPS-38/evidence/citizen_preset_codec_markers_postroute_20260222T204352Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-38/evidence/explorer_gh_pages_build_postroute_20260222T204143Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-38/evidence/tracker_gate_postroute_20260222T204143Z.txt`

Outcome:
- Preset sharing is now modular and test-backed, reducing regression risk while preserving static-first citizen delivery.
