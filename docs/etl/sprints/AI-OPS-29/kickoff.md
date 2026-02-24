# AI-OPS-29 Kickoff

Date:
- 2026-02-22

Objective:
- Harden `programas_partidos` declared-evidence loop so reruns preserve review adjudication state.

Why now:
- Live reruns were reopening review debt (`review_pending`) despite prior manual closeout.

Primary lane (controllable):
- Pipeline fix in `programas` ingest + reproducible status reporting + regression tests.

Acceptance gates:
- Stable `evidence_id` across reingest for unchanged program evidence keys.
- Rerun does not reopen ignored review rows.
- New status artifact command for declared sources (`programas_partidos` first).
- Tracker/README updated with canonical commands and fresh KPIs.
