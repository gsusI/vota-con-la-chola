# AI-OPS-10 T21 Source Parity SQL Index

Date:
- `2026-02-17`

Objective:
- Consolidate SQL snapshot evidence for carryover source families and publish strict vs replay parity tables.

## Scope

Carryover source_ids:
- `placsp_sindicacion`
- `placsp_autonomico`
- `bdns_api_subvenciones`
- `bdns_autonomico`
- `eurostat_sdmx`
- `bde_series_api`
- `aemet_opendata_series`

Input snapshot sets:
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-strict-sql/`
- `docs/etl/sprints/AI-OPS-10/evidence/placsp-replay-sql/`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-strict-sql/`
- `docs/etl/sprints/AI-OPS-10/evidence/bdns-replay-sql/`
- `docs/etl/sprints/AI-OPS-10/evidence/eurostat-sql/`
- `docs/etl/sprints/AI-OPS-10/evidence/bde-sql/`
- `docs/etl/sprints/AI-OPS-10/evidence/aemet-sql/`
- `etl/data/staging/politicos-es.db`

## Evidence files in this folder

- `all_run_snapshots.csv`
  - Union of all carryover `*_run_snapshot.csv` rows (`21` rows: `7` sources x `3` modes).
- `all_source_records_snapshots.csv`
  - Union of all carryover `*_source_records_snapshot.csv` rows (`21` rows).
- `strict_vs_replay_by_source.csv`
  - Per-source strict vs replay counters/status parity view.
- `strict_vs_replay_by_family.csv`
  - Aggregated parity by family (`placsp`, `bdns`, `eurostat`, `bde`, `aemet`).
- `current_source_records_totals.csv`
  - Current `source_records` totals from SQLite by source_id.
- `current_ingestion_runs_by_status.csv`
  - Current `ingestion_runs` status counts by source_id.
- `missing_required_metadata.csv`
  - Required metadata gaps for strict/replay modes.

## Parity summary

From `strict_vs_replay_by_source.csv`:
- total sources checked: `7`
- `MATCH`: `0`
- `DIFF`: `7`
- `MISSING`: `0`

From `strict_vs_replay_by_family.csv`:
- `placsp`: `strict_records_loaded_total=0`, `replay_records_loaded_total=5`
- `bdns`: `strict_records_loaded_total=0`, `replay_records_loaded_total=5`
- `eurostat`: `strict_records_loaded_total=2394`, `replay_records_loaded_total=2`
- `bde`: `strict_records_loaded_total=0`, `replay_records_loaded_total=2`
- `aemet`: `strict_records_loaded_total=0`, `replay_records_loaded_total=2`

Interpretation:
- strict and replay record counts are intentionally not equal in this sprint because strict-network used live endpoints while replay used bounded fixtures.
- strict failures in `placsp`, `bdns`, `bde`, and `aemet` were already captured in prior apply reports as expected blockers/contracts/network issues.

## Escalation rule check

Rule:
- escalate if required run metadata is missing after normalized export changes.

Observed:
- `missing_required_metadata.csv` has `0` missing rows.

Decision:
- `NO_ESCALATION`.
