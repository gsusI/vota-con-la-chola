# Sprint AI-OPS-03 Closeout

Fecha: 2026-02-16  
Repo: `REPO_ROOT/vota-con-la-chola`  
DB evaluada: `etl/data/staging/politicos-es.db`

## Resumen ejecutivo

Decisión de sprint: **PASS**.

AI-OPS-03 cierra en verde los 6 gates definidos para calidad/integridad, señal declarada, coherencia auditable, reconciliación de tracker y paridad de publicación estática.

## Tabla de gates (PASS/FAIL)

| Gate | Criterio | Evidencia (comando y salida) | Resultado |
|---|---|---|---|
| 1 | `PRAGMA foreign_key_check` devuelve 0 filas | `sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;" \| wc -l` -> `0` | PASS |
| 2 | `topic_evidence_reviews pending == 0` | `sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM topic_evidence_reviews WHERE status='pending';"` -> `0` | PASS |
| 3 | `declared_signal_pct` mejora vs kickoff AI-OPS-03 | Baseline kickoff (`docs/etl/sprints/AI-OPS-03/kickoff.md`): `614|199|0.324104234527687`. Actual: `sqlite3 ... source_id='congreso_intervenciones'` -> `614|202|0.328990228013029` | PASS |
| 4 | `coherence overlap > 0` y drill-down incoherente devuelve evidencia | `build_topics_coherence_payload` -> `overlap_total=155`, `explicit_total=100`, `coherent_total=52`, `incoherent_total=48`; `build_topics_coherence_evidence_payload(bucket='incoherent')` -> `pairs_total=48`, `evidence_total=1711`, `rows_returned=20` | PASS |
| 5 | Filas analytics `PARTIAL` reconciliadas con evidencia y siguiente paso claro | `docs/etl/e2e-scrape-load-tracker.md` contiene filas `Intervenciones Congreso` y `Posiciones por tema (politico x scope)` con referencias a `docs/etl/sprints/AI-OPS-03/evidence/analytics-partials.md`, blocker único y comando siguiente explícito | PASS |
| 6 | Snapshot exportado de `explorer-sources` en paridad con live DB para KPIs auditados | Paridad (`docs/gh-pages/explorer-sources/data/status.json` vs SQL live): `declared_with_signal 202=202`, `declared_with_signal_pct 0.328990228013029=0.328990228013029 (15dp)`, `overlap 155=155`, `explicit 100=100`, `coherent 52=52`, `incoherent 48=48`; `all_match=True` | PASS |

## Evidencia de comandos (extracto)

### Gate 1
```bash
sqlite3 etl/data/staging/politicos-es.db "PRAGMA foreign_key_check;" | wc -l
```
```text
0
```

### Gate 2
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS pending_reviews FROM topic_evidence_reviews WHERE status='pending';"
```
```text
0
```

### Gate 3
```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 15) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
```
```text
614|202|0.328990228013029
```

### Gate 4
```bash
python3 - <<'PY'
from pathlib import Path
from scripts.graph_ui_server import build_topics_coherence_payload, build_topics_coherence_evidence_payload
p=Path('etl/data/staging/politicos-es.db')
coh=build_topics_coherence_payload(p, limit=5, offset=0)
asof=(coh.get('meta',{}) or {}).get('as_of_date','')
s=coh.get('summary',{})
print('coherence_as_of_date',asof)
print('coherence_overlap_total', s.get('overlap_total',0))
print('coherence_explicit_total', s.get('explicit_total',0))
print('coherence_coherent_total', s.get('coherent_total',0))
print('coherence_incoherent_total', s.get('incoherent_total',0))
rows=build_topics_coherence_evidence_payload(p,bucket='incoherent',as_of_date=asof,limit=20,offset=0)
print('incoherent_pairs_total', (rows.get('summary') or {}).get('pairs_total',0))
print('incoherent_evidence_total', (rows.get('summary') or {}).get('evidence_total',0))
print('incoherent_rows_returned', (rows.get('page') or {}).get('returned',0))
PY
```
```text
coherence_as_of_date 2026-02-12
coherence_overlap_total 155
coherence_explicit_total 100
coherence_coherent_total 52
coherence_incoherent_total 48
incoherent_pairs_total 48
incoherent_evidence_total 1711
incoherent_rows_returned 20
```

### Gate 5
```bash
python3 - <<'PY'
from pathlib import Path
import re
path=Path('docs/etl/e2e-scrape-load-tracker.md')
for line in path.read_text(encoding='utf-8').splitlines():
    if re.search(r'\| Intervenciones Congreso \|', line) or re.search(r'\| Posiciones por tema \(politico x scope\) \|', line):
        print(line)
PY
```
```text
| Intervenciones Congreso | ... | PARTIAL | ... `topic_evidence_declared_rows=614`, `topic_evidence_declared_with_signal=202`, `review_pending=0` ... Bloqueador: cobertura de señal declarada sigue parcial (`202/614`). Siguiente comando: `just parl-backfill-declared-stance`. |
| Posiciones por tema (politico x scope) | ... | PARTIAL | ... `topic_positions_total=137379`, `computed_method_combined=68612`, `computed_method_declared=239`, `computed_method_votes=68528` ... Bloqueador: latest de Congreso sigue anclado en `as_of_date=2026-02-16` con cobertura `20.0%`. Siguiente comando: `python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db etl/data/staging/politicos-es.db --as-of-date 2026-02-16 --taxonomy-seed etl/data/seeds/topic_taxonomy_es.json`. |
```

### Gate 6
```bash
python3 - <<'PY'
import json, sqlite3
from pathlib import Path
from scripts.graph_ui_server import _resolve_topic_coherence_as_of_date
db='etl/data/staging/politicos-es.db'
status=json.loads(Path('docs/gh-pages/explorer-sources/data/status.json').read_text(encoding='utf-8'))
ev=((status.get('analytics') or {}).get('evidence') or {})
coh=((status.get('analytics') or {}).get('coherence') or {})
conn=sqlite3.connect(db); conn.row_factory=sqlite3.Row
r=conn.execute("SELECT SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS sig, (SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0) AS pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%'").fetchone()
asof=_resolve_topic_coherence_as_of_date(conn)
c=conn.execute("""
WITH votes AS (
  SELECT topic_id, person_id, as_of_date, stance AS does_stance FROM topic_positions WHERE computed_method='votes' AND as_of_date=?
),
decl AS (
  SELECT topic_id, person_id, as_of_date, stance AS says_stance FROM topic_positions WHERE computed_method='declared' AND as_of_date=?
),
pairs AS (
  SELECT v.topic_id, v.person_id, v.as_of_date, v.does_stance, d.says_stance FROM votes v JOIN decl d USING(topic_id, person_id, as_of_date)
)
SELECT COUNT(*) AS overlap_total,
       SUM(CASE WHEN does_stance IN ('support','oppose') AND says_stance IN ('support','oppose') THEN 1 ELSE 0 END) AS explicit_total,
       SUM(CASE WHEN (does_stance='support' AND says_stance='support') OR (does_stance='oppose' AND says_stance='oppose') THEN 1 ELSE 0 END) AS coherent_total,
       SUM(CASE WHEN (does_stance='support' AND says_stance='oppose') OR (does_stance='oppose' AND says_stance='support') THEN 1 ELSE 0 END) AS incoherent_total
FROM pairs
""",(asof,asof)).fetchone()
conn.close()
checks=[
 int(r['sig'] or 0)==int(ev.get('topic_evidence_declared_with_signal') or 0),
 f"{float(r['pct'] or 0.0):.15f}"==f"{float(ev.get('topic_evidence_declared_with_signal_pct') or 0.0):.15f}",
 int(c['overlap_total'] or 0)==int(coh.get('overlap_total') or 0),
 int(c['explicit_total'] or 0)==int(coh.get('explicit_total') or 0),
 int(c['coherent_total'] or 0)==int(coh.get('coherent_total') or 0),
 int(c['incoherent_total'] or 0)==int(coh.get('incoherent_total') or 0),
]
print('all_match', all(checks))
PY
```
```text
all_match True
```

## Decisión de proyecto (L3)

Decisión: **PASS AI-OPS-03**.

Razonamiento de framing:
- Se cerró el slice crítico de Fase 2 (`says/does` trazable) con mejoras reales de señal declarada y coherencia auditable.
- Se cerró el riesgo de publish drift (`explorer-sources` estático vs live DB) para los KPIs auditados.
- El tracker de analytics queda reconciliado y operativo (blocker + next command explícitos).

## Apertura AI-OPS-04 (source family único)

Se abre **AI-OPS-04** con una sola familia de fuentes, alineada al critical path del roadmap técnico:
- **Familia**: `Accion ejecutiva (Consejo de Ministros)` (`La Moncloa: referencias + RSS`).

Justificación de prioridad:
- Extiende el marco de “lo que hacen” fuera del parlamento (siguiente salto de cobertura con mayor valor producto).
- Encaja con la guía de roadmap técnico para doble entrada trazable (señal comunicacional + validación contra registros con efectos cuando aplique).

Primer comando operativo (arranque de baseline AI-OPS-04):
```bash
just etl-tracker-status
```
