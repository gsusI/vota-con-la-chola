# Citizen Explainability Copy Audit v1 (AI-OPS-87)

Date:
- 2026-02-23

Goal:
- Add plain-language explainability glossary/tooltips and enforce readability via strict static contracts.

What shipped:
- `/citizen` glossary/tooltips in `ui/citizen/index.html`:
  - `data-explainability-glossary="1"`
  - `data-explainability-term` markers for `unknown|cobertura|confianza|evidencia`
  - `data-explainability-tooltip="1"` + `data-term-definition` + `title` copy
  - `data-explainability-copy="1"` markers for short guidance text
- Strict UI contract test:
  - `tests/test_citizen_explainability_copy_ui_contract.js`
- Strict readability reporter:
  - `scripts/report_citizen_explainability_copy.py`
  - output status `ok|degraded|failed`
  - strict modes: `--strict`, `--strict-require-complete`
- Reporter tests:
  - `tests/test_report_citizen_explainability_copy.py`
- `just` integration:
  - `just citizen-test-explainability-copy`
  - `just citizen-report-explainability-copy`
  - `just citizen-check-explainability-copy`
  - lane added into `just citizen-release-regression-suite`

Validation:
- `just citizen-test-explainability-copy`
- `just citizen-report-explainability-copy`
- `just citizen-check-explainability-copy`
- `just citizen-release-regression-suite`
- `just explorer-gh-pages-build`
- `just citizen-check-release-hardening`

Strict explainability-copy result:
- `status=ok`
- `glossary_terms_total=4`
- `glossary_terms_with_tooltip=4`
- `glossary_terms_with_definition=4`
- `help_copy_sentences_total=9`
- `max_definition_words_seen=7`
- `max_help_copy_sentence_words_seen=7`
- `jargon_hits_total=0`

Evidence:
- `docs/etl/sprints/AI-OPS-87/evidence/citizen_explainability_copy_latest.json`
- `docs/etl/sprints/AI-OPS-87/evidence/citizen_explainability_copy_summary_20260223T124734Z.json`
- `docs/etl/sprints/AI-OPS-87/evidence/citizen_explainability_copy_markers_20260223T124734Z.txt`
- `docs/etl/sprints/AI-OPS-87/evidence/just_citizen_check_explainability_copy_20260223T124734Z.txt`
- `docs/etl/sprints/AI-OPS-87/evidence/just_citizen_release_regression_suite_20260223T124734Z.txt`
- `docs/etl/sprints/AI-OPS-87/evidence/just_explorer_gh_pages_build_20260223T124734Z.txt`
- `docs/etl/sprints/AI-OPS-87/evidence/just_citizen_check_release_hardening_20260223T124734Z.txt`
