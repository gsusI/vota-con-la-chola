# Senado Unlinked Drain 5 Summary (2026-02-20)

Run ID:
- `senado_unlinked_drain5_20260220T140606Z`

Command mode:
- Bounded passes on full Senate queue (linked + unlinked):

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --include-unlinked \
  --retry-forbidden \
  --limit-initiatives 40 \
  --max-docs-per-initiative 1 \
  --timeout 10 \
  --sleep-seconds 0 \
  --sleep-jitter-seconds 0
```

Loop outcomes:
- `loop_1`: `ok=80`
- `loop_2`: `ok=71`
- `loop_3`: `ok=70`
- `loop_4`: `ok=80`
- `loop_5`: `ok=72`
- `loop_6`: `ok=0` -> stop (throttle window)

Tranche delta:
- `+373` docs downloaded.

Post-run status:
- Senate doc-link coverage: `3753/7905` (`47.48%`).
- Senate initiatives with downloaded docs: `2556/3607` (`70.86%`).
- Senate linked-to-votes initiatives with downloaded docs remains complete: `647/647` (`100%`).
