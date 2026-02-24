# Senado Unlinked Cookie Drain 8 Summary (2026-02-20)

Run ID:
- `senado_unlinked_cookie_drain8_20260220T141131Z`

Command mode:
- Bounded full-queue passes with cookie context:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --include-unlinked \
  --retry-forbidden \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --limit-initiatives 40 \
  --max-docs-per-initiative 1 \
  --timeout 10 \
  --sleep-seconds 0 \
  --sleep-jitter-seconds 0
```

Loop outcomes:
- `loop_1`: `ok=80`
- `loop_2`: `ok=80`
- `loop_3`: `ok=80`
- `loop_4`: `ok=80`
- `loop_5`: `ok=71`
- `loop_6`: `ok=0` -> stop (throttle window)

Tranche delta:
- `+391` docs downloaded.

Post-run status:
- Senate doc-link coverage: `4175/7905` (`52.81%`).
- Senate initiatives with downloaded docs: `2786/3607` (`77.24%`).
- Senate linked-to-votes initiatives with downloaded docs remains complete: `647/647` (`100%`).
