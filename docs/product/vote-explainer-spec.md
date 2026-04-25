# Vote explainer spec

Estado: `v1`
Fecha: `2026-04-04`

## Objetivo

Definir una pagina publica y compartible que responda, para **una votacion concreta**:

- que se voto,
- que paso en esa votacion,
- como votaron los grupos relevantes,
- donde estan las fuentes oficiales,
- y que caveats limitan la lectura.

Esta spec implementa el wedge principal definido en `docs/product/killer-use-case.md` y debe respetar el contrato de `docs/method/truth-contract.md`.

## Alcance del MVP

El MVP debe funcionar **solo con datos de votaciones ya existentes**.

Eso significa:

- usar el stack actual de `parl_vote_events`, `parl_vote_event_initiatives`, `parl_vote_member_votes` y snapshots/public exports equivalentes;
- no depender de la capa `declared`;
- no depender de `reviewed_implications` para abrir la pagina, porque hoy el snapshot publicado devuelve `0`;
- no exigir member roll-call detallado en la primera version si la pagina ya puede explicar bien el resultado a nivel de grupos.

## No objetivos del MVP

- no construir una home o ranking de votaciones;
- no resolver "dice vs hace" en esta pagina;
- no explicar el articulado completo de una ley omnibus;
- no convertir la pagina en un opinionador con framing editorial fuerte;
- no depender de APIs server-side para render minimo en GH Pages.

## Usuario y job to be done

Usuario principal:

- ciudadania esceptica con mentalidad de verificacion

Job to be done:

- "Quiero abrir una pagina de una votacion concreta, entender rapido que se voto y poder contrastarlo con la fuente oficial sin saltar entre varias tablas."

## Fuente de datos actual disponible

Base observada hoy en `docs/gh-pages/explorer-votaciones/data/votes-preview.json`:

- `meta.total = 502`
- `meta.returned = 200`
- eventos de `congreso_votaciones` y `senado_votaciones`
- cada evento expone:
  - `vote_event_id`
  - `source_id`
  - `source_name`
  - `source_url`
  - `vote_date`
  - `title`
  - `expediente_text`
  - `subgroup_title`
  - `subgroup_text`
  - `assentimiento`
  - `initiative`
  - `totals`
  - `group_breakdown`
  - `party_participation` opcional
  - `citizen_implication` opcional

La pagina debe diseñarse contra este contrato, no contra campos hipoteticos inexistentes.

## Ruta canonica

### Decision de routing

La ruta publica **no** debe usar `vote_event_id` crudo como segmento de URL porque hoy algunos IDs contienen valores inseguros para path, por ejemplo:

- `url:https://...`
- IDs con `:` o strings largas derivadas de origen

### Ruta MVP obligatoria

- `/vote-explainer/<public_vote_id>/`

### Identificador publico

`public_vote_id` debe ser un slug estable, determinista y seguro para path.

Formato recomendado:

- `<source_id>--<yyyymmdd>--<short_hash>`

Donde:

- `source_id` viene de `event.source_id`
- `yyyymmdd` viene de `vote_date`
- `short_hash = sha1(vote_event_id)[0:10]`

Ejemplo:

- `senado_votaciones--20240508--4b13d82a11`

### Identidad canonica real

La identidad de auditoria sigue siendo:

- `vote_event_id`

El JSON y la pagina deben exponer ambos:

- `public_vote_id` para compartir y ruta
- `vote_event_id` para trazabilidad tecnica

### Rutas opcionales no canonicas

Aceptables solo como ayuda tecnica o dev:

- `/vote-explainer/?event=<urlencoded_vote_event_id>`

Regla:

- nunca usar query-string-only como URL compartible principal porque empeora SEO, OG crawlers y estabilidad de metadatos en un sitio estatico.

## Estructura de pagina

La pagina debe tener, en este orden:

### 1. Hero/resumen

Debe responder en el primer viewport:

- titulo entendible del voto
- camara (`Congreso` o `Senado`)
- fecha
- resultado resumido
- fuente oficial principal
- badge de caveats/frescura

### 2. Que se votaba

Bloque textual corto con:

- `initiative.title` si existe
- si no existe, `title`
- `expediente`
- `subgroup_title` o `subgroup_text` si la votacion es una subparte, enmienda o tramo concreto

Regla:

- si la votacion es solo una parte de un expediente, debe decirse explicitamente

Copy recomendado:

- `Esta pagina resume esta votacion concreta, no todo el expediente.`

### 3. Que paso

Bloque de resultado con:

- `Sí`, `No`, `Abstención`, `No vota`
- total de presentes
- etiqueta de resultado
- nota de confianza del resultado si fue derivado y no explicitamente emitido por fuente

### 4. Como votaron los grupos

Bloque obligatorio con:

- tabla o barras por `group_breakdown`
- top 5 grupos como minimo
- enlace a explorer para auditoria

MVP:

- grupos parlamentarios obligatorios
- member roll-call individual opcional

### 5. Fuentes oficiales y documentos

Bloque con:

- `source_url` del evento cuando exista
- `initiative.url` cuando exista
- documentos ligados a la iniciativa (`initiative.documents.docs`) cuando existan

### 6. Caveats metodologicos

Bloque obligatorio con badges/copy para:

- iniciativa no enlazada
- resultado derivado automaticamente
- falta de URL oficial del evento
- snapshot con frescura `aging` o `stale`
- lectura parcial porque la votacion es una sub-votacion o enmienda

### 7. Auditoria / drill-down

Bloque final con enlaces a:

- explorer de votaciones
- explorer de evidencia o temas cuando aplique
- source URLs oficiales

## Reglas de resultado

La pagina debe responder "que paso" de forma conservadora.

### Campos del resultado

- `result_status`
- `result_label`
- `result_confidence`
- `result_summary_text`

### Valores permitidos para `result_status`

- `approved`
- `rejected`
- `assent`
- `tie_or_unclear`
- `unknown`

### Regla de derivacion para MVP

1. Si `assentimiento` indica aprobacion por asentimiento:
   - `result_status = assent`
   - `result_label = Aprobada por asentimiento`
   - `result_confidence = high`

2. Si no hay asentimiento y `yes > no`:
   - `result_status = approved`
   - `result_label = Aprobada en esta votacion`
   - `result_confidence = medium`

3. Si no hay asentimiento y `no > yes`:
   - `result_status = rejected`
   - `result_label = Rechazada en esta votacion`
   - `result_confidence = medium`

4. Si no puede derivarse de forma segura:
   - `result_status = unknown`
   - `result_label = Resultado no derivable automaticamente`
   - `result_confidence = low`

Regla editorial:

- cuando `result_confidence != high`, la pagina debe dejar claro que el resultado esta inferido de esta votacion concreta y debe contrastarse con la fuente oficial.

## Contrato de caveats

El vote explainer debe usar el truth contract y añadir caveats especificos de voto.

### Codigos minimos

- `aging_snapshot`
- `stale_snapshot`
- `future_snapshot`
- `initiative_missing`
- `event_source_url_missing`
- `derived_result`
- `subvote_not_whole_file`
- `group_breakdown_partial`

### Severidades

- `info`
- `warn`
- `block`

### Regla de bloqueo

La pagina no debe ocultarse por:

- `initiative_missing`
- `event_source_url_missing`

Pero si debe bloquear claims concluyentes cuando:

- `freshness_tier in (future, unknown)`

## Contrato JSON

La pagina y cualquier share card deben renderizar desde un JSON por voto.

### Ruta de artefacto recomendada

- `docs/gh-pages/vote-explainer/data/<public_vote_id>.json`

### Contrato v1

```json
{
  "meta": {
    "schema_version": "vote_explainer_v1",
    "public_vote_id": "senado_votaciones--20240508--4b13d82a11",
    "vote_event_id": "url:https://www.senado.es/legis15/votaciones/ses_19_179.xml",
    "canonical_path": "/vote-explainer/senado_votaciones--20240508--4b13d82a11/",
    "generated_at": "2026-04-04T12:00:00+00:00",
    "snapshot_as_of_date": "2026-02-16",
    "source_snapshot_path": "/explorer-votaciones/data/votes-preview.json",
    "static_snapshot": true
  },
  "event": {
    "source_id": "senado_votaciones",
    "source_name": "Senado - Votaciones",
    "source_url": "https://www.senado.es/legis15/votaciones/ses_19.xml",
    "chamber": "Senado",
    "vote_date": "2024-05-08",
    "title": "Resto del proyecto de ley",
    "expediente_text": "Proyecto de Ley por la que se regulan las enseñanzas artísticas superiores...",
    "subgroup_title": "",
    "subgroup_text": "",
    "assentimiento": ""
  },
  "result": {
    "status": "approved",
    "label": "Aprobada en esta votacion",
    "confidence": "medium",
    "summary_text": "Sí 238 · No 7 · Abstención 12 · No vota 4"
  },
  "totals": {
    "present": 261,
    "yes": 238,
    "no": 7,
    "abstain": 12,
    "no_vote": 4
  },
  "initiative": {
    "initiative_id": "senado:leg15:exp:621/000001",
    "expediente": "621/000001",
    "title": "Proyecto de Ley por la que se regulan las enseñanzas artísticas superiores...",
    "grouping": "Votaciones por iniciativa (Senado)",
    "procedure_type": "",
    "current_status": "",
    "url": "https://www.senado.es/web/ficopendataservlet?tipoFich=9&legis=15",
    "confidence": 1.0,
    "documents": {
      "total": 5,
      "by_kind": {
        "bocg": 2,
        "ds": 3
      },
      "docs": [
        {
          "kind": "bocg",
          "url": "https://www.senado.es/...",
          "downloaded": false
        }
      ]
    }
  },
  "groups": [
    {
      "group_code": "GP",
      "yes": 0,
      "no": 136,
      "abstain": 0,
      "no_vote": 1,
      "other": 0,
      "total": 137
    }
  ],
  "citizen_implication": null,
  "caveats": [
    {
      "code": "derived_result",
      "severity": "warn",
      "label": "Resultado derivado",
      "detail": "El resultado se infiere de los totales de esta votacion concreta."
    }
  ],
  "audit_links": {
    "explorer_votaciones": "/explorer-votaciones/?q=url%3Ahttps%3A%2F%2Fwww.senado.es%2Flegis15%2Fvotaciones%2Fses_19_179.xml",
    "explorer_source": "https://www.senado.es/legis15/votaciones/ses_19.xml",
    "initiative_url": "https://www.senado.es/web/ficopendataservlet?tipoFich=9&legis=15"
  },
  "social": {
    "title": "¿Que se voto? Resto del proyecto de ley | Vota Con La Chola",
    "description": "Senado · 2024-05-08 · Sí 238 · No 7 · Abstención 12. Fuente oficial y caveats visibles.",
    "canonical_url": "https://gsusI.github.io/vota-con-la-chola/vote-explainer/senado_votaciones--20240508--4b13d82a11/"
  }
}
```

## Campos obligatorios vs opcionales

### Obligatorios MVP

- `meta.public_vote_id`
- `meta.vote_event_id`
- `meta.canonical_path`
- `event.source_id`
- `event.vote_date`
- `event.title` o `event.expediente_text`
- `totals`
- `groups`
- `caveats`
- `audit_links`
- `social.title`
- `social.description`

### Opcionales MVP

- `initiative`
- `citizen_implication`
- documentos descargados
- roll-call nominal individual

## Reglas de render

### Titulo principal

Prioridad:

1. `initiative.title`
2. `event.title`
3. `event.expediente_text`
4. `vote_event_id`

### Subtitulo

Prioridad:

1. `event.subgroup_title`
2. `event.subgroup_text`
3. `initiative.expediente`

### Fuente oficial primaria

Prioridad:

1. `event.source_url`
2. `initiative.url`
3. URL parseada desde `vote_event_id` si el ID empieza por `url:`
4. explorer de votaciones como ultimo fallback

### Camara

Derivar de `source_id`:

- `congreso_votaciones` -> `Congreso`
- `senado_votaciones` -> `Senado`
- otro -> `Institucion parlamentaria`

## Metadatos sociales

La pagina debe tener metadata pre-renderizada por voto. No basta con cambiar `<title>` en cliente.

### Requeridos

- `title`
- `description`
- `alternates.canonical`
- `openGraph.title`
- `openGraph.description`
- `openGraph.url`
- `twitter.card`
- `twitter.title`
- `twitter.description`

### Recomendados

- `openGraph.images`
- `twitter.images`

### Plantillas de copy

#### Title

- `¿Que se votó? <headline corto> | Vota Con La Chola`

#### Description

- `<Camara> · <fecha> · <resultado corto>. Fuente oficial y caveats visibles.`

Ejemplo:

- `Senado · 2024-05-08 · Sí 238, No 7, Abstención 12. Fuente oficial y caveats visibles.`

#### OG/Twitter image

Si existe imagen:

- incluir fecha, camara, headline, totales y badge de caveat principal

Si no existe imagen aun:

- usar imagen fallback del sitio sin bloquear el MVP

## Estados vacios y errores

### Vote not found

Mensaje:

- `No encontramos esa votacion en el snapshot publico actual.`

Acciones:

- enlace a `/explorer-votaciones/`
- enlace al obstruction tracker si el source esta degradado o missing

### Votacion encontrada pero incompleta

Mensaje:

- `La votacion existe, pero faltan piezas para una lectura completa.`

Mostrar:

- lo que si se sabe
- caveats visibles
- enlaces de auditoria

## Definition of Done para la implementacion posterior

La tarea de implementacion del MVP (`TODO 10`) estara completa cuando:

1. exista al menos una ruta publica canonica `/vote-explainer/<public_vote_id>/`
2. la pagina responda claramente:
   - que se voto
   - que paso
   - como votaron los grupos
   - donde estan las fuentes oficiales
   - que caveats aplican
3. el contenido se renderice desde un JSON reproducible y versionado
4. la pagina funcione sin API server-side en GH Pages
5. el share metadata este pre-renderizado por voto
6. haya pruebas del contrato minimo del JSON y del routing canonico

## Decisiones abiertas

- si el MVP usara una sola votacion hardcoded de demo o varias paginas generadas desde snapshot
- si se añadira OG image especifica en el mismo slice o como follow-up
- si el member roll-call nominal entra en MVP o se deja para una segunda iteracion
