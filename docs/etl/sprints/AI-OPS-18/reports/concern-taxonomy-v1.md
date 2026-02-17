# AI-OPS-18 Task 4: Concern Taxonomy v1 (Navigation Layer)

Date: 2026-02-17  
Owner: L2 Specialist Builder

## Purpose

Citizens don't think in `topic_id` and initiative titles.

This taxonomy provides a **deterministic navigation layer** to group existing initiative-level items into citizen-friendly "concerns".

Non-negotiables:
- This is NOT a substantive classifier.
- This must not be presented as "what the initiative is really about".
- It is only a convenience filter to find relevant items faster.

## Artifact

- Config: `ui/citizen/concerns_v1.json`

## Matching Rules (Deterministic)

A topic is tagged with a concern if:
- after normalization (lowercase + strip diacritics), the topic label contains any keyword substring from that concern.

Normalization assumptions:
- `lowercase=true`
- `strip_diacritics=true`

Keyword conventions:
- most keywords are stems (e.g. `trabaj`, `inmigr`) to tolerate inflection.
- multi-word keywords are allowed (e.g. `atencion primaria`).

## Concern List (v1)

Shipped concerns (12):
- `vivienda`
- `empleo`
- `sanidad`
- `educacion`
- `coste_vida`
- `energia`
- `transporte`
- `seguridad_justicia`
- `inmigracion`
- `corrupcion`
- `campo_rural`
- `igualdad`

## Known Limitations

- Initiative titles can be long and contain unrelated phrases; keyword tagging may overmatch.
- Some concerns overlap (e.g. `energia` vs `coste_vida`). This is acceptable for navigation.
- Some important concerns may have low recall until keyword lists are extended.

## Update Policy

- Additive updates only in v1: add concerns or add keywords.
- When changing existing keywords materially, bump version to `v2`.

## Acceptance Check (Manual)

- Load `ui/citizen/concerns_v1.json` successfully.
- For common concerns (`vivienda`, `empleo`, `sanidad`) confirm at least 1 matching item exists in the current scope (topic_set_id=1).
