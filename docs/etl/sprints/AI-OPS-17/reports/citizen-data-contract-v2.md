# Citizen Snapshot Data Contract (v2, additive)

Date: 2026-02-17  
Sprint: `AI-OPS-17`  
Canonical contract: `docs/etl/sprints/AI-OPS-18/reports/citizen-data-contract.md`

## Goal
Enable the citizen UI/UX v2 (concern-first summaries + drill-down) with **additive**, backward compatible contract extensions.

Principles:
- Keep GH Pages static.
- Keep artifacts bounded (target `<= 5MB`).
- Preserve auditability: links over embedding raw evidence.
- Backward compatible: existing `ui/citizen/index.html` must keep working if it ignores new keys.

## Status
UI v2 can be implemented **without** contract changes by computing summaries client-side from:
- `topics[]`
- `party_topic_positions[]`
- `concerns_v1.json` keywords

However, to reduce duplication and make exports more deterministic/portable, we define optional v2 extensions below.

## v2 Extensions (All Optional)

### 1) Server-Side Topic Tagging: `topics[].concern_ids` (recommended)

Add an optional list of concern ids a topic matches:

```json
{
  "topic_id": 250,
  "label": "...",
  "concern_ids": ["vivienda", "coste_vida"]
}
```

Rules:
- `concern_ids` must be a list of strings matching ids in `ui/citizen/concerns_v1.json`.
- Computation must be deterministic and documented:
  - normalize with `lowercase + strip_diacritics` (same as UI)
  - match by substring containment of any concern keyword in topic label
- Ordering: `concern_ids` sorted ascending (lexicographic) for stability.

Why:
- avoids duplicating `topic_concerns` logic in every UI/client
- enables exporter-side enforcement of `max_items_per_concern`
- allows future UIs to render the same concerns without reimplementing keyword logic

### 2) Optional Concern Summary Grid (Hechos): `party_concern_positions[]` (optional)

Add a compact per-party summary per concern:

```json
{
  "party_concern_positions": [
    {
      "concern_id": "vivienda",
      "party_id": 12,
      "stance": "support",
      "confidence": 0.42,
      "window": { "max_items": 60, "sort": "high_stakes_first" },
      "counts": { "support": 12, "oppose": 3, "mixed": 1, "unclear": 7, "no_signal": 37 },
      "links": { "audit_topic": "../explorer-temas/?topic_set_id=1&topic_id=250" }
    }
  ]
}
```

Notes:
- This is a *convenience grid*. The UI may still recompute summaries on the fly when the user changes filters/limits.
- If this key exists, its semantics MUST specify the window used (`window.max_items`, sort) so it cannot be misread as “all items ever”.

### 3) Method Metadata: `meta.methods_available` (optional)

To support honest labeling and future toggles:

```json
{
  "meta": {
    "computed_method": "combined",
    "methods_available": ["combined", "votes"]
  }
}
```

Rules:
- `methods_available` is a list of strings present in the DB for the exported scope (topic_set_id + institution_id), for the chosen `as_of_date`.
- Sorted ascending for determinism.

Why:
- allows UI copy to say “we chose combined; votes also exists” without guessing
- supports shipping multi-artifact variants later (e.g. `citizen_votes.json`, `citizen_combined.json`)

## Existing v1 Extension (unchanged): `party_concern_programas[]`
`party_concern_programas` remains as the optional programs/promise lane. v2 does not change its meaning.

## Backward Compatibility
- All keys above are optional.
- Existing required keys from v1 remain required.
- Validator and UI must:
  - ignore unknown keys
  - treat missing optional keys as absent (fallback to client-side computation)

## Acceptance (for v2 adoption)
- Exporter can emit `topics[].concern_ids` deterministically.
- If `party_concern_positions` is emitted, it includes `window` metadata.
- Validator accepts new optional keys (and still enforces v1 required keys).
