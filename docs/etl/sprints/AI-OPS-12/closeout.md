# AI-OPS-12 Closeout

Date: 2026-02-17  
Decision owner: L3 Orchestrator

## Sprint Verdict
- **FAIL**
- Reason: must-pass gates remained green, but sprint objective was to reduce blocker debt and in-scope `PARTIAL` sources did not decrease (`6 -> 6`).

## Gate Evaluation

| Gate | Result | Evidence | Notes |
|---|---|---|---|
| Gate G1 - Integrity | PASS | `docs/etl/sprints/AI-OPS-12/evidence/final-integrity-metrics.csv` | `fk_violations=0`. |
| Gate G2 - Queue health | PASS | `docs/etl/sprints/AI-OPS-12/evidence/final-review-queue.csv` | `topic_evidence_reviews_pending=0`. |
| Gate G3 - Tracker strict gate | PASS | `docs/etl/sprints/AI-OPS-12/evidence/tracker-gate-final.log`; `docs/etl/sprints/AI-OPS-12/evidence/tracker-gate-final.exit` | strict gate exit `0`; `mismatches=0`, `waivers_expired=0`, `done_zero_real=0`. |
| Gate G4 - Publish/status parity | PASS | `docs/etl/sprints/AI-OPS-12/evidence/status-final.json`; `docs/etl/sprints/AI-OPS-12/evidence/status-parity-summary.txt`; `docs/etl/sprints/AI-OPS-12/reports/final-gate-parity.md` | `indicator_series_total=2400` and `indicator_points_total=37431` are non-null, SQL-aligned, and match published status payload. |
| Gate G5 - Reconciliation discipline | PASS | `docs/etl/sprints/AI-OPS-12/reports/reconciliation-apply.md`; `docs/etl/e2e-scrape-load-tracker.md` | In-scope rows stayed truthful `PARTIAL`; no fake `DONE` transitions and no waiver mutations. |

## Blocker Debt Outcome

Baseline in-scope `PARTIAL` rows:
- `6`

Final in-scope `PARTIAL` rows:
- `6`

Unresolved carryover sources:
- `parlamento_galicia_deputados` (`network` WAF `HTTP 403`, `run_id=250`)
- `parlamento_navarra_parlamentarios_forales` (`network` WAF `HTTP 403`, `run_id=251`)
- `bdns_autonomico` (`auth` anti-bot HTML payload, `run_id=252`)
- `bdns_api_subvenciones` (`auth` anti-bot HTML payload, `run_id=253`)
- `bde_series_api` (`network` DNS resolution `Errno 8`, `run_id=254`)
- `aemet_opendata_series` (`contract` `aemet_blocker=contract` / `HTTP 404`, `run_id=255`)

## Evidence Commands (Final Run)

```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-17
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-17 --fail-on-mismatch --fail-on-done-zero-real
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-12/evidence/status-final.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json
sqlite3 -csv -header etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
sqlite3 -csv -header etl/data/staging/politicos-es.db "SELECT COUNT(*) AS topic_evidence_reviews_pending FROM topic_evidence_reviews WHERE lower(status)='pending';"
```

## next sprint trigger

AI-OPS-13 should start when at least one unblock path is executable:
1. At least one carryover source has reproducible strict-network success (`exit 0` and `run_records_loaded>0`) enabling an evidence-backed `PARTIAL -> DONE` transition.
2. A reproducible mitigation is accepted for current blocker classes (WAF/anti-bot/DNS/contract), with deterministic runbook and evidence capture.
3. Strict gate or parity regresses (`mismatches>0`, `waivers_expired>0`, `done_zero_real>0`, or impact totals drift from SQL), requiring corrective sprint.

## Escalation rule check

T6 escalation condition:
- escalate if closeout cannot evaluate must-pass gates or cannot compute objective delta from produced artifacts.

Observed:
- all gate artifacts are present and objective delta is explicit (`in-scope PARTIAL 6 -> 6`).

Decision:
- `NO_ESCALATION`.
