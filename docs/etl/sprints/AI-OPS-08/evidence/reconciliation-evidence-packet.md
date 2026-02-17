# AI-OPS-08 Reconciliation Evidence Packet

## Scope and objective
- Prove reproducible parity between tracker/sql payload (`status.json`) and checker outputs for AI-OPS-08 closeout.
- Focus sources: `boe_api_legal`, `parlamento_navarra_parlamentarios_forales`, `moncloa_referencias`, `moncloa_rss_referencias`.
- Waiver registry input: `docs/etl/mismatch-waivers.json`.

## Command list (exact)
1. `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json`
2. `just etl-tracker-gate`
3. `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real`
4. `python3 - <<'PY' ... payload summary for boe/moncloa/navarra ... PY`
5. regenerate parity matrix: `docs/etl/sprints/AI-OPS-08/exports/mismatch_matrix.csv`

## Command outputs
- Snapshot refresh:
  - `OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json`
- Strict gate (`just etl-tracker-gate`) result:
  - `mismatches: 0`
  - `waived_mismatches: 0`
  - `waivers_active: 0`
  - `waivers_expired: 0`
  - `done_zero_real: 0`
  - exit code `0`
- Focus payload rows:
  - `boe_api_legal`: `tracker=DONE`, `sql_status=DONE`, `mismatch_state=MATCH`
  - `moncloa_referencias`: `tracker=DONE`, `sql_status=DONE`, `mismatch_state=MATCH`
  - `moncloa_rss_referencias`: `tracker=DONE`, `sql_status=DONE`, `mismatch_state=MATCH`
  - `parlamento_navarra_parlamentarios_forales`: `tracker=PARTIAL`, `sql_status=PARTIAL`, `mismatch_state=MATCH`
- Payload summary tracker block:
  - `mismatch=0`
  - `waived_mismatch=0`
  - `waivers_active=0`
  - `waivers_expired=0`
  - `done_zero_real=0`

## Mismatch matrix
- Artifact: `docs/etl/sprints/AI-OPS-08/exports/mismatch_matrix.csv`
- Result: all four audited sources parity-consistent (`parity_overall=TRUE`, `field_diff` empty).

## Gate-ready summary
- Reconciliation is green for audited fields.
- No active/expired waivers in closeout state.
- Strict gate contract is satisfied with deterministic default path.

## Evidence artifacts
- `docs/etl/sprints/AI-OPS-08/reports/boe-tracker-mapping-hardening.md`
- `docs/etl/sprints/AI-OPS-08/reports/tracker-gate-policy-default.md`
- `docs/etl/sprints/AI-OPS-08/reports/waiver-burndown-apply-recompute.md`
- `docs/etl/sprints/AI-OPS-08/evidence/tracker-row-reconciliation.md`
- `docs/etl/sprints/AI-OPS-08/exports/mismatch_matrix.csv`
