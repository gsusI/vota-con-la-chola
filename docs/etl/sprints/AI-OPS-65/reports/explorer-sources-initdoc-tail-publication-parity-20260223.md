# Explorer Sources Initdoc Tail Publication Parity (AI-OPS-65)

Date:
- 2026-02-23

Summary:
- Embedded initiative-doc actionable-tail contract+digest into explorer-sources status payload at generation time (`build_sources_status_payload`).
- Added a global KPI card in `/explorer-sources` to display Senate tail actionable status directly from that payload.
- Regenerated static GH Pages artifacts so published `status.json` and UI use the same contract path as local API mode.

Real payload status:
- `initdoc_actionable_tail.digest.status=ok`
- `actionable_missing=0`
- `redundant_missing=119`
- `total_missing=119`

Timestamp:
- 20260223T075839Z

Evidence:
- `docs/etl/sprints/AI-OPS-65/evidence/explorer_sources_status_20260223T075839Z.json`
- `docs/etl/sprints/AI-OPS-65/evidence/explorer_sources_initdoc_tail_summary_20260223T075839Z.json`
- `docs/etl/sprints/AI-OPS-65/evidence/export_explorer_sources_status_cmd_20260223T075839Z.txt`
- `docs/etl/sprints/AI-OPS-65/evidence/explorer_gh_pages_build_20260223T075853Z.txt`
- `docs/etl/sprints/AI-OPS-65/evidence/explorer_sources_initdoc_tail_markers_20260223T075912Z.txt`
