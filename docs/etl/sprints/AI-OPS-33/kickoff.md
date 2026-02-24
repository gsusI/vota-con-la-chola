# AI-OPS-33 Kickoff

Date:
- 2026-02-22

Objective:
- Make citizen snapshot quality semantics explicit and machine-validated so users can distinguish clear signal vs unknown and confidence tiers without ambiguity.

Why now:
- The citizen surface already exposes positions, but quality semantics (`unknown`, confidence level, clear coverage) were implicit.
- We need a bounded static contract for GH Pages and a validator guardrail to keep future snapshots consistent.

Primary lane (controllable):
- Extend `export_citizen_snapshot.py` with `meta.quality`, enforce contract checks in `validate_citizen_snapshot.py`, and render the semantics in `ui/citizen/index.html`.

Acceptance gates:
- Exported snapshot includes stable `meta.quality` fields and confidence thresholds.
- Validator enforces `meta.quality` consistency and bounds.
- Citizen UI shows explicit `unknown` and confidence-tier semantics in cards/status.
- GH Pages build + strict validation pass for `citizen.json`, `citizen_declared.json`, and `citizen_votes.json`.
