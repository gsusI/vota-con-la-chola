# Project Knowledge Base

Canonical agent-facing durable knowledge for this repo lives in `project_kb/`.

Use the resolver/tests instead of duplicating project lore in chat notes:

```bash
python3 <project-knowledge-base-skill>/scripts/validate_project_kb.py --target .
```

Scope:
- durable decisions
- verified facts
- gotchas
- repeatable workflows
- evidence pointers

Not scope:
- roadmap authority, which stays in `ROADMAP.md`
- operational backlog/status, which stays in `docs/etl/e2e-scrape-load-tracker.md`
- raw sprint evidence, which stays under `docs/etl/sprints/**`
