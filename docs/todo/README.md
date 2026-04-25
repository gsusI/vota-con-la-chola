# TODO Index

Purpose:
- Single entrypoint for open work without duplicating backlog content or future-planning scope.

Canonical sources (source of truth):
- Future direction and sequencing: `ROADMAP.md`
- Operational backlog (rows `TODO/PARTIAL/DONE`): `docs/etl/e2e-scrape-load-tracker.md`
- Near-term technical execution derived from the roadmap: `docs/roadmap-tecnico.md`
- Public-data access blockers: `docs/etl/name-and-shame-access-blockers.md`

Rules:
- Update future direction only in `ROADMAP.md`.
- Update connector status only in `docs/etl/e2e-scrape-load-tracker.md`.
- Update execution checklists only in `docs/roadmap-tecnico.md`, and only for scope that already exists in `ROADMAP.md`.
- Register access obstructions only in `docs/etl/name-and-shame-access-blockers.md`.
- Other TODO-like docs must be pointers to this index (no duplicated roadmaps/backlogs).

Quick checks:
- `just etl-tracker-status`
- `just etl-tracker-gate`
