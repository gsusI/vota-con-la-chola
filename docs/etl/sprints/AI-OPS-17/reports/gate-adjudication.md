# Gate Adjudication (AI-OPS-17)

Date: 2026-02-17

## Gate Table (G1-G6)

| Gate | Requirement | Verdict | Evidence |
|---|---|---|---|
| G1 Visible product | Citizen-first page exists under GH Pages and is linked from landing | PASS | `docs/etl/sprints/AI-OPS-17/evidence/landing-link.txt`; `docs/etl/sprints/AI-OPS-17/evidence/gh-pages-build-citizen.log`; `docs/etl/sprints/AI-OPS-17/evidence/gh-pages-publish.log` |
| G2 Evidence drill-down | Every stance card links to concrete explorer drill-down | PASS | `docs/etl/sprints/AI-OPS-17/reports/link-check.md`; `docs/etl/sprints/AI-OPS-17/reports/citizen-walkthrough.md` |
| G3 Honesty | Unknown/no-signal rendered explicitly (not imputed) | PASS | `docs/etl/sprints/AI-OPS-17/evidence/citizen-validate.txt`; `docs/etl/sprints/AI-OPS-17/reports/citizen-ui-design.md` |
| G4 Size/perf | Citizen snapshot JSON bounded (no giant blobs) | PASS | `docs/etl/sprints/AI-OPS-17/evidence/citizen-json-size.txt`; `docs/etl/sprints/AI-OPS-17/evidence/citizen-export.log`; `docs/etl/sprints/AI-OPS-17/evidence/citizen-validate.txt` |
| G5 Strict gate/parity | Strict tracker gate green and status parity overall_match=true | PASS | `docs/etl/sprints/AI-OPS-17/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-17/evidence/tracker-gate-postrun.log`; `docs/etl/sprints/AI-OPS-17/evidence/status-parity-postrun.txt` |
| G6 Reproducibility | Snapshot export deterministic from `--db` + scope/as-of | PASS | `scripts/export_citizen_snapshot.py`; `docs/etl/sprints/AI-OPS-17/reports/citizen-export-design.md`; `docs/etl/sprints/AI-OPS-17/evidence/citizen-export.log` |

## Notes
- Citizen app is static-only; it consumes `citizen.json` and `concerns_v1.json` via `fetch()` from GH Pages.
- Concern tags are keyword matches over topic labels (navigation, not classification).
