# AI-OPS-09 Replay / Duplicate / Schema Audit

Date: 2026-02-17
Scope: New source families from PLACSP/BDNS/Eurostat/BDE/AEMET apply outputs (tasks T16-T20)

## 1) Evidence commands
- `sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*), SUM(CASE WHEN source_record_id IS NULL OR TRIM(source_record_id)='' THEN 1 ELSE 0 END), COUNT(*)-COUNT(DISTINCT source_record_id) FROM source_records WHERE source_id IN ('placsp_autonomico','placsp_sindicacion','bdns_api_subvenciones','bdns_autonomico','eurostat_sdmx','bde_series_api','aemet_opendata_series') GROUP BY source_id ORDER BY source_id;"`
- Snapshot headers and rows read from `docs/etl/sprints/AI-OPS-09/evidence/*-apply-sql/*_run_snapshot.csv`
- Snapshot headers and rows read from `docs/etl/sprints/AI-OPS-09/evidence/*-ingest-logs/sql/*_run_snapshot.csv`
- Export file headers inspected under `docs/etl/sprints/AI-OPS-09/exports/*.csv` and `docs/etl/sprints/AI-OPS-09/exports/*.tsv`

## 2) Duplicate check audit on `(source_id, source_record_id)`

| source_id | rows | null_empty_source_record_id | duplicate_pairs |
|---|---:|---:|---:|
| aemet_opendata_series | 2 | 0 | 0 |
| bde_series_api | 2 | 0 | 0 |
| bdns_api_subvenciones | 3 | 0 | 0 |
| bdns_autonomico | 2 | 0 | 0 |
| eurostat_sdmx | 2396 | 0 | 0 |
| placsp_autonomico | 108 | 0 | 0 |
| placsp_sindicacion | 109 | 0 | 0 |

Result:
- `duplicate` count is zero for all audited source_ids.
- No duplicate-key root cause to escalate.

## 3) Replay parity audit (strict baseline vs replay/from-file)

For each source/path, the replay/parity check compares first successful strict-network output with replay and/or from-file output using `run_records_loaded`/`run_records_seen` and exit code.

### 3.1 Eurostat
- `une_rt_a_freq_A_geo_ES_unit_PC_ACT`
  - strict-network: `exit_code=0`, `run_records_seen=2394`, `run_records_loaded=2394`
  - from-file: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay parity status: **FAIL** (strict non-zero vs replay/from-file zero)

- `une_rt_a_freq_A_geo_PT_unit_PC_ACT`
  - strict-network: `exit_code=0`, `run_records_seen=2394`, `run_records_loaded=2394`
  - from-file: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay parity status: **FAIL**

### 3.2 BDE
- `PARO_TASA_ES_M`
  - strict-network: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay parity status: **NOT APPLICABLE** (both modes failed, no first-run baseline success)

- `TI.TMM.T.4F.EUR.4F.N.M`
  - strict-network: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay parity status: **NOT APPLICABLE**

### 3.3 AEMET
- `station_0076_prec` and `station_3195_tmed`
  - strict-network: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay: `exit_code=1`, `run_records_seen=0`, `run_records_loaded=0`
  - replay parity status: **NOT APPLICABLE** (strict-network endpoint blocked, replay fixture paths missing in some runs)

### 3.4 PLACSP
- `placsp_autonomico` and `placsp_sindicacion`
  - source `_run_snapshot.csv` files in `placsp-apply-sql` and `placsp-ingest-logs/sql` are `metric,value` payloads and do not contain execution metrics (`run_records_loaded`, `exit_code`).
  - replay parity status: **NOT COMPUTABLE** from current artifacts; evidence exists only for command and mode, not replay numeric counters.

### 3.5 BDNS
- `bdns_autonomico` and `bdns_api_subvenciones`
  - snapshot files are `metric,value` payloads and do not contain execution metrics in snapshot CSVs.
  - replay parity status: **NOT COMPUTABLE** from current artifacts.

## 4) Header / schema audit

### 4.1 Exported CSV/TSV artifacts (pre-reconciliation manifests/matrices)
- `docs/etl/sprints/AI-OPS-09/exports/placsp_ingest_matrix.csv` header present and includes expected command/evidence columns.
- `docs/etl/sprints/AI-OPS-09/exports/bdns_ingest_matrix.csv` header present and includes expected command/evidence columns.
- `docs/etl/sprints/AI-OPS-09/exports/eurostat_ingest_matrix.csv` header present and includes expected command/evidence columns.
- `docs/etl/sprints/AI-OPS-09/exports/eurostat_series_manifest.csv` header present and includes dimensions/frequency metadata.
- `docs/etl/sprints/AI-OPS-09/exports/bde_ingest_matrix.csv`, `bde_series_manifest.csv`, `aemet_ingest_matrix.csv`, `aemet_station_manifest.csv` all include expected headers and non-empty row counts.
- `tracker_reconciliation_candidates.csv` and `tracker_row_patch_plan.tsv` include required transition/evidence columns.

### 4.2 Run snapshot CSV headers by family
Observed schema families across `*_run_snapshot.csv`:
- `metric,value` (bdns/placsp; no run metric fields).
- `series_id,mode,command,station_id,variable,exit_code,...,run_records_loaded,...` (aemet)
- `series_id,mode,command,exit_code,...,run_records_loaded,...,source_url,snapshot,source_record_id` (eurostat)
- `series_id,mode,command,exit_code,...,run_records_loaded,...,source_url,snapshot,message` (bde)

This is a `schema` **heterogeneity** condition by source family; for this audit it is treated as non-fatal, but it must be considered in replay parsers and parity tooling.

## 5) Replay/duplicate escalation decision
- No duplicate-key violations found, so duplicate-based escalation is not triggered.
- Replay parity is **non-compliant** for Eurostat due strict-only success and replay/from-file zero-load failures.
- Replay numeric parity is **not computable** for BDNS and PLACSP due missing `run_records_*` columns in their snapshot payloads.
