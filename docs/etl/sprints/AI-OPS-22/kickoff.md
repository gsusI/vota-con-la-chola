# AI-OPS-22 Kickoff

Date: 2026-02-17  
Decision owner: L3 Orchestrator

## Objective
Citizen Alignment + Onboarding v0 (static GH Pages, audit-first, privacy-first):
- express preferences on concrete topics
- see match/mismatch/unknown per party (method-selectable)
- drill down to evidence via explorers

## Must-pass Gates (G1-G6)
See the prompt pack for the canonical gate contract:
- `docs/etl/sprints/AI-OPS-22/sprint-ai-agents.md`

## Baseline (to be captured in FAST wave)
Artifacts to capture:
- `docs/etl/sprints/AI-OPS-22/evidence/baseline_metrics.json`
- `docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json`

## Repro Commands (canonical)
Build static GH Pages output:
```bash
just explorer-gh-pages-build
```

Strict tracker gate:
```bash
just etl-tracker-gate
```

