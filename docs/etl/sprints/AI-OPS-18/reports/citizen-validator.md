# Citizen Snapshot Validator

Sprint: `AI-OPS-18`  
Date: `2026-02-17`

## Purpose
Prevent accidental regressions in the citizen snapshot (`citizen.json`):
- missing keys / type drift
- broken references (topic_id/party_id)
- exploding file size

## Command
```bash
python3 scripts/validate_citizen_snapshot.py \
  --path docs/gh-pages/citizen/data/citizen.json \
  --max-bytes 5000000 \
  --strict-grid
```

## PASS/FAIL Rules
- PASS if:
  - JSON parses
  - required top-level keys exist: `meta, topics, parties, party_topic_positions, concerns`
  - `topic_id` and `party_id` sets are unique
  - every `party_topic_positions[*].topic_id/party_id` references existing ids
  - snapshot is `<= max-bytes`
  - (with `--strict-grid`) `len(party_topic_positions) == len(topics) * len(parties)`
- FAIL otherwise (exit code `2`).

## Output
Validator prints a compact JSON KPI line (counts + stance distribution) to stdout for easy logging.
