# AI-OPS-16 Closeout

Date: 2026-02-17  
Decision owner: L3 Orchestrator

## Sprint Verdict
- **PASS**
- Reason: the sprint objective was met with measurable, evidence-backed declared-signal improvement on `congreso_intervenciones` while strict gate, integrity, queue health, publish parity, and anti-loop blocker policy all stayed green.

## Gate Evaluation

| Gate | Result | Evidence | Notes |
|---|---|---|---|
| Gate G1 - Integrity | PASS | live SQL check (`pragma_foreign_key_check`); `docs/etl/sprints/AI-OPS-16/reports/gate-adjudication.md` | `fk_violations=0`. |
| Gate G2 - Queue health | PASS | `docs/etl/sprints/AI-OPS-16/exports/review_queue_snapshot.csv`; `docs/etl/sprints/AI-OPS-16/reports/gate-adjudication.md` | `topic_evidence_reviews_pending=0`. |
| Gate G3 - Tracker strict gate | PASS | `docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log`; `docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-16/reports/final-gate-parity.md` | strict gate exit `0`; `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`. |
| Gate G4 - Publish/status parity | PASS | `docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json`; `docs/etl/sprints/AI-OPS-16/evidence/status-parity-postrun.txt`; `docs/etl/sprints/AI-OPS-16/reports/final-gate-parity.md` | `overall_match=true`; required tracker/impact keys matched. |
| Gate G5 - Visible progress (primary lane) | PASS | `docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv`; `docs/etl/sprints/AI-OPS-16/exports/declared_selected_metrics.csv`; `docs/etl/sprints/AI-OPS-16/exports/declared_diff_matrix.csv`; `docs/etl/sprints/AI-OPS-16/reports/reconciliation-apply.md` | measurable delta achieved in declared signal. |
| Gate G6 - Blocker lane policy | PASS (policy-neutral) | `docs/etl/sprints/AI-OPS-16/evidence/blocker-lever-check.log`; `docs/etl/sprints/AI-OPS-16/exports/unblock_feasibility_matrix.csv` | `strict_probes_executed=0`, `no_new_lever_count=4`; no blind retries. |

## Objective Delta

Primary objective (declared signal quality/coverage for `congreso_intervenciones`):
- `declared_total`: `614 -> 614` (`0`)
- `declared_with_signal`: `202 -> 204` (`+2`)
- `declared_with_signal_pct`: `0.32899 -> 0.332248` (`+0.003258`)
- `review_pending`: `0 -> 0`
- `review_conflicting_signal`: `0 -> 0`

Supporting postrun metrics:
- `coherence_overlap_total=155`
- `coherence_explicit_total=99`
- `coherence_coherent_total=52`
- `coherence_incoherent_total=47`
- `topic_evidence_reviews_pending=0`

## External Blocker Carryover

Unchanged blocker set (no new lever detected):
- `aemet_opendata_series` (`AEMET_API_KEY_present=0`)
- `bde_series_api` (`bde_dns_resolves=0`, DNS error)
- `parlamento_galicia_deputados` (no approved reproducible bypass policy)
- `parlamento_navarra_parlamentarios_forales` (no approved reproducible bypass policy)

Policy handling:
- blockers were evaluated by lever checks only.
- no strict-network retries were executed without a new lever.

## Evidence Commands (Postrun)

```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-17
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-17 --fail-on-mismatch --fail-on-done-zero-real
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id congreso_intervenciones --min-auto-confidence 0.58
python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db etl/data/staging/politicos-es.db --source-id congreso_intervenciones --as-of-date 2026-02-16
python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db etl/data/staging/politicos-es.db --as-of-date 2026-02-16
```

## next sprint trigger

AI-OPS-18 should start when at least one of these is true:
1. Product/roadmap priority moves to line `74` (`Posiciones declaradas (programas)`) to build the missing semistructured + human-review pipeline and reduce that `TODO` surface.
2. A new unblock lever appears for any carryover blocker (AEMET key provision, BDE DNS/endpoint restoration, or approved reproducible non-interactive bypass policy for Galicia/Navarra).
3. Strict gate/parity regresses (`mismatches>0`, `waivers_expired>0`, `done_zero_real>0`, or `overall_match=false`).
4. Declared-signal quality target is raised beyond current `0.332248` and requires another bounded quality wave (regex/rules + adjudication throughput) with the same anti-loop policy.

## Escalation rule check

T24 escalation condition:
- escalate if verdict cannot be supported by evidence.

Observed:
- all verdict claims are directly backed by gate/parity/delta artifacts.

Decision:
- `NO_ESCALATION`.
