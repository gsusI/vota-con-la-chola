# Polish Notes (Post-FAST Evidence)

Sprint: `AI-OPS-17`  
Date: `2026-02-17`

## Summary
FAST wave checks did not surface hard failures (build, validation, link drill-down, strict gate/parity all PASS). No scope-expanding changes applied in this polish pass.

## Observations
- The citizen app is usable under a plain static server (GH Pages equivalent): JSON loads and core explorers resolve.
- Concern matching is intentionally naive (keyword substring); it should be treated as navigation, not classification.
- Drill-down currently resolves to three targets (`/explorer-temas`, `/explorer`, `/explorer-politico`) which is good for robustness.

## Optional Next Polish (Not Required For Gates)
- Add a short in-app “Como funciona” expandable block (copy-only; no new data).
- Add a visible “share link” affordance (copy current URL with `concern` + `topic_id`).
- Add a `prefers-reduced-motion` guard to disable animations for users who request it.
