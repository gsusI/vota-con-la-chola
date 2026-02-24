# AI-OPS-51 Prompt Pack

Objective:
- Add trend-aware SLO semantics to preset bundle history with deltas vs previous window and a compact risk severity enum.

Acceptance gates:
- `scripts/report_citizen_preset_contract_bundle_history_slo.js` outputs:
  - `previous_window` summary (`available`, `entries_in_window`, `regressions_in_window`, `regression_rate_pct`, `latest_entry_clean`, `green_streak_latest`)
  - `deltas` (`regressions_in_window_delta`, `regression_rate_pct_delta`, `green_streak_latest_delta`)
  - `risk_level` (`green|amber|red`) and `risk_reasons`
- `--strict` exit behavior still tied to `strict_fail_reasons`.
- Tests cover `green`, `amber`, and `red` SLO outcomes.
- `just citizen-test-preset-codec` remains green.

Status update (2026-02-22):
- SLO reporter now includes previous-window trend deltas and risk severity output.
- Added amber-path coverage where thresholds pass but trend worsens vs previous window.
- Strict chain + tracker gate remain green.
- evidence:
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_codec_parity_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_codec_sync_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_history_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_history_window_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_history_compaction_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_history_slo_report_20260222T215935Z.json`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_history_compacted_20260222T215935Z.jsonl`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_contract_bundle_history_tail_20260222T215935Z.jsonl`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_codec_tests_20260222T215935Z.txt`
  - `docs/etl/sprints/AI-OPS-51/evidence/explorer_gh_pages_build_20260222T215935Z.txt`
  - `docs/etl/sprints/AI-OPS-51/evidence/tracker_gate_posttrackeredit_20260222T215935Z.txt`
  - `docs/etl/sprints/AI-OPS-51/evidence/citizen_preset_ci_bundle_history_slo_markers_20260222T215935Z.txt`
