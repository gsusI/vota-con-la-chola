# Probe Matrix Generator (T3)

Date:
- `2026-02-17`

Objective:
- Generate one deterministic, tracker-aligned command matrix for carryover sources with strict/from-file/replay execution rows and canonical artifact expectations.

## Delivered artifacts

- `scripts/build_source_probe_matrix.py`
- `docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv`

## Scope locked in matrix

Carryover `source_id` set (1:1 with tracker target rows):
- `placsp_autonomico`
- `bdns_autonomico`
- `placsp_sindicacion`
- `bdns_api_subvenciones`
- `eurostat_sdmx`
- `bde_series_api`
- `aemet_opendata_series`

Modes emitted per source:
- `strict-network`
- `from-file`
- `replay`

Total rows:
- `21` (`7 sources x 3 modes`)

## Matrix schema (TSV columns)

- `row_id`, `source_family`, `source_id`, `mode`
- `snapshot_date`
- `timeout_seconds`, `timeout_policy`
- `strict_network`, `required_env`
- `url_override`, `from_file_input`
- `replay_input_expected`, `replay_input_policy`
- `ingest_command`
- `expected_stdout_log`, `expected_stderr_log`
- `expected_run_snapshot_csv`, `expected_source_records_snapshot_csv`
- `notes`

## Timeout policy (deterministic)

Default timeout:
- `45s` (`DEFAULT_TIMEOUT`) for `from-file` and `replay` rows.

Strict-network tracker overrides:
- `placsp_sindicacion`: `60s`
- `placsp_autonomico`: `30s`
- `bdns_api_subvenciones`: `30s`
- `bdns_autonomico`: `30s`
- `eurostat_sdmx`: `30s`
- `bde_series_api`: `30s`
- `aemet_opendata_series`: `30s`

## Replay input expectations

Replay rows are explicit `--from-file` executions and require pre-existing fixtures:
- root: `docs/etl/sprints/AI-OPS-10/evidence/replay-inputs/<source_id>/`
- filename: `<source_id>_replay_YYYYMMDD.<ext>`
- policy: `replay_input_policy=must-exist-before-run`

Extension rules:
- `placsp_*` -> `.xml`
- `bdns_*`, `eurostat_sdmx`, `bde_series_api`, `aemet_opendata_series` -> `.json`

Operational note:
- `aemet_opendata_series` strict rows include `required_env=AEMET_API_KEY`.

## L1 handoff instructions

1. Regenerate frozen matrix (TSV):
```bash
python3 scripts/build_source_probe_matrix.py \
  --out docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv \
  --snapshot-date 2026-02-17
```

2. Optional CSV export (same row contract):
```bash
python3 scripts/build_source_probe_matrix.py \
  --format csv \
  --out docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.csv \
  --snapshot-date 2026-02-17
```

3. Preflight replay fixture expectations:
```bash
awk -F '\t' 'NR==1 || $4=="replay" {print $3 "\t" $11 "\t" $12}' docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv
```

4. Preflight strict rows and timeout policy:
```bash
awk -F '\t' 'NR==1 || $4=="strict-network" {print $3 "\t" $6 "\t" $7 "\t" $14}' docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv
```

## Validation run

- `python3 scripts/build_source_probe_matrix.py --help`
- `python3 scripts/build_source_probe_matrix.py --out docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv --snapshot-date 2026-02-17`

Result:
- PASS (`21` rows written; source/mode coverage complete)
