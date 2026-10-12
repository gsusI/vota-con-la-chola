# Cortes de Aragon strict-network 403 in GitHub Actions

Observed UTC: `2026-05-11T14:02:45Z`

Source: `cortes_aragon_diputados`

Command:

```sh
python3 scripts/ingestar_politicos_es.py ingest \
  --db etl/data/staging/politicos-es.ci-gate.db \
  --source cortes_aragon_diputados \
  --snapshot-date 2026-02-12 \
  --strict-network
```

Failure signal:

```text
urllib.error.HTTPError: HTTP Error 403: Forbidden
```

CI evidence:

- Run: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25674919149`
- Job: `https://github.com/gsusI/vota-con-la-chola/actions/runs/25674919149/job/75369994978`

Impact:

- Tracker row `Representantes y mandatos (Cortes de Aragon)` downgraded from `DONE` to `PARTIAL`.
- Existing local snapshot rows remain useful as partial historical evidence.
- Source should return to `DONE` only after a strict-network run loads non-zero records in CI/live automation, or after a reproducible unblock path is documented.
