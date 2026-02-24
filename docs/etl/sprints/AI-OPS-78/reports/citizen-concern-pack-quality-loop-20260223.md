# Citizen Concern-Pack Quality Loop (AI-OPS-78)

Date:
- 2026-02-23

Goal:
- Add a reproducible quality loop for concern packs and expose weak-pack signals directly in `/citizen`.

What shipped:
- New machine-readable contract script:
  - `scripts/report_citizen_concern_pack_quality.py`
  - computes per-pack metrics (`topics_total`, `clear/unknown pct`, `confidence_avg_signal`, `high_stakes_share`, `quality_score`)
  - emits per-pack `weak` + `weak_reasons`
  - supports strict gating (`--strict`) via `max_weak_packs` threshold
- New tests:
  - `tests/test_report_citizen_concern_pack_quality.py`
  - `tests/test_citizen_concern_pack_quality_ui_contract.js`
- `justfile` integration:
  - new env vars `CITIZEN_PACK_QUALITY_*`
  - new targets:
    - `just citizen-test-concern-pack-quality`
    - `just citizen-report-concern-pack-quality`
    - `just citizen-check-concern-pack-quality`
  - GH Pages build now emits:
    - `docs/gh-pages/citizen/data/concern_pack_quality.json`
- `/citizen` UI integration (`ui/citizen/index.html`):
  - optional load of `./data/concern_pack_quality.json`
  - quality-aware pack recommendation tie-break
  - pack tags with quality score and weak marker (`data-pack-weak`)
  - active-pack hint includes `pack_debil` marker and reasons (`data-pack-weak-hint`)
  - status chips include `packs_weak` and active `pack_quality`

Validation:
- `just citizen-test-concern-pack-quality`
- `just citizen-check-concern-pack-quality`
- regression:
  - `just citizen-test-preset-codec`
  - `just citizen-test-mobile-performance`
  - `just citizen-test-first-answer-accelerator`

Current quality snapshot (default thresholds):
- `packs_total=4`
- `weak_packs_total=0`
- `status=ok`
- artifact: `docs/etl/sprints/AI-OPS-78/evidence/citizen_concern_pack_quality_20260223T112045Z.json`

Evidence:
- `docs/etl/sprints/AI-OPS-78/evidence/citizen_concern_pack_quality_contract_summary_20260223T112045Z.json`
- `docs/etl/sprints/AI-OPS-78/evidence/citizen_concern_pack_quality_contract_markers_20260223T112045Z.txt`
- `docs/etl/sprints/AI-OPS-78/evidence/just_citizen_test_concern_pack_quality_20260223T112045Z.txt`
- `docs/etl/sprints/AI-OPS-78/evidence/just_citizen_check_concern_pack_quality_20260223T112045Z.txt`
