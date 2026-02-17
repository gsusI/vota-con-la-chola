# Evidence packet: analytics PARTIAL tracker rows (AI-OPS-02)

Generated on: 2026-02-16
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`
DB: `etl/data/staging/politicos-es.db`

## Target rows in `docs/etl/e2e-scrape-load-tracker.md`

```bash
DB=etl/data/staging/politicos-es.db
python3 - <<'PY'
import re
from pathlib import Path
path = Path('docs/etl/e2e-scrape-load-tracker.md')
for line in path.read_text(encoding='utf-8').splitlines():
    if re.search(r'\| Intervenciones Congreso \|', line) or re.search(r'\| Posiciones por tema \(politico x scope\) \|', line):
        print(line)
PY
```

Observed:

```text
| Intervenciones Congreso | Parlamentario | Congreso intervenciones | PARTIAL | Conector implementado (`congreso_intervenciones`) y materializa evidencia `declared:intervention` en `topic_evidence` (solo para temas presentes en `topic_set_topics` del Congreso; requiere `backfill-topic-analytics` antes). Comando recomendado (end-to-end “temas + evidencia auditable”): `just parl-temas-pipeline` (incluye `backfill-text-documents` + `backfill-declared-stance` + `backfill-declared-positions`). Estado actual: `backfill-declared-stance` usa regex v2 conservador y alimenta `topic_evidence_reviews` para casos ambiguos; `review-decision` permite cerrar el loop (`pending -> resolved/ignored`) y recomputar posiciones. Pendiente: mejorar cobertura de signal y decidir si las intervenciones necesitan modelo canónico separado de `topic_evidence` o si basta con `topic_evidence + text_documents`. |
| Posiciones por tema (politico x scope) | Analitica | Agregacion reproducible + drill-down a evidencia | PARTIAL | MVP: `topic_positions` se llena por método (`computed_method=votes` para does; `computed_method=declared` para says cuando hay signal; `computed_method=combined` como selector KISS: votes si existe, si no declared). Pendiente: ventanas y KPIs de cobertura high-stakes por scope. |
```

## Tracker consistency (reproducible)

```bash
python3 scripts/e2e_tracker_status.py --db "$DB" --tracker docs/etl/e2e-scrape-load-tracker.md
```

Observed (excerpt from full output):

```text
source_id                                 | checklist | sql     | runs_ok/total | max_net | max_any | last_loaded | net/fallback_fetches | result
------------------------------------------+-----------+---------+---------------+---------+---------+-------------+----------------------+-------
congreso_intervenciones                   | N/A       | DONE    | 1/2           | 614     | 614     | 614         | 1/0                  | OK
...
tracker_sources: 28
sources_in_db: 30
mismatches: 0
done_zero_real: 0
```

## Intervenciones Congreso (proof metrics)

```bash
sqlite3 $DB "SELECT 'topic_evidence_rows' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones';"
sqlite3 $DB "SELECT 'topic_evidence_declared_rows' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%';"
sqlite3 $DB "SELECT 'topic_evidence_declared_with_topic_id' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND topic_id IS NOT NULL;"
sqlite3 $DB "SELECT 'topic_evidence_declared_with_stance' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND stance IS NOT NULL;"
sqlite3 $DB "SELECT 'topic_evidence_declared_with_signal' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND stance IN ('support','oppose','mixed');"
sqlite3 $DB "SELECT 'topic_evidence_declared_with_source_url' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND source_url IS NOT NULL AND TRIM(source_url) <> '';"
sqlite3 $DB "SELECT 'topic_evidence_declared_with_evidence_date' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND evidence_date IS NOT NULL AND TRIM(evidence_date) <> '';"
sqlite3 $DB "SELECT 'review_rows' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones';"
sqlite3 $DB "SELECT 'review_pending' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' AND status='pending';"
sqlite3 $DB "SELECT 'review_resolved' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' AND status='resolved';"
sqlite3 $DB "SELECT 'review_ignored' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' AND status='ignored';"
```

Observed:

```text
topic_evidence_rows|614
topic_evidence_declared_rows|614
topic_evidence_declared_with_topic_id|614
topic_evidence_declared_with_stance|614
topic_evidence_declared_with_signal|199
topic_evidence_declared_with_source_url|614
topic_evidence_declared_with_evidence_date|614
review_rows|524
review_pending|0
review_resolved|50
review_ignored|474
```

### Interpretation
- Source `congreso_intervenciones` has 614 declared evidence rows and 199 rows with explicit signal (`support|oppose|mixed`).
- Review queue for this source has no pending rows (`0`), but remaining non-`resolved` rows are `ignored`.
- This matches tracker text indicating `PARTIAL` due signal quality and decision-loop closure steps.

## Posiciones por tema (politico x scope) (proof metrics)

```bash
sqlite3 $DB "SELECT 'topic_positions_total' AS metric, COUNT(*) AS value FROM topic_positions;"
sqlite3 $DB "SELECT 'topic_positions_with_evidence_count' AS metric, COUNT(*) AS value FROM topic_positions WHERE evidence_count > 0;"
sqlite3 $DB "SELECT as_of_date, COUNT(*) AS rows FROM topic_positions GROUP BY as_of_date ORDER BY as_of_date DESC LIMIT 20;"
sqlite3 $DB "SELECT 'topic_positions_by_method' AS metric, computed_method, COUNT(*) AS c FROM topic_positions GROUP BY computed_method ORDER BY computed_method;"
sqlite3 $DB "SELECT as_of_date, computed_method, COUNT(*) AS c FROM topic_positions WHERE as_of_date=(SELECT MAX(as_of_date) FROM topic_positions) GROUP BY as_of_date,computed_method ORDER BY computed_method;"
sqlite3 $DB "WITH hs AS (SELECT DISTINCT topic_set_id, topic_id FROM topic_set_topics WHERE is_high_stakes=1) SELECT 'high_stakes_pairs' AS metric, COUNT(*) AS high_stakes_pairs FROM hs;"
sqlite3 $DB "WITH latest AS (SELECT topic_set_id, MAX(as_of_date) AS latest_as_of_date FROM topic_positions GROUP BY topic_set_id), hs AS (SELECT topic_set_id, topic_id FROM topic_set_topics WHERE is_high_stakes=1), latest_rows AS (SELECT DISTINCT p.topic_set_id, p.topic_id FROM topic_positions p JOIN latest l ON l.topic_set_id = p.topic_set_id AND p.as_of_date = l.latest_as_of_date WHERE p.evidence_count > 0), coverage AS (SELECT h.topic_set_id, COUNT(*) AS high_stakes_pairs, SUM(CASE WHEN lr.topic_id IS NOT NULL THEN 1 ELSE 0 END) AS high_stakes_pairs_with_position FROM hs h LEFT JOIN latest_rows lr ON lr.topic_set_id=h.topic_set_id AND lr.topic_id=h.topic_id GROUP BY h.topic_set_id), rows_latest AS (SELECT l.topic_set_id, l.latest_as_of_date, COUNT(*) AS rows_latest FROM topic_positions p JOIN latest l ON l.topic_set_id = p.topic_set_id AND p.as_of_date=l.latest_as_of_date GROUP BY l.topic_set_id, l.latest_as_of_date) SELECT r.topic_set_id, r.latest_as_of_date, ts.name AS topic_set_name, c.high_stakes_pairs, c.high_stakes_pairs_with_position, CASE WHEN c.high_stakes_pairs = 0 THEN 0.0 ELSE ROUND((c.high_stakes_pairs_with_position * 100.0 / c.high_stakes_pairs),2) END AS high_stakes_coverage_pct, r.rows_latest FROM rows_latest r JOIN topic_sets ts ON ts.topic_set_id = r.topic_set_id LEFT JOIN coverage c ON c.topic_set_id=r.topic_set_id ORDER BY r.topic_set_id;"
```

Observed:

```text
topic_positions_total|137377
topic_positions_with_evidence_count|137377
2026-02-16|164
2026-02-12|137213
computed_method|combined|68612
computed_method|declared|237
computed_method|votes|68528
2026-02-16|combined|82
2026-02-16|declared|82
high_stakes_pairs|84
1|2026-02-16|Congreso de los Diputados / leg 15 / votaciones (auto)|60|12|20.0|164
2|2026-02-12|Senado de Espana / leg 15 / votaciones (auto)|24|23|95.83|11916
```

### Interpretation
- Topic positions table is populated, but the latest snapshot for topic_set 1 is very sparse (164 rows; combined/declared only 82 each) vs historical 2026-02-12 base for topic_set 2 (11,916 rows).
- High-stakes coverage is incomplete and inconsistent at the topic-set level:
  - Congreso topic set: 12/60 high-stakes topic pairs covered in latest rows (`20.0%`).
  - Senado topic set: 23/24 high-stakes topic pairs covered in latest rows (`95.83%`).
- `as_of_date` split indicates non-uniform recompute recency across topic sets; this aligns with tracker’s `PARTIAL` text calling out missing window/coverage work.

## Replay recipe

An agent can replay this evidence run with:

1. `DB=etl/data/staging/politicos-es.db`
2. Re-run the exact SQL blocks under each section.
3. Re-run the tracker extraction command.
4. Verify the two tracker-row lines remain `PARTIAL` in `docs/etl/e2e-scrape-load-tracker.md` and compare numeric baselines.
