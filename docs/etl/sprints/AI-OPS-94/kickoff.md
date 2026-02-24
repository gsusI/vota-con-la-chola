# AI-OPS-94 Kickoff

Date:
- 2026-02-23

Primary objective:
- Close the coherence drilldown parity gap between `/citizen` and `/explorer-temas` by supporting party-scoped evidence filtering and URL-intent replay.

Definition of done:
- Coherence API accepts `party_id` for summary/evidence filters and preserves deterministic results.
- Coherence evidence rows expose party metadata needed for audit context.
- `explorer-temas` reads and applies `party_id` + `bucket/view/source` drilldown params.
- URL-intent opens coherence evidence directly (no manual re-selection required).
- Tests + `just` lane pass and release regression/build remain green.
