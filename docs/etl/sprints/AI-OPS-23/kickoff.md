# AI-OPS-23 Kickoff

Date: 2026-02-17  
Decision owner: L3 Orchestrator

## Objective
Citizen Onboarding v1 (static GH Pages, audit-first, privacy-first):
- start from 0 and reach a defensible answer fast (concerns -> view)
- share non-sensitive view state by URL (preferences local-first; share opt-in via fragment)
- keep unknown/coverage explicit and auditable

## Must-pass Gates (G1-G6)
See the prompt pack for the canonical gate contract:
- `docs/etl/sprints/AI-OPS-23/sprint-ai-agents.md`

## Repro Commands (canonical)
Build static GH Pages output:
```bash
just explorer-gh-pages-build
```

Strict tracker gate:
```bash
just etl-tracker-gate
```
