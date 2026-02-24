# Tracker Reconciliation Draft (AI-OPS-26)

Status date:
- 2026-02-19

## Parity summary

Postrun checker:
- `docs/etl/sprints/AI-OPS-26/evidence/status-parity-postrun.txt`

Current counters:
- `mismatches=0`
- `waived_mismatches=0`
- `waivers_active=0`
- `waivers_expired=0`
- `done_zero_real=0`

## Proposed tracker row actions

- `programas_partidos`: keep `PARTIAL`.
  reason: queue apply executed (pending reduced), but source still depends on additional declared evidence + broader apply scope beyond current 6-row queue.
- `aemet_opendata_series`: keep `PARTIAL`.
  evidence: strict retry on 2026-02-19 still blocked (`Error: Expecting value: line 1 column 1 (char 0)`).
- `bde_series_api`: keep `PARTIAL`.
  evidence: strict retry on 2026-02-19 still blocked (`Errno 8 nodename nor servname provided`).
- `parlamento_galicia_deputados`: keep `PARTIAL`.
  evidence: strict retry on 2026-02-19 still blocked (`HTTP Error 403: Forbidden`).
- `parlamento_navarra_parlamentarios_forales`: keep `PARTIAL`.
  evidence: strict retry on 2026-02-19 still blocked (`HTTP Error 403: Forbidden`).

No tracker state transition to `DONE` is proposed in this draft.

## Evidence bundle

- `docs/etl/sprints/AI-OPS-26/evidence/status-parity-postrun.txt`
- `docs/etl/sprints/AI-OPS-26/exports/unblock_feasibility_matrix.csv`
- `docs/etl/sprints/AI-OPS-26/evidence/blocker-probe-refresh.log`
- `docs/etl/sprints/AI-OPS-26/reports/lane_a_apply.md`

## Next escalation actions

- AEMET: require validated API response contract or token/session lever before next retry.
- BDE: require DNS/network routing lever before next retry.
- Galicia/Navarra: require reproducible anti-bot bypass approval (cookie/session capture policy) before higher-frequency retries.
