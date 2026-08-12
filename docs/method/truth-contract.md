# Truth contract

Estado: `v1`
Fecha: `2026-04-04`

## Objetivo

Este documento define el contrato publico de verdad para las superficies ciudadanas del proyecto, empezando por:

- `/citizen`
- `/citizen/leaderboards`
- el futuro **vote explainer**
- cualquier tarjeta o ranking que resuma postura, coherencia, cobertura o frescura

La regla base es simple:

- **una interfaz bonita no puede ocultar insuficiencia de evidencia**

## Fuentes canonicas revisadas

- `docs/product/killer-use-case.md`
- `docs/preguntas-metodologia-citizen.md`
- `docs/audits/public-claims-audit.md`
- `docs/gh-pages/legacy/citizen/data/citizen.json`
- `docs/gh-pages/legacy/citizen/data/citizen_votes.json`
- `docs/gh-pages/legacy/citizen/data/citizen_declared.json`
- `ui/citizen/index.html`
- `ui/citizen/leaderboards.html`
- `scripts/export_citizen_snapshot.py`
- `docs/method/integrity-signal-policy.md`

## Principios no negociables

1. **Metodo explicito siempre**
   - Todo porcentaje, ranking o lectura debe indicar si usa `combined`, `votes` o `declared`.

2. **No imputacion silenciosa**
   - Si falta senal o comparabilidad, el estado mostrado debe reflejarlo como `unclear`, `no_signal` o `unknown`.

3. **Evidencia antes que opinion**
   - Cada conclusion publica debe enlazar a evidencia primaria o a un drill-down trazable.

4. **La confianza no sustituye a la cobertura**
   - Un score alto con muestra o cobertura insuficiente no autoriza una lectura fuerte.

5. **La frescura es parte del resultado**
   - Un snapshot viejo o temporalmente inconsistente debe seguir viendose, pero con advertencia o bloqueo segun el caso.

6. **La identidad publica no se oculta**
   - Todo dato personal publicado por una fuente oficial se conserva con URL, checksum y lineage. La clasificacion de entidad no autoriza supresion. Solo se bloquean secretos, estado local/no publico y trazas de workstation.

## Metodos publicos

### `combined`

- Etiqueta publica: `combinado`
- Regla: usa `votes` si existe; si no, usa `declared`
- Importante: **no es una media ponderada**

### `votes`

- Etiqueta publica: `votos`
- Regla: sintetiza solo evidencia revelada por voto

### `declared`

- Etiqueta publica: `dichos`
- Regla: sintetiza solo evidencia declarativa/textual

## Estados de postura

| Codigo | Etiqueta publica | Significado | Cuando debe mostrarse |
|---|---|---|---|
| `support` | `A favor` | La direccion observada favorece la medida o el tema en el recorte actual | Solo cuando hay senal clara y comparable |
| `oppose` | `En contra` | La direccion observada se opone a la medida o el tema en el recorte actual | Solo cuando hay senal clara y comparable |
| `mixed` | `Mixto` | Hay señales en direcciones distintas dentro del mismo recorte | Mostrar como estado propio, no forzar a favor/en contra |
| `unclear` | `Incierto` | Existe alguna senal, pero no alcanza comparabilidad suficiente o la direccion no es estable | Mostrar cuando hay evidencia parcial o cobertura insuficiente |
| `no_signal` | `Sin señal` | No hay evidencia util suficiente para emitir una lectura | Mostrar cuando no hay base para clasificar |
| `unknown` | `Unknown` | Estado paraguas para `unclear + no_signal` | Usar solo como resumen agregado o metrica de incertidumbre, no como sustituto de los estados atomicos |

## Definiciones publicas obligatorias

Estas frases deben mantenerse estables salvo versionado explicito del contrato:

- `unknown = incierto + sin_senal`
- `match/mismatch solo cuentan cuando hay senal clara comparable`
- `si ves unknown alto o confianza baja, abre la evidencia enlazada`
- `No se imputan estimaciones para faltantes`

## Etiquetas de confianza

Las etiquetas de confianza publicas se derivan de `meta.quality.confidence_thresholds` del snapshot:

- `alta`: `confidence >= 0.66`
- `media`: `0.33 <= confidence < 0.66`
- `baja`: `0 < confidence < 0.33`
- `sin_confianza_util`: `confidence = 0` o `stance = no_signal`

Reglas:

- La confianza se muestra como **calidad de la lectura**, no como probabilidad de verdad absoluta.
- `alta` nunca puede convertir `unclear` o `no_signal` en una lectura fuerte.
- Si el estado es `mixed`, la confianza puede mostrarse, pero no debe colorearse como si fuera una postura clara.

## Gating de cobertura y muestra

### 1. Gating de celda tema-partido

Definicion:

- `coverage_signal_ratio = members_with_signal / members_total`

Regla obligatoria:

- si `coverage_signal_ratio < 0.20`, la interfaz debe mostrar **`Incierto`**

Texto publico recomendado:

- `Regla: si cobertura < 20%, mostramos Incierto`

Interpretacion:

- menos del `20%` de senal util dentro del partido no permite una lectura fuerte por tema
- esta regla aplica aunque exista algo de evidencia

Fallbacks:

- si `members_total = 0` o falta metadata equivalente: mostrar `Sin señal`
- si el ratio es `>= 0.20` pero la direccion sigue siendo contradictoria o debil: mantener `Mixto` o `Incierto`

### 2. Gating de match/mismatch

`match` y `mismatch` solo se permiten cuando:

- ambos lados comparados tienen estado claro (`support` o `oppose`)
- el recorte es comparable
- no se cruza un metodo con otro sin declararlo

No se debe computar ni mostrar `match/mismatch` sobre:

- `mixed`
- `unclear`
- `no_signal`

### 3. Gating de rankings e hipotesis

Para rankings tipo H1/H2 y cualquier tabla ordenada que dependa de comparables:

- **ocultar ranking** si `comparables < 5`
- **mostrar con warning / grisado** si `5 <= comparables < 40`
- **mostrar normal** si `comparables >= 40`

Estos umbrales vienen del comportamiento actual de `ui/citizen/leaderboards.html`:

- `H1_MIN_COMPARABLES = 5`
- `H1_WARN_TOTAL_COMPARABLES = 40`

Definicion de estados visuales:

- `ocultar` = no ordenar ni presentar como leaderboard concluyente; mostrar placeholder explicativo
- `grisado` = renderizar, pero con badge y copy de lectura exploratoria

Copy obligatoria:

- oculto: `Ranking oculto: la muestra comparable no alcanza el minimo para una lectura responsable.`
- grisado: `Lectura exploratoria: la muestra comparable sigue siendo debil y puede cambiar mucho con nueva evidencia.`

## Estados de frescura

Los estados de frescura del snapshot se derivan de `generated_at` y `as_of_date` y ya estan implementados en `scripts/export_citizen_snapshot.py`.

| Tier | Rango | Etiqueta publica | should_warn | Uso recomendado |
|---|---|---|---|---|
| `fresh` | `0-7` dias | `reciente` | `false` | Mostrar sin warning adicional |
| `aging` | `8-30` dias | `vigente` | `true` | Mostrar con advertencia de antigüedad |
| `stale` | `>30` dias | `antigua` | `true` | Mostrar con advertencia fuerte y de-emphasis |
| `future` | `generated_at < as_of_date` | `futura` | `true` | No usar para rankings; tratar como inconsistencia |
| `unknown` | fechas faltantes o invalidas | `desconocida` | `true` | No usar para afirmaciones fuertes ni rankings concluyentes |

## Reglas de visualizacion por frescura

- `fresh`: mostrar normal
- `aging`: mostrar normal pero con badge y texto explicito de advertencia
- `stale`: mostrar grisado + advertencia fuerte
- `future`: ocultar ranking y bloquear claims concluyentes hasta corregir metadata
- `unknown`: ocultar ranking y mostrar explicacion de inconsistencia

Copy recomendado:

- `reciente`: `reciente · sin advertencia de antigüedad`
- `aging`: `vigente · con advertencia de antigüedad (${data_age_days} días) por no refresco reciente`
- `stale`: `antigua · la evidencia puede haber cambiado de forma material desde el corte (${data_age_days} días)`
- `future`: `futura · inconsistencia temporal detectada; no usar para rankings hasta corregir el snapshot`
- `unknown`: `desconocida · faltan fechas consistentes para evaluar la frescura`

## Cuando grisar y cuando ocultar

### Grisar

Se debe grisar una tarjeta, comparativa o ranking cuando:

- `freshness_tier` es `aging` o `stale`
- la muestra comparable existe pero cae en zona de warning (`5-39`)
- la confianza agregada es baja y el `unknown` sigue alto

Grisar significa:

- mantener la superficie visible
- reducir enfasis visual
- añadir badge o copy de cautela
- evitar lenguaje concluyente

### Ocultar

Se debe ocultar el ranking o sustituirlo por placeholder explicativo cuando:

- `comparables < 5`
- `freshness_tier` es `future` o `unknown`
- el metodo seleccionado no tiene base suficiente para sostener el orden presentado

Ocultar significa:

- no renderizar posicion ordinal concluyente
- mostrar razon y siguiente accion del usuario

## Copy exacta para insuficiencia de evidencia

Estas frases deben usarse tal cual o con variantes minimas de estilo:

### Falta de senal

- `Sin señal: no encontramos evidencia suficiente del método seleccionado para este partido y tema.`

### Senal parcial o poco comparable

- `Incierto: existe alguna señal, pero no alcanza comparabilidad suficiente para una lectura fuerte.`

### Mezcla de direcciones

- `Mixto: hay señales en direcciones distintas dentro del mismo recorte.`

### Match/mismatch no computable

- `No comparable todavía: falta señal clara en uno o ambos lados de la comparación.`

### Ranking oculto

- `Ranking oculto: la muestra comparable no alcanza el mínimo para una lectura responsable.`

### Ranking exploratorio

- `Lectura exploratoria: la muestra comparable sigue siendo débil y puede cambiar mucho con nueva evidencia.`

### Aviso de frescura

- `La señal no es de última hora; prioriza abrir evidencia en partidos con unknown alto o confianza baja.`

## Consecuencias practicas para el wedge principal

Para el **vote explainer** elegido en `docs/product/killer-use-case.md`, este contrato implica:

- nunca resumir un voto solo con un badge fuerte si faltan enlaces a fuente oficial
- separar claramente `que paso` de `que podemos afirmar`
- usar las reglas de `freshness`, `coverage` y `confidence` en la misma pagina, no en un pie escondido
- enlazar al obstruction tracker cuando una pieza critica falte por bloqueo de fuente

## Lo que este contrato prohíbe

- ocultar `unknown` para que una tabla parezca mas completa
- mezclar `votes` y `declared` sin etiquetar el metodo
- presentar `match/mismatch` sobre evidencia no comparable
- mantener rankings visibles cuando la muestra o la frescura no lo sostienen
- usar la confianza como sustituto de falta de cobertura
- presentar una anomalía o señal de revisión como corrupción, ilegalidad, intención o culpa personal

## Vinculo con el glosario JSON

La version maquina-legible de este contrato vive en:

- `docs/method/glossary.json`

Si hay divergencia entre ambos archivos, este markdown manda y el JSON debe regenerarse o corregirse.
