# Signal Uplift (AI-OPS-02)

Fecha: 2026-02-16
Objetivo: mejorar calidad de señal declarada (`regex_v3`) para `congreso_intervenciones` y recomputar posiciones derivadas.

## Cambios de extracción (`etl/parlamentario_es/declared_stance.py`)

Se ampliaron patrones positivos y negativos con foco en falsos negativos observados en staging:

- Positivos nuevos (support):
  - `vamos/voy/iremos a votar favorablemente|afirmativamente|positivamente`
  - `votamos a favor`
  - `votamos favorablemente`
  - `hemos votado a favor`
  - catalán: `votarem favorablement`
- Negativos nuevos (oppose):
  - `vamos/voy/iremos a votar negativamente`
  - `votamos en contra`
  - `votamos negativamente`
  - `hemos votado en contra`
  - negación explícita de apoyo en voto: `no votaremos a favor`, `no vamos a votar a favor`, `no ... votar favorablemente`
  - catalán: `votarem negativament`, `no votarem a favor`

## Tests de regresión

Archivo actualizado: `tests/test_parl_declared_stance.py`

- Se añadieron casos de falsos negativos (ahora deben detectar):
  - `vamos a votar favorablemente`
  - `votamos a favor`
  - `hemos votado en contra`
  - `no votaremos a favor`
- Se añadieron casos de falsos positivos (deben seguir en `None`):
  - `Esperamos que ustedes voten favorablemente...`
  - `Nadie ha votado a favor...`
  - `Se inicia la votación de conjunto...`

Ejecución:

```bash
python3 -m unittest tests.test_parl_declared_stance
python3 -m unittest tests.test_parl_declared_positions tests.test_parl_combined_positions tests.test_parl_review_queue
```

Resultado:
- `tests.test_parl_declared_stance`: `Ran 4 tests ... OK`
- suite relacionada: `Ran 3 tests ... OK`

## KPI baseline vs after

Baseline (antes de cambios):

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, (SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
```

Salida:

```text
614|194|0.315960912052117
```

## Recompute ejecutado

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance \
  --db etl/data/staging/politicos-es.db \
  --source-id congreso_intervenciones \
  --min-auto-confidence 0.62 \
  --skip-review-queue

python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions \
  --db etl/data/staging/politicos-es.db \
  --source-id congreso_intervenciones \
  --as-of-date 2026-02-12

python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions \
  --db etl/data/staging/politicos-es.db \
  --as-of-date 2026-02-12
```

Salidas relevantes:

- `backfill-declared-stance`:

```json
{
  "seen": 613,
  "updated": 6,
  "support": 110,
  "oppose": 71,
  "mixed": 17,
  "review_pending": 0,
  "review_queue_enabled": false
}
```

- `backfill-declared-positions`:

```json
{
  "positions_total": 151,
  "topic_sets": [{"topic_set_id": 1, "inserted": 151}],
  "as_of_date": "2026-02-12"
}
```

- `backfill-combined-positions`:

```json
{
  "inserted": 68528,
  "would_insert": 68528,
  "as_of_date": "2026-02-12"
}
```

After (después de cambios + recompute):

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, (SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
```

Salida:

```text
614|199|0.324104234527687
```

Delta KPI:
- `declared_signal`: `194 -> 199` (`+5`)
- `declared_signal_pct`: `0.315960912052117 -> 0.324104234527687` (`+0.00814332247557`)

## Cola pendiente (DoD)

Comprobación:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT status, COUNT(*) FROM topic_evidence_reviews GROUP BY status ORDER BY status;"
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM topic_evidence_reviews WHERE status='pending';"
```

Salida:

```text
ignored|474
resolved|50

0
```

Resultado: `pending queue` se mantiene en `0`.
