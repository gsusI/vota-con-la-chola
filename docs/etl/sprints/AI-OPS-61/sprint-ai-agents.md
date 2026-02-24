# AI-OPS-61 Prompt Pack

Objective:
- Convert Senado initiative-doc tail handling into an explicit actionable contract and gate:
  - export actionable-only queue
  - fail fast when actionable queue is non-empty

Acceptance gates:
- `scripts/export_missing_initiative_doc_urls.py` supports:
  - `--only-actionable-missing` (operational shortcut)
  - `--strict-empty` (exit `4` when exported queue has rows)
- `tests/test_export_missing_initiative_doc_urls.py` covers:
  - redundant Senado global URL filtering in actionable mode
  - strict-empty fail path
  - strict-empty pass path
- `justfile` includes actionable export/check targets.
- `docs/etl/README.md` operational section reflects the new commands.
- Real-state evidence proves:
  - Senado actionable queue `0`
  - excluded redundant global URLs `119`

Status update (2026-02-22):
- Shipped end-to-end with tests and just targets.
