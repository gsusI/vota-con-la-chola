# TODO Index

Purpose:
- Single entrypoint for open work without duplicating backlog content.

Canonical sources (source of truth):
- Operational backlog (rows `TODO/PARTIAL/DONE`): `docs/etl/e2e-scrape-load-tracker.md`
- Near-term execution checklist: `docs/roadmap-tecnico.md` (section `TODO operativo: convergencia a ingesta real robusta`)
- Public-data access blockers: `docs/etl/name-and-shame-access-blockers.md`

Rules:
- Update connector status only in `docs/etl/e2e-scrape-load-tracker.md`.
- Update execution checklists only in `docs/roadmap-tecnico.md`.
- Register access obstructions only in `docs/etl/name-and-shame-access-blockers.md`.
- Other TODO-like docs must be pointers to this index (no duplicated roadmaps/backlogs).

Quick checks:
- `just etl-tracker-status`
- `just etl-tracker-gate`
