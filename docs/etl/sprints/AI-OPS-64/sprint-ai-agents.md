# AI-OPS-64 Prompt Pack

Objective:
- Produce a lightweight, machine-readable initiative-doc actionable-tail digest for alerting/dashboard cards while preserving strict CI contracts.

Acceptance gates:
- `scripts/report_initdoc_actionable_tail_digest.py`:
  - consumes JSON from `report_initdoc_actionable_tail_contract.py`
  - emits compact payload with `status`, `totals`, `thresholds`, `checks`, `strict_fail_reasons`
  - strict mode exits `4` only for `status=failed`
- `tests/test_report_initdoc_actionable_tail_digest.py` covers:
  - `ok` (queue empty),
  - `degraded` (queue non-empty but within thresholds),
  - strict fail/pass exit codes.
- `justfile` adds digest wrappers.
- CI `initdoc-actionable-tail-contract` validates digest strict fail/pass and uploads artifacts.

Status update (2026-02-22):
- Implemented and validated on fixture tests + real DB strict run (`status=ok`, `actionable_missing=0`).
