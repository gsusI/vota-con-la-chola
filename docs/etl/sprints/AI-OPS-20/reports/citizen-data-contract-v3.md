# Citizen Data Contract v3 (AI-OPS-20)

Status:
- `DRAFT`

Canonical contract:
- `docs/etl/sprints/AI-OPS-18/reports/citizen-data-contract.md`

This doc is additive: it describes v3 packaging (multi-method artifacts) without changing the core JSON schema.

## v3 Packaging (multi-method, bounded)

We ship multiple bounded citizen datasets (same schema, different `meta.computed_method`):
- `docs/gh-pages/citizen/data/citizen.json` (default; `combined`)
- `docs/gh-pages/citizen/data/citizen_votes.json`
- `docs/gh-pages/citizen/data/citizen_declared.json` (optional if useful; enable only when exported + linked in UI)

Constraints:
- Each JSON artifact must be `<= 5MB`.
- Each artifact must pass:
  - `python3 scripts/validate_citizen_snapshot.py --path <file> --max-bytes 5000000 --strict-grid`

## Invariants (must hold across methods)
- Same top-level keys as v1 contract:
  - `meta`, `topics`, `parties`, `party_topic_positions`, `concerns`
  - optional: `party_concern_programas`
- `party_topic_positions` is a full grid (topics x parties), filling missing rows with:
  - `stance=no_signal`, `score=0`, `confidence=0`, coverage zeros, links still present where possible.
- `meta.methods_available` (if present) is sorted unique and includes `meta.computed_method`.

## Method semantics (labels must be honest)
- `votes`: derived from roll-call votes ("hechos").
- `declared` (optional): derived from declared evidence from interventions ("dichos").
- `combined`: conservative combination of available signals (must not hide uncertainty).

## Citizen UI mapping (method -> file)
- default: `citizen.json`
- `method=votes`: `citizen_votes.json`
- `method=declared`: `citizen_declared.json`

## Build integration (single command)
- `just explorer-gh-pages-build` is the canonical builder.
- It must output citizen artifacts under `docs/gh-pages/citizen/data/`.

## Evidence required by gates
- Budget evidence: `docs/etl/sprints/AI-OPS-20/evidence/citizen-json-budget.txt`
- Validator outputs per artifact (stdout JSON summary captured to files).
