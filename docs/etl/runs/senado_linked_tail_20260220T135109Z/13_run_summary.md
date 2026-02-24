# Senado Linked Tail Summary (2026-02-20)

Run ID:
- `senado_linked_tail_20260220T135109Z`

Goal:
- Close remaining Senate initiatives linked-to-votes gaps by focusing retries on linked initiatives only.

Command mode:
- `backfill-initiative-documents` without `--include-unlinked`:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --retry-forbidden \
  --limit-initiatives 30 \
  --max-docs-per-initiative 1 \
  --timeout 10 \
  --sleep-seconds 0 \
  --sleep-jitter-seconds 0
```

Loop outcomes:
- `loop_1`: `ok=2` -> linked-vote docs `645/647`
- `loop_2`: `ok=3` -> linked-vote docs `647/647`

Result:
- Linked-to-votes Senate initiative docs reached full coverage (`647/647 = 100%`).
- Tranche delta: `+5` docs.

Post-run status:
- Senate doc-link coverage (all linked/unlinked URLs): `3380/7905` (`42.76%`).
- Senate initiatives with downloaded docs (initiative-level): `2358/3607` (`65.37%`).

Note:
- Remaining missing docs are outside the linked-to-votes target and can be drained opportunistically in later windows.
