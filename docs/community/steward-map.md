# Steward map

Verified GitHub handles on `2026-05-11`:

- `@gsusI`: repository collaborator with admin, maintain, and push permissions.
- `@codex`: automation contributor visible in repository contributors; no maintainer authority.

| Area | Steward | Scope |
|---|---|---|
| Project | `@gsusI` | roadmap, scope, public claims |
| Data | `@gsusI` | source quality, tracker truth, blocker taxonomy |
| Infrastructure | `@gsusI` | CI, Docker, Just, publish pipelines |
| Community intake | `@gsusI` | issue triage, labels, milestone ownership until more maintainers exist |

Rotation rule:

- the reviewer who approves a new source becomes steward for that source until the next published snapshot;
- sensitive schema, legal, security, or public-contract changes need two core approvals once more maintainers exist;
- if a source PR is blocked more than five days, mark `status:blocked` and escalate to Project Steward.

Source stewardship minimum:

- source has issue,
- source has docs entry,
- gate result is recorded,
- blocker/legal notes are explicit,
- public catalog state is not misleading.

GitHub routing:

- milestone: `H2 - plataforma contributiva`;
- source work labels: `area:etl`, `type:data-source`, `status:needs-repro`;
- blocked source labels: add `status:blocked`;
- maintainer-decision labels: add `status:needs-maintainer`;
- docs-only labels: `area:docs`;
- governance/process labels: `area:governance`.
