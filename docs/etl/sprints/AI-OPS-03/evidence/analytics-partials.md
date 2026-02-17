# Evidence packet: analytics PARTIAL tracker rows (AI-OPS-03)

Generated on: 2026-02-16
Repository: `/Users/jesus/Library/CloudStorage/GoogleDrive-gsus123456@gmail.com/My Drive/CdC/Obsidian Vault/vota-con-la-chola`
DB: `etl/data/staging/politicos-es.db`

## Scope (targets)
- Intervenciones Congreso
- Posiciones por tema (politico x scope)

## 1) Commands and outputs

### 1.1 Tracker rows (source of truth)

Command:
```bash
DB=etl/data/staging/politicos-es.db
python3 - <<'PY'
from pathlib import Path
import re
path = Path('docs/etl/e2e-scrape-load-tracker.md')
for line in path.read_text(encoding='utf-8').splitlines():
    if re.search(r'\| Intervenciones Congreso \|', line) or re.search(r'\| Posiciones por tema \(politico x scope\) \|', line):
        print(line)
PY
```

Observed:
```text
| Intervenciones Congreso | Parlamentario | Congreso intervenciones | PARTIAL | Evidencia reproducible en `docs/etl/sprints/AI-OPS-02/evidence/analytics-partials.md`: SQL reporta `topic_evidence_declared_rows=614`, `topic_evidence_declared_with_signal=199`, `review_pending=0`, y `python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md` muestra `congreso_intervenciones` con `max_net=614` y `result=OK`. Bloqueador: cobertura de signal sigue parcial (`199/614`). Siguiente comando: `python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id congreso_intervenciones --min-auto-confidence 0.62`. |
| Posiciones por tema (politico x scope) | Analitica | Agregacion reproducible + drill-down a evidencia | PARTIAL | Evidencia reproducible en `docs/etl/sprints/AI-OPS-02/evidence/analytics-partials.md`: SQL reporta `topic_positions_total=137377`, `computed_method_combined=68612`, `computed_method_declared=237`, `computed_method_votes=68528`, y cobertura high-stakes latest por set `topic_set_id=1: 12/60 (20.0%)`, `topic_set_id=2: 23/24 (95.83%)`. Bloqueador: cobertura high-stakes latest en Congreso es baja y el `as_of_date` está desalineado entre sets (`2026-02-16` vs `2026-02-12`). Siguiente comando: `python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db etl/data/staging/politicos-es.db --as-of-date 2026-02-16 --taxonomy-seed etl/data/seeds/topic_taxonomy_es.json`. |
```

### 1.2 e2e tracker status

Command:
```bash
python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md
```

Observed (relevant lines):
```text
source_id                                 | checklist | sql     | runs_ok/total | max_net | max_any | last_loaded | net/fallback_fetches | result
------------------------------------------+-----------+---------+---------------+---------+---------+-------------+----------------------+---------
congreso_intervenciones                   | N/A       | DONE    | 1/2           | 614     | 614     | 614         | 1/0                  | OK
...
parlamento_galicia_deputados              | PARTIAL   | PARTIAL | 4/6           | 0       | 75      | 0           | 0/4                  | OK
...
parlamento_navarra_parlamentarios_forales | PARTIAL   | DONE    | 2/6           | 50      | 50      | 0           | 1/1                  | MISMATCH
...
tracker_sources: 28
sources_in_db: 30
mismatches: 1
done_zero_real: 0
```

### 1.3 Intervenciones Congreso proof metrics

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_rows' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_declared_rows' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_declared_with_topic_id' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND topic_id IS NOT NULL;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_declared_with_stance' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND stance IS NOT NULL;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_declared_with_signal' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND stance IN ('support','oppose','mixed');"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_declared_with_source_url' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND source_url IS NOT NULL AND TRIM(source_url) <> '';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_evidence_declared_with_evidence_date' AS metric, COUNT(*) AS value FROM topic_evidence WHERE source_id='congreso_intervenciones' AND evidence_type LIKE 'declared:%' AND evidence_date IS NOT NULL AND TRIM(evidence_date) <> '';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'review_rows' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'review_pending' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' AND status='pending';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'review_resolved' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' AND status='resolved';"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'review_ignored' AS metric, COUNT(*) AS value FROM topic_evidence_reviews WHERE source_id='congreso_intervenciones' AND status='ignored';"
```

Observed:
```text
topic_evidence_rows|614
topic_evidence_declared_rows|614
topic_evidence_declared_with_topic_id|614
topic_evidence_declared_with_stance|614
topic_evidence_declared_with_signal|202
topic_evidence_declared_with_source_url|614
topic_evidence_declared_with_evidence_date|614
review_rows|524
review_pending|0
review_resolved|50
review_ignored|474
```

### 1.4 Posiciones por tema proof metrics

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_positions_total' AS metric, COUNT(*) AS value FROM topic_positions;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_positions_with_evidence_count' AS metric, COUNT(*) AS value FROM topic_positions WHERE evidence_count > 0;"
sqlite3 etl/data/staging/politicos-es.db "SELECT as_of_date, COUNT(*) AS rows FROM topic_positions GROUP BY as_of_date ORDER BY as_of_date DESC LIMIT 20;"
sqlite3 etl/data/staging/politicos-es.db "SELECT 'topic_positions_by_method' AS metric, computed_method, COUNT(*) AS c FROM topic_positions GROUP BY computed_method ORDER BY computed_method;"
sqlite3 etl/data/staging/politicos-es.db "SELECT as_of_date, computed_method, COUNT(*) AS c FROM topic_positions WHERE as_of_date=(SELECT MAX(as_of_date) FROM topic_positions) GROUP BY as_of_date,computed_method ORDER BY computed_method;"
sqlite3 etl/data/staging/politicos-es.db "WITH hs AS (SELECT DISTINCT topic_set_id, topic_id FROM topic_set_topics WHERE is_high_stakes=1) SELECT 'high_stakes_pairs' AS metric, COUNT(*) AS high_stakes_pairs FROM hs;"
sqlite3 etl/data/staging/politicos-es.db "WITH latest AS (SELECT topic_set_id, MAX(as_of_date) AS latest_as_of_date FROM topic_positions GROUP BY topic_set_id), hs AS (SELECT topic_set_id, topic_id FROM topic_set_topics WHERE is_high_stakes=1), latest_rows AS (SELECT DISTINCT p.topic_set_id, p.topic_id FROM topic_positions p JOIN latest l ON l.topic_set_id = p.topic_set_id AND p.as_of_date = l.latest_as_of_date WHERE p.evidence_count > 0), coverage AS (SELECT h.topic_set_id, COUNT(*) AS high_stakes_pairs, SUM(CASE WHEN lr.topic_id IS NOT NULL THEN 1 ELSE 0 END) AS high_stakes_pairs_with_position FROM hs h LEFT JOIN latest_rows lr ON lr.topic_set_id=h.topic_set_id AND lr.topic_id=h.topic_id GROUP BY h.topic_set_id), rows_latest AS (SELECT l.topic_set_id, l.latest_as_of_date, COUNT(*) AS rows_latest FROM topic_positions p JOIN latest l ON l.topic_set_id = p.topic_set_id AND p.as_of_date=l.latest_as_of_date GROUP BY l.topic_set_id, l.latest_as_of_date) SELECT r.topic_set_id, r.latest_as_of_date, ts.name AS topic_set_name, c.high_stakes_pairs, c.high_stakes_pairs_with_position, CASE WHEN c.high_stakes_pairs = 0 THEN 0.0 ELSE ROUND((c.high_stakes_pairs_with_position * 100.0 / c.high_stakes_pairs),2) END AS high_stakes_coverage_pct, r.rows_latest FROM rows_latest r JOIN topic_sets ts ON ts.topic_set_id = r.topic_set_id LEFT JOIN coverage c ON c.topic_set_id=r.topic_set_id ORDER BY r.topic_set_id;"
sqlite3 etl/data/staging/politicos-es.db "SELECT topic_set_id, computed_method, as_of_date, COUNT(*) AS rows FROM topic_positions GROUP BY topic_set_id, computed_method, as_of_date ORDER BY topic_set_id, computed_method, as_of_date;"
```

Observed:
```text
topic_positions_total|137379
topic_positions_with_evidence_count|137379
2026-02-16|164
2026-02-12|137215
topic_positions_by_method|combined|68612
topic_positions_by_method|declared|239
topic_positions_by_method|votes|68528
2026-02-16|combined|82
2026-02-16|declared|82
high_stakes_pairs|84
1|2026-02-16|Congreso de los Diputados / leg 15 / votaciones (auto)|60|12|20.0|164
2|2026-02-12|Senado de Espana / leg 15 / votaciones (auto)|24|23|95.83|11916
1|combined|2026-02-12|62572
1|combined|2026-02-16|82
1|declared|2026-02-12|157
1|declared|2026-02-16|82
2|combined|2026-02-12|5958
2|votes|2026-02-12|5958
```

### 1.5 Sprint-kickoff parity checks (for reproducibility)

Command:
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS fk_violations FROM pragma_foreign_key_check;"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS pending_reviews FROM topic_evidence_reviews WHERE status='pending';"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 15) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
python3 - <<'PY'
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload
p=Path('etl/data/staging/politicos-es.db')
s=build_topics_coherence_payload(p, limit=5, offset=0).get('summary', {})
print(s)
PY
```

Observed:
```text
0
0
614|202|0.328990228013029
{'groups_total': 26, 'overlap_total': 155, 'explicit_total': 100, 'coherent_total': 52, 'incoherent_total': 48, 'coherence_pct': 0.52, 'incoherence_pct': 0.48}
```

## 2) Conclusions (AI-OPS-03 context)
- The two target rows in `docs/etl/e2e-scrape-load-tracker.md` are still present as `PARTIAL`.
- `Intervenciones Congreso`: declared evidence remains `614`, with explicit signal now `202` (up from `199`), and review queue remains without pending (`review_pending=0`).
- `Posiciones por tema (politico x scope)`: table remains populated (`137379` rows total), but `as_of_date` is still split (`2026-02-16` for small set of 164 topic-position rows; `2026-02-12` for the bulk), and high-stakes coverage remains incomplete in topic_set 1 (`12/60`, `20.0%`).
- These outputs are replayable exactly using the commands listed in §1.

## 3) Replay recipe
Execute in repo root:
```bash
DB=etl/data/staging/politicos-es.db
# 1) Run tracker row extraction
python3 - <<'PY'
from pathlib import Path
import re
path = Path('docs/etl/e2e-scrape-load-tracker.md')
for line in path.read_text(encoding='utf-8').splitlines():
    if re.search(r'\| Intervenciones Congreso \|', line) or re.search(r'\| Posiciones por tema \(politico x scope\) \|', line):
        print(line)
PY

# 2) Run e2e tracker status
python3 scripts/e2e_tracker_status.py --db "$DB" --tracker docs/etl/e2e-scrape-load-tracker.md

# 3) Run SQL proof blocks for both target rows
# (use exactly the sections in 1.3 and 1.4)
```
