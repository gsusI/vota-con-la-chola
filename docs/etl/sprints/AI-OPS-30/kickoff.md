# AI-OPS-30 Kickoff

Date:
- 2026-02-22

Objective:
- Add fail-fast manifest validation for `programas_partidos` and enforce it in the canonical programas pipeline.

Why now:
- Programas workflow was stable after AI-OPS-29 but still accepted malformed manifests.
- Need deterministic preflight guard before ingest/backfill.

Primary lane (controllable):
- New validator script + tests + `just` preflight integration + evidence.

Acceptance gates:
- `scripts/validate_programas_manifest.py` shipped with row/column/key/path checks.
- Unit tests cover valid and invalid manifests.
- `parl-programas-pipeline` executes validator first.
- Real run on sample manifest produces valid preflight artifact and keeps queue stable (`review_pending=0`).
