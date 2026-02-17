# AI-OPS-14 Closeout

Date: 2026-02-17  
Decision owner: L3 Orchestrator

## Sprint Verdict
- **FAIL**
- Reason: must-pass non-objective gates remained green, but sprint objective required at least one evidence-backed in-scope `PARTIAL -> DONE` transition and outcome stayed `4 -> 4` `PARTIAL`.

## Gate Evaluation

| Gate | Result | Evidence | Notes |
|---|---|---|---|
| Gate G1 - Integrity | PASS | `docs/etl/sprints/AI-OPS-14/evidence/final-integrity-metrics.csv` | `fk_violations=0`. |
| Gate G2 - Queue health | PASS | `docs/etl/sprints/AI-OPS-14/evidence/final-review-queue.csv` | `topic_evidence_reviews_pending=0`. |
| Gate G3 - Tracker strict gate | PASS | `docs/etl/sprints/AI-OPS-14/evidence/tracker-gate-final.log`; `docs/etl/sprints/AI-OPS-14/evidence/tracker-gate-final.exit` | strict gate exit `0`; `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`. |
| Gate G4 - Publish/status parity | PASS | `docs/etl/sprints/AI-OPS-14/evidence/status-final.json`; `docs/etl/sprints/AI-OPS-14/evidence/status-parity-summary.txt`; `docs/etl/sprints/AI-OPS-14/reports/final-gate-parity.md` | `indicator_series_total=2400` and `indicator_points_total=37431` are non-null, SQL-aligned, and match published status payload. |
| Gate G5 - Unblock outcome gate | FAIL | `docs/etl/sprints/AI-OPS-14/evidence/unblock-execution.log`; `docs/etl/sprints/AI-OPS-14/reports/reconciliation-apply.md` | No in-scope strict-network success (`records_loaded=0` for all 4 sources), so no `PARTIAL -> DONE` transition. |

## Blocker Debt Outcome

Baseline in-scope `PARTIAL` rows:
- `4`

Final in-scope `PARTIAL` rows:
- `4`

In-scope transitions to `DONE`:
- none

Unresolved carryover sources:
- `parlamento_galicia_deputados` (`network` WAF `HTTP 403`, `run_id=265`)
- `parlamento_navarra_parlamentarios_forales` (`network` WAF/Cloudflare `HTTP 403`, `run_id=266`)
- `bde_series_api` (`network` DNS resolution `Errno 8`, `run_id=264`)
- `aemet_opendata_series` (`contract` `aemet_blocker=contract` / JSON invalido payload vacío, `run_id=263`)

## Evidence Commands (Final Run)

```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-17
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-17 --fail-on-mismatch --fail-on-done-zero-real
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-14/evidence/status-final.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
```

## next sprint trigger

AI-OPS-15 should start when at least one unblock path is executable:
1. `AEMET_API_KEY` is available and AEMET endpoint contract yields non-empty parseable payload under strict-network.
2. BDE machine endpoint contract is resolved (DNS + parseable payload) for reproducible strict-network success.
3. A reproducible, approved non-interactive strategy exists for Galicia/Navarra anti-bot blockers (or sanctioned deterministic capture policy).
4. Strict gate/parity regresses (`mismatches>0`, `waivers_expired>0`, `done_zero_real>0`, or impact totals drift), requiring corrective sprint.

## Escalation rule check

T7 escalation condition:
- escalate if closeout cannot evaluate must-pass gates or cannot compute objective delta from produced artifacts.

Observed:
- all gate artifacts are present and objective delta is explicit (`in-scope PARTIAL 4 -> 4`).

Decision:
- `NO_ESCALATION`.
