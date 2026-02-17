# Dashboard Refresh (AI-OPS-03)

Fecha: 2026-02-16  
Objetivo: alinear snapshot estático de `/explorer-sources` (GH Pages) con métricas live de `etl/data/staging/politicos-es.db`.

## Artefacto refrescado

Comando ejecutado:

```bash
python3 scripts/export_explorer_sources_snapshot.py \
  --db etl/data/staging/politicos-es.db \
  --out docs/gh-pages/explorer-sources/data/status.json
```

Salida:

```text
OK sources status snapshot -> docs/gh-pages/explorer-sources/data/status.json
```

Archivo actualizado:
- `docs/gh-pages/explorer-sources/data/status.json`

## Paridad live DB vs export (campos auditados)

Comando de paridad:

```bash
python3 - <<'PY'
import json, sqlite3
from pathlib import Path
from scripts.graph_ui_server import _resolve_topic_coherence_as_of_date

db='etl/data/staging/politicos-es.db'
status_path=Path('docs/gh-pages/explorer-sources/data/status.json')
status=json.loads(status_path.read_text(encoding='utf-8'))
ev=((status.get('analytics') or {}).get('evidence') or {})
coh=((status.get('analytics') or {}).get('coherence') or {})

conn=sqlite3.connect(db)
conn.row_factory=sqlite3.Row
row=conn.execute("""
SELECT
  SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS topic_evidence_declared_with_signal,
  (SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0) AS topic_evidence_declared_with_signal_pct
FROM topic_evidence
WHERE evidence_type LIKE 'declared:%'
""").fetchone()

asof=_resolve_topic_coherence_as_of_date(conn)
crow=conn.execute("""
WITH votes AS (
  SELECT topic_id, person_id, as_of_date, stance AS does_stance
  FROM topic_positions
  WHERE computed_method = 'votes' AND as_of_date = ?
),
decl AS (
  SELECT topic_id, person_id, as_of_date, stance AS says_stance
  FROM topic_positions
  WHERE computed_method = 'declared' AND as_of_date = ?
),
pairs AS (
  SELECT v.topic_id, v.person_id, v.as_of_date, v.does_stance, d.says_stance
  FROM votes v
  JOIN decl d USING(topic_id, person_id, as_of_date)
)
SELECT
  COUNT(*) AS overlap_total,
  SUM(CASE WHEN does_stance IN ('support','oppose') AND says_stance IN ('support','oppose') THEN 1 ELSE 0 END) AS explicit_total,
  SUM(CASE WHEN (does_stance = 'support' AND says_stance = 'support') OR (does_stance = 'oppose' AND says_stance = 'oppose') THEN 1 ELSE 0 END) AS coherent_total,
  SUM(CASE WHEN (does_stance = 'support' AND says_stance = 'oppose') OR (does_stance = 'oppose' AND says_stance = 'support') THEN 1 ELSE 0 END) AS incoherent_total
FROM pairs
""", (asof, asof)).fetchone()
conn.close()

checks=[
  ('topic_evidence_declared_with_signal', int(row['topic_evidence_declared_with_signal'] or 0), int(ev.get('topic_evidence_declared_with_signal') or 0)),
  ('topic_evidence_declared_with_signal_pct_15dp', f"{float(row['topic_evidence_declared_with_signal_pct'] or 0.0):.15f}", f"{float(ev.get('topic_evidence_declared_with_signal_pct') or 0.0):.15f}"),
  ('coherence_overlap_total', int(crow['overlap_total'] or 0), int(coh.get('overlap_total') or 0)),
  ('coherence_explicit_total', int(crow['explicit_total'] or 0), int(coh.get('explicit_total') or 0)),
  ('coherence_coherent_total', int(crow['coherent_total'] or 0), int(coh.get('coherent_total') or 0)),
  ('coherence_incoherent_total', int(crow['incoherent_total'] or 0), int(coh.get('incoherent_total') or 0)),
]

print('status_json', status_path)
print('coherence_as_of_date', asof)
for name,live,exp in checks:
  print(f"{name}|live={live}|export={exp}|match={live==exp}")
print('all_match', all(live==exp for _,live,exp in checks))
PY
```

Salida:

```text
status_json docs/gh-pages/explorer-sources/data/status.json
coherence_as_of_date 2026-02-12
topic_evidence_declared_with_signal|live=202|export=202|match=True
topic_evidence_declared_with_signal_pct_15dp|live=0.328990228013029|export=0.328990228013029|match=True
coherence_overlap_total|live=155|export=155|match=True
coherence_explicit_total|live=100|export=100|match=True
coherence_coherent_total|live=52|export=52|match=True
coherence_incoherent_total|live=48|export=48|match=True
all_match True
```

## Resultado

- Paridad validada para todos los campos auditados.
- No fue necesario ajustar `export` ni backend: la ruta actual (`scripts/export_explorer_sources_snapshot.py` -> `build_sources_status_payload`) ya produce valores consistentes con live DB.
