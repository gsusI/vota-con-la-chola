# AI-OPS-18 Task 2: Citizen Snapshot Data Contract

Date: 2026-02-17  
Owner: L2 Specialist Builder

## Purpose

Define the minimal, bounded JSON contract consumed by the citizen-first GH Pages app.

Constraints:
- Static-only (GH Pages). No API required.
- Deterministic export from SQLite given `--db`, `--topic-set-id`, `--as-of-date`.
- Bounded size (initial hard target: `<= 5 MB`).
- Drill-down links must point to existing explorers.

## Source Scope (v1)

Default v1 scope:
- Institution: Congreso (`institution_id=7`)
- Topic set: `topic_set_id=1`
- As-of: explicit `--as-of-date` (recommended default = DB max `topic_positions.as_of_date` for this scope)
- Computed method for stances:
  - preferred: `combined`
  - fallback: `votes` when combined is missing

## Output File Layout

GH Pages output:
- `docs/gh-pages/citizen/data/citizen.json`
- `docs/gh-pages/citizen/data/concerns_v1.json` (shipped separately; not embedded)

## JSON Schema (v1)

Top-level shape:

```json
{
  "meta": {
    "generated_at": "2026-02-17T00:00:00Z",
    "db_path": "etl/data/staging/politicos-es.db",
    "topic_set_id": 1,
    "as_of_date": "2026-02-16",
    "computed_method": "combined",
    "computed_version": "v1",
    "limits": {
      "max_topics": 200,
      "max_parties": 40,
      "max_items_per_concern": 60
    },
    "guards": {
      "max_bytes": 5000000
    }
  },
  "concerns": {
    "version": "v1",
    "path": "data/concerns_v1.json"
  },
  "topics": [
    {
      "topic_id": 250,
      "label": "...",
      "stakes_rank": 26,
      "is_high_stakes": true,
      "source": {
        "topic_set_id": 1
      },
      "links": {
        "explorer_temas": "../explorer-temas/?topic_id=250",
        "explorer_positions": "../explorer/?t=topic_positions&wc=topic_id&wv=250",
        "explorer_evidence": "../explorer/?t=topic_evidence&wc=topic_id&wv=250"
      }
    }
  ],
  "parties": [
    {
      "party_id": 12,
      "name": "...",
      "acronym": "...",
      "links": {
        "explorer_politico_party": "../explorer-politico/?party_id=12"
      }
    }
  ],
  "party_topic_positions": [
    {
      "topic_id": 250,
      "party_id": 12,
      "stance": "support",
      "score": 0.73,
      "confidence": 0.61,
      "coverage": {
        "members_total": 137,
        "members_with_signal": 94,
        "evidence_count_total": 512,
        "last_evidence_date": "2026-02-10"
      },
      "links": {
        "explorer_temas": "../explorer-temas/?topic_id=250",
        "explorer_positions": "../explorer/?t=topic_positions&wc=topic_id&wv=250"
      }
    }
  ]
}
```

### Optional: Programas (Promesas) Per Concern (v1 extension)

If present, the snapshot MAY include an additional lane derived from party programs (`source_id=programas_partidos`):

- `meta.programas` (object):
  - `source_id`: `"programas_partidos"`
  - `topic_set_id`: programas topic_set id (per `election_cycle`)
  - `election_cycle`: string (e.g. `es_generales_2023`)
  - `as_of_date`: max evidence_date observed for that programas set (best-effort)
  - `evidence_total`, `signal_total`, `review_pending`: compact KPIs for UI status chips

- `party_concern_programas[]` (array):
  - Full grid of `concerns_v1.json` x `parties[]` (missing combos => `no_signal`)
  - Shape:
    - `concern_id` (string): must match concerns config ids (e.g. `vivienda`)
    - `party_id` (int): must exist in `parties[]`
    - `stance` (string): `support|oppose|mixed|unclear|no_signal`
    - `confidence` (number): best evidence confidence (0..1) if signal exists, else `0`
    - `evidence` (object): best evidence pointers (`evidence_id`, `evidence_date`, `source_record_pk`, `source_url`)
    - `links.explorer_evidence` (string): Explorer SQL link to program evidence rows

Semantics:
- This is a *promises* lane (text-derived). It is expected to be sparser and more uncertain than votes.
- It is keyed by citizen concerns (not initiative topics) and is meant to be shown alongside “hechos”.

### Field Semantics

- `topics[]`:
  - One row per `topic_id` in the exported scope.
  - Must include `stakes_rank` and `is_high_stakes` from `topic_set_topics`.
  - `links` must be relative paths under GH Pages.

- `parties[]`:
  - Parties present in active Congreso mandates for the export scope.
  - `party_id` comes from `mandates.party_id`.

- `party_topic_positions[]`:
  - Aggregated party stance for a given topic.
  - Computed from member-level `topic_positions` for the export scope:
    - `institution_id=7`
    - `topic_set_id=meta.topic_set_id`
    - `as_of_date=meta.as_of_date`
    - `computed_method=meta.computed_method`
  - `stance` is canonical: `support|oppose|mixed|unclear|no_signal`
  - Coverage rules:
    - `members_total`: number of active mandates in the party in Congreso
    - `members_with_signal`: number of those members whose `stance != no_signal` for that topic
    - `evidence_count_total`: sum of `topic_positions.evidence_count` across members (bounded integer)

## Determinism Rules

Exporter MUST:
- sort `topics` by `(is_high_stakes desc, stakes_rank asc, topic_id asc)`
- sort `parties` by `(name asc, party_id asc)`
- sort `party_topic_positions` by `(topic_id asc, party_id asc)`

## Size Guardrails

Hard guard:
- `citizen.json` must not exceed `meta.guards.max_bytes` (default `5_000_000`).

To stay under the guard:
- do not embed evidence rows
- do not embed full person lists
- keep only aggregated coverage counts + links

## Drill-Down Links Contract

Minimum required drill-down links per topic and per party-topic position:
- `explorer_temas`: topic focus in temas explorer
- `explorer_positions`: filtered topic_positions list in explorer
- `explorer_evidence`: filtered topic_evidence list in explorer

Links MUST be:
- relative (so they work under GH Pages)
- stable (no dependency on a local API host)

## Known Limitations (v1)

- Initiative-level topics are not citizen-friendly categories; concern tags are navigational only.
- Party aggregation from member positions can hide internal disagreement; therefore coverage is mandatory.
- `declared` signal coverage is currently small vs votes; UI must clearly display unknown/no-signal.

## Acceptance Checks

- `test -f docs/gh-pages/citizen/data/citizen.json` after build.
- `python3 scripts/validate_citizen_snapshot.py --path docs/gh-pages/citizen/data/citizen.json` passes.
- Link check report finds `broken_link_count=0` for required link fields.

## Optional v2 Extensions (Additive, Backward Compatible)

Citizen UI/UX can evolve without breaking the existing contract by adding optional keys. These are **optional** and must not be required for v1 consumers.

### v2: Server-Side Topic Tagging (`topics[].concern_ids`)

Problem:
- Today, concern tags are computed client-side from `concerns_v1.json` keywords.

Optional solution:
- Add `topics[].concern_ids` (array of concern ids) so clients do not need to re-implement keyword matching.

Rules:
- Values must match ids in `ui/citizen/concerns_v1.json`.
- Deterministic normalization/matching (same as UI): lowercase + strip diacritics + substring match by keyword.
- Sort `concern_ids` lexicographically for stability.

### v2: Concern Summary Grid (Hechos) (`party_concern_positions[]`)

Optional convenience grid keyed by `(concern_id, party_id)` for fast rendering of concern-level summaries.

Rules:
- Must be explicit about the summary window used (e.g. `max_items`, sort order), otherwise it is misleading.
- UI may still recompute summaries dynamically when users change filters.

### v2: Method Metadata (`meta.methods_available`)

Optional:
- `meta.methods_available`: list of methods present for the exported scope (e.g. `["combined","votes"]`).

This supports honest UI labeling and future multi-artifact toggles.
