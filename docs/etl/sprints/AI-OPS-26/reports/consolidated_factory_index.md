# consolidated factory index

- lanes_total: `5`
- ready_for_apply: `1`
- hold_for_review: `4`
- needs_rework: `0`

## lane status
- `lane_a` (`factory-20260219-lane_a-001`): readiness=`ready_for_apply`, action=`applied`, tasks=`6`, decisions=`6`, rejected=`0`
  reason: lane_a decisions already applied with recompute evidence.
- `lane_b` (`factory-20260219-lane_b-001`): readiness=`hold_for_review`, action=`proposal_ready`, tasks=`120`, decisions=`120`, rejected=`56`
  reason: import-ready proposals require HI review before DB apply.
- `lane_c` (`factory-20260219-lane_c-001`): readiness=`hold_for_review`, action=`preview_ready`, tasks=`120`, decisions=`120`, rejected=`0`
  reason: sql_patch generated; apply deferred per sprint gate.
- `lane_d` (`factory-20260219-lane_d-001`): readiness=`hold_for_review`, action=`proposal_ready`, tasks=`120`, decisions=`120`, rejected=`0`
  reason: import-ready proposals require HI review before DB apply.
- `lane_e` (`factory-20260219-lane_e-001`): readiness=`hold_for_review`, action=`proposal_ready`, tasks=`120`, decisions=`120`, rejected=`52`
  reason: import-ready proposals require HI review before DB apply.

Evidence:
- `docs/etl/sprints/AI-OPS-26/exports/factory/import_queue.csv`
- `docs/etl/sprints/AI-OPS-26/reports/lane_a_apply.md`
- `docs/etl/sprints/AI-OPS-26/reports/lane_c_apply_preview.md`
