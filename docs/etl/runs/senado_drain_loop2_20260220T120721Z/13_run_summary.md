# Senado Initiative Documents Recovery Summary (2026-02-20)

Run family:
- `docs/etl/runs/senado_stable_loop_20260220T115905Z`
- `docs/etl/runs/senado_drain_loop_20260220T120121Z`
- `docs/etl/runs/senado_drain_loop2_20260220T120721Z`

Objective:
- Resume deterministic Senate initiative-document downloads using the existing queue processor (`backfill-initiative-documents`) after VPN/network context change.

## Effective command mode

The reliable mode in this window was bounded repeated passes (not `--auto`):

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

Operational note:
- `--auto` run was observed to stall in this environment before emitting summary output, while single-pass bounded loops produced measurable progress and preserved retry control.

## Quantified progress (this session)

DB-level docs coverage (`parl_initiative_documents` -> `text_documents`):
- Before: `senado_iniciativas downloaded_docs=1998` of `7633` known doc links.
- After: `senado_iniciativas downloaded_docs=3129` of `7905` known doc links.
- Net downloaded in this recovery window: `+1131` Senate docs.

Initiative KPI (`quality-report`, linked-to-votes focus):
- `senado_iniciativas` linked-to-votes with downloaded docs:
  - Before baseline (prior sprint evidence): `235/647 (36.32%)`
  - After this run family: `583/647 (90.11%)`

Combined initiatives KPI (`quality_post.json`):
- `initiatives_linked_to_votes_with_downloaded_docs_pct = 0.914780292942743`

## Failure pattern

- Upstream behavior is intermittent, not hard-fail:
  - Some loops reached full success (`80/80`).
  - Other loops degraded (`0-30` failures) and recovered in later loops.
- This is consistent with temporary WAF/rate windows rather than permanent access denial.

## Where to continue

- Reuse the same bounded command above in short batches.
- Stop when a batch returns `fetched_ok=0` (temporary throttle), wait, then resume.
- Keep storing each loop JSON under a timestamped `docs/etl/runs/senado_*` folder.
