# AI-OPS-37 Kickoff

Date:
- 2026-02-22

Objective:
- Add a strict validator for `ui/citizen/concerns_v1.json` (concerns + packs contract), wire it into the GH Pages build, and cover it with tests.

Why now:
- Citizen onboarding/alignment now depends on `packs` and concern descriptions; malformed config can silently break the UI.
- We need fail-fast guardrails in the canonical build path, not only runtime behavior.

Primary lane (controllable):
- Ship validator script + unit tests + build hook in `explorer-gh-pages-build`.

Acceptance gates:
- `scripts/validate_citizen_concerns.py` validates contract keys/types/references (`concerns`, `packs`, `concern_ids` integrity).
- `tests/test_validate_citizen_concerns.py` covers valid config plus representative failure cases.
- `just explorer-gh-pages-build` fails on invalid concerns config (validator hook integrated).
- `just etl-tracker-gate` remains green with evidence.
