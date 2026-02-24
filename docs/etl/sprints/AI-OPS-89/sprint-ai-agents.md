# AI-OPS-89 Prompt Pack

Objective:
- Ship concern-level coherence drilldown links v1 in `/citizen` so party mismatch cards open an audit URL that preserves party/topic/concern context.

Acceptance gates:
- Add deterministic coherence drilldown URL builder in `ui/citizen/index.html`.
- Drilldown link must include trace context (`party_id`, `topic_id`, `concern`, `view=coherence`, `bucket`, `source=citizen_coherence`).
- Expose stable link markers in coherence cards for contract tests.
- Add strict UI contract test lane for coherence drilldown links.
- Integrate lane into `citizen-release-regression-suite`.
- Keep GH Pages build green.

Status update (2026-02-23):
- Implemented and validated with regression + build evidence.
