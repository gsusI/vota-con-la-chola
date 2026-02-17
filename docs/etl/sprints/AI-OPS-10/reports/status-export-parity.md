# AI-OPS-10 T24 Status Export Parity

Date:
- `2026-02-17`

Objective:
- Refresh explorer-sources status payload and verify parity for indicator impact keys plus tracker mismatch summary.

## Commands run

1. Export postrun evidence snapshot:

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json
```

2. Refresh published snapshot:

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json
```

## Output artifacts

- `docs/etl/sprints/AI-OPS-10/evidence/status-postrun.json`
- `docs/gh-pages/explorer-sources/data/status.json`
- `docs/etl/sprints/AI-OPS-10/reports/status-export-parity.md`

## Snapshot values (status-postrun)

From `status-postrun.json`:

`analytics.impact`:
- `indicator_series_total=2400`
- `indicator_points_total=37431`
- `causal_estimates_total=0`

`summary.tracker`:
- `items_total=47`
- `mismatch=3`
- `waived_mismatch=0`
- `done_zero_real=0`
- `waivers_active=0`
- `waivers_expired=0`

Mismatch source_ids in payload:
- `eurostat_sdmx`
- `placsp_autonomico`
- `placsp_sindicacion`

## Parity checks

1. Impact parity (`status` vs SQL):
- SQL (`etl/data/staging/politicos-es.db`): `indicator_series_total=2400`, `indicator_points_total=37431`
- `status-postrun.json` `analytics.impact`: `indicator_series_total=2400`, `indicator_points_total=37431`
- Result: `MATCH`

2. Tracker gate parity (`status` vs T22 postrun logs):
- T22 logs (`docs/etl/sprints/AI-OPS-10/evidence/tracker-gate-postrun.log`):
  - `mismatches=3`
  - `done_zero_real=0`
  - `waivers_expired=0`
- `status-postrun.json` `summary.tracker`:
  - `mismatch=3`
  - `done_zero_real=0`
  - `waivers_expired=0`
- Result: `MATCH`

3. Mismatch source set parity:
- payload mismatch sources: `eurostat_sdmx`, `placsp_autonomico`, `placsp_sindicacion`
- T22 gate mismatch sources: `eurostat_sdmx`, `placsp_autonomico`, `placsp_sindicacion`
- Result: `MATCH`

## Escalation rule check

T24 escalation condition:
- escalate if exporter cannot emit populated impact metrics despite non-zero SQL totals.

Observed:
- exporter emitted populated impact keys:
  - `indicator_series_total=2400`
  - `indicator_points_total=37431`
- both totals are non-zero and equal to SQL totals.

Decision:
- `NO_ESCALATION`.
