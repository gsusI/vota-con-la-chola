# AI-OPS-87 Prompt Pack

Objective:
- Ship explainability copy audit v1 in `/citizen`: plain-language glossary/tooltips with strict readability contract checks.

Acceptance gates:
- Add stable explainability glossary markers and tooltip definitions in `ui/citizen/index.html`.
- Keep copy short/plain-language and avoid prohibited jargon in glossary/help text.
- Add strict UI contract test for glossary + tooltip markers.
- Add strict machine-readable readability reporter (`ok|degraded|failed`) with `--strict` and `--strict-require-complete`.
- Add `just` lanes and include explainability-copy lane in `citizen-release-regression-suite`.
- Keep release hardening and GH Pages build green.

Status update (2026-02-23):
- Implemented and validated with strict evidence.
