# AI-OPS-27 Sprint Prompt Pack

Objective:
- Close the Senate initiative-document tail with evidence-first blocker handling, and prepare the next 10-sprint execution runway.

References:
- `docs/etl/sprints/AI-OPS-27/reports/senado-tail-status-20260222.md`
- `docs/etl/sprints/AI-OPS-27/reports/next-10-sprints-plan-20260222.md`

## Prompts

1. Agent: L2 Specialist Builder
```text
Repo: /Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola
Objective: Keep Senate tail retries deterministic while preventing anti-loop churn.
Tasks:
- Run exactly one bounded retry probe for senado tail when no new unblock lever exists.
- Persist run artifacts under docs/etl/runs/<run_id>/ and summarize status in AI-OPS-27 reports.
- Update tracker + blockers with exact counters and evidence links.
Output contract:
- Updated docs/etl/e2e-scrape-load-tracker.md row for initiative docs.
- Updated docs/etl/name-and-shame-access-blockers.md incident row.
- New/updated report under docs/etl/sprints/AI-OPS-27/reports/.
Acceptance checks:
- SQL coverage query and linked-initiative query embedded in report.
- No fabricated DONE claims; unresolved tail stays OPEN with factual evidence.
```

2. Agent: L1 Mechanical Executor
```text
Repo: /Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola
Objective: Generate repetitive evidence packets for remaining Senate URLs.
Tasks:
- Export remaining missing URLs with status metadata.
- Produce sampled HTTP probe logs (status codes + timestamps).
- Emit concise CSV/JSON artifacts for blocker evidence.
Output contract:
- Artifacts under docs/etl/sprints/AI-OPS-27/evidence/ and exports/.
Acceptance checks:
- Deterministic command list included in report.
- Artifact paths referenced from blocker log entry.
```

3. Agent: L3 Orchestrator
```text
Repo: /Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola
Objective: Lock the next 10-sprint strategy with controllable-first policy and subagent boundaries.
Tasks:
- Finalize sprint sequence AI-OPS-27..AI-OPS-36 with explicit visible deltas.
- Enforce >=70% controllable work and <=30% unblock probes each sprint.
- Define where PDF/data-source subagents are mandatory and where they are forbidden.
Output contract:
- docs/etl/sprints/AI-OPS-27/reports/next-10-sprints-plan-20260222.md
Acceptance checks:
- Every sprint has one user-visible delta and one bounded unblock lane.
- Includes yes/no decision on "download more" and "subagents for PDFs".
```
