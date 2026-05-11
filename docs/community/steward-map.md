# Steward map

Current GitHub handle:

| Area | Steward | Scope |
|---|---|---|
| Project | `@gsusI` | roadmap, scope, public claims |
| Data | `@gsusI` | source quality, tracker truth, blocker taxonomy |
| Infrastructure | `@gsusI` | CI, Docker, Just, publish pipelines |

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
