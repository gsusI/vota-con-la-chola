# AI-OPS-03: Alineacion de `as_of_date` en topic analytics/positions

## Objetivo
Eliminar drift de `as_of_date` entre:
- `backfill-topic-analytics`
- `backfill-declared-positions`
- `backfill-combined-positions`
- export/status de `explorer-sources` (coherence)

## Causa raiz detectada
- `backfill-topic-analytics` podia terminar con fechas distintas por `topic_set` cuando no se pasaba `--as-of-date`.
- `backfill-declared-positions` y `backfill-combined-positions` no compartian un fallback comun alineado a `votes`.
- `build_sources_status_payload()` tomaba `MAX(topic_positions.as_of_date)` global, no el `as_of_date` de overlap `votes` vs `declared`.

## Cambio aplicado (KISS)
- `etl/parlamentario_es/cli.py`
  - Nuevo resolver compartido de `as_of_date`:
    - prioridad: `--as-of-date` -> `$SNAPSHOT_DATE` -> fallback determinista
    - `topic-analytics`: `MAX(vote_date)` sobre fuentes/legislatura efectiva
    - `declared-positions`: `MAX(votes.as_of_date)` acotado a `topic_sets` con evidencia declarada del `source_id`
    - `combined-positions`: `MAX(votes.as_of_date)` (no mezcla con `declared` mas reciente)
  - Mensajes/help de CLI actualizados para reflejar fallback alineado a `votes`.
- `scripts/graph_ui_server.py`
  - `build_sources_status_payload()` ahora usa `_resolve_topic_coherence_as_of_date()` (overlap-aware) en vez de `MAX(topic_positions.as_of_date)` global.
- Tests:
  - `tests/test_parl_cli_asof_alignment.py` (nuevo)
  - `tests/test_graph_ui_server_coherence.py` (nuevo caso `/api/sources/status`)

## Runbook reproducible (sin `--as-of-date`)
Se ejecuto en una copia descartable para no mutar el staging principal:

```bash
TMP_DB=/tmp/politicos-es.asof-ai-ops-03.db
cp etl/data/staging/politicos-es.db "$TMP_DB"
```

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db "$TMP_DB" > /tmp/asof_topic_analytics.json
python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db "$TMP_DB" --source-id congreso_intervenciones > /tmp/asof_declared_positions.json
python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db "$TMP_DB" > /tmp/asof_combined_positions.json
```

Extraccion de outputs clave:

```json
{
  "topic_analytics": {
    "as_of_date": "2026-02-12",
    "results": [
      {
        "topic_set_id": 1,
        "vote_source_id": "congreso_votaciones",
        "as_of_date": "2026-02-12",
        "positions_inserted": 62570
      },
      {
        "topic_set_id": 2,
        "vote_source_id": "senado_votaciones",
        "as_of_date": "2026-02-12",
        "positions_inserted": 5958
      }
    ]
  },
  "declared_positions": {
    "as_of_date": "2026-02-12",
    "positions_total": 155,
    "topic_sets": [
      {
        "inserted": 155,
        "topic_set_id": 1
      }
    ]
  },
  "combined_positions": {
    "as_of_date": "2026-02-12",
    "inserted": 68530,
    "would_insert": 68530
  }
}
```

## Gate SQL (sin mezcla de `as_of_date` en la corrida)
Validacion por metodo/topic_set para filas recomputadas en la corrida:

```bash
RUN_TS=$(python3 - <<'PY'
import json
with open('/tmp/asof_topic_analytics.json', 'r', encoding='utf-8') as f:
    print(json.load(f).get('generated_at', ''))
PY
)

sqlite3 -header -column "$TMP_DB" "
SELECT
  topic_set_id,
  computed_method,
  COUNT(*) AS rows,
  COUNT(DISTINCT as_of_date) AS asof_distinct,
  MIN(as_of_date) AS asof_min,
  MAX(as_of_date) AS asof_max
FROM topic_positions
WHERE computed_method IN ('votes','declared','combined')
  AND computed_at >= '$RUN_TS'
GROUP BY topic_set_id, computed_method
ORDER BY topic_set_id, computed_method;
"
```

Salida:

```text
topic_set_id  computed_method  rows   asof_distinct  asof_min    asof_max
------------  ---------------  -----  -------------  ----------  ----------
1             combined         62572  1              2026-02-12  2026-02-12
1             declared         155    1              2026-02-12  2026-02-12
1             votes            62570  1              2026-02-12  2026-02-12
2             combined         5958   1              2026-02-12  2026-02-12
2             votes            5958   1              2026-02-12  2026-02-12
```

## Export/status coherence (explorer-sources)
Comando:

```bash
python3 scripts/export_explorer_sources_snapshot.py --db "$TMP_DB" --out /tmp/sources_status_asof_ai_ops_03.json
python3 - <<'PY'
import json
with open('/tmp/sources_status_asof_ai_ops_03.json', 'r', encoding='utf-8') as f:
    payload = json.load(f)
coh = ((payload.get('analytics') or {}).get('coherence') or {})
print('coherence.as_of_date=', coh.get('as_of_date'))
print('coherence.overlap_total=', coh.get('overlap_total'))
print('coherence.explicit_total=', coh.get('explicit_total'))
PY
```

Salida:

```text
OK sources status snapshot -> /tmp/sources_status_asof_ai_ops_03.json
coherence.as_of_date= 2026-02-12
coherence.overlap_total= 153
coherence.explicit_total= 98
```

Resultado: la fecha de coherence exportada queda alineada con la corrida (`2026-02-12`) y no deriva a un `MAX(as_of_date)` global no comparable.
