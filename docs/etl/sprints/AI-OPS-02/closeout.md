# Sprint AI-OPS-02 Closeout

Fecha de cierre: 2026-02-16
Repositorio: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Decision

**PASS**

Motivo: los 5 gates definidos para AI-OPS-02 pasan con evidencia reproducible por comando.

## Gate checks (evidencia)

| Gate | Comando | Salida observada | Estado |
| --- | --- | --- | --- |
| 1) `PRAGMA foreign_key_check` returns 0 rows | `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"` | `0` | PASS |
| 2) `topic_evidence_reviews pending == 0` | `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS pending_reviews FROM topic_evidence_reviews WHERE status='pending';"` | `0` | PASS |
| 3) Declared signal KPI improved vs baseline | Baseline evidence: `rg -n "614\|194\|0.315960912052117\|614\|199\|0.324104234527687\|Delta KPI" docs/etl/sprints/AI-OPS-02/reports/signal-uplift.md` | Baseline line: `614\|194\|0.315960912052117`; after line: `614\|199\|0.324104234527687` | PASS |
| 4) Coherence overlap > 0 and drill-down works | `python3` calling `build_topics_coherence_payload(...)` and `build_topics_coherence_evidence_payload(bucket='incoherent', ...)` | `overlap_total=153`, `explicit_total=98`, `coherent_total=51`, `incoherent_total=47`, `drilldown_rows=5`, `drilldown_pairs_total=47`, `drilldown_evidence_total=1694` | PASS |
| 5) Analytics PARTIAL rows reconciled in tracker | `rg -n "Intervenciones Congreso\|Posiciones por tema \(politico x scope\)\|evidence-ai-ops-02-analytics-partials.md" docs/etl/e2e-scrape-load-tracker.md` | Ambas filas PARTIAL contienen evidencia reproducible, bloqueador explícito y siguiente comando, referenciando `docs/etl/sprints/AI-OPS-02/evidence/analytics-partials.md` | PASS |

## Supporting artifacts produced in AI-OPS-02

- `docs/etl/sprints/AI-OPS-02/kickoff.md`
- `docs/etl/sprints/AI-OPS-02/reports/coherence-backend.md`
- `docs/etl/sprints/AI-OPS-02/reports/coherence-ui.md`
- `docs/etl/sprints/AI-OPS-02/reports/signal-uplift.md`
- `docs/etl/sprints/AI-OPS-02/reports/mturk-apply.md`
- `docs/etl/sprints/AI-OPS-02/evidence/analytics-partials.md`

## Open AI-OPS-03 scope (one source family only)

Chosen source family: **`congreso_intervenciones`**

Scope rule:
- No expansion to new families (BOE/PLACSP/BDNS) during AI-OPS-03.
- Focus only on declared signal quality, review-loop throughput, and publish visibility for `congreso_intervenciones`.

Proposed AI-OPS-03 objective:
- Raise useful declared signal in high-stakes/latest slices while preserving auditability and `pending=0`.

Initial AI-OPS-03 backlog (carryover from PARTIAL analytics rows):
- Increase `topic_evidence_declared_with_signal` coverage beyond current `199/614` without adding false positives.
- Align `as_of_date` consistency across topic sets in analytics snapshots.
- Refresh published dashboard snapshot so coherence and declared metrics match live DB outputs.

Owners:
- `L3 Orchestrator`: acceptance gates and arbitration on KPI/quality tradeoffs.
- `L2 Specialist Builder`: extractor + recompute + publish pipeline updates.
- `L1 Mechanical Executor`: MTurk batch prep/apply loop under current review protocol.
