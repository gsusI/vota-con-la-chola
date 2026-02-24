# Explorer Sources Initdoc Tail Trend Lane (AI-OPS-66)

Date:
- 2026-02-23

Summary:
- Added a heartbeat lane for the initdoc actionable-tail digest (`docs/etl/runs/initdoc_actionable_tail_digest_heartbeat.jsonl`) with dedupe by `heartbeat_id`.
- Added a window reporter (`last N`) with strict checks for failed/degraded rates and latest row health.
- Embedded `initdoc_actionable_tail.heartbeat_window` in `/api/sources/status` and static `docs/gh-pages/explorer-sources/data/status.json`.
- Updated `/explorer-sources` card to show trend status and a one-line summary (`failed/degraded/latest`).

Observed status (real DB run):
- digest:
  - `status=ok`
  - `actionable_missing=0`
  - `redundant_missing=119`
  - `total_missing=119`
- heartbeat window:
  - `status=ok`
  - `entries_in_window=1`
  - `failed=0`
  - `degraded=0`
  - `latest=ok`

Evidence:
- `docs/etl/sprints/AI-OPS-66/evidence/initdoc_actionable_tail_contract_20260223T081121Z.json`
- `docs/etl/sprints/AI-OPS-66/evidence/initdoc_actionable_tail_digest_20260223T081121Z.json`
- `docs/etl/sprints/AI-OPS-66/evidence/initdoc_actionable_tail_digest_heartbeat_20260223T081121Z.json`
- `docs/etl/sprints/AI-OPS-66/evidence/initdoc_actionable_tail_digest_heartbeat_window_20260223T081121Z.json`
- `docs/etl/sprints/AI-OPS-66/evidence/explorer_sources_status_20260223T081139Z.json`
- `docs/etl/sprints/AI-OPS-66/evidence/explorer_sources_initdoc_tail_summary_20260223T081139Z.json`
