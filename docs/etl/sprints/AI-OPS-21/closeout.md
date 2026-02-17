# AI-OPS-21 Closeout

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Sprint Verdict
- `PASS`

## Objective
Ship a citizen-first static upgrade that makes two truths explicit:
1. Coverage: what we know (and do not know) per concern by method.
2. Coherence: conservative “dice vs hace” only when votes and declared are comparable.

## What Shipped (Visible)
- New citizen view: `Vista: coherencia` (shareable via `view=coherence`).
- Coverage map per selected concern:
  - `votes` vs `declared` vs `combined` with `any` and `clear` ratios.
- Party coherence cards:
  - comparable/match/mismatch/not-comparable counts
  - deterministic audit links (Temas + method-specific Explorer SQL links) when comparables exist.
- Party focus in coherence view:
  - topic list shows `v:` and `d:` mini chips and highlights `mismatch` when comparable+different.

## Gates (G1-G6)
See:
- `docs/etl/sprints/AI-OPS-21/reports/gate-adjudication.md`

## Evidence (final run)
```bash
just explorer-gh-pages-build > docs/etl/sprints/AI-OPS-21/evidence/gh-pages-build.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-21/evidence/gh-pages-build.exit

for f in docs/gh-pages/citizen/data/citizen*.json; do
  echo "VALIDATE $f"
  python3 scripts/validate_citizen_snapshot.py --path "$f" --max-bytes 5000000 --strict-grid
done > docs/etl/sprints/AI-OPS-21/evidence/citizen-validate-post.log 2>&1

just etl-tracker-gate > docs/etl/sprints/AI-OPS-21/evidence/tracker-gate-postrun.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-21/evidence/tracker-gate-postrun.exit

python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/etl/sprints/AI-OPS-21/evidence/status-postrun.json
python3 scripts/export_explorer_sources_snapshot.py --db etl/data/staging/politicos-es.db --out docs/gh-pages/explorer-sources/data/status.json

just etl-test > docs/etl/sprints/AI-OPS-21/evidence/tests.log 2>&1; echo $? > docs/etl/sprints/AI-OPS-21/evidence/tests.exit
```

## Follow-ups
- If coherence becomes a primary citizen surface, consider a dedicated filter/sort control (mismatch-first) instead of reusing stance/confidence UI.
- Declared sparsity is currently the binding constraint; do not “fix” it in UI. Improve signal upstream when a new lever exists.
