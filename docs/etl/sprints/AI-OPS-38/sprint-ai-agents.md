# AI-OPS-38 Prompt Pack

Objective:
- Make citizen preset sharing (`#preset=v1`) test-backed and reusable through a dedicated codec module.

Acceptance gates:
- `ui/citizen/preset_codec.js` provides deterministic codec API:
  - `encodePresetPayload`
  - `decodePresetPayload`
  - `readPresetFromHash`
  - `buildAlignmentPresetShareUrl`
- `ui/citizen/index.html` delegates preset share/load logic to that module.
- Local explorer server serves `/citizen/preset_codec.js`; GH Pages build copies `preset_codec.js`.
- Test command `just citizen-test-preset-codec` passes.
- Build + tracker gate remain green.

Status update (2026-02-22):
- Added shared codec module:
  - `ui/citizen/preset_codec.js`
- Citizen UI updated to consume codec:
  - `ui/citizen/index.html` now loads `./preset_codec.js` and delegates preset functions through wrappers.
- Local server/static parity:
  - `scripts/graph_ui_server.py` serves `/citizen/preset_codec.js`.
  - `scripts/graph_ui_server.py` redirects `/citizen` -> `/citizen/` to keep relative asset paths stable.
  - `justfile` `explorer-gh-pages-build` copies `ui/citizen/preset_codec.js` to `docs/gh-pages/citizen/preset_codec.js`.
- Tests:
  - `tests/test_citizen_preset_codec.js`
  - helper recipe `just citizen-test-preset-codec`
- evidence:
  - `docs/etl/sprints/AI-OPS-38/evidence/citizen_preset_codec_tests_postroute_20260222T204230Z.txt`
  - `docs/etl/sprints/AI-OPS-38/evidence/citizen_preset_codec_markers_postroute_20260222T204352Z.txt`
  - `docs/etl/sprints/AI-OPS-38/evidence/explorer_gh_pages_build_postroute_20260222T204143Z.txt`
  - `docs/etl/sprints/AI-OPS-38/evidence/tracker_gate_postroute_20260222T204143Z.txt`
