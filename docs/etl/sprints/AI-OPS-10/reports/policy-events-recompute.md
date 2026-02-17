# AI-OPS-10 T19 Policy Events Recompute

Date:
- `2026-02-17`

Objective:
- Recompute money policy-event mapping after PLACSP/BDNS apply waves and refresh traceability slices.

## Inputs used

- `docs/etl/sprints/AI-OPS-10/reports/placsp-replay-run.md`
- `docs/etl/sprints/AI-OPS-10/reports/bdns-replay-run.md`
- `scripts/ingestar_politicos_es.py`
- `etl/data/staging/politicos-es.db`

## Recompute command

```bash
python3 scripts/ingestar_politicos_es.py backfill-policy-events-money \
  --db etl/data/staging/politicos-es.db \
  --source-ids placsp_sindicacion placsp_autonomico bdns_api_subvenciones bdns_autonomico
```

Backfill log:
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/backfill-policy-events-money.log`

Command result summary:
- `source_records_seen=222`
- `source_records_mapped=222`
- `source_records_skipped=0`
- `policy_events_upserted=222`
- `policy_events_total=222`
- `policy_events_by_source`: `placsp_contratacion=217`, `bdns_subvenciones=5`

## Evidence packet

- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/before_counts.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/after_counts.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/before_totals.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/after_totals.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/before_trace_counts.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/after_trace_counts.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/before_trace_sample.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/after_trace_sample.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/before_source_records_counts.csv`
- `docs/etl/sprints/AI-OPS-10/evidence/policy-events-sql/after_source_records_counts.csv`

## Before/After summary

Totals:
- `policy_events_total`: `222 -> 222` (`delta=0`)
- `placsp_total`: `217 -> 217` (`delta=0`)
- `bdns_total`: `5 -> 5` (`delta=0`)

Traceability counts:
- `placsp_contratacion`: `row_count=217`, `with_source_record_pk=217`, `with_source_url=217` (unchanged)
- `bdns_subvenciones`: `row_count=5`, `with_source_record_pk=5`, `with_source_url=5` (unchanged)

Source-record input counts (money source_ids):
- `placsp_sindicacion=109`
- `placsp_autonomico=108`
- `bdns_api_subvenciones=3`
- `bdns_autonomico=2`

## Integrity and escalation check

Integrity:
- `PRAGMA foreign_key_check`: `0` violations.

Escalation rule (T19):
- escalate if recompute introduces integrity errors or source totals regress unexpectedly.

Observed:
- no integrity errors,
- no regressions in `policy_events_total`, `placsp`, or `bdns` totals.

Decision:
- `NO_ESCALATION`.
