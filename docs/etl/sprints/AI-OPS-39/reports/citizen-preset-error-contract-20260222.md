# Citizen Preset Error Contract (AI-OPS-39)

Date:
- 2026-02-22

Goal:
- Make malformed `#preset` links deterministic and explainable so share-link failures are explicit and safe.

## What shipped

1. Deterministic codec error contract
- `ui/citizen/preset_codec.js` now emits structured `{ preset, error, error_code }`.
- Added explicit error codes:
  - `decode_error`
  - `unsupported_version`
  - `empty_payload`
  - `no_supported_fields`
- `#preset` payloads that decode but contain no supported fields are now rejected.

2. Citizen UX hardening for preset failures
- `ui/citizen/index.html` now stores `presetLoadErrorCode`.
- Added `presetErrorHint(errorCode)` to map error codes to user-facing guidance.
- Banner now shows both raw error and actionable hint.

3. Test coverage expansion
- `tests/test_citizen_preset_codec.js` now validates:
  - malformed URI decode failure
  - unknown-field hash rejection
  - minimal valid hash acceptance
  - prior roundtrip behavior

## Validation evidence

- Codec tests:
  - `docs/etl/sprints/AI-OPS-39/evidence/citizen_preset_codec_tests_postdocs_20260222T204927Z.txt`
- Marker checks:
  - `docs/etl/sprints/AI-OPS-39/evidence/citizen_preset_error_contract_markers_20260222T204717Z.txt`
- GH Pages build:
  - `docs/etl/sprints/AI-OPS-39/evidence/explorer_gh_pages_build_postdocs_20260222T204927Z.txt`
- Tracker gate:
  - `docs/etl/sprints/AI-OPS-39/evidence/tracker_gate_posttrackeredit_20260222T205129Z.txt`

Outcome:
- Preset sharing now has a stable, test-backed failure contract and clearer citizen UX on invalid shared links.
