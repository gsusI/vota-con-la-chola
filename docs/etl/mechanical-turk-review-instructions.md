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

## 7) Export files contract (required)

Batch id format:
- `mturk-YYYYMMDD-<short_slug>` (example: `mturk-20260216-congreso-a1`)

Required folder per batch:
- `etl/data/raw/manual/mturk_reviews/<batch_id>/`

Required files:
- `tasks_input.csv`: the exact rows sent to workers (immutable once launched).
- `workers_raw.csv`: raw platform export from MTurk (immutable; no edits).
- `decisions_adjudicated.csv`: final internal decisions to apply to DB.

Minimum columns:
- `tasks_input.csv`:
  - `batch_id`, `evidence_id`, `person_name`, `topic_label`, `evidence_excerpt`, `evidence_date`, `source_url`, `review_reason`
- `workers_raw.csv`:
  - `batch_id`, `evidence_id`, `worker_id`, `worker_stance`, `worker_confidence`, `worker_note`
- `decisions_adjudicated.csv`:
  - `batch_id`, `evidence_id`, `proposed_status`, `proposed_final_stance`, `agreement_ratio`, `adjudicator_note`

Immutability rule:
- Never overwrite `tasks_input.csv` or `workers_raw.csv`.
- If adjudication changes, append a new `decisions_adjudicated_v2.csv` (or higher) and keep prior versions.

## 8) Internal handoff to DB

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

## 9) Progress checks (live)

Before apply:
- `wc -l etl/data/raw/manual/mturk_reviews/<batch_id>/workers_raw.csv`
- `wc -l etl/data/raw/manual/mturk_reviews/<batch_id>/decisions_adjudicated.csv`

After apply (DB progress):

```bash
sqlite3 etl/data/staging/politicos-es.db "
SELECT status, COUNT(*) AS c
FROM topic_evidence_reviews
GROUP BY status
ORDER BY status;"
```

```bash
sqlite3 etl/data/staging/politicos-es.db "
SELECT COUNT(*) AS c
FROM topic_evidence_reviews
WHERE LOWER(COALESCE(note,'')) LIKE '%mturk%';"
```

## 10) Out-of-scope (do not delegate)

- Codebook changes.
- Final arbitration for disputed or politically sensitive items.
- Intervention definition for causal analysis.
- Any public narrative/scoring decision.

## 11) Auditability requirements

- Keep raw MTurk export files immutable by batch.
- Preserve row-level mapping `evidence_id -> worker labels -> final proposal`.
- Log adjudication decisions and rationale.
- Every DB write must include a note with `batch_id`.
