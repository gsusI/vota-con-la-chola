# Citizen Coherence Drilldown Links v1 (AI-OPS-89)

Date:
- 2026-02-23

Goal:
- Make coherence mismatch cards in `/citizen` open traceable drilldown URLs that preserve party+topic+concern context for fast audit.

What shipped:
- New helpers in citizen UI:
  - `resolveConcernIdForTopic(topicId, selectedConcernIds)`
  - `buildCoherenceDrilldownLink(rawLink, opts)`
- Coherence card drilldown links now include:
  - `party_id`
  - `topic_id`
  - `concern`
  - `view=coherence`
  - `bucket=incoherent|coherent`
  - `source=citizen_coherence`
- Coherence card link markers:
  - `data-coherence-drilldown-link="1"`
  - `data-party-id`
  - `data-topic-id`
  - `data-concern-id`
- New strict UI contract test:
  - `tests/test_citizen_coherence_drilldown_ui_contract.js`
- New `just` lane:
  - `just citizen-test-coherence-drilldown`
  - integrated in `just citizen-release-regression-suite`

Validation:
- `just citizen-test-coherence-drilldown`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`

Evidence:
- `docs/etl/sprints/AI-OPS-89/evidence/citizen_coherence_drilldown_markers_20260223T130321Z.txt`
- `docs/etl/sprints/AI-OPS-89/evidence/just_citizen_test_coherence_drilldown_20260223T130321Z.txt`
- `docs/etl/sprints/AI-OPS-89/evidence/just_citizen_release_regression_suite_20260223T130321Z.txt`
- `docs/etl/sprints/AI-OPS-89/evidence/just_explorer_gh_pages_build_20260223T130321Z.txt`
