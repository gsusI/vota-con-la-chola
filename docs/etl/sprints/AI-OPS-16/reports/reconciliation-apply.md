# AI-OPS-16 T21 Reconciliation Apply

Date:
- `2026-02-17`

Objective:
- Convert postrun reconciliation draft into a policy-aligned apply report with explicit decision, delta summary, and tracker/doc patch plan.

## Inputs used

- `docs/etl/sprints/AI-OPS-16/reports/reconciliation-draft.md`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-status-postrun.log`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-status-postrun.exit`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.log`
- `docs/etl/sprints/AI-OPS-16/evidence/tracker-gate-postrun.exit`
- `docs/etl/sprints/AI-OPS-16/evidence/status-postrun.json`
- `docs/etl/sprints/AI-OPS-16/evidence/status-parity-postrun.txt`
- `docs/etl/sprints/AI-OPS-16/exports/declared_kpi_baseline.csv`
- `docs/etl/sprints/AI-OPS-16/exports/declared_selected_metrics.csv`
- `docs/etl/sprints/AI-OPS-16/exports/declared_diff_matrix.csv`
- `docs/etl/sprints/AI-OPS-16/exports/coherence_post.csv`
- `docs/etl/sprints/AI-OPS-16/exports/review_queue_snapshot.csv`
- `docs/etl/sprints/AI-OPS-16/evidence/blocker-lever-check.log`
- `docs/etl/sprints/AI-OPS-16/reports/kpi-acceptance-pack.md`
- `docs/etl/e2e-scrape-load-tracker.md`

## Evidence validation

Postrun gate evidence:
- `tracker-status-postrun.exit=0`
- `tracker-gate-postrun.exit=0`
- `mismatches=0`
- `waived_mismatches=0`
- `waivers_expired=0`
- `done_zero_real=0`

Postrun parity evidence:
- `overall_match=true` in `status-parity-postrun.txt`.
- parity keys matched for tracker summary and impact counters:
  - `summary.tracker.mismatch`
  - `summary.tracker.waived_mismatch`
  - `summary.tracker.done_zero_real`
  - `summary.tracker.waivers_expired`
  - `analytics.impact.indicator_series_total`
  - `analytics.impact.indicator_points_total`

Delivery-lane evidence:
- declared KPI delta (`declared_diff_matrix.csv`):
  - `declared_with_signal`: `202 -> 204` (`+2`)
  - `declared_with_signal_pct`: `0.32899 -> 0.332248` (`+0.003258`)
- selected threshold evidence (`declared_backfill_selected.log`): `selected_pass=pass2`, `selected_threshold=0.58`.
- queue closeout evidence (`review_queue_snapshot.csv`): `topic_evidence_reviews_pending=0`.
- coherence post packet (`coherence_post.csv`):
  - `coherence_overlap_total=155`
  - `coherence_explicit_total=99`
  - `coherence_coherent_total=52`
  - `coherence_incoherent_total=47`

Blocker-lane evidence:
- `strict_probes_executed=0`
- `no_new_lever_count=4`
- no new unblock levers detected for `aemet_opendata_series`, `bde_series_api`, `parlamento_galicia_deputados`, `parlamento_navarra_parlamentarios_forales`.

## Delta adjudication

Against frozen acceptance contract (`kpi-acceptance-pack.md`):
- hard gates `H1-H4`: PASS.
- delivery gate `D1` (selection policy): PASS.
- delivery gate `D2` (visible progress): PASS via declared signal delta (`+2`, `+0.003258`).
- delivery gate `D3` (queue closeout): PASS (`pending=0`).

## Decision

- `decision=APPLY_RECONCILIATION_NO_TRACKER_STATUS_CHANGE`

Rationale:
- strict gate/parity are green and evidence-backed.
- visible delivery delta is present and reproducible.
- there is no checklist/sql mismatch requiring status reconciliation in tracker rows.
- blocker lane remains policy-neutral (`no_new_lever`) with explicit evidence.

## Tracker/doc update patch plan

Apply now:
- no `Status` column transitions in `docs/etl/e2e-scrape-load-tracker.md`.

Patch candidates for final synthesis (Task 23/24):
- keep tracker line `74` (`Posiciones declaradas (programas)`) as `TODO` (out-of-scope editorial/program pipeline remains unresolved).
- add AI-OPS-16 evidence references in sprint final report (`final-gate-parity.md`/`closeout.md`) for declared-signal deltas and queue closure.
- optional tracker note refresh on analytical context rows (without status transitions) only if final gate adjudication confirms the same metrics.

## Outcome

- reconciliation claims are supported by evidence.
- no contradictory gate/parity signals detected.
- apply path is ready for gate adjudication task with `NO_ESCALATION`.

## Escalation rule check

T21 escalation condition:
- escalate if evidence does not support reconciliation claims.

Observed:
- evidence supports strict gate, parity, and delivery delta claims.

Decision:
- `NO_ESCALATION`.
