# AI-OPS-63 Prompt Pack

Objective:
- Harden initiative-doc actionable-tail operations with a JSON contract (`actionable_missing`) that can be consumed by humans, CI artifacts, and future automations.

Acceptance gates:
- `scripts/report_initdoc_actionable_tail_contract.py`:
  - emits deterministic JSON summary
  - computes `total_missing`, `redundant_missing`, `actionable_missing`
  - includes strict check `checks.actionable_queue_empty`
  - exits `4` under `--strict` when actionable rows remain
- `tests/test_report_initdoc_actionable_tail_contract.py` covers split + strict fail/pass.
- CI `initdoc-actionable-tail-contract` validates both CSV strict-empty and JSON reporter strict modes.
- `justfile` and `docs/etl/README.md` include operational commands.

Status update (2026-02-22):
- Implemented end-to-end and validated on real DB + deterministic fixtures.
