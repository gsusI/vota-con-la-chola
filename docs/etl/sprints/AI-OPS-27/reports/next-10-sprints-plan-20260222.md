# Next 10 Sprints Plan (AI-OPS-27 .. AI-OPS-36)

Date:
- 2026-02-22

Planning rules applied:
- `>=70%` controllable work, `<=30%` external-unblock probes.
- Every sprint must ship one visible delta under repo control.
- Blocked probes only when there is a new lever or one bounded retry per sprint.

Current baseline:
- Senate initiative docs: `8154/8273` (`98.56%`), remaining `119` hard `HTTP 500` XML URLs.
- Linked-to-votes initiative-doc objective: `647/647` (`100%`).
- Queue helper shipped in this sprint: `scripts/export_pdf_analysis_queue.py` (sample output: `docs/etl/sprints/AI-OPS-27/exports/senado_pdf_analysis_queue_sample_20260222.csv`).
- Excerpt backfill shipped in this sprint: `scripts/backfill_initiative_doc_excerpts.py` (KPI delta: `missing_excerpt 4996 -> 0` on `parl_initiative_docs`).

## Should we download more data?
- Yes, but targeted by leverage:
  1. Keep periodic bounded retries for the `119` Senate `500` URLs.
  2. Expand to high-value uncovered sources in tracker (`PARTIAL`/`TODO`) with strong downstream user impact.
  3. Prioritize data that improves citizen-facing evidence completeness over raw volume.

## Should we use subagents for PDF/other-source analysis?
- Yes, with strict role boundaries:
  - `L2` builds deterministic extraction/validation code.
  - `L1` runs batch extraction queues, evidence packets, and QA checks.
  - `L3` arbitrates ambiguous semantics and acceptance gates.
- Use subagents for repetitive PDF text extraction, citation linking, and queue triage; do not delegate policy/arbitration logic to `L1`.

## Sprint sequence

### AI-OPS-27 (2026-02-22 -> 2026-02-28)
Primary (controllable):
- Freeze Senate tail status with reproducible evidence + periodic retry runbook + blocker packet.
Visible delta:
- Tracker/blocker/docs aligned to `8154/8273` and live retry artifacts under sprint folder.
Unblock lane:
- One bounded strict retry on remaining `119`.

### AI-OPS-28 (2026-03-01 -> 2026-03-07)
Primary (controllable):
- Build `pdf_text_extraction_queue` pipeline for `text_documents` (PDF/HTML) with checksum-based idempotence.
Visible delta:
- New queue artifact + extraction KPIs + tests.
Unblock lane:
- Validate one external PDF parser fallback if primary extractor fails on >5% sample.

### AI-OPS-29 (2026-03-08 -> 2026-03-14)
Primary (controllable):
- Subagent throughput lane for PDF/HTML evidence extraction at scale (`L1` batch runs, `L2` fixes).
Visible delta:
- Measurable increase in `declared_evidence_with_text_excerpt_pct` and explorer drill-down coverage.
Unblock lane:
- One bounded probe for blocked Senate XML endpoints.

### AI-OPS-30 (2026-03-15 -> 2026-03-21)
Primary (controllable):
- Initiative-document semantic enrichment (`what was voted`) from extracted text into structured fields.
Visible delta:
- New normalized fields/table + Explorer relation for initiative->evidence summary.
Unblock lane:
- One archive/repo discovery sweep for missing Senate docs.

### AI-OPS-31 (2026-03-22 -> 2026-03-28)
Primary (controllable):
- Programas/declared-evidence expansion and review-queue burn-down with MTurk/internal loop.
Visible delta:
- Reduced pending review queue + increased declared signal coverage.
Unblock lane:
- One bounded probe for Galicia/Navarra blockers with fresh evidence.

### AI-OPS-32 (2026-03-29 -> 2026-04-04)
Primary (controllable):
- Citizen UI evidence quality upgrade: stronger citations, unknown/no-signal handling, per-topic confidence chips.
Visible delta:
- GH Pages update with new evidence UX and snapshot validation pass.
Unblock lane:
- One bounded probe for AEMET/BdE connector blockers.

### AI-OPS-33 (2026-04-05 -> 2026-04-11)
Primary (controllable):
- EU roll-call MVP ingest (small but real slice) + person/entity linking contract.
Visible delta:
- New source rows + published KPI panel for EU coverage.
Unblock lane:
- One bounded source contract check for EUR-Lex/TED feasibility.

### AI-OPS-34 (2026-04-12 -> 2026-04-18)
Primary (controllable):
- Recommendation engine reliability v1 (confidence-aware scoring with explicit uncertainty).
Visible delta:
- API/CLI output includes confidence intervals and evidence counts by topic.
Unblock lane:
- One bounded calibration pass against newly ingested EU/initiative evidence.

### AI-OPS-35 (2026-04-19 -> 2026-04-25)
Primary (controllable):
- HF publication hardening + reproducibility checks (manifest parity, checksums, sensitivity guardrails).
Visible delta:
- Green dry-run + publish run with updated integrity report in repo.
Unblock lane:
- One bounded external mirror check for large artifacts.

### AI-OPS-36 (2026-04-26 -> 2026-05-02)
Primary (controllable):
- Close-loop sprint: tracker reconciliation, blocker reclassification, and citizen-facing changelog summarizing 10-sprint deltas.
Visible delta:
- Strict tracker gate pass + public changelog artifact with KPI deltas.
Unblock lane:
- Final bounded retry for persistent Senate tail; resolve or keep OPEN with current evidence.

## Subagent operating contract (for these 10 sprints)
- `L3 Orchestrator`: acceptance criteria, arbitration, method changes.
- `L2 Specialist Builder`: extraction/parsing code, schema additions, tests, CLI wiring.
- `L1 Mechanical Executor`: queue runs, artifact generation, parity checks, evidence packets, tracker transcriptions.

## Immediate next command block
```bash
# status baseline
sqlite3 etl/data/staging/politicos-es.db "WITH t AS (SELECT COUNT(*) total FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id WHERE i.source_id='senado_iniciativas'), d AS (SELECT COUNT(*) done FROM parl_initiative_documents pid JOIN parl_initiatives i ON i.initiative_id=pid.initiative_id LEFT JOIN text_documents td ON td.source_record_pk=pid.source_record_pk AND td.source_id='parl_initiative_docs' WHERE i.source_id='senado_iniciativas' AND td.source_record_pk IS NOT NULL) SELECT t.total,d.done,(t.total-d.done),printf('%.2f',100.0*d.done/t.total) FROM t,d;"

# bounded retry (single probe per sprint when no new lever)
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --include-unlinked \
  --retry-forbidden \
  --limit-initiatives 240 \
  --max-docs-per-initiative 1 \
  --timeout 10
```
