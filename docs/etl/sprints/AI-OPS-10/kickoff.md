# AI-OPS-10 Kickoff

Date:
- `2026-02-17` (captured at `2026-02-17T09:48:39Z` / `2026-02-17 10:48:39 CET`)

Decision owner:
- `L3 Orchestrator`

## Scope Lock

Single sprint objective:
- Close carryover strict/replay contract debt for money/outcomes sources (`placsp_*`, `bdns_*`, `eurostat_sdmx`, `bde_series_api`, `aemet_opendata_series`) with deterministic evidence and tracker/dashboard reconciliation.

Bottleneck class:
- `pipeline bottleneck`

## Baseline Metrics (Live)

### Tracker and Gate

Command:
```bash
just etl-tracker-status
```

Observed summary:
- `tracker_sources=35`
- `sources_in_db=42`
- `mismatches=0`
- `waived_mismatches=0`
- `waivers_active=0`
- `waivers_expired=0`
- `done_zero_real=0`

Command:
```bash
just etl-tracker-gate
```

Observed summary:
- strict gate exited `0`
- `mismatches=0`
- `done_zero_real=0`
- `waivers_expired=0`

### Integrity and Queue

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "
SELECT 'fk_violations', COUNT(*) FROM pragma_foreign_key_check;
SELECT 'topic_evidence_reviews_pending', COUNT(*) FROM topic_evidence_reviews WHERE lower(status)='pending';
"
```

Observed summary:
- `fk_violations=0`
- `topic_evidence_reviews_pending=0`

### Action and Impact Totals

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "
SELECT 'policy_events_total', COUNT(*) FROM policy_events;
SELECT 'policy_events_by_source', source_id || ':' || COUNT(*) FROM policy_events GROUP BY source_id ORDER BY source_id;
SELECT 'indicator_series_total', COUNT(*) FROM indicator_series;
SELECT 'indicator_points_total', COUNT(*) FROM indicator_points;
"
```

Observed summary:
- `policy_events_total=548`
- `policy_events_by_source`: `boe_api_legal=298`, `moncloa_referencias=20`, `moncloa_rss_referencias=8`, `placsp_contratacion=217`, `bdns_subvenciones=5`
- `indicator_series_total=2400`
- `indicator_points_total=37431`

### Explorer Status Snapshot Check

Command:
```bash
python3 - <<'PY'
import json
p='docs/gh-pages/explorer-sources/data/status.json'
with open(p,'r',encoding='utf-8') as f:
    d=json.load(f)
s=d.get('summary',{})
print('summary.tracker', s.get('tracker'))
print('summary.sql', s.get('sql'))
print('analytics.impact', s.get('analytics',{}).get('impact'))
PY
```

Observed summary:
- `summary.tracker`: `items_total=46`, `done=27`, `partial=3`, `todo=16`, `unmapped=13`
- `summary.sql`: `done=34`, `partial=6`, `todo=2`, `foreign_key_violations=0`
- `analytics.impact.indicator_series_total=None`
- `analytics.impact.indicator_points_total=None`

Status note:
- SQL shows non-zero impact totals, but `status.json` impact fields are currently null; this is a required parity fix in this sprint.

## Tracker Target Rows (Confirmed)

In-scope tracker rows (all currently `PARTIAL`):
- line `56`: `placsp_autonomico`
- line `57`: `bdns_autonomico`
- line `63`: `placsp_sindicacion`
- line `64`: `bdns_api_subvenciones`
- line `65`: `eurostat_sdmx`
- line `66`: `bde_series_api`
- line `67`: `aemet_opendata_series`

Source file:
- `docs/etl/e2e-scrape-load-tracker.md`

Out-of-scope (monitor only, no status transitions in this sprint unless regression appears):
- parliamentary ingest families (`congreso_*`, `senado_*`)
- already-stable action sources (`boe_api_legal`, `moncloa_*`)
- representational assemblies and municipal rows not part of carryover contract debt

## Must-Pass Gates (Frozen)

`G1` Integrity:
- pass if `fk_violations=0`

`G2` Queue health:
- pass if `topic_evidence_reviews_pending=0`

`G3` Tracker strict gate:
- pass if `just etl-tracker-gate` exits `0` with `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`

`G4` Carryover source evidence parity:
- pass if every in-scope source has strict/replay artifacts with comparable run fields (`mode`, `exit_code`, `run_records_loaded`, `source_id`, `snapshot_date`) and a computed parity status (`PASS`/`DRIFT`/`BLOCKED`)

`G5` Publish/status parity:
- pass if exported status payload includes non-null impact counters consistent with SQL totals (`indicator_series_total`, `indicator_points_total`)

`G6` Tracker reconciliation discipline:
- pass if row status transitions are evidence-backed only; blocked rows remain `PARTIAL` with blocker text + next command

## Escalation Policy (Frozen)

Escalate from `L1 -> L2` when:
- strict-mode payload signature changes (e.g., HTML/challenge where structured payload is expected)
- replay parity cannot be computed despite normalized artifact schema
- command contract in matrix cannot be executed as written

Escalate from `L2 -> L3` when:
- tracker status transition cannot be justified with command/SQL evidence
- blocker class is ambiguous (`auth` vs `contract` vs `network`) after evidence capture
- meeting gate targets would require non-additive or destructive changes

Non-negotiable policy:
- do not mark `DONE` without reproducible proof
- do not hide blockers; keep `PARTIAL` plus explicit next command

## Owner Matrix

- `L3 Orchestrator`: scope lock, gate arbitration, closeout verdict
- `L2 Specialist Builder`: contract/schema/runbook hardening, tests, final reconciliation patch
- `L1 Mechanical Executor`: deterministic prep/apply/replay/recompute/evidence packet generation

## Queue Order (Frozen)

Wave plan:
1. `HI wave 1` (`T1-T10`): setup, contract hardening, tests, handoff runbook
2. `FAST wave` (`T11-T27`): batch prep, strict/replay execution, recompute, evidence assembly
3. `HI wave 2` (`T28-T30`): tracker reconciliation, final parity check, closeout decision

Lane switches:
- `2` total (`HI -> FAST -> HI`)

## Commands Logged for Kickoff

```bash
just etl-tracker-status
just etl-tracker-gate
sqlite3 etl/data/staging/politicos-es.db "SELECT 'fk_violations', COUNT(*) FROM pragma_foreign_key_check;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_reviews_pending', COUNT(*) FROM topic_evidence_reviews WHERE lower(status)='pending';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'policy_events_total', COUNT(*) FROM policy_events;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'policy_events_by_source', source_id || ':' || COUNT(*) FROM policy_events GROUP BY source_id ORDER BY source_id;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'indicator_series_total', COUNT(*) FROM indicator_series;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'indicator_points_total', COUNT(*) FROM indicator_points;"
python3 - <<'PY'
import json
p='docs/gh-pages/explorer-sources/data/status.json'
with open(p,'r',encoding='utf-8') as f:
    d=json.load(f)
print(d.get('summary',{}).get('tracker'))
print(d.get('summary',{}).get('sql'))
print(d.get('summary',{}).get('analytics',{}).get('impact'))
PY
```
