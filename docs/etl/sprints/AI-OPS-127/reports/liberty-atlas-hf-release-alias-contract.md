# AI-OPS-127 — Liberty Atlas HF `release-latest` alias contract

## Goal
Close the remaining gap for Atlas public distribution by making the HF bundle contract fail-fast when `release-latest` is missing/misaligned, and tighten release heartbeat tolerance to `hf_unavailable=0` in strict window mode.

## Delivered
- `scripts/publicar_hf_snapshot.py`
  - Added `--require-liberty-atlas-release-latest` guardrail.
  - Added `ensure_liberty_atlas_release_latest_for_publish(...)` to enforce:
    - `etl/data/published/liberty-restrictions-atlas-release-latest.json` exists.
    - JSON payload is valid.
    - `snapshot_date` matches `--snapshot-date`.
    - `status` is `ok` when present.
  - Included `liberty-restrictions-atlas-release-latest.json` explicitly in HF `published/*` packaging.
  - Propagated `liberty_atlas_release_latest` contract metadata into `manifest.json` and `latest.json`.

- `justfile`
  - New env guard: `HF_REQUIRE_LIBERTY_ATLAS_RELEASE_LATEST` (default `1`).
  - `just etl-publish-hf` and `just etl-publish-hf-dry-run` now pass `--require-liberty-atlas-release-latest` by default.
  - Hardened release window threshold: `LIBERTY_ATLAS_RELEASE_WINDOW_MAX_HF_UNAVAILABLE=0`.

- `scripts/report_liberty_atlas_release_heartbeat.py`
  - Added `.env` fallback loader for `HF_DATASET_REPO_ID` / `HF_USERNAME`.
  - HF repo resolution now works without manual shell exports in default local runs.

- `tests/test_publicar_hf_snapshot.py`
  - Added alias inclusion assertion in `collect_published_files`.
  - Added contract tests for `ensure_liberty_atlas_release_latest_for_publish`:
    - success,
    - missing alias,
    - snapshot mismatch.

## Verification
Run timestamp baseline: `20260223T195745Z`.

- Unit tests:
  - `python3 -m unittest tests/test_publicar_hf_snapshot.py tests/test_report_liberty_atlas_release_heartbeat.py tests/test_report_liberty_atlas_release_heartbeat_window.py`
  - Evidence: `docs/etl/sprints/AI-OPS-127/evidence/unittest_hf_alias_and_release_heartbeat_20260223T195613Z.txt`

- HF dry-run contract:
  - `SNAPSHOT_DATE=2026-02-23 just etl-publish-hf-dry-run`
  - PASS with `Published files: 11` (alias included under `published/*`).
  - Evidence: `docs/etl/sprints/AI-OPS-127/evidence/just_etl_publish_hf_dry_run_post_contract_20260223T195745Z.txt`

- Liberty lane regression:
  - `SNAPSHOT_DATE=2026-02-23 just parl-test-liberty-restrictions`
  - `SNAPSHOT_DATE=2026-02-23 just parl-liberty-restrictions-pipeline`
  - PASS.
  - Evidence:
    - `docs/etl/sprints/AI-OPS-127/evidence/just_parl_test_liberty_restrictions_20260223T195745Z.txt`
    - `docs/etl/sprints/AI-OPS-127/evidence/just_parl_liberty_restrictions_pipeline_20260223T195745Z.txt`

- Strict release window (`max_hf_unavailable=0`):
  - `SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-atlas-release-heartbeat-window`
  - PASS with `window_last=20`, `failed=0`, `hf_unavailable=0`, `status=ok`.
  - Evidence: `docs/etl/sprints/AI-OPS-127/evidence/just_parl_check_liberty_atlas_release_heartbeat_window_post_warm_20260223T195629Z.txt`

## Notes
- During cutover, old heartbeat rows with `hf_repo_unresolved` caused temporary window failures under the new threshold. This was resolved by appending clean runs until the strict `last 20` window fully reflected the new contract behavior.
