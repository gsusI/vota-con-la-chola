# AI-OPS-20 Closeout

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Sprint Verdict
- `PASS`
- Reason:
  - Multi-concern dashboard + party focus are now shareable/restorable via URL state.
  - Static GH Pages build exports + validates bounded multi-method citizen artifacts (`combined|votes|declared`).
  - Audit links resolve to existing explorers, and strict tracker gate/parity remains green.

## Gate Evaluation

| Gate | Result | Evidence | Notes |
|---|---|---|---|
| G1 Visible product delta | PASS | `docs/etl/sprints/AI-OPS-20/reports/citizen-walkthrough.md`; `docs/etl/sprints/AI-OPS-20/reports/shareable-url-matrix.md` | URL restore is the primary share mechanism (localStorage only as fallback). |
| G2 Auditability | PASS | `docs/etl/sprints/AI-OPS-20/reports/link-check.md`; `docs/etl/sprints/AI-OPS-20/evidence/link-check.json` | Explorer compatibility updated for `topic_set_id/topic_id` and `party_id` links. |
| G3 Honesty | PASS | `docs/etl/sprints/AI-OPS-20/reports/honesty-audit.md` | Combined method is explicitly labeled as "prioriza votos" (selector, not mixer). |
| G4 Static budgets | PASS | `docs/etl/sprints/AI-OPS-20/evidence/citizen-json-budget.txt`; `docs/etl/sprints/AI-OPS-20/reports/citizen-mobile-a11y-smoke.md` | Each citizen JSON <= 5MB. |
| G5 Reproducibility | PASS | `docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.exit`; `docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.log`; `docs/etl/sprints/AI-OPS-20/evidence/tests.exit` | `just explorer-gh-pages-build` is the single canonical builder (exports + strict validation). |
| G6 Strict gate/parity | PASS | `docs/etl/sprints/AI-OPS-20/evidence/tracker-gate-postrun.exit`; `docs/etl/sprints/AI-OPS-20/evidence/status-parity-postrun.txt` | Strict tracker gate exit `0`, parity `overall_match=true`. |

## Visible Progress Outcome (user-facing)
- Citizen can now:
  - select multiple concerns and switch to "mi dashboard" synthesis view
  - share a URL that restores selected concerns + view + party focus + method
  - toggle methods (`combined|votes|declared`) using bounded static artifacts
  - drill down via audit links to existing explorers (temas, SQL explorer, politico)

## Carryover / Follow-ups
- Consider adding a compact "how computed" drawer for combined vs votes vs declared and programa lane.
- If we want higher citizen trust: add an explicit "coverage warning" chip when `no_signal` dominates in declared mode.

## Evidence Commands (final run)
```bash
just explorer-gh-pages-build > docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/gh-pages-build.exit

for f in docs/gh-pages/citizen/data/citizen*.json; do
  echo "VALIDATE $f"
  python3 scripts/validate_citizen_snapshot.py --path "$f" --max-bytes 5000000 --strict-grid
done > docs/etl/sprints/AI-OPS-20/evidence/citizen-validate-post.log 2>&1

just etl-tracker-gate > docs/etl/sprints/AI-OPS-20/evidence/tracker-gate-postrun.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/tracker-gate-postrun.exit

python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-20/evidence/status-postrun.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json

just etl-test > docs/etl/sprints/AI-OPS-20/evidence/tests.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-20/evidence/tests.exit
```

## next sprint trigger
AI-OPS-21 should start when at least one of the following is true:
1. A new citizen-visible slice is selected (recommendation onboarding, scope expansion, new audit surface) with bounded static artifacts.
2. Strict gate/parity regresses (mismatch/waiver expiry/done_zero_real or parity drift).
3. A new unblock lever appears for key blocked sources (and passes anti-loop policy).

## Escalation rule check
- No blockers encountered; no scope escalation required.
