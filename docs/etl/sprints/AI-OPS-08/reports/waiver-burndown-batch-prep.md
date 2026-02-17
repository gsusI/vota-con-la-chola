# AI-OPS-08 waiver burn-down + tracker-contract batch prep report

## Snapshot
- Timestamp UTC: 2026-02-16T21:13:50Z
- Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`
- DB: `etl/data/staging/politicos-es.db`
- Inputs used: `just etl-tracker-status`, `python3 scripts/e2e_tracker_status.py`, `docs/etl/e2e-scrape-load-tracker.md`, `docs/etl/mismatch-waivers.json`

## Commands executed
1. `just etl-tracker-status`
2. `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-mismatch --fail-on-done-zero-real`
3. `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real`

## Generated artifacts
- `docs/etl/sprints/AI-OPS-08/exports/waiver_burndown_candidates.csv`
- `docs/etl/sprints/AI-OPS-08/exports/tracker_contract_candidates.csv`
- `docs/etl/sprints/AI-OPS-08/evidence/waiver-burndown-generation.log`
- `docs/etl/sprints/AI-OPS-08/evidence/tracker-contract-candidates-generation.log`

## Candidate counts
- total waiver burndown candidates: 2
- unresolved waiver burndown rows: 0
- total tracker-contract rows: 2
- unresolved tracker-contract rows: 0

## Escalation check
- A row is marked `UNRESOLVED` only when evidence command output is missing.
- Unresolved waiver rows: none
- Unresolved tracker rows: none
- Apply-set policy: only deterministic non-UNRESOLVED rows are eligible.

## Output validation commands
```bash
test -f docs/etl/sprints/AI-OPS-08/exports/waiver_burndown_candidates.csv
test -f docs/etl/sprints/AI-OPS-08/exports/tracker_contract_candidates.csv
rg -n "waiver_expires_on|recommendation|mapped_source_id|expected_status" docs/etl/sprints/AI-OPS-08/exports/*.csv
```
