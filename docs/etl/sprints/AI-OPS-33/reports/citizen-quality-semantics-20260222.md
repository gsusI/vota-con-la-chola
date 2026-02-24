# Citizen Quality Semantics (AI-OPS-33)

Date:
- 2026-02-22

Goal:
- Make the citizen-facing quality semantics explicit, reproducible, and validated in the exported static snapshot.

## Changes

1. Export contract (`scripts/export_citizen_snapshot.py`)
- Added `meta.quality` summary with:
  - `cells_total`
  - `stance_counts`
  - `clear_total`, `clear_pct`
  - `any_signal_total`, `any_signal_pct`
  - `unknown_total`, `unknown_pct`
  - `confidence_avg_signal`
  - `confidence_tiers` (`high/medium/low/none`)
  - `confidence_thresholds` (`high_min`, `medium_min`)

2. Validator contract (`scripts/validate_citizen_snapshot.py`)
- Added optional strict checks for `meta.quality`:
  - key presence/type
  - percentage bounds `[0,1]`
  - stance/tier sum consistency with `cells_total`
  - threshold order consistency

3. Citizen UI semantics (`ui/citizen/index.html`)
- Added explicit copy and status chips for quality semantics.
- Added confidence tier tags in party/program cards.
- Kept static-first/no-server requirements intact.

## Evidence

- Build:
  - `docs/etl/sprints/AI-OPS-33/evidence/explorer_gh_pages_build_20260222T195640Z.txt`
- Snapshot quality summary:
  - `docs/etl/sprints/AI-OPS-33/evidence/citizen_quality_meta_summary_20260222T195715Z.json`
- Validator triplet:
  - `docs/etl/sprints/AI-OPS-33/evidence/citizen_validator_triplet_20260222T195715Z.txt`

## Key Results

- `citizen.json`: `clear_pct=0.824324`, `unknown_pct=0.175676`, `confidence_avg_signal=0.594253`
- `citizen_declared.json`: `clear_pct=0.006194`, `unknown_pct=0.993806`, `confidence_avg_signal=0.090323`
- `citizen_votes.json`: `clear_pct=0.824324`, `unknown_pct=0.175676`, `confidence_avg_signal=0.594902`

Outcome:
- Quality semantics are now first-class in artifacts and UI, enabling clearer citizen interpretation without changing the underlying evidence model.
