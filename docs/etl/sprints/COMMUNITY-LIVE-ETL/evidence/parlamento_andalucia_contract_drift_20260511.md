# Parlamento de Andalucia strict-network contract drift

Observed UTC: `2026-05-11T14:17:39Z`

Source: `parlamento_andalucia_diputados`

Command:

```sh
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.ci-gate.db \
  --source parlamento_andalucia_diputados \
  --snapshot-date 2026-02-12 \
  --strict-network
```

Failure signal:

```text
RuntimeError: No se encontraron diputados actuales (codmie/nlegis) en Parlamento de Andalucia
```

CI evidence:

- Run: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25675240502`
- Job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25675240502/job/75371175950`

Impact:

- Tracker row `Representantes y mandatos (Parlamento de Andalucia)` downgraded from `DONE` to `PARTIAL`.
- This is parser/upstream-contract drift, not confirmed access obstruction.
- Source should return to `DONE` only after strict-network loads non-zero records again in CI/live automation.
