# Citizen App: “Programa” Lane Integration

Date: 2026-02-17  
Sprint: `AI-OPS-18`

## Goal
Expose `programas_partidos` (party programs, promises) inside the citizen GH Pages app so users can compare:
- **Hechos**: aggregated party stances derived from votes/positions (existing lane)
- **Programa**: best-effort text-derived stance per citizen concern (new lane)

This is a UI + snapshot extension only. It does not change the main votes topic_set scope.

## Changes
- Exporter now emits an optional programs grid:
  - `scripts/export_citizen_snapshot.py`: adds `meta.programas` + `party_concern_programas[]`
  - `scripts/validate_citizen_snapshot.py`: validates `party_concern_programas` if present and prints `programas_stances` counts
- Citizen UI shows “Programa” per party card (by current concern):
  - `ui/citizen/index.html`

## Data Semantics (v1)
- `party_concern_programas` is keyed by `(concern_id, party_id)` and is a full grid for UI convenience.
- Stance comes from the strongest evidence row per `(topic_id, proxy_party_person_id)` in:
  - `topic_evidence` where `source_id=programas_partidos`, `evidence_type=declared:programa`,
    `stance_method in (declared:regex_v1..v3)`.

## How To Reproduce
Build snapshot (local):
```bash
python3 scripts/export_citizen_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out /tmp/citizen_programas.json \
  --topic-set-id 1 \
  --computed-method auto \
  --max-bytes 5000000

python3 scripts/validate_citizen_snapshot.py \
  --path /tmp/citizen_programas.json \
  --max-bytes 5000000 \
  --strict-grid
```

Then build GH Pages (optional):
```bash
just explorer-gh-pages-build
```

## Evidence
- `docs/etl/sprints/AI-OPS-18/evidence/citizen_programas_validator_post.json`

