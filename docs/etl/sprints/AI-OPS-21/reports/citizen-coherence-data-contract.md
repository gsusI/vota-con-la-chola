# AI-OPS-21 Coherence Data Contract (Decision)

Status:
- `DONE`

Inputs (already shipped by AI-OPS-20 build):
- `docs/gh-pages/citizen/data/citizen_votes.json`
- `docs/gh-pages/citizen/data/citizen_declared.json`

Goal:
- Enable a static “Coverage + Coherence” view without adding a backend and without exceeding JSON budgets.

## Options Considered

### Option A (Chosen): UI join votes + declared in-browser
- Coherence UI loads both datasets (lazy) and joins on:
  - `(topic_id, party_id)` over `party_topic_positions[]`
- Pros:
  - No ETL changes.
  - Keeps schema stable (reuses existing citizen contract).
  - Links remain correct per method because each dataset provides its own `topics[].links` and scope meta.
- Cons:
  - Extra download (~2MB) when coherence view is used.

### Option B: Export a new `citizen_coherence.json`
- Export a pre-joined artifact with both stances per cell and pre-aggregated coherence counts.
- Pros:
  - Smaller/constant runtime on the client.
- Cons:
  - Adds a new contract + validator surface area.
  - Risks duplication and drift (needs careful link/metadata handling).

## Decision
Choose **Option A** for v1:
- declared coverage is currently sparse; coherence is “best effort” and must prioritize honesty over polish.
- We already ship bounded votes+declared artifacts and validate them in `just explorer-gh-pages-build`.

## Join Contract (UI)
- The coherence view must treat datasets as full grids:
  - `party_topic_positions` is expected to include all `(topics x parties)` rows (strict-grid validated).
- Comparable only when both stances are in `{support, oppose}`.
- For audit links:
  - Use `topics[].links` from the corresponding method dataset (votes vs declared) to avoid guessing computed_version.

## Performance Budget (Expectation)
- Votes + Declared combined download target: `<= 3MB` (lazy-load only for coherence view).
