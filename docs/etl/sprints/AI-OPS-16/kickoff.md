# AI-OPS-16 Kickoff

Date:
- `2026-02-17`

Decision owner:
- `L3 Orchestrator`

## Scope Lock

Single sprint objective:
- Increase declared-position signal quality/coverage for `congreso_intervenciones` with reproducible evidence, while preserving strict gate/parity and enforcing anti-loop blocker handling (`no_new_lever` policy).

Primary lane (controllable):
- declared stance quality + review loop throughput + recompute/parity evidence.

Secondary lane (time-boxed blockers):
- `parlamento_galicia_deputados`
- `parlamento_navarra_parlamentarios_forales`
- `bde_series_api`
- `aemet_opendata_series`

## Baseline (AI-OPS-16 step 1 capture)

Tracker/gate:
- strict status exit: `0`
- strict gate exit: `0`
- `mismatches=0`
- `waivers_expired=0`
- `done_zero_real=0`

Tracker mix:
- `DONE=34`
- `PARTIAL=4`
- `TODO=9`

Declared signal baseline (`congreso_intervenciones`):
- `declared_total=614`
- `declared_with_signal=202`
- `declared_with_signal_pct=0.32899`

Review queue baseline:
- `topic_evidence_reviews_total=524`
- `topic_evidence_reviews_pending=0`
- `topic_evidence_reviews_resolved=50`
- `topic_evidence_reviews_ignored=474`

## In-scope rows/sources

Primary:
- line `74`: `Posiciones declaradas (programas)` (`TODO`, editorial/declarative pipeline)
- `congreso_intervenciones` declared stance + review queue + recompute outputs

Secondary:
- line `45`: `parlamento_galicia_deputados`
- line `53`: `parlamento_navarra_parlamentarios_forales`
- line `67`: `bde_series_api`
- line `68`: `aemet_opendata_series`

Out of scope:
- changing reproducibility policy for anti-bot sources without explicit approval.

## Must-pass gates (AI-OPS-16)

`G1` Integrity:
- `fk_violations=0`

`G2` Queue health:
- `topic_evidence_reviews_pending=0` at closeout.

`G3` Tracker strict gate:
- strict checker exits `0` with:
  - `mismatches=0`
  - `waivers_expired=0`
  - `done_zero_real=0`

`G4` Publish/status parity:
- status export and published payload remain in parity for tracker summary and impact counters.

`G5` Visible progress (primary):
- pass only if declared-signal lane shows measurable, evidence-backed delta (at least one of: `declared_with_signal`, `declared_with_signal_pct`, coherence explainability metrics) with reconciliation evidence.

`G6` Blocker lane policy:
- blocker probes execute only with new lever; if no lever, outcome must explicitly record `no_new_lever` and keep retries skipped.

## Execution policy

- No fake completion.
- Preserve truthful blockers and executable next commands.
- Prefer controllable L1 throughput work for most sprint points.
- Do not loop blind strict-network retries in blocker lane.
