# Encargos a subagentes (tal cual)

Mensajes con los que el agente principal (Claude Opus 5.5) lanzó cada tipo de subagente (modelo `sonnet` = Claude Sonnet 5.5) el 2026-10-12. Se muestra uno por tipo: los demás lotes solo cambian el número de lote. `<scratchpad>` sustituye la ruta temporal local donde estaban los lotes de entrada y salida.

## Bullets batch text_01 (2026-10-12 06:52 UTC, modelo `sonnet`)

```text
Lee y sigue al pie de la letra las instrucciones de <scratchpad>/batches/INSTRUCTIONS.md.
Lote de entrada: <scratchpad>/batches/text_01.json
Fichero de salida: <scratchpad>/bullets/text_01.json
No uses la red. No toques el repositorio.
```

## Bullets redo batch (2026-10-12 07:21 UTC, modelo `sonnet`)

```text
Lee y sigue al pie de la letra las instrucciones de <scratchpad>/batches/INSTRUCTIONS.md (incluida la sección de fase 2).
Lote de entrada: <scratchpad>/batches/redo_01.json
Fichero de salida: <scratchpad>/bullets/redo_01.json
Nota específica para el documento 3689aeae71cc (BOCG-15-B-33-2, votación de conjunto de una reforma del Reglamento del Congreso que modifica su artículo 46.1): ese PDF reúne varias publicaciones (toma en consideración, enmiendas —incluida una enmienda a la totalidad con texto alternativo— y el texto aprobado por el Pleno). Localiza el texto aprobado/definitivo de la reforma del artículo 46.1 (busca «46.1», «Aprobación», «texto aprobado», «Pleno») y resume eso, no las enmiendas; si de verdad no hay texto aprobado en el documento, resume la proposición tomada en consideración y dilo en notes. Ninguna salida puede quedar con bullets vacías salvo que el texto no exista.
No uses la red. No toques el repositorio. Escribe el fichero con la herramienta Write.
```

## Review curated bullets 01 (2026-10-12 08:10 UTC, modelo `sonnet`)

```text
Lee y sigue al pie de la letra <scratchpad>/batches/REVIEW_INSTRUCTIONS.md.
Entrada: <scratchpad>/batches/review_01.json
Salida: <scratchpad>/bullets_review/review_01.json
No uses la red. No toques el repositorio. Escribe con la herramienta Write.
```

## Review pool bullets 01 (2026-10-12 08:47 UTC, modelo `sonnet`)

```text
Lee y sigue al pie de la letra <scratchpad>/batches/REVIEW_INSTRUCTIONS.md. Aquí no hay afirmación curada: la pregunta es el título de la votación (`vote_title`, ya sin proponente) y las viñetas deben decir qué contenía el texto. En PNL y mociones el texto ya es solo la parte dispositiva literal.
Entrada: <scratchpad>/batches/review_pool_01.json
Salida: <scratchpad>/bullets_review/review_pool_01.json
No uses la red. No toques el repositorio. Escribe con la herramienta Write.
```

## Review fixed menopause PNL (2026-10-12 08:59 UTC, modelo `sonnet`)

```text
Lee y sigue al pie de la letra <scratchpad>/batches/REVIEW_INSTRUCTIONS.md. No hay afirmación curada; el texto es solo la parte dispositiva literal aprobada (9 puntos). Las viñetas actuales se escribieron con un texto cortado en el punto 7: asegúrate de cubrir también los puntos 8 y 9 (máx. 6 viñetas, agrupa si hace falta).
Entrada: <scratchpad>/batches/review_fix_01.json
Salida: <scratchpad>/bullets_review/review_fix_01.json
No uses la red. No toques el repositorio. Escribe con la herramienta Write.
```

## Claims review batch0 A — revisor A del lote 0; hubo 6 lotes × 2 revisores (A y B) (2026-10-12 12:00 UTC, modelo `sonnet`)

```text
Read <scratchpad>/claims/PROMPT.md and follow it exactly with these substitutions: INPUT_FILE=<scratchpad>/claims/batch0.json, OUTPUT_FILE=<scratchpad>/claims/review_0_A.json, REVIEWER=0A. Working directory for commands: <repo> (read-only).
```

## Draft bullets for 6 votes (2026-10-12 12:01 UTC, modelo `sonnet`)

```text
Lee y sigue exactamente <scratchpad>/batches/INSTRUCTIONS.md (incluidas las «Notas para la fase 2»).

Entrada: <scratchpad>/p3/p3_input.json (6 documentos).
Salida: <scratchpad>/p3/p3_draft.json

Además de lo que piden las instrucciones, añade en cada elemento un campo "simple": las mismas viñetas resumidas en UNA sola frase llana (≤180 caracteres), sin añadir nada que no digan, sin partidos ni resultado.

Notas por tipo: «toma» = toma en consideración de una proposición (texto inicial: usa el condicional, «se permitiría…»); «final» = votación de conjunto de un proyecto en lectura única (el texto es el aprobado por el Pleno; si solo actualiza cifras o cupos de un concierto/convenio económico, di en lenguaje llano qué impuestos o cifras cambian según el articulado). Para la reforma del Reglamento del Congreso y la reforma constitucional (artículo 69.3), explica en llano qué cambiaría. No uses la red; no toques el repositorio.
```

## Review bullets for 6 votes (2026-10-12 12:03 UTC, modelo `sonnet`)

```text
Lee y sigue exactamente <scratchpad>/batches/REVIEW_INSTRUCTIONS.md.

Entrada: <scratchpad>/p3/p3_review_input.json (6 documentos; aquí `votes` no trae afirmación curada, solo tipo y título).
Salida: <scratchpad>/p3/p3_review.json

Además: revisa también el campo "simple" (una frase ≤180 caracteres que resume las viñetas sin añadir nada) y devuélvelo final en cada elemento como "simple". Atención especial: (1) en la reforma del Reglamento, el redactor dedujo «rebaja de 15 % y 5 % a 10 % y 3 %» comparando con el Reglamento vigente, que NO está en el texto: una viñeta solo puede decir lo que dice el documento (si el documento no da el umbral anterior, quita la comparación y di solo el nuevo umbral); (2) en el Estatuto del Empleado Público el texto viene truncado con «[...]»: no afirmes nada sobre lo omitido; (3) usa el condicional en las tomas en consideración (proposiciones).
```

