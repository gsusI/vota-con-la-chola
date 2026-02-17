# Setup Wave Signoff (GO/NO-GO)

Sprint: `AI-OPS-18`  
Date: `2026-02-17`

## Summary
Setup wave delivers a reproducible, static citizen-first app wired into GH Pages build output.

## Gates (G1-G6)
- **G1 Visible product**: PASS (citizen app under `docs/gh-pages/citizen/` and linked from landing).
- **G2 Evidence drill-down**: PASS (topic + stance cards link to existing explorers).
- **G3 Honesty**: PASS (`no_signal` and `unclear` rendered explicitly).
- **G4 Size/perf**: PASS (`citizen.json` guarded `<= 5MB` and validated).
- **G5 Strict gate/parity**: Not evaluated in setup wave (must remain green during FAST lane).
- **G6 Reproducibility**: PASS (export driven by `--db` and deterministic scope inference).

## Artifacts (Must Exist)
- `ui/citizen/index.html`
- `ui/citizen/concerns_v1.json`
- `scripts/export_citizen_snapshot.py`
- `scripts/validate_citizen_snapshot.py`
- `docs/etl/sprints/AI-OPS-18/reports/scope-lock.md`
- `docs/etl/sprints/AI-OPS-18/reports/citizen-data-contract.md`
- `docs/etl/sprints/AI-OPS-18/reports/citizen-export-design.md`
- `docs/etl/sprints/AI-OPS-18/reports/concern-taxonomy-v1.md`
- `docs/etl/sprints/AI-OPS-18/reports/citizen-ui-design.md`
- `docs/etl/sprints/AI-OPS-18/reports/gh-pages-integration.md`
- `docs/etl/sprints/AI-OPS-18/reports/citizen-validator.md`

## Runnable Commands
Build everything to `docs/gh-pages/` (includes export + validation):
```bash
just explorer-gh-pages-build
```

Validate snapshot explicitly (standalone):
```bash
python3 scripts/validate_citizen_snapshot.py \
  --path docs/gh-pages/citizen/data/citizen.json \
  --max-bytes 5000000 \
  --strict-grid
```

## GO / NO-GO
- **GO** to FAST lane: citizen build is one-command reproducible and validated locally.
- **NO-GO** if:
  - `just explorer-gh-pages-build` fails
  - validator fails (schema drift, broken refs, size > limit)
  - landing link disappears or evidence drill-down breaks
