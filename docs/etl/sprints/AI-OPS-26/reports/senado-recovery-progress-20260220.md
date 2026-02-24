# Senado Initiative Docs Recovery Progress (2026-02-20)

## What changed

The Senate docs pipeline is no longer in a strictly blocked state in this environment.
Using the existing downloader with bounded retries, downloads progressed from low 403/500 windows to high-success windows.

## Commands used

- Baseline/probe (existing process only):
  - `backfill-initiative-documents --include-unlinked --retry-forbidden --limit-initiatives 20 --max-docs-per-initiative 1`
- Recovery drain mode (effective):
  - `backfill-initiative-documents --include-unlinked --retry-forbidden --limit-initiatives 40 --max-docs-per-initiative 1 --timeout 10 --sleep-seconds 0 --sleep-jitter-seconds 0`

## Outcomes

- Session net docs downloaded (Senate): `+3726` (`1998 -> 5724`).
- Senate docs coverage by doc-link rows: `5724/7905` (`72.41%`).
- Senate initiatives with downloaded docs: `2822/3607` (`78.24%`).
- Senate initiatives linked to votes with downloaded docs: `647/647` (`100%`).

## Evidence

- `docs/etl/runs/senado_stable_loop_20260220T115905Z/`
- `docs/etl/runs/senado_drain_loop_20260220T120121Z/`
- `docs/etl/runs/senado_drain_loop2_20260220T120721Z/`
- `docs/etl/runs/senado_drain_loop3_20260220T123003Z/`
- `docs/etl/runs/senado_drain_loop4_20260220T134620Z/`
- `docs/etl/runs/senado_linked_tail_20260220T135109Z/`
- `docs/etl/runs/senado_unlinked_cookie_drain8_20260220T141131Z/`
- `docs/etl/runs/senado_unlinked_skip_blocked16_20260220T142634Z/`
- `docs/etl/runs/senado_unlinked_skip_blocked17_20260220T142756Z/`
- `docs/etl/runs/senado_finish_fast_20260220T144046Z/`
- `docs/etl/runs/senado_tail_grind_20260221T075630Z/`
- `docs/etl/runs/senado_tail_daemon_20260221T080416Z/`
- `docs/etl/runs/senado_drain_loop2_20260220T120721Z/quality_post.json`
- `docs/etl/runs/senado_drain_loop2_20260220T120721Z/13_run_summary.md`

## Operational learning

- Keep retrying with bounded non-auto passes.
- For non-linked tail, prefer skip-blocked mode (no `--retry-forbidden`) so accumulated `403/404/500` pockets are bypassed.
- Use wider windows (`--limit-initiatives 2000+`) to harvest sparse fetchable pockets after head-of-queue blockers accumulate.
- Keep a long-running loop active (`scripts/senado_tail_daemon.sh`) so transient reopen windows are captured without manual intervention.
- Treat short-term zero-success loops as throttle windows, not terminal blockers.

## Update (2026-02-21)

- Root cause identified for plateau: with `--max-docs-per-initiative 1`, already-downloaded first URLs could starve missing secondary URLs per initiative.
- Fix shipped in `etl/parlamentario_es/text_documents.py` (missing-first selection before per-initiative cap).
- Post-fix bounded drain result:
  - `+873` docs in one run (`6375 -> 7248`), evidence: `docs/etl/runs/senado_postfix_bounded_20260221T093208Z/13_run_summary.md`.
- Additional bounded follow-up:
  - `+244` docs (`7248 -> 7492`), evidence: `docs/etl/runs/senado_postfix_bounded3_20260221T095449Z/13_run_summary.md`.
- Current checkpoint (same DB):
  - Senate doc-link coverage: `7492/8272` (`90.57%`).
  - By type: `bocg=3311/3969`, `ds=4181/4303`.
  - Linked-to-votes objective remains complete: `647/647` (`100%`).
