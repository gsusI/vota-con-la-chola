# Signal Uplift (AI-OPS-03)

Fecha: 2026-02-16  
Scope: `congreso_intervenciones` (`declared:regex_v3`)

## Objetivo
Mejorar `declared_signal_pct` sin abrir falsos positivos nuevos y sin reabrir la cola manual.

Baseline kickoff (referencia de sprint):

```text
614|199|0.324104234527687
```

Fuente: `docs/etl/sprints/AI-OPS-03/kickoff.md`.

## Cambios en extractor (`etl/parlamentario_es/declared_stance.py`)

Se añadieron patrones de alta precisión para recuperar falsos negativos observados en staging:

- soporte:
  - `votaremos, <adverbios>, a favor`
  - `nuestro/mi voto sea favorable|positivo|afirmativo`
- oposición:
  - `votaremos, <adverbios>, en contra`
  - `no vamos a votar en absoluto a favor`
  - `no votaremos en absoluto a favor`
  - `nuestro/mi voto sea negativo|desfavorable`

No se introdujeron patrones genéricos tipo `votar favorablemente` sin sujeto propio.

## Precision risk controls (explícitos)

1. Patrones anclados a primera persona/plural (`votaremos`, `nuestro voto`, `no vamos a votar`) para evitar capturar texto narrativo o sobre terceros.
2. Se mantiene bloqueo de negación previa (`_is_negated`) para evitar invertir polaridad por contexto (`no ...`).
3. No se habilitan expresiones hipotéticas/procedimentales (`si votar favorablemente`, `votaremos las enmiendas por separado`) como señal.
4. Se conserva `min_auto_confidence=0.62`: lo ambiguo sigue yendo a revisión, no a autoetiquetado.
5. Se añadieron regresiones de falsos positivos y falsos negativos en tests.

## Tests de regresión

Archivo actualizado: `tests/test_parl_declared_stance.py`

Nuevos falsos negativos recuperados:
- `Votaremos, obviamente, en contra de su enmienda.`
- `No vamos a votar en absoluto a favor de la enmienda de Vox.`
- `Hará que nuestro voto sea favorable a que esta ley continúe.`

Falsos positivos que deben seguir bloqueados:
- `Luego votaremos las enmiendas por separado.`
- `Nos genera dudas a la hora de si votar favorablemente esta proposición.`
- `Esperamos que ustedes voten favorablemente esta enmienda.`

Ejecución:

```bash
python3 -m unittest tests/test_parl_declared_stance.py tests/test_parl_declared_positions.py tests/test_parl_combined_positions.py
```

Salida:

```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.152s

OK
```

## Recompute E2E ejecutado (snapshot)

Comandos requeridos:

```bash
just parl-backfill-text-documents
just parl-backfill-declared-stance
just parl-backfill-declared-positions
just parl-backfill-combined-positions
```

Salidas relevantes:

- `parl-backfill-text-documents`:

```json
{
  "documents_total_for_source": 614,
  "seen": 614,
  "skipped_existing": 614,
  "upserted": 0,
  "extracted_excerpt": 0,
  "failures": []
}
```

- `parl-backfill-declared-stance`:

```json
{
  "seen": 613,
  "updated": 3,
  "support": 111,
  "oppose": 73,
  "mixed": 17,
  "review_pending": 0,
  "review_total": 524
}
```

- `parl-backfill-declared-positions`:

```json
{
  "as_of_date": "2026-02-12",
  "positions_total": 157,
  "topic_sets": [
    {
      "topic_set_id": 1,
      "inserted": 157
    }
  ]
}
```

- `parl-backfill-combined-positions`:

```json
{
  "as_of_date": "2026-02-12",
  "inserted": 68530,
  "would_insert": 68530
}
```

## KPI before/after (declared signal)

Comando:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS declared_total, SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END) AS declared_signal, ROUND((SUM(CASE WHEN stance IN ('support','oppose','mixed') THEN 1 ELSE 0 END)*1.0)/NULLIF(COUNT(*),0), 15) AS declared_signal_pct FROM topic_evidence WHERE evidence_type LIKE 'declared:%' AND source_id='congreso_intervenciones';"
```

Antes (kickoff):

```text
614|199|0.324104234527687
```

Después (tras recompute AI-OPS-03):

```text
614|202|0.328990228013029
```

Delta:
- `declared_signal`: `199 -> 202` (`+3`)
- `declared_signal_pct`: `0.324104234527687 -> 0.328990228013029` (`+0.004885993485342`)

## Queue health y checks de aceptación

Pending review queue:

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) AS pending_reviews FROM topic_evidence_reviews WHERE status='pending';"
```

Salida:

```text
0
```

Estado final:
- `declared_signal_pct` mejora estrictamente vs baseline kickoff.
- tests de regresión pasan.
- `topic_evidence_reviews` pendiente se mantiene en `0`.
