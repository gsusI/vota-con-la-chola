# Senado Senadores Strict-Network 403

Date: `2026-05-11`

Source: `senado_senadores`

CI evidence:
- Run: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25675911518`
- Job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25675911518/job/75373580601`
- Timestamp: `2026-05-11T14:34:55Z`

Command:

```bash
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.ci-gate.db \
  --source senado_senadores \
  --snapshot-date 2026-02-12 \
  --strict-network
```

Endpoint family:
- `https://www.senado.es/web/ficopendataservlet?tipoFich=4&legis=...`
- `https://www.senado.es/web/ficopendataservlet?tipoFich=6&legis=...`
- `https://www.senado.es/web/ficopendataservlet?tipoFich=2&cod=...`
- `https://www.senado.es/web/ficopendataservlet?tipoFich=1&cod=...`

Failure signal:

```text
urllib.error.HTTPError: HTTP Error 403: Forbidden
```

Decision:
- Downgrade tracker row from `DONE` to `PARTIAL`.
- Keep existing database rows as partial evidence only.
- Do not include this source in the live-clean `DONE` set until a reproducible strict-network run succeeds.

Next action:
- Reintentar por snapshot desde CI/live automation.
- If 403 persists, request a stable machine-readable public channel or approved reproducible access path.
