# Initiative Quality Actionable Gate (AI-OPS-28)

Date:
- 2026-02-22

Objective:
- Close the loop on initiative-document quality by making actionable tail debt a hard gate condition.

Shipped:
- `etl/parlamentario_es/quality.py`
  - added canonical initiative KPI:
    - `actionable_doc_links_closed_pct`
  - default initiative gate thresholds now include:
    - `actionable_doc_links_closed_pct >= 1.0`
- tests updated:
  - `tests/test_parl_quality.py`
  - `tests/test_cli_quality_report.py`

Validation (real DB):
```bash
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --source-ids congreso_votaciones,senado_votaciones \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --enforce-gate \
  --json-out docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_actionable_gate_enforce_20260222T190825Z.json
```

Re-validation (same day, fresh timestamp):
```bash
python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report -q
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --source-ids congreso_votaciones,senado_votaciones \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas \
  --enforce-gate \
  --json-out docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_actionable_gate_enforce_20260222T191055Z.json
```

Results:
- Initiative gate: `passed=true`
- Actionable-tail KPI (overall initiatives):
  - `missing_doc_links=119`
  - `missing_doc_links_actionable=0`
  - `actionable_doc_links_closed_pct=1.0`
- By source:
  - `senado_iniciativas`: `missing_doc_links_actionable=0`, `actionable_doc_links_closed_pct=1.0`

Evidence:
- `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_actionable_gate_enforce_20260222T190825Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/quality_initiatives_actionable_gate_enforce_20260222T191055Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/initiative_quality_gate_tests_20260222T191055Z.txt`

Outcome:
- The initiative gate now fails only when truly actionable document links remain open.
- The known Senate tail (`119` links) is explicitly tracked as non-actionable in the gate math, preventing blind retry loops while preserving traceability.
