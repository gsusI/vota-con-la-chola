# Explorer Sources Initdoc Tail Compaction Trend (AI-OPS-67)

Date:
- 2026-02-23

Summary:
- Added compaction for initdoc tail heartbeat with explicit incident preservation.
- Added `raw vs compacted` parity checks over `last N` rows.
- Published parity block in status payload as `initdoc_actionable_tail.heartbeat_compaction_window`.
- Extended explorer-sources card with a compact parity pill.

Observed status (real DB run):
- digest:
  - `status=ok`
  - `actionable_missing=0`
  - `redundant_missing=119`
  - `total_missing=119`
- heartbeat window:
  - `status=ok`
  - `entries_in_window=4`
  - `failed=0`
  - `degraded=0`
  - `latest=ok`
- heartbeat compaction window:
  - `status=ok`
  - `window_raw_entries=4`
  - `missing_in_compacted_in_window=0`

Evidence:
- `docs/etl/sprints/AI-OPS-67/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_20260223T082401Z.json`
- `docs/etl/sprints/AI-OPS-67/evidence/initdoc_actionable_tail_digest_heartbeat_compaction_window_20260223T082401Z.json`
- `docs/etl/sprints/AI-OPS-67/evidence/explorer_sources_status_20260223T082658Z.json`
- `docs/etl/sprints/AI-OPS-67/evidence/explorer_sources_initdoc_tail_summary_20260223T082658Z.json`
