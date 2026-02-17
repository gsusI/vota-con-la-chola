# AI-OPS-07 reconciliation evidence packet

## Scope and objective
- Date: 2026-02-16 (sprint AI-OPS-07)
- Goal: produce a reproducible packet proving gate outcome, dashboard parity, and waiver governance artifacts.
- Inputs:
  - `docs/gh-pages/explorer-sources/data/status.json`
  - `docs/etl/sprints/AI-OPS-07/reports/dual-entry-apply-recompute.md`
  - `docs/etl/sprints/AI-OPS-07/evidence/tracker-row-reconciliation.md`
  - `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json`

## Command list and log paths
1. Refresh explorer snapshot
   - Command: `python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json`
   - Log: `docs/etl/sprints/AI-OPS-07/evidence/final_packet_snapshot_refresh.log`
2. Snapshot summary extraction
   - Command: `jq '.summary.sql,.summary.tracker' docs/gh-pages/explorer-sources/data/status.json`
   - Log: `docs/etl/sprints/AI-OPS-07/evidence/final_packet_snapshot_summary.log`
3. Policy-events matrix counters (applied state at snapshot time)
   - Log: `docs/etl/sprints/AI-OPS-07/evidence/final_packet_counts.log`
4. Gate matrix and checker references
   - Strict unwaived checker: `docs/etl/sprints/AI-OPS-07/evidence/post_apply_strict_checker_final.log`
   - Waiver-aware checker: `docs/etl/sprints/AI-OPS-07/evidence/post_apply_waiveraware_checker_final.log`
   - Apply report context: `docs/etl/sprints/AI-OPS-07/reports/dual-entry-apply-recompute.md`

## Command outputs (exact values)
- Snapshot command output:
  - `OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json`
- Snapshot summary:
  - `summary.sql` = `{ "todo": 0, "partial": 1, "done": 32, "foreign_key_violations": 0 }`
  - `summary.tracker` = `{ "items_total": 46, "unmapped": 21, "todo": 16, "partial": 5, "done": 25, "mismatch": 3, "waived_mismatch": 0, "done_zero_real": 0, "untracked_sources": 6, "waivers_active": 0, "waivers_expired": 0, "waivers_error": "" }`
- Policy-event policy counts from `final_packet_counts.log`:
  - `policy_events_moncloa = 28`
  - `policy_events_boe = 298`

## Gate-ready metrics
### Before apply (from `dual-entry-apply-recompute.md` and pre-apply logs)
- strict path: `mismatches: 3`, `waived_mismatches: 0`, `waivers_active: 0`
- waiver-aware path: `mismatches: 0`, `waived_mismatches: 3`, `waivers_active: 3`
- policy events: `policy_events_moncloa = 28`, `policy_events_boe = 3`

### After apply (post-apply logs)
- strict path:
  - `mismatches: 3`
  - `waived_mismatches: 0`
  - `waivers_active: 0`
  - `done_zero_real: 0`
  - `EXIT_CODE_STRICT_UNWAIVED = 1`
  - mismatch sources: `moncloa_referencias`, `moncloa_rss_referencias`, `parlamento_navarra_parlamentarios_forales`
- waiver-aware path:
  - `mismatches: 0`
  - `waived_mismatches: 3`
  - `waivers_active: 3`
  - `waivers_expired: 0`
  - `done_zero_real: 0`
  - `EXIT_CODE_WAIVER_AWARE = 0`
  - `WAIVED_MISMATCH` sources: `moncloa_referencias`, `moncloa_rss_referencias`, `parlamento_navarra_parlamentarios_forales`

## Audit parity matrix
- Parity source artifact: `docs/etl/sprints/AI-OPS-07/evidence/parity_matrix.tsv`
- Field comparison artifact: `docs/etl/sprints/AI-OPS-07/evidence/payload_parity_field_level.tsv`
- Required audited fields: `tracker.status`, `sql_status`, `mismatch_state`, `mismatch_waived`, `waiver_expiry`

### Field-level divergence table (payload vs checker + policy expected)
Source IDs below differ from expected strict/waiver-aware parity.

| source_id | tracker_status | sql_status | mismatch_state | expected_mismatch_state | mismatch_waived | expected_mismatch_waived | waiver_expiry | expected_waiver_expiry |
|---|---|---|---|---|---|---|---|---|
| congreso_iniciativas | `N/A` (UNTRACKED) | `DONE` | `UNTRACKED` | `MATCH` | `FALSE` | `FALSE` | `` | `` |
| congreso_votaciones | `N/A` (UNTRACKED) | `DONE` | `UNTRACKED` | `MATCH` | `FALSE` | `FALSE` | `` | `` |
| senado_votaciones | `N/A` (UNTRACKED) | `DONE` | `UNTRACKED` | `MATCH` | `FALSE` | `FALSE` | `` | `` |
| moncloa_referencias | `PARTIAL` | `DONE` | `MISMATCH` | `WAIVED_MISMATCH` | `FALSE` | `TRUE` | `` | `2026-02-20` |
| moncloa_rss_referencias | `PARTIAL` | `DONE` | `MISMATCH` | `WAIVED_MISMATCH` | `FALSE` | `TRUE` | `` | `2026-02-20` |
| parlamento_navarra_parlamentarios_forales | `PARTIAL` | `DONE` | `MISMATCH` | `WAIVED_MISMATCH` | `FALSE` | `TRUE` | `` | `2026-02-20` |

### Escalation note
- `mismatch_waived`/`waiver_expiry` in snapshot are empty/false for all rows because `scripts/export_explorer_sources_snapshot.py` currently reads `docs/etl/mismatch-waivers.json` (currently `[]`) and does not ingest `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json` directly.
- This creates a reproducibility gap for waiver governance in the dashboard payload.

## Waiver expiry audit
- Source: `docs/etl/sprints/AI-OPS-06/evidence/mismatch-policy-applied.json`
- Upcoming expiries (as-of snapshot run, remaining days <=14):
  - `moncloa_referencias` — `expires_on: 2026-02-20`, `owner: L2` (4 days)
  - `moncloa_rss_referencias` — `expires_on: 2026-02-20`, `owner: L2` (4 days)
  - `parlamento_navarra_parlamentarios_forales` — `expires_on: 2026-02-20`, `owner: L2` (4 days)

## Proof inventory (command and artifact list)
- `docs/etl/sprints/AI-OPS-07/evidence/reconciliation_snapshot_refresh.log`
- `docs/etl/sprints/AI-OPS-07/evidence/final_packet_snapshot_refresh.log`
- `docs/etl/sprints/AI-OPS-07/evidence/final_packet_snapshot_summary.log`
- `docs/etl/sprints/AI-OPS-07/evidence/final_packet_counts.log`
- `docs/etl/sprints/AI-OPS-07/evidence/parity_matrix.tsv`
- `docs/etl/sprints/AI-OPS-07/evidence/waiver_expiry_audit.tsv`
- `docs/etl/sprints/AI-OPS-07/evidence/payload_parity_field_level.tsv`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_strict_checker_final.log`
- `docs/etl/sprints/AI-OPS-07/evidence/post_apply_waiveraware_checker_final.log`
- `docs/etl/sprints/AI-OPS-07/reports/dual-entry-apply-recompute.md`
- `docs/etl/sprints/AI-OPS-07/evidence/tracker-row-reconciliation.md`

## Gate exit status
- `EXIT_CODE_STRICT_UNWAIVED = 1`
- `EXIT_CODE_WAIVER_AWARE = 0`

