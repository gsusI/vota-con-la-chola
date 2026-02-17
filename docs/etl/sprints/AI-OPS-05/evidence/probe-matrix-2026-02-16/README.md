# Probe Matrix Batch (2026-02-16)

Scope:
- Moncloa: `moncloa_referencias`, `moncloa_rss_referencias`
- Navarra: `parlamento_navarra_parlamentarios_forales`
- Galicia: `parlamento_galicia_deputados`

Artifacts:
- `run-probe-matrix.sh`: deterministic runner for strict-network + from-file probes.
- `command-matrix.tsv`: source/mode/command/artifact mapping.
- `logs/*.stdout.log` + `logs/*.stderr.log`: pre-created execution capture files.
- `sql/*_snapshot.csv`: pre-created SQL evidence snapshot files.

Run (from repo root):

```bash
bash docs/etl/sprints/AI-OPS-05/evidence/probe-matrix-2026-02-16/run-probe-matrix.sh
```

Optional env overrides:
- `DB_PATH` (default: `etl/data/staging/probe-matrix-20260216.db`)
- `SNAPSHOT_DATE` (default: `2026-02-16`)
