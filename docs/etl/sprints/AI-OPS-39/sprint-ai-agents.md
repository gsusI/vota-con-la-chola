# AI-OPS-39 Prompt Pack

Objective:
- Enforce a strict malformed-hash contract for citizen preset links and expose clear UX hints without backend dependencies.

Acceptance gates:
- `ui/citizen/preset_codec.js` adds deterministic `error_code` contract:
  - `decode_error`
  - `unsupported_version`
  - `empty_payload`
  - `no_supported_fields`
- `readPresetFromHash` rejects `#preset` payloads that decode to zero recognized fields.
- `ui/citizen/index.html` stores `presetLoadErrorCode` and renders actionable hint text by code.
- `tests/test_citizen_preset_codec.js` covers malformed encoding and unsupported-field payloads.
- Build + tracker gates remain green.

Status update (2026-02-22):
- Codec hardening:
  - `ui/citizen/preset_codec.js` now returns `{ preset, error, error_code }` and rejects unsupported/empty/invalid hashes explicitly.
- UI hardening:
  - `ui/citizen/index.html` adds `presetLoadErrorCode` state and `presetErrorHint(...)`.
  - banner now includes hint text when preset load fails.
- Tests:
  - `tests/test_citizen_preset_codec.js` expanded to cover malformed encoding, unknown fields hash rejection, and minimal valid hash.
- evidence:
  - `docs/etl/sprints/AI-OPS-39/evidence/citizen_preset_codec_tests_postdocs_20260222T204927Z.txt`
  - `docs/etl/sprints/AI-OPS-39/evidence/citizen_preset_error_contract_markers_20260222T204717Z.txt`
  - `docs/etl/sprints/AI-OPS-39/evidence/explorer_gh_pages_build_postdocs_20260222T204927Z.txt`
  - `docs/etl/sprints/AI-OPS-39/evidence/tracker_gate_posttrackeredit_20260222T205129Z.txt`
