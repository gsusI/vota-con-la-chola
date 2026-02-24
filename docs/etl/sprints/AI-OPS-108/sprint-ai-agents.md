# AI-OPS-108 Prompt Pack

Objective:
- Ship Tailwind+MD3 drift heartbeat retention v1 so `/citizen` visual-drift trend monitoring can compact history safely while keeping strict parity guarantees in last-N windows.

Acceptance gates:
- Add Tailwind+MD3 drift heartbeat compaction reporter (`scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction.py`).
- Add Tailwind+MD3 drift heartbeat compaction-window parity reporter (`scripts/report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window.py`).
- Preserve incident classes: `failed`, `degraded`, `strict`, `malformed`, contract flags (`tailwind_contract_exists/status_ok/checks_ok`), and parity mismatch flags (`source_published`, `marker`, `tokens`, `tokens_data`, `css`, `ui_html`, `parity_fail`).
- Add deterministic tests for compaction preservation + compaction-window strict parity.
- Wire `just` report/check lanes and include new tests in `citizen-test-tailwind-md3`.
- Publish strict evidence bundle under `docs/etl/sprints/AI-OPS-108/evidence/`.

Status update (2026-02-23):
- Implemented and validated with strict evidence (`compaction_strict_fail_reasons=[]`, `compaction_window_status=ok`, `incident_missing_in_compacted=0`).
