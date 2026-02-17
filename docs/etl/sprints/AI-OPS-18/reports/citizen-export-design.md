# AI-OPS-18 Task 3: Citizen Snapshot Export Design

Date: 2026-02-17  
Owner: L2 Specialist Builder

## Goal

Produce a static-friendly, bounded JSON snapshot that powers the citizen GH Pages app.

The export must be:
- deterministic from (`--db`, `--topic-set-id`, `--as-of-date`, `--computed-method`)
- honest about uncertainty and missing signal
- small enough for GH Pages (`<= 5 MB` default)
- link-heavy for audit (drill-down via existing explorers)

## Files

- Exporter: `scripts/export_citizen_snapshot.py`
- Contract: `docs/etl/sprints/AI-OPS-18/reports/citizen-data-contract.md`

## Input Data (Current)

We reuse what the repo already computes:
- `topic_set_topics` + `topics` for the list of items
- `topic_positions` for member-level stances and scores
- `mandates` + `parties` to aggregate stances to parties

We DO NOT export raw evidence rows.
Evidence drill-down stays in `/explorer` and `/explorer-temas`.

## Scope Resolution (Deterministic)

The exporter resolves a concrete scope:
- `topic_set_id`: user-provided (default `1`)
- `institution_id`: user-provided (default `7`, Congreso)
- `computed_method`: `auto|combined|votes` (default `auto`)
- `as_of_date`:
  - if provided: used as-is
  - else: inferred as the latest date for preferred method(s): `combined` then `votes`
- `computed_version`:
  - chosen as the most common version for that scope+date+method

This avoids ambiguous mixes when multiple computed versions exist.

## Party Aggregation Logic

We aggregate per `(topic_id, party_id)` from member positions.

### Inputs

Member positions are selected by:
- `topic_positions.institution_id = scope.institution_id`
- `topic_positions.topic_set_id = scope.topic_set_id`
- `topic_positions.as_of_date = scope.as_of_date`
- `topic_positions.computed_method = scope.computed_method`
- `topic_positions.computed_version = scope.computed_version`

Party membership comes from active mandates:
- `mandates.institution_id = scope.institution_id`
- `mandates.is_active = 1`

### Aggregates

For each `(topic_id, party_id)`:
- `members_with_signal`: count of member rows where `stance != 'no_signal'`
- stance breakdown counts: support/oppose/mixed/unclear
- `evidence_count_total`: sum of `topic_positions.evidence_count`
- `last_evidence_date`: max of `topic_positions.last_evidence_date`
- `score_weighted`: weighted average of `topic_positions.score` by `evidence_count`
- `confidence_weighted`: weighted average of `topic_positions.confidence` by `evidence_count`

### Stance Derivation (Conservative)

`derive_party_stance()` returns one of:
- `no_signal` when `members_with_signal == 0`
- `unclear` when coverage is too low to claim a stance
- otherwise `support|oppose|mixed`:
  - if both support and oppose exist and no supermajority (>= 0.75), label `mixed`
  - else label the majority direction

Coverage guardrail:
- require `members_with_signal >= max(1, min(3, members_total), ceil(0.20 * members_total))`
- otherwise downgrade to `unclear`

Rationale:
- prevents claiming party stance from tiny samples (e.g. when only a few member votes are mapped)

### Confidence

`confidence = confidence_weighted * (members_with_signal / members_total)` clamped to `[0,1]`.

If stance is `no_signal` or downgraded to `unclear`, the exporter sets `score=0.0` to avoid contradictory presentation.

## Determinism and Ordering

Exporter sorts:
- `topics`: `is_high_stakes desc`, `stakes_rank asc`, `topic_id asc`
- `parties`: `name asc`, `party_id asc`
- `party_topic_positions`: full grid ordered by `(topic_id asc, party_id asc)`

The exporter emits the full grid (`topic x party`) so the UI can render explicit `no_signal` rows.

## Size Guardrails

Defaults:
- `--max-bytes 5000000`
- output uses compact JSON (`separators=(',',':')`) unless `--pretty`.

If the output exceeds `--max-bytes`, exporter exits with code `3`.

## Drill-Down Links

All rendered entities include relative links to existing explorers:
- topic-level links:
  - `/explorer-temas/?topic_set_id=...&topic_id=...`
  - `/explorer/?t=topic_positions ...`
  - `/explorer/?t=topic_evidence ...`
- party-topic link:
  - `/explorer/?t=topic_positions ...` filtered to the scope

## Acceptance Checks

```bash
python3 scripts/export_citizen_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/citizen/data/citizen.json \
  --topic-set-id 1 \
  --computed-method auto

python3 -c 'import json; import pathlib; json.loads(pathlib.Path("docs/gh-pages/citizen/data/citizen.json").read_text())'
```

- Output JSON exists and is valid.
- Output size <= 5MB.
- `meta` includes resolved `as_of_date`, `computed_method`, `computed_version`.
