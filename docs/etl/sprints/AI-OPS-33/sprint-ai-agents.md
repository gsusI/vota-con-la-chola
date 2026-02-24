# AI-OPS-33 Prompt Pack

Objective:
- Ship explicit, reproducible quality semantics in the citizen snapshot/UI so data confidence and unknown states are first-class.

Acceptance gates:
- `scripts/export_citizen_snapshot.py` emits `meta.quality` summary + thresholds.
- `scripts/validate_citizen_snapshot.py` validates `meta.quality` contract and invariants.
- `ui/citizen/index.html` renders unknown semantics and confidence-tier tags.
- GH Pages build + validator triplet pass and evidence artifacts are saved.

Status update (2026-02-22):
- `scripts/export_citizen_snapshot.py`:
  - added `summarize_snapshot_quality(...)`
  - added confidence tiers (`high/medium/low/none`) with thresholds
  - snapshot now emits `meta.quality` with stance counts, clear/unknown/any_signal metrics and `confidence_avg_signal`
- `scripts/validate_citizen_snapshot.py`:
  - added validation for `meta.quality` keys, bounds, sums, and threshold ordering
- `tests/test_export_citizen_snapshot.py`:
  - updated assertions for `meta.quality` contract
- `ui/citizen/index.html`:
  - explicit text `unknown = incierto + sin_senal`
  - status chips from `meta.quality` (`senal_clara`, `unknown`, `conf_media`)
  - per-card `conf_tier` tags for party/program rows
- evidence:
  - `docs/etl/sprints/AI-OPS-33/evidence/explorer_gh_pages_build_20260222T195640Z.txt`
  - `docs/etl/sprints/AI-OPS-33/evidence/citizen_quality_meta_summary_20260222T195715Z.json`
  - `docs/etl/sprints/AI-OPS-33/evidence/citizen_validator_triplet_20260222T195715Z.txt`
