# AI-OPS-143 - Liberty personal identity provenance gate

## Context (where we are now)
- Row `103` (evidencia y scoring de atribucion personal) had identity resolution at `100%` after AI-OPS-142, but all alias mappings came from `manual_seed`.
- This created a quality blind spot: `resolved` did not distinguish manual alias coverage vs official-source alias coverage.

## Goal (where we are going)
- Keep identity-resolution determinism (`exact_name + alias`) while making provenance quality explicit and enforceable.
- Add a measurable contract to track migration from `manual_seed` aliases to `official_*` alias evidence.

## Shipped in this slice
1. Schema hardening (`person_name_aliases`)
- New columns: `source_kind`, `evidence_date`, `evidence_quote`.
- New index: `idx_person_name_aliases_source_kind`.
- Forward-compat in `ensure_schema_compat()` for existing DBs.

2. Seed contract hardening (`liberty_person_identity_resolution_seed_v1`)
- Each mapping now declares `source_kind`.
- Validator enforces:
  - `source_kind` in allowed enum.
  - For `official_*`: required `source_url`, `evidence_date`, `evidence_quote`.
- Current seed stays explicit `manual_seed` for all 9 mappings (no fake official coverage).

3. Import hardening
- Import persists `source_kind`, `evidence_date`, `evidence_quote`.
- Adds import counters for provenance mix:
  - `manual_mappings_total`, `official_mappings_total`
  - totals `manual_aliases_total`, `official_aliases_total`.

4. Scoring + queue provenance gates
- `report_liberty_personal_accountability_scores.py` adds:
  - `indirect_person_edges_identity_resolved_alias_non_manual_total`
  - `indirect_person_edges_identity_resolved_alias_manual_total`
  - `coverage.indirect_non_manual_alias_resolution_pct`
  - check `indirect_non_manual_alias_resolution_gate`.
- `report_liberty_person_identity_resolution_queue.py` adds parallel totals/coverage/check.
- Gate semantics: if alias-resolved edges exist, enforce minimum non-manual share; if no alias-resolved edges, gate is N/A-pass.

5. `justfile` integration
- New env thresholds for personal scoring:
  - `LIBERTY_PERSONAL_INDIRECT_NON_MANUAL_ALIAS_RESOLUTION_MIN_PCT`
  - `LIBERTY_PERSONAL_MIN_INDIRECT_NON_MANUAL_ALIAS_RESOLUTION_EDGES`
- New env thresholds for queue gate:
  - `LIBERTY_PERSON_IDENTITY_NON_MANUAL_ALIAS_RESOLUTION_MIN_PCT`
  - `LIBERTY_PERSON_IDENTITY_NON_MANUAL_ALIAS_RESOLUTION_MIN_EDGES`
- Wired into `parl-report/check-liberty-personal-accountability-gate` and `parl-report/check-liberty-person-identity-resolution-gate`.

## Reproducible execution and evidence
- Run timestamp: `20260223T221925Z`
- Temp DB: `tmp/liberty_person_identity_provenance_20260223T221925Z.db`

Key evidence:
- Import provenance mix:
  - `docs/etl/sprints/AI-OPS-143/evidence/liberty_person_identity_import_20260223T221925Z.json`
- Personal scoring (pass path):
  - `docs/etl/sprints/AI-OPS-143/evidence/liberty_personal_accountability_scores_20260223T221925Z.json`
- Queue (pass path):
  - `docs/etl/sprints/AI-OPS-143/evidence/liberty_person_identity_resolution_queue_20260223T221925Z.json`
- Personal fail-path (`non_manual_alias_min_pct=1.0`):
  - `docs/etl/sprints/AI-OPS-143/evidence/liberty_personal_accountability_non_manual_alias_fail_20260223T221925Z.json`
  - `docs/etl/sprints/AI-OPS-143/evidence/just_parl_check_liberty_personal_accountability_non_manual_alias_fail_rc_20260223T221925Z.txt`
- Queue fail-path (`non_manual_alias_min_pct=1.0`):
  - `docs/etl/sprints/AI-OPS-143/evidence/liberty_person_identity_resolution_queue_non_manual_alias_fail_20260223T221925Z.json`
  - `docs/etl/sprints/AI-OPS-143/evidence/just_parl_check_liberty_person_identity_non_manual_alias_fail_rc_20260223T221925Z.txt`

Contract summary:
- Pass path: identity resolution stays `9/9` with explicit provenance split (`non_manual=0`, `manual=9`).
- Fail path: both new gates fail in strict mode with `exit=2` (expected).

## Tests
- Focused suite:
  - `Ran 20`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-143/evidence/unittest_liberty_person_identity_provenance_contract_20260223T221925Z.txt`
- Full rights suite:
  - `Ran 78`, `OK (skipped=1)`
  - `docs/etl/sprints/AI-OPS-143/evidence/just_parl_test_liberty_restrictions_20260223T221925Z.txt`

## Next (what is next)
- Start replacing `manual_seed` alias rows with `official_*` mappings from reproducible sources (nombramientos/resoluciones/expedientes), preserving evidence fields per mapping.
- Raise non-manual alias thresholds from `0.0` to strict values once official coverage is non-trivial.
