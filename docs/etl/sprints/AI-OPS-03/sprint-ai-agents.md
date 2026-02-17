# Sprint AI-OPS-03 Prompt Pack

Output contract for this sprint:
- format is a numbered list of prompts,
- each prompt explicitly states the executing agent,
- each prompt is self-contained,
- execution evidence must be written to markdown artifacts in this repo.

Repository root for all prompts:
- `REPO_ROOT/vota-con-la-chola`

## Overall project context (why this sprint)

This sprint is a thin vertical slice in service of the full roadmap (`docs/roadmap.md`, `docs/roadmap-tecnico.md`):
- strengthens the says-vs-does reliability layer needed before recommendation credibility,
- keeps architecture KISS (single SQLite, additive changes, reproducible snapshots),
- closes quality/publish drift so dashboards reflect real state.

Scope constraint from AI-OPS-02 closeout:
- only source family `congreso_intervenciones`.
- do not open BOE/PLACSP/BDNS or new connector families in this sprint.

Sprint objective:
- move `congreso_intervenciones` and related topic-position analytics from operational PARTIAL toward DONE quality gates, without violating reproducibility/auditability.

Sprint budget (points):
- total: 32 pts
- L3: 4 pts
- L2: 18 pts
- L1: 10 pts

1. **Agent: L3 Orchestrator (2 pts)**
```text
You are the L3 Orchestrator for sprint AI-OPS-03.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Freeze a baseline tied to overall roadmap outcomes before any implementation.

Tasks:
1) Run baseline commands:
- sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
- sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS pending_reviews FROM topic_evidence_reviews WHERE status='pending';"
- sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 15) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
- python3 - <<'PY'
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload
p=Path('etl/data/staging/politicos-es.db')
s=build_topics_coherence_payload(p, limit=5, offset=0).get('summary', {})
print(s)
PY
2) Read and align with:
- docs/roadmap.md
- docs/roadmap-tecnico.md
- docs/etl/e2e-scrape-load-tracker.md
- docs/etl/sprints/AI-OPS-02/closeout.md
3) Write kickoff file:
- docs/etl/sprints/AI-OPS-03/kickoff.md

Output contract:
- kickoff includes baseline values, sprint objective, ordered execution, and gates mapped to roadmap phases.

Acceptance check:
- kickoff file exists and contains exact command outputs.
```

2. **Agent: L2 Specialist Builder (5 pts)**
```text
You are an L2 Specialist Builder.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Eliminate as_of_date drift in topic analytics/positions for congreso_intervenciones workflows.

Tasks:
1) Identify where as_of_date divergence is introduced across:
- backfill-topic-analytics
- backfill-declared-positions
- backfill-combined-positions
- explorer-sources status export
2) Implement minimal, KISS-safe fix to keep a single explicit as_of_date across this sprint pipeline.
3) Add or update tests for as_of consistency in affected path(s).
4) Document behavior and runbook in:
- docs/etl/sprints/AI-OPS-03/reports/asof-alignment.md

Output contract:
- code/test changes merged in working tree,
- doc with reproducible commands proving alignment.

Acceptance check:
- no mixed as_of_date between the relevant topic sets for the same sprint run.
```

3. **Agent: L2 Specialist Builder (8 pts)**
```text
You are an L2 Specialist Builder.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Improve declared stance signal quality for congreso_intervenciones without increasing false positives.

Tasks:
1) Refine extraction in:
- etl/parlamentario_es/declared_stance.py
2) Add regression tests for both:
- known false negatives (recover signal)
- known false positives (must remain blocked)
3) Recompute end-to-end for one snapshot:
- just parl-backfill-text-documents
- just parl-backfill-declared-stance
- just parl-backfill-declared-positions
- just parl-backfill-combined-positions
4) Write KPI report:
- docs/etl/sprints/AI-OPS-03/reports/signal-uplift.md

Output contract:
- updated extractor and tests,
- before/after metrics for declared signal,
- explicit statement of precision risk controls.

Acceptance check:
- declared_signal_pct strictly improves vs kickoff baseline,
- tests pass,
- review queue pending remains 0.
```

4. **Agent: L1 Mechanical Executor (3 pts)**
```text
You are an L1 Mechanical Executor. Use the $mturk-review-loop skill.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Prepare targeted MTurk batches for unresolved high-value declared evidence in congreso_intervenciones.

Tasks:
1) Select up to 120 rows prioritized by:
- high-stakes topics first,
- low_confidence/conflicting_signal/no_signal hotspots.
2) Create batches under:
- etl/data/raw/manual/mturk_reviews/mturk-YYYYMMDD-congreso-bxx/
3) Generate tasks_input.csv with required schema.
4) Validate no duplicate evidence_id across new batches.
5) Write report:
- docs/etl/sprints/AI-OPS-03/reports/mturk-batch-prep.md

Output contract:
- prepared batch folders,
- validation evidence in markdown report.

Acceptance check:
- schema valid,
- duplicate evidence_id count is zero in new batch set.
```

5. **Agent: L1 Mechanical Executor (3 pts)**
```text
You are an L1 Mechanical Executor. Use the $mturk-review-loop skill.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Apply adjudicated MTurk exports and keep queue health stable.

Tasks:
1) Validate and apply each completed batch via review-decision.
2) Use canonical note format:
- "mturk batch <batch_id>: ..."
3) Recompute declared and combined positions after apply.
4) Write apply report:
- docs/etl/sprints/AI-OPS-03/reports/mturk-apply.md

Output contract:
- per-batch applied/skipped/failed outcomes,
- post-apply queue metrics,
- mturk note coverage summary.

Acceptance check:
- topic_evidence_reviews pending = 0,
- failed batches explicitly listed.
```

6. **Agent: L2 Specialist Builder (5 pts)**
```text
You are an L2 Specialist Builder.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Refresh dashboard publication so static explorer-sources matches live DB for AI-OPS-03 metrics.

Tasks:
1) Export/refresh explorer-sources snapshot artifacts used by GH pages.
2) Verify parity between live DB and exported status for:
- topic_evidence_declared_with_signal
- topic_evidence_declared_with_signal_pct
- coherence overlap/explicit/coherent/incoherent
3) If parity fails, fix export path/code with minimal changes.
4) Write report:
- docs/etl/sprints/AI-OPS-03/reports/dashboard-refresh.md

Output contract:
- refreshed snapshot file(s),
- parity check commands + values.

Acceptance check:
- exported dashboard metrics equal live DB metrics for the audited fields.
```

7. **Agent: L1 Mechanical Executor (2 pts)**
```text
You are an L1 Mechanical Executor.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Produce a reproducible evidence packet for analytics PARTIAL rows tied to this sprint.

Targets:
- Intervenciones Congreso
- Posiciones por tema (politico x scope)

Tasks:
1) Run SQL/CLI proof commands from the sprint reports.
2) Capture exact outputs.
3) Write:
- docs/etl/sprints/AI-OPS-03/evidence/analytics-partials.md

Output contract:
- markdown packet with replayable commands and observed values.

Acceptance check:
- another agent can replay and verify the same conclusions.
```

8. **Agent: L2 Specialist Builder (2 pts)**
```text
You are an L2 Specialist Builder.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Reconcile tracker status text and roadmap visibility for the two analytics PARTIAL rows.

Inputs:
- docs/etl/sprints/AI-OPS-03/evidence/analytics-partials.md
- docs/etl/e2e-scrape-load-tracker.md
- docs/roadmap-tecnico.md

Tasks:
1) Update tracker row text for both analytics PARTIAL rows.
2) Mark DONE only if DoD evidence is complete; otherwise keep PARTIAL with one blocker + one next command.
3) Ensure wording reflects contribution to roadmap phase progression (no duplicated roadmap prose).

Output contract:
- tracker rows updated with concrete evidence references.

Acceptance check:
- row text points to exact artifact/command outputs and is consistent with current state.
```

9. **Agent: L3 Orchestrator (2 pts)**
```text
You are the L3 Orchestrator.

Repository:
REPO_ROOT/vota-con-la-chola

Objective:
Run sprint closeout and decide PASS/FAIL for AI-OPS-03 with project-level framing.

Gate checks:
1) PRAGMA foreign_key_check returns 0 rows.
2) topic_evidence_reviews pending == 0.
3) declared signal KPI improved vs AI-OPS-03 kickoff baseline.
4) coherence overlap > 0 and incoherent drill-down returns evidence rows.
5) tracker analytics PARTIAL rows reconciled with evidence and next-step clarity.
6) explorer-sources exported snapshot matches live DB for declared/coherence audited KPIs.

Tasks:
1) Run gate commands.
2) Write closeout file:
- docs/etl/sprints/AI-OPS-03/closeout.md
3) Record decision:
- PASS => open AI-OPS-04 with one source family aligned to roadmap critical path.
- FAIL => carryover blockers with owner (L3/L2/L1) and next command.

Output contract:
- closeout file with explicit pass/fail table, command evidence, and project-context decision.
```
