# Senado Initiative Docs - Queue Selection Fix Drain (2026-02-21)

## Goal
Resume Senate initiative-document downloads and break the plateau caused by per-initiative URL selection.

## What Changed
- Patched `etl/parlamentario_es/text_documents.py` so `backfill-initiative-documents` skips already downloaded URLs when `only_missing=True` before enforcing `--max-docs-per-initiative` caps.
- This prevents starvation where `--max-docs-per-initiative 1` kept picking an already downloaded first URL.

## Command
```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --include-unlinked \
  --retry-forbidden \
  --limit-initiatives 220 \
  --max-docs-per-initiative 1 \
  --timeout 10 \
  --sleep-seconds 0 \
  --sleep-jitter-seconds 0
```

## Result
- Start: `6375/7963`
- End: `7248/7963`
- Delta: `+873` docs downloaded in one bounded run.
- Major productive rounds:
  - Round 1: `+262`
  - Round 2: `+341`

## Evidence
- Run artifacts: `docs/etl/runs/senado_postfix_bounded_20260221T093208Z/`
- Per-round JSON: `round_*.json`
