# AI-OPS-16 Task 4: declared stance v3 tests

## Where we are now
- `declared_stance.py` now has v3 confidence tiers and strong/weak declared reasons.
- Existing tests covered generic inference and idempotence, but did not pin exact v3 reason/confidence outputs or queue behavior for low-confidence weak/conflicting signals.

## What changed
Updated `tests/test_parl_declared_stance.py` with deterministic v3-focused coverage:

1. `test_infer_declared_stance_regex_v3_reason_confidence_policy`
- Asserts exact `(stance, polarity, confidence, reason)` for:
  - explicit vote intent (`0.74`)
  - abstention (`0.68`)
  - strong declared support/oppose (`0.66`)
  - weak declared support/oppose (`0.58`)
  - conflicting signal (`0.58`)

2. `test_backfill_declared_stance_regex_v3_queues_low_confidence_and_conflicts`
- Builds a temp DB with two declared rows:
  - weak declared support (`Defendemos este modelo social.`)
  - explicit+declared conflict (`Votaremos a favor, pero no apoyamos esta ley.`)
- Runs `backfill_declared_stance_from_topic_evidence(..., min_auto_confidence=0.62)` and asserts:
  - no auto updates (`updated=0`)
  - both rows queued as pending (`review_pending=2`)
  - reason split via `review_pending_by_reason`:
    - `low_confidence=1`
    - `conflicting_signal=1`
  - persisted queue suggestions/confidence are traceable and deterministic.

## Validation run
Commands executed:
- `python3 -m unittest tests.test_parl_declared_stance`
- `python3 -m unittest tests.test_parl_review_queue`
- `python3 -m unittest tests.test_parl_declared_positions`

Result:
- `6 + 1 + 1` tests passed.

## What is next
- Task 5: build acceptance KPI pack for declared signal delta/coherence/parity gates and fail-fast thresholds before baseline/candidate runs.
