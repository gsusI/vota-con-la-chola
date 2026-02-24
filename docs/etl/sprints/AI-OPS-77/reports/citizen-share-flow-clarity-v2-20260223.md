# Citizen Share-Flow Clarity V2 (AI-OPS-77)

Date:
- 2026-02-23

Goal:
- Make `#preset` shared links resilient and self-healing while preserving static-first citizen architecture.

What shipped:
- Preset codec recovery/canonicalization in `ui/citizen/preset_codec.js`:
  - decode recovery helper for raw/unencoded and double-encoded payloads
  - version/payload parser that supports legacy payload recovery
  - `readPresetFromHash` now returns `canonical_hash` and `recovered_from`
  - case-insensitive `#preset=` acceptance
- Citizen UI recovery UX in `ui/citizen/index.html`:
  - new state fields: `presetCanonicalHash`, `presetRecoveredFrom`, `presetHashWasNormalized`
  - auto-normalization of hash via `history.replaceState(...${u.pathname}${u.search}${u.hash})`
  - banner notices for recovery and canonicalization
  - banner actions: `Copiar enlace canonico` and `Limpiar hash preset`
- Fixture and test hardening:
  - expanded `tests/fixtures/citizen_preset_hash_matrix.json` to schema `v2` with 13 hash cases and 3 share cases
  - updated `tests/test_citizen_preset_codec.js` assertions for `canonical_hash` and `recovered_from`
  - new UI contract test `tests/test_citizen_preset_recovery_ui_contract.js`
  - `just citizen-test-preset-codec` includes the recovery UI contract test

Validation:
- `node --test tests/test_citizen_preset_codec.js tests/test_citizen_preset_recovery_ui_contract.js`
- `just citizen-test-preset-codec`
- `just citizen-test-mobile-performance` (regression)
- `just citizen-test-first-answer-accelerator` (regression)
- `node --check` on extracted inline script from `ui/citizen/index.html`

Evidence:
- `docs/etl/sprints/AI-OPS-77/evidence/citizen_preset_recovery_contract_summary_20260223T110953Z.json`
- `docs/etl/sprints/AI-OPS-77/evidence/citizen_preset_recovery_contract_markers_20260223T110953Z.txt`
- `docs/etl/sprints/AI-OPS-77/evidence/just_citizen_test_preset_codec_20260223T110953Z.txt`
- `docs/etl/sprints/AI-OPS-77/evidence/just_citizen_test_mobile_performance_20260223T110953Z.txt`
- `docs/etl/sprints/AI-OPS-77/evidence/just_citizen_test_first_answer_accelerator_20260223T110953Z.txt`
