# Next Sprint Trigger (AI-OPS-26 -> AI-OPS-27)

## Trigger conditions

AI-OPS-27 should start when all of the following hold:

1. `lane_a` apply has already reduced pending queue (met in AI-OPS-26).
2. `import_queue.csv` contains non-applied lanes with valid contracts (`lane_b/c/d/e`).
3. At least one non-blocker, user-visible delta can be shipped from those lanes.

Current trigger status:
- `READY`

## Primary objective for AI-OPS-27

- Convert one hold lane (`lane_c` preferred) from preview to controlled DB apply with measurable KPI delta (`initiative_docs_missing_excerpt` reduction), while preserving parity gate green.

## Secondary lane (bounded)

- Re-run blocker probes only if a new lever exists; otherwise log `no_new_lever` and avoid repeated retries.

## First three executable tasks

1. Validate and apply `lane_c` `sql_patch.csv` to `text_documents` under strict prechecks.
2. Recompute/export affected snapshots (`explorer-temas` + citizen where relevant) and publish KPI delta.
3. Execute HI review for `lane_b` ambiguous rows and prepare first apply subset.

## Required carryover artifacts

- `docs/etl/sprints/AI-OPS-26/exports/factory/import_queue.csv`
- `docs/etl/sprints/AI-OPS-26/reports/import-runbook-bcde.md`
- `docs/etl/sprints/AI-OPS-26/exports/kpi_delta.csv`
