# AI-OPS-16 Task 3: declared stance v3 design

## Where we are now
- Source: `congreso_intervenciones` declared evidence (`topic_evidence.evidence_type LIKE 'declared:%'`).
- Baseline (Task 1): `614` declared rows, `202` with signal (`32.90%`), `412` as `unclear`.
- Current extractor already uses `declared:regex_v3`, but broad declared verbs (for example `defendemos`) can over-fire outside explicit vote intent.

## Where we are going
Implement a clearer confidence ladder and keep conservative defaults:
- High confidence only for explicit vote intent phrases.
- Medium confidence for abstention and contextual declared-support/oppose phrases.
- Low confidence for weak declared verbs and all conflicting signals, so they route to review when `min_auto_confidence=0.62`.

## Implemented rule changes
File changed: `etl/parlamentario_es/declared_stance.py`

1. Split declared patterns into `strong` and `weak`
- Added contextual (strong) declared patterns that require a policy object near the verb (`iniciativa`, `enmienda`, `proposición`, `ley`, `proyecto`, etc.).
- Kept broad (weak) declared patterns (`apoyamos`, `defendemos`, `rechazamos`, etc.) but assigned lower confidence.

2. Added parliamentary oppose cue
- Added explicit oppose pattern for first-person framing of `enmienda a la totalidad` (`mantenemos|reafirmamos ... enmienda a la totalidad`).

3. Tightened conflict policy
- Any mixed signal across explicit/declared families now returns `reason=conflicting_signal` with low confidence (`0.58`).
- This makes conflict handling review-first under the default threshold.

4. Confidence ladder (explicit policy)
- `explicit_vote_intent`: `0.74`
- `abstention_intent`: `0.68`
- `declared_support` / `declared_oppose` (strong contextual): `0.66`
- `weak_declared_support` / `weak_declared_oppose`: `0.58`
- `conflicting_signal`: `0.58`

## Expected behavior
- Preserve extraction for direct vote intent (`votaremos a favor`, `votaremos en contra`).
- Preserve contextual declared stance (`apoyamos esta iniciativa`, `no apoyamos esta ley`).
- Reduce blind auto-classification from weak rhetoric-only phrases by sending them to review by default.
- Keep reason strings traceable for auditability and downstream review notes.

## What is next
- Task 4 will add/adjust targeted tests for:
  - strong vs weak declared patterns,
  - conflict-to-review behavior,
  - regression guardrails against known false positives/negatives.
