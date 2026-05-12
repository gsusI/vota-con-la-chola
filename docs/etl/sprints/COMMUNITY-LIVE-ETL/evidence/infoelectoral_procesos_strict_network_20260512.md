# Infoelectoral procesos strict-network proof

Date: `2026-05-12`

GitHub issue:

- `https://github.com/gsusI/vota-con-la-chola/issues/8`

Command:

```bash
python3 scripts/ingestar_infoelectoral_es.py ingest \
  --db /tmp/vclc-infoelectoral-procesos.db \
  --source infoelectoral_procesos \
  --snapshot-date 2026-05-12 \
  --strict-network \
  --timeout 30
```

Result:

```text
infoelectoral_procesos: 257/257 registros validos [network-with-partial-errors (default_url_404: https://infoelectoral.interior.gob.es/min/procesos/; archivos[6:198305]: RuntimeError: Respuesta inesperada (HTML recibido); proceso_id tipo:6|conv:198305: sin resultados directos)]
Total: 257/257 registros validos
```

SQLite proof:

| Table | Rows |
|---|---:|
| `infoelectoral_procesos` | 69 |
| `infoelectoral_proceso_resultados` | 188 |
| `source_records` | 257 |
| `ingestion_runs` | 1 |

Integrity:

- `PRAGMA foreign_key_check`: no rows.
- Last run status: `ok`.
- Last run loaded: `257/257`.

Decision:

- Issue `#8` can close as reproducible.
- The default `/min/procesos/` endpoint returns `404`, but the connector has a real network fallback through `convocatorias` plus extraction files.
- One historical `archivos[6:198305]` payload returns HTML; this is recorded as a partial error, not a blocker, because the run still loads non-zero current records and preserves the partial-error note.
