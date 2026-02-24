# AI-OPS-193 - Packet-fix to ready-cycle bridge (`fix queue -> ready subset cycle`)

## Objective
Close the operational gap between packet remediation diagnostics and incremental loading by running both steps in one deterministic command:

1. Export packet-fix queue for non-ready sources.
2. Execute ready-packets cycle only when packets are actually ready.

This keeps Scenario A moving without blind retries and without manual orchestration across separate lanes.

## What Was Delivered
- New orchestrator script: `scripts/run_sanction_procedural_official_review_packet_fix_ready_cycle.py`.
- New `just` lanes already wired:
  - `parl-run-sanction-procedural-official-review-packet-fix-ready-cycle`
  - `parl-run-sanction-procedural-official-review-packet-fix-ready-cycle-dry-run`
- Integration into `parl-sanction-data-catalog-pipeline`.
- Test coverage via `tests/test_run_sanction_procedural_official_review_packet_fix_ready_cycle.py`.

## Validation Runs

### 1. Staging packets (expected skip path)
- Command lane: `just parl-run-sanction-procedural-official-review-packet-fix-ready-cycle-dry-run`
- Scope: packets from `AI-OPS-188/latest` (`period=2026-02-12`, `year`)
- Result:
  - `fix_queue.status=degraded`
  - `fix_queue.queue_rows_total=4`
  - `fix_queue.queue_rows_by_packet_status.invalid_row=4`
  - `ready_packets_selected_total=0`
  - `ready_cycle.cycle.cycle.apply.skip_reason=no_ready_packets`

### 2. Fixture packets (expected pass path)
- Command lane: `just parl-run-sanction-procedural-official-review-packet-fix-ready-cycle-dry-run`
- Scope: ready fixture packets from `AI-OPS-189` (`period=2025-12-31`, `year`, strict gates enabled)
- Result:
  - `fix_queue.status=ok`
  - `fix_queue.queue_rows_total=0`
  - `ready_packets_selected_total=4`
  - `ready_cycle.cycle.raw.status=ok`
  - `ready_cycle.cycle.prepare.status=ok`
  - `ready_cycle.cycle.cycle.readiness.status=ok`
  - `ready_cycle.cycle.cycle.apply.counts.rows_ready=12` (`dry_run`)

### 3. Regression + pipeline
- `just parl-test-sanction-data-catalog`: `Ran 59`, `OK`.
- `just parl-sanction-data-catalog-pipeline`: `PASS` with new lane included.

## Outcome
Scenario A now has a single reproducible bridge from packet remediation backlog to actionable incremental load:

- If packets are not ready, the command exits with explicit diagnostics and skip reason.
- If packets are ready, the command advances automatically through the strict ready-cycle path.

## Evidence
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_20260224T122017Z.json`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_fix_queue_20260224T122017Z.json`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_progress_20260224T122017Z.json`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_ready_cycle_20260224T122017Z.json`
- `docs/etl/sprints/AI-OPS-193/exports/sanction_procedural_official_review_packet_fix_queue_20260224T122017Z.csv`
- `docs/etl/sprints/AI-OPS-193/evidence/just_parl_run_sanction_procedural_official_review_packet_fix_ready_cycle_dry_run_20260224T122017Z.txt`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_fixture_20260224T122029Z.json`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_fix_queue_fixture_20260224T122029Z.json`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_progress_fixture_20260224T122029Z.json`
- `docs/etl/sprints/AI-OPS-193/evidence/sanction_procedural_official_review_packet_fix_ready_cycle_ready_cycle_fixture_20260224T122029Z.json`
- `docs/etl/sprints/AI-OPS-193/exports/sanction_procedural_official_review_packet_fix_queue_fixture_20260224T122029Z.csv`
- `docs/etl/sprints/AI-OPS-193/evidence/just_parl_run_sanction_procedural_official_review_packet_fix_ready_cycle_dry_run_fixture_20260224T122029Z.txt`
- `docs/etl/sprints/AI-OPS-193/evidence/just_parl_test_sanction_data_catalog_20260224T122034Z.txt`
- `docs/etl/sprints/AI-OPS-193/evidence/just_parl_sanction_data_catalog_pipeline_20260224T122047Z.txt`
