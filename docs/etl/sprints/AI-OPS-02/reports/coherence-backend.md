# Coherence Backend (AI-OPS-02)

Objetivo: exponer drill-down de coherencia `says vs does` por `topic_set_id`, `topic_id`, `scope`, con conteos auditables y acceso a filas de evidencia por bucket.

## Endpoint 1: grupos de coherencia

Ruta:

```http
GET /api/topics/coherence
```

Query params:
- `as_of_date` (opcional, `YYYY-MM-DD`; default: max disponible en `topic_positions` para `votes/declared`)
- `topic_set_id` (opcional)
- `topic_id` (opcional)
- `scope` (opcional; compara en minusculas)
- `limit` (opcional, default `200`)
- `offset` (opcional, default `0`)

Respuesta (shape):

```json
{
  "meta": {
    "db_path": "etl/data/staging/politicos-es.db",
    "generated_at": "2026-02-16T10:35:00+00:00",
    "as_of_date": "2026-02-12"
  },
  "filters": {
    "topic_set_id": null,
    "topic_id": null,
    "scope": ""
  },
  "summary": {
    "groups_total": 1,
    "overlap_total": 2,
    "explicit_total": 2,
    "coherent_total": 1,
    "incoherent_total": 1,
    "coherence_pct": 0.5,
    "incoherence_pct": 0.5
  },
  "page": {
    "limit": 200,
    "offset": 0,
    "returned": 1
  },
  "groups": [
    {
      "topic_set_id": 1,
      "topic_set_name": "Set Coherence Demo",
      "topic_id": 1,
      "topic_label": "Demo coherence topic",
      "scope": "nacional",
      "overlap_total": 2,
      "explicit_total": 2,
      "coherent_total": 1,
      "incoherent_total": 1,
      "coherence_pct": 0.5,
      "incoherence_pct": 0.5
    }
  ]
}
```

Notas:
- `overlap_total`: pares con posicion `votes` y `declared`.
- `explicit_total`: subset donde ambos lados estan en `support|oppose`.
- `coherent_total`: `support/support` o `oppose/oppose`.
- `incoherent_total`: `support/oppose` o `oppose/support`.
- `scope` se resuelve por `admin_level` del par y fallback a `topic_set.admin_level`.

## Endpoint 2: evidencia por bucket (drill-down)

Ruta:

```http
GET /api/topics/coherence/evidence
```

Query params:
- `bucket` (requerido/por default `incoherent`): `overlap|explicit|coherent|incoherent`
- `as_of_date` (opcional, `YYYY-MM-DD`)
- `topic_set_id` (opcional)
- `topic_id` (opcional)
- `scope` (opcional)
- `person_id` (opcional)
- `limit` (opcional, default `100`)
- `offset` (opcional, default `0`)

Respuesta (shape):

```json
{
  "meta": {
    "db_path": "etl/data/staging/politicos-es.db",
    "generated_at": "2026-02-16T10:35:10+00:00",
    "as_of_date": "2026-02-12"
  },
  "filters": {
    "bucket": "incoherent",
    "topic_set_id": 1,
    "topic_id": 1,
    "scope": "nacional",
    "person_id": null
  },
  "summary": {
    "pairs_total": 1,
    "evidence_total": 2
  },
  "page": {
    "limit": 100,
    "offset": 0,
    "returned": 2
  },
  "rows": [
    {
      "evidence_id": 4,
      "topic_set_id": 1,
      "topic_set_name": "Set Coherence Demo",
      "topic_id": 1,
      "topic_label": "Demo coherence topic",
      "person_id": 1,
      "person_name": "Persona Incoherente",
      "scope": "nacional",
      "does_stance": "support",
      "says_stance": "oppose",
      "evidence_type": "declared:intervention",
      "evidence_date": "2026-02-12",
      "evidence_stance": "oppose",
      "evidence_polarity": -1,
      "evidence_confidence": 0.9,
      "topic_method": "fixture",
      "stance_method": "declared:regex_v3",
      "source_id": "congreso_intervenciones",
      "source_url": "https://example.invalid/evidence",
      "source_record_pk": null,
      "excerpt": "declared:intervention for 1"
    }
  ]
}
```

Error esperado para bucket invalido:

```json
{
  "error": "Parametro 'bucket' invalido: 'unknown'. Valores validos: coherent, explicit, incoherent, overlap"
}
```
