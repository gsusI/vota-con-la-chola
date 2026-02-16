# Mechanical Turk Instructions (Topic Evidence Review)

Version: `v1`

Purpose:
- Close the manual review queue for declared evidence (`topic_evidence_reviews`) in a controlled, auditable way.
- Produce label proposals only. Final write to production DB is done by internal reviewer.

Scope:
- Source: `congreso_intervenciones`
- Unit of work: one `evidence_id`
- Goal label set: `support`, `oppose`, `mixed`, `unclear`, `no_signal`

## 1) What workers see

Each task row includes:
- `evidence_id`
- `person_name`
- `topic_label`
- `evidence_excerpt`
- `evidence_date`
- `source_url`
- `review_reason` (why the model could not auto-resolve)

Workers must read the excerpt and assign one stance label for the topic.

## 2) Label definitions (strict)

- `support`: clear support for the topic direction.
- `oppose`: clear opposition to the topic direction.
- `mixed`: both support and opposition signals in the same unit, or abstention/conditional stance that cannot be reduced to one side.
- `unclear`: text exists, but stance cannot be inferred with confidence.
- `no_signal`: no usable stance signal for that topic in the excerpt.

Rule:
- If in doubt between `unclear` and `no_signal`, use `unclear` when text is political but ambiguous; use `no_signal` when the excerpt is off-topic or purely procedural.

## 3) Decision tree (KISS)

1. Is the excerpt readable and related to the assigned topic?
2. If no, choose `no_signal`.
3. If yes, is there explicit support or opposition language?
4. If explicit support only, choose `support`.
5. If explicit opposition only, choose `oppose`.
6. If both or internally contradictory, choose `mixed`.
7. If none of the above but still political/contextual text, choose `unclear`.

## 4) Worker constraints

- Language: native or near-native Spanish reading proficiency.
- Political neutrality: annotate text signal only, never personal preference.
- No guessing from party identity or ideology.
- No external research required; classify from provided row only.

## 5) Quality controls

- Use `3` independent workers per item.
- Include `10%` gold items with known labels.
- Acceptance threshold per worker:
  - Gold accuracy `>= 85%`
  - Completion quality checks passed (non-empty rationale, no repeated spam text)
- Auto-accept row if at least `2/3` workers agree on label and no gold failure.
- Send to internal arbitration if:
  - `3-way` disagreement
  - Any worker flags text as malformed
  - Item is high-impact and disagreement persists

## 6) Required output schema

CSV fields:
- `batch_id`
- `evidence_id`
- `worker_id`
- `worker_stance` (`support|oppose|mixed|unclear|no_signal`)
- `worker_confidence` (`high|medium|low`)
- `worker_note` (max 240 chars, required)

Aggregated decision file (post-MTurk):
- `evidence_id`
- `proposed_status` (`resolved|ignored`)
- `proposed_final_stance` (`support|oppose|mixed|unclear|no_signal`, empty when ignored)
- `agreement_ratio` (0-1)
- `adjudicator_note`

Mapping rule:
- `proposed_status=resolved` when stance is actionable and agreement threshold is met.
- `proposed_status=ignored` when consensus is `no_signal` or evidence is malformed/off-topic.

## 7) Internal handoff to DB

Internal reviewer applies accepted proposals with:

```bash
python3 scripts/ingestar_parlamentario_es.py review-decision \
  --db <db_path> \
  --source-id congreso_intervenciones \
  --evidence-ids <comma_ids> \
  --status resolved \
  --final-stance <support|oppose|mixed|unclear|no_signal> \
  --note "mturk batch <batch_id>" \
  --recompute \
  --as-of-date <YYYY-MM-DD>
```

For ignored decisions:

```bash
python3 scripts/ingestar_parlamentario_es.py review-decision \
  --db <db_path> \
  --source-id congreso_intervenciones \
  --evidence-ids <comma_ids> \
  --status ignored \
  --note "mturk batch <batch_id>: no actionable signal"
```

## 8) Out-of-scope (do not delegate)

- Codebook changes.
- Final arbitration for disputed or politically sensitive items.
- Intervention definition for causal analysis.
- Any public narrative/scoring decision.

## 9) Auditability requirements

- Keep raw MTurk export files immutable by batch.
- Preserve row-level mapping `evidence_id -> worker labels -> final proposal`.
- Log adjudication decisions and rationale.
- Every DB write must include a note with `batch_id`.
