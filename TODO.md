## Phase 1 - Make the project legible, trustworthy, and easy to join

\[ \] 1. Project thesis and boundaries
Context: The project needs a sharp public identity before it can attract durable contributors. Right now it risks looking like a general data platform without a clear first promise.
Prompt: Read README.md, docs/roadmap.md, docs/personas-y-flujos-ideales.md, and the homepage copy. Write docs/strategy/project-thesis.md that defines: what the project is, who it serves first, what it can claim now, what it must not claim yet, and what the long-term accountability framework should become. Also create docs/strategy/non-goals.md.
Output: docs/strategy/project-thesis.md, docs/strategy/non-goals.md

\[ \] 2. Public claims and metric consistency audit
Context: Contradictory public numbers destroy trust fast, especially in a political accountability project.
Prompt: Read docs/strategy/project-thesis.md, README.md, homepage copy, /citizen/leaderboards/, /citizen/data/citizen.json, and docs/communications/press-releases-2026-02-24.md. Produce docs/audits/public-claims-audit.md listing every public metric and claim, its canonical source, whether it is current, where it conflicts, and the exact copy change needed.
Output: docs/audits/public-claims-audit.md

\[ \] 3. Code license and data-rights package
Context: Developers hesitate to contribute when code and data rights are unclear or mixed together.
Prompt: Read current legal files, README.md, and the Hugging Face dataset card/config. Recommend and implement a code license, then document a separate data-rights matrix by source. Make it explicit what applies to code, compiled datasets, snapshots, and third-party source material. Flag anything that needs human legal review.
Output: LICENSE, docs/legal/data-rights.md, updates to README.md and dataset docs

\[ \] 4. Repo onboarding, metadata, and governance pack
Context: A serious project should look open to collaborators, not like a private working repo with public visibility.
Prompt: Read README.md, CONTRIBUTING.md, .github/, and docs/strategy/project-thesis.md. Improve onboarding for outsiders: draft GitHub About text, repo topics, badges, maintainer roles, issue template(s), PR template, label taxonomy, decision log process, and release checklist. Save anything that cannot be set directly in docs/ops/github-about.md.
Output: updated README.md, CONTRIBUTING.md, .github templates, docs/ops/github-about.md, docs/governance/decision-log-process.md

\[x\] 5. Fast local dev path and tiny fixture dataset
Context: If contributors cannot get a working local environment quickly, many will drop off before the first commit.
Prompt: Read current dev setup docs, Docker/Just/Make config, and CI config. Create a one-command local dev path, a tiny fixture SQLite snapshot or equivalent seed data, and a smoke test that proves the project boots on minimal data. Document it in docs/dev/quickstart.md.
Output: docs/dev/quickstart.md, tiny fixture dataset, smoke test, small DX improvements in tooling

\[x\] 6. Public roadmap and issue map
Context: A project attracts builders when the path from "today" to "useful system" is visible and broken into joinable chunks.
Prompt: Using outputs from tasks 1 to 5, write docs/roadmap/public-roadmap.md with three horizons: current product value, contributor platform, and full accountability framework. Add milestone issue drafts or markdown issue seeds for each major step.
Output: docs/roadmap/public-roadmap.md, docs/issues-seed/

## Phase 2 - Make the current value undeniable

\[x\] 7. Choose the primary public wedge
Context: The project should lead with one unforgettable use case, not many partial surfaces.
Prompt: Read docs/strategy/project-thesis.md, docs/personas-y-flujos-ideales.md, /explorer-votaciones/data/votes-preview.json, /explorer-sources/data/status.json, and /citizen/leaderboards/. Decide the strongest primary public wedge for the next 3-6 months. Compare at least: vote explainer, source obstruction tracker, and said-vs-did analysis. Write docs/product/killer-use-case.md with one primary wedge, one supporting wedge, target user, and success metric.
Output: docs/product/killer-use-case.md

\[x\] 8. Truth contract, glossary, and sample gating
Context: The system must show uncertainty and insufficiency clearly instead of hiding weak evidence behind polished UI.
Prompt: Read docs/product/killer-use-case.md, /citizen/data/citizen.json, /citizen/leaderboards/, and docs/preguntas-metodologia-citizen.md. Write docs/method/truth-contract.md defining confidence labels, sample thresholds, unknown states, freshness states, when to gray out or hide rankings, and exact wording for insufficient evidence. Also create a machine-readable glossary JSON.
Output: docs/method/truth-contract.md, docs/method/glossary.json

\[x\] 9. Vote explainer spec
Context: A single shareable vote page can become the first thing users and journalists pass around.
Prompt: Read docs/product/killer-use-case.md, docs/method/truth-contract.md, and /explorer-votaciones/data/votes-preview.json. Write docs/product/vote-explainer-spec.md for a public page/card that answers: what was voted, what happened, who voted how, where are the official sources, and what caveats apply. Include route structure, JSON contract, and social share metadata.
Output: docs/product/vote-explainer-spec.md

\[x\] 10. Vote explainer MVP
Context: A spec alone will not generate attention; the first public artifact needs to exist and be linkable.
Prompt: Implement docs/product/vote-explainer-spec.md using existing vote data only. Add one canonical route, official source links, caveat badges from the truth contract, tests, and a short demo note.
Output: code for vote explainer MVP, docs/release-notes/vote-explainer-mvp.md

\[ \] 11. Source obstruction tracker MVP
Context: One of the project's strongest unique angles is showing where public-data accountability is blocked.
Prompt: Read docs/product/killer-use-case.md, docs/method/truth-contract.md, and /explorer-sources/data/status.json. Build a public obstruction tracker page plus JSON feed showing source health, blocked sources, evidence artifacts, affected coverage, and last change.
Output: code for obstruction tracker MVP, docs/release-notes/obstruction-tracker-mvp.md

\[ \] 12. Transparency dashboard and release-note flow
Context: Contributors and users trust projects that expose freshness, source health, and what changed.
Prompt: Read outputs from tasks 10 and 11 plus current publish/snapshot flow. Build a small transparency dashboard that shows last refresh, source health summary, latest snapshot version, recent changes, and links to release notes. Keep every number traceable to a source.
Output: transparency dashboard, docs/product/transparency-dashboard.md, lightweight release-note process

## Phase 3 - Make it modular so outsiders can build on it

\[ \] 13. Core ontology v1
Context: To grow from votes into promises, spending, agreements, and outcomes, the project needs a stable shared vocabulary.
Prompt: Read docs/strategy/project-thesis.md, docs/product/killer-use-case.md, and current schemas/tables. Design docs/data-model/core-ontology-v1.md for actor, organization, role, territory, source, document, evidence, topic, claim, promise, initiative, vote, spending item, contract, agreement, meeting, event, indicator, and outcome. Include IDs, timestamps, provenance, and relationships.
Output: docs/data-model/core-ontology-v1.md

\[ \] 14. Plugin architecture v1
Context: Activist developers should be able to add connectors and analysis modules without deep coupling to the whole repo.
Prompt: Read docs/data-model/core-ontology-v1.md and the current pipeline code. Write docs/architecture/plugin-system-v1.md defining interfaces for connectors, parsers, extractors, linkers, scorers, and publishers. Include plugin manifest format, lifecycle hooks, versioning, and test hooks.
Output: docs/architecture/plugin-system-v1.md

\[ \] 15. Minimal SDK and sample plugin
Context: A plugin architecture becomes real only when there is an example that new contributors can copy.
Prompt: Implement a minimal SDK and one example plugin based on docs/architecture/plugin-system-v1.md and docs/data-model/core-ontology-v1.md. The example should ingest one simple public source into the standard schema, run locally, and include tests and docs.
Output: SDK code, example plugin, docs/examples/sample-plugin.md

\[ \] 16. Provenance, reproducibility, and signed snapshot flow
Context: A political accountability system needs strong provenance and reproducibility, not just raw data dumps.
Prompt: Read the current snapshot/publish flow, Hugging Face publication config, and docs/data-model/core-ontology-v1.md. Add checksums, schema version stamps, snapshot manifests, diff reports, and a simple way to verify that a published artifact matches a build. Document it.
Output: provenance/reproducibility improvements, docs/ops/reproducibility.md

\[ \] 17. Stable Evidence API / export contract
Context: Outside tools and partner projects need a stable way to consume entities and evidence chains.
Prompt: Read docs/data-model/core-ontology-v1.md, docs/ops/reproducibility.md, and current public exports. Define and implement a stable read-only Evidence API or export contract for entities, evidence chains, source health, and question results. Include versioning, pagination, and provenance fields.
Output: docs/api/evidence-api-v1.md, implementation of stable export/API surface

## Phase 4 - Expand the accountability surface beyond votes

\[ \] 18. Promises and manifesto data model
Context: Accountability starts before parliamentary action, with campaign promises and explicit commitments.
Prompt: Read docs/data-model/core-ontology-v1.md and any existing promise/topic logic. Write docs/data-model/promises-spec-v1.md defining how to represent explicit promises, softer commitments, preferences, slogans, coalition agreements, and issue positions. Include extraction rules and ambiguity cases.
Output: docs/data-model/promises-spec-v1.md

\[ \] 19. First promises pipeline
Context: The framework needs one real promise source, not just a schema.
Prompt: Using docs/data-model/promises-spec-v1.md, implement one end-to-end promise ingestion pipeline for a single party manifesto or equivalent source. Include segmentation, topic tagging, actor attribution, evidence links, and a small published sample.
Output: first promises pipeline, docs/release-notes/promises-pipeline-mvp.md

\[ \] 20. Spending and procurement data model
Context: The user-facing ambition includes accountability from promises to spending, so money must be first-class in the model.
Prompt: Read docs/data-model/core-ontology-v1.md and docs/strategy/project-thesis.md. Write docs/data-model/spending-spec-v1.md for budgets, amendments, procurement notices, awards, contracts, beneficiaries, amounts, dates, territories, and linked actors. Include provenance requirements and unresolved edge cases.
Output: docs/data-model/spending-spec-v1.md

\[ \] 21. First spending/procurement connector
Context: A working money path is necessary to move beyond legislative behavior alone.
Prompt: Using docs/data-model/spending-spec-v1.md, implement one official spending or procurement connector. Publish a small normalized sample and one query example that traces actor -> spending item -> source evidence.
Output: first spending connector, docs/release-notes/spending-connector-mvp.md

\[ \] 22. Agreements, meetings, and influence data model
Context: Accountability also depends on who meets whom, what is agreed, and what formal or semi-formal pacts exist.
Prompt: Read docs/data-model/core-ontology-v1.md. Write docs/data-model/agreements-influence-spec-v1.md covering coalition agreements, parliamentary pacts, meeting disclosures, lobbying disclosures, agendas, attendees, counterparties, and topics. Separate verified document facts from inferred influence.
Output: docs/data-model/agreements-influence-spec-v1.md

\[ \] 23. First agreements / influence connector
Context: The framework should prove it can capture at least one source of agreements or meeting disclosures.
Prompt: Using docs/data-model/agreements-influence-spec-v1.md, implement one connector for an official agreement or meeting disclosure source. Normalize actors, dates, and topics, then publish a small sample with evidence links.
Output: first agreements/influence connector, docs/release-notes/agreements-connector-mvp.md

\[ \] 24. Geopolitics data model
Context: The long-term system should cover foreign-policy positions and actions, not only domestic legislative behavior.
Prompt: Read docs/data-model/core-ontology-v1.md. Write docs/data-model/geopolitics-spec-v1.md covering treaties, resolutions, sanctions, aid commitments, defense agreements, international votes, counterpart states or organizations, and time-scoped positions. Mark what is verifiable fact vs later inference.
Output: docs/data-model/geopolitics-spec-v1.md

\[ \] 25. First geopolitics connector
Context: A real foreign-policy source will prove the model extends beyond domestic politics.
Prompt: Using docs/data-model/geopolitics-spec-v1.md, implement one small connector for an official foreign-policy source and publish a sample dataset with evidence links and coverage notes.
Output: first geopolitics connector, docs/release-notes/geopolitics-mvp.md

\[ \] 26. Economic and social indicators data model
Context: To connect politics to public results, the project needs structured outcome indicators with time and geography.
Prompt: Read docs/data-model/core-ontology-v1.md. Write docs/data-model/indicators-spec-v1.md covering economic and social indicators, revisions, geographic scope, time intervals, methodology notes, uncertainty, and provenance.
Output: docs/data-model/indicators-spec-v1.md

\[ \] 27. First indicators pipeline
Context: The system needs at least one official indicator family to support later descriptive outcome links.
Prompt: Using docs/data-model/indicators-spec-v1.md, implement one official indicator pipeline. Preserve revisions and metadata, link indicators to territories and time periods, and document limitations.
Output: first indicators pipeline, docs/release-notes/indicators-mvp.md

\[ \] 28. Time-aware actor graph and entity resolution
Context: The hard question "who did what" requires stable identity across office changes, coalitions, aliases, and institutional shifts.
Prompt: Read outputs from tasks 19, 21, 23, 25, and 27 plus docs/data-model/core-ontology-v1.md. Implement a time-aware actor graph and entity resolution layer for people, parties, institutions, offices, aliases, mergers, splits, and coalition membership. Document rules and failure modes.
Output: entity-resolution system, docs/architecture/entity-resolution-v1.md

\[ \] 29. Comparison engine for promises / stated positions vs actions
Context: The project becomes much more valuable once it can compare commitments or declared stances to later actions with explicit evidence and caveats.
Prompt: Read docs/data-model/promises-spec-v1.md, docs/method/truth-contract.md, and current position/vote logic. Define and implement docs/method/comparison-engine-v1.md for comparing explicit promise or declared stance against later action. Support statuses such as aligned, conflicted, insufficient evidence, ambiguous mapping, changed framing, and not comparable.
Output: comparison engine, docs/method/comparison-engine-v1.md

\[ \] 30. Descriptive outcome-link layer
Context: Users will want to connect actions to social or economic results, but the system should not claim causality it cannot support.
Prompt: Read docs/data-model/indicators-spec-v1.md, docs/method/truth-contract.md, and docs/strategy/project-thesis.md. Implement docs/method/outcome-linking-v1.md that links actions to later indicators or events descriptively while clearly stating that no causal inference is claimed unless stronger methods are later added.
Output: outcome-link layer, docs/method/outcome-linking-v1.md

## Phase 5 - Turn the framework into answerable questions

\[ \] 31. Question catalog v1
Context: The platform should answer repeatable hard questions, not merely expose raw data tables.
Prompt: Read outputs from tasks 19 to 30. Build docs/product/question-catalog-v1.md with the 20 highest-value evidence-backed question types across promises, actions, spending, agreements, geopolitics, and outcomes. For each question type, define required data, answer shape, caveats, and explicit "cannot answer yet" rules. Also include a template for future additions.
Output: docs/product/question-catalog-v1.md

\[ \] 32. Evidence-backed Q&A endpoint for a first subset
Context: A public query layer is a better attention magnet than static tables once the answer format is disciplined.
Prompt: Using docs/product/question-catalog-v1.md and docs/api/evidence-api-v1.md, implement a Q&A endpoint or service for 5 initial question types only. Every answer must include evidence items, confidence/freshness, and an explicit unanswerable state when needed.
Output: initial Q&A endpoint/service, docs/api/question-answering-v1.md

\[ \] 33. Reporter and researcher workflows
Context: Journalists and civic researchers are likely the first strong multipliers if the workflows are fast and cited.
Prompt: Read outputs from tasks 10, 11, 21, 23, 25, 27, and 32. Create 3 end-to-end workflows: verify a political claim, trace a vote to official documents, and trace a spending item to beneficiaries and related actors. Provide notebooks or step-by-step docs.
Output: docs/workflows/, notebooks or scripts for 3 workflows

\[ \] 34. Weekly investigation kit
Context: Recurring publication builds attention better than one-off launches.
Prompt: Using docs/product/question-catalog-v1.md and docs/workflows/, build a weekly investigation kit: one markdown template, one data-pull script, one share-card spec, and one short publication checklist for turning fresh data into a public story quickly.
Output: docs/publishing/weekly-investigation-kit/, helper scripts

## Phase 6 - Make developers want to join and make the project visible

\[ \] 35. Contributor challenge pack
Context: New contributors are more likely to join when they can see concrete starter problems mapped to real impact.
Prompt: Read docs/roadmap/public-roadmap.md, docs/architecture/plugin-system-v1.md, and docs/dev/quickstart.md. Create a contributor challenge pack with 10 starter issues. Each should include context, files to read, acceptance criteria, skill tags, and why it matters. Include at least one connector task, one docs task, one UI task, one data-model task, and one test/CI task.
Output: docs/community/contributor-challenges-v1.md, issue drafts in docs/issues-seed/

\[ \] 36. Partner integration guide
Context: The project becomes a framework when external groups can plug in their own tools or data pipelines.
Prompt: Read docs/architecture/plugin-system-v1.md, docs/api/evidence-api-v1.md, and docs/community/contributor-challenges-v1.md. Write docs/community/partner-integration-guide.md for NGOs, media labs, civic hackers, and independent developers explaining how to add connectors, downstream tools, dashboards, and research modules.
Output: docs/community/partner-integration-guide.md

\[ \] 37. Launch kit and attention plan
Context: Attention has to be engineered with concrete artifacts, not left to chance.
Prompt: Read docs/strategy/project-thesis.md, docs/product/killer-use-case.md, docs/method/truth-contract.md, docs/community/partner-integration-guide.md, and the outputs of tasks 10, 11, and 34. Produce docs/communications/launch-kit-v1/ with: landing-page copy, demo script, press note, FAQ, contributor pitch, and a 30-day attention plan focused on journalists, civic-tech groups, activist developers, and watchdog communities.
Output: docs/communications/launch-kit-v1/
