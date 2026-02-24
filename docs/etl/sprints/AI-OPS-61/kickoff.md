# AI-OPS-61 Kickoff

Date:
- 2026-02-22

Objective:
- Lock a reproducible actionable-tail contract for Senado initiative docs so operators stop reprocessing known non-actionable `global_enmiendas_vetos` 404 URLs.

Primary lane (controllable):
- Initiative-doc queue operations (`scripts/export_missing_initiative_doc_urls.py`, docs, just targets, tests).

Acceptance gates:
- New CLI flags in `scripts/export_missing_initiative_doc_urls.py`:
  - `--only-actionable-missing`
  - `--strict-empty`
- New just targets:
  - `just parl-export-missing-initdoc-urls-actionable`
  - `just parl-check-missing-initdoc-urls-actionable-empty`
- New tests for actionable filtering + strict exit behavior.
- Real DB evidence confirms actionable queue is empty while redundant tail is explicitly excluded.

DoD:
- Tests pass.
- Real run outputs captured under `docs/etl/sprints/AI-OPS-61/evidence/` and `docs/etl/sprints/AI-OPS-61/exports/`.
- Tracker/README/sprint index updated.
