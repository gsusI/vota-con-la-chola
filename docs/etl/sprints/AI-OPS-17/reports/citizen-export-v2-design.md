# Citizen Export v2 Design (Bounded + Deterministic)

Date: 2026-02-17  
Sprint: `AI-OPS-17`

## Objective
Support citizen UX v2 (concern-level summaries + party drill-down) with **bounded**, **deterministic** GH Pages artifacts, without shipping raw evidence blobs to the browser.

## Decision: Single Artifact (Option A)
For AI-OPS-17 we keep one primary artifact:
- `docs/gh-pages/citizen/data/citizen.json`

Rationale:
- Lowest complexity and least risk of regressions.
- Current artifact is well under budget (~1.7MB) and already validated in build.
- UX v2 can compute summaries client-side from the existing grid.

Future option (explicitly deferred, but enabled by metadata):
- Option B: publish two artifacts and add a UI toggle:
  - `docs/gh-pages/citizen/data/citizen_votes.json`
  - `docs/gh-pages/citizen/data/citizen_combined.json`

## Make `--max-items-per-concern` Meaningful (Forward-Compatible)
Today `topic_set_id=1` has exactly 200 topics, so `--max-topics=200` already exports the full set.

To ensure the export stays bounded even if future topic sets expand, define v2 selection semantics:

1. Compute deterministic concern tags for each topic (same normalization as UI):
   - lowercase + strip diacritics
   - keyword substring match on `topics[].label`
2. If `--max-items-per-concern > 0`:
   - for each concern, take the first N matching topics using stable sort:
     - `is_high_stakes desc`, `stakes_rank asc`, `topic_id asc`
   - export only the union of selected topics across all concerns
3. If `--max-items-per-concern == 0` (or missing):
   - export all topics in the topic_set (current behavior)

This preserves bounded growth as topic sets evolve, while keeping selection deterministic and explainable.

## Contract Additions (Optional v2)
These are additive and backward compatible:

1. `topics[].concern_ids` (recommended):
   - precomputed concern ids for each topic, sorted lexicographically.
2. `meta.methods_available` (recommended):
   - list like `["combined","votes"]` for the exported scope/as_of_date (sorted).

We do NOT plan to emit `party_concern_positions[]` in this sprint:
- It is easy to misread as “all evidence”, and it becomes misleading once UI filters/limits change.
- UI can compute concern summaries on the fly from `party_topic_positions[]` and the current item window.

## Artifact Strategy

### Primary artifact (AI-OPS-17)
- `citizen.json` is exported with:
  - `computed_method=auto` (prefers `combined`, fallback `votes`)
  - UI must label honestly based on `meta.computed_method` and should avoid calling non-`votes` outputs “Hechos”.

### Deferred multi-artifact strategy (Option B)
If we later want a citizen toggle:
- run exporter twice:
  - `--computed-method votes` -> `citizen_votes.json`
  - `--computed-method combined` -> `citizen_combined.json`
- publish both and validate both in `just explorer-gh-pages-build`
- UI loads one by default and can switch.

## Deterministic Ordering Rules (Required)
Exporter must keep stable ordering for reproducibility and diffs:
- `topics[]`: `(is_high_stakes desc, stakes_rank asc, topic_id asc)`
- `topics[].concern_ids`: lexicographic ascending
- `parties[]`: `(LOWER(name) asc, party_id asc)`
- `party_topic_positions[]`: `(topic_id asc, party_id asc)` full grid for exported topics x parties
- `party_concern_programas[]` (if present): `(concern_id asc, party_id asc)` full grid for concerns x parties
- `meta.methods_available`: lexicographic ascending

## Bounded Size Policy
- Hard target: each citizen JSON `<= 5,000,000` bytes.
- Keep the payload bounded by:
  - exporting only aggregated rows (no evidence tables)
  - limiting topics via `--max-items-per-concern` if the topic_set expands
  - limiting parties (already bounded by active mandates)

## KPI Outputs (Minimal Set)
To judge impact and keep visibility:
- Validator summary JSON:
  - `python3 scripts/validate_citizen_snapshot.py ... > .../citizen_validate_post.json`
- Size evidence:
  - `ls -l` bytes (and optionally gzip) to `.../citizen-json-size.txt`
- Concern coverage sanity CSV:
  - per concern: items_total, high_stakes_total, and any “zero items” flags
- Stance mix summary:
  - counts of `support/oppose/mixed/unclear/no_signal` (already printed by validator)

## Acceptance Criteria (Design-Level)
- Export remains bounded and deterministic under the selection rules above.
- UI can render concern-level summaries without requiring new server infrastructure.
- No change requires shipping raw evidence blobs to GH Pages.

