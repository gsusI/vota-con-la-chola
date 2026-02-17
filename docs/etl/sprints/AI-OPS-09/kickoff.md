# AI-OPS-09 Kickoff

Date: 2026-02-17  
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`

## Sprint Focus

Money/outcomes source expansion with deterministic tracker contract and strict-gate safety for LONG_10X execution.

## Objective

Freeze scope, must-pass gates, escalation rules, and queue order before implementation starts.

## Inputs Reviewed

- `docs/roadmap.md`
- `docs/roadmap-tecnico.md`
- `docs/etl/e2e-scrape-load-tracker.md`
- `docs/gh-pages/explorer-sources/data/status.json`
- `docs/etl/sprints/AI-OPS-08/closeout.md`
- `sqlite3 etl/data/staging/politicos-es.db`

## Baseline Commands (Exact Outputs)

### 1) Tracker baseline

Command:
```bash
tmp=$(mktemp); python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json > "$tmp"; s=$?; tail -n 8 "$tmp"; echo tracker_status_exit=$s; rm -f "$tmp"
```

Output:
```text
tracker_sources: 28
sources_in_db: 33
mismatches: 0
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
tracker_status_exit=0
```

### 2) Strict gate baseline

Command:
```bash
tmp=$(mktemp); python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --waivers docs/etl/mismatch-waivers.json --as-of-date 2026-02-16 --fail-on-mismatch --fail-on-done-zero-real > "$tmp"; s=$?; tail -n 8 "$tmp"; echo strict_exit=$s; rm -f "$tmp"
```

Output:
```text
tracker_sources: 28
sources_in_db: 33
mismatches: 0
waived_mismatches: 0
waivers_active: 0
waivers_expired: 0
done_zero_real: 0
strict_exit=0
```

### 3) Integrity + queue + impact baseline (DB)

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT 'fk_violations' AS metric, COUNT(*) AS value FROM pragma_foreign_key_check UNION ALL SELECT 'topic_evidence_reviews_pending', COUNT(*) FROM topic_evidence_reviews WHERE lower(status)='pending' UNION ALL SELECT 'indicator_series_total', COUNT(*) FROM indicator_series UNION ALL SELECT 'indicator_points_total', COUNT(*) FROM indicator_points UNION ALL SELECT 'policy_events_moncloa', COUNT(*) FROM policy_events WHERE source_id LIKE 'moncloa_%' UNION ALL SELECT 'policy_events_boe', COUNT(*) FROM policy_events WHERE source_id LIKE 'boe_%';"
```

Output:
```text
metric                          value
------------------------------  -----
fk_violations                   0
topic_evidence_reviews_pending  0
indicator_series_total          0
indicator_points_total          0
policy_events_moncloa           28
policy_events_boe               298
```

### 4) Published status snapshot baseline

Command:
```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
tr=(obj.get('summary') or {}).get('tracker') or {}
imp=(obj.get('analytics') or {}).get('impact') or {}
for k,v in [
    ('tracker_items_total',tr.get('items_total')),
    ('tracker_done',tr.get('done')),
    ('tracker_partial',tr.get('partial')),
    ('tracker_todo',tr.get('todo')),
    ('tracker_unmapped',tr.get('unmapped')),
    ('indicator_series_total_status',imp.get('indicator_series_total')),
    ('indicator_points_total_status',imp.get('indicator_points_total')),
]:
    print(f"{k}={v}")
PY
```

Output:
```text
tracker_items_total=46
tracker_done=27
tracker_partial=3
tracker_todo=16
tracker_unmapped=20
indicator_series_total_status=0
indicator_points_total_status=0
```

### 5) Target tracker rows confirmation (PLACSP, BDNS, Eurostat, Banco de Espana, AEMET)

Command:
```bash
rg -n -i "placsp|bdns|eurostat|banco de espa|banco de españa|aemet" docs/etl/e2e-scrape-load-tracker.md
```

Output:
```text
56:| Contratación autonómica (piloto 3 CCAA) | Dinero | PLACSP (filtrado por órganos autonómicos) | TODO | Falta estrategia reproducible: ingesta incremental + agregación CPV/órgano/importe; no intentar “leerlo todo” |
57:| Subvenciones autonómicas (piloto 3 CCAA) | Dinero | BDNS/SNPSAP (filtrado por órgano convocante/territorio) | TODO | Falta ingesta y normalización; entity resolution de beneficiario cuando no haya ID estable |
63:| Contratacion publica (Espana) | Dinero | PLACSP: sindicación/ATOM (CODICE) | TODO | Falta ingesta y modelo de licitacion/adjudicacion; KPI: cobertura + trazabilidad por expediente |
64:| Subvenciones y ayudas (Espana) | Dinero | BDNS/SNPSAP: API | TODO | Falta ingesta y modelo de convocatorias/concesiones; KPI: % con importe, organo y beneficiario |
65:| Indicadores (outcomes): Eurostat | Outcomes | Eurostat (API/SDMX) | TODO | Falta conector SDMX/JSON; normalizar dimensiones/codelists y documentar mapeos semánticos |
66:| Indicadores (confusores): Banco de España | Outcomes | Banco de España (API series) | TODO | Falta conector; normalizar códigos y unidades; versionar definiciones por snapshot |
67:| Indicadores (confusores): AEMET | Outcomes | AEMET OpenData | TODO | Falta conector; mapeo geográfico estación->territorio; cambios de cobertura/metodología |
```

### 6) Current source registration baseline for target families

Command:
```bash
sqlite3 -header -column etl/data/staging/politicos-es.db "SELECT COUNT(*) AS target_sources_present FROM sources WHERE lower(source_id) LIKE 'placsp%' OR lower(source_id) LIKE 'bdns%' OR lower(source_id) LIKE 'eurostat%' OR lower(source_id) LIKE 'bde%' OR lower(source_id) LIKE 'aemet%';"
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
keys=('placsp','bdns','eurostat','bde','aemet','banco')
rows=[s for s in obj.get('sources',[]) if any(k in (s.get('source_id') or '').lower() or k in (s.get('name') or '').lower() for k in keys)]
print('target_sources_in_status', len(rows))
PY
```

Output:
```text
target_sources_present
----------------------
0

target_sources_in_status 0
```

## Must-Pass Gates (Frozen)

| Gate | Condition | Closeout evidence command | PASS threshold |
|---|---|---|---|
| G1 Data integrity | `fk_violations=0` | `sqlite3 ... "SELECT COUNT(*) FROM pragma_foreign_key_check;"` | Exactly `0` |
| G2 Queue health | `topic_evidence_reviews_pending=0` | `sqlite3 ... "SELECT COUNT(*) FROM topic_evidence_reviews WHERE lower(status)='pending';"` | Exactly `0` |
| G3 Strict tracker policy | `mismatches=0`, `waivers_expired=0`, `done_zero_real=0` | `python3 scripts/e2e_tracker_status.py ... --fail-on-mismatch --fail-on-done-zero-real` | Exit `0` and all counters `0` |
| G4 Target row reconciliation | 7 target rows (lines 56-57, 63-67) updated with reproducible evidence state | `rg -n -i "placsp|bdns|eurostat|banco de espa|aemet" docs/etl/e2e-scrape-load-tracker.md` | No stale text; each row has concrete blocker+next command or DONE evidence |
| G5 Money ingestion baseline delivered | PLACSP + BDNS have reproducible non-zero ingest in at least one mode each | `sqlite3 ... "SELECT source_id, records_loaded FROM ingestion_runs WHERE source_id LIKE 'placsp_%' OR source_id LIKE 'bdns_%' ORDER BY run_id DESC LIMIT 20;"` | At least one `records_loaded > 0` per family |
| G6 Outcomes ingestion baseline delivered | Eurostat + BDE + AEMET feed indicator layer | `sqlite3 ... "SELECT COUNT(*) FROM indicator_series;"` and `sqlite3 ... "SELECT COUNT(*) FROM indicator_points;"` | `indicator_series_total > 0` and `indicator_points_total > 0` |
| G7 Publish parity | Explorer snapshot reflects live DB for target source families and impact counts | `python3 scripts/export_explorer_sources_snapshot.py ...` + JSON probe | Payload values equal DB values for audited fields |
| G8 Workload balance | L1 owns majority throughput evidence packets | `test -f docs/etl/sprints/AI-OPS-09/reports/*.md` + evidence files | L1 throughput artifacts are majority of execution packets |

## Escalation Rules (Blocked Upstream Contracts)

1. If upstream is blocked (`403/429`, WAF challenge, auth break, schema/contract drift), do not mark tracker row `DONE`.
2. Keep ingest non-fatal: persist run metadata and explicit failure reason/signature in sprint report.
3. Mark row `PARTIAL` with exactly one blocker and one reproducible next command.
4. Temporary waiver is allowed only with explicit owner and expiry date; expired waiver is gate-failing.
5. If a blocker affects existing `DONE` rows or risks `DONE_ZERO_REAL`, escalate to L3 before merge.

## Ordered Execution Queue (Frozen)

1. P1 (HI, L3): Kickoff lock (this artifact), baseline capture, gates freeze.
2. P2 (HI, L2): Contract/setup wave: source config, deterministic IDs, parser scaffolding, tests skeletons for PLACSP/BDNS/Eurostat/BDE/AEMET.
3. P3 (FAST, L1): PLACSP throughput wave: ingest replay, idempotence checks, evidence packet.
4. P4 (FAST, L1): BDNS throughput wave: ingest replay, idempotence checks, evidence packet.
5. P5 (FAST, L1): Outcomes throughput wave: Eurostat then BDE then AEMET ingest + indicator backfill + evidence packet.
6. P6 (HI, L2): Reconciliation wave: tracker wording alignment, status export parity, strict-gate hardening adjustments if needed.
7. P7 (HI, L3): Closeout wave: evaluate G1..G8 and publish PASS/FAIL with carryover (owner + first command) for any red gate.

## Artifact

- `docs/etl/sprints/AI-OPS-09/kickoff.md`
