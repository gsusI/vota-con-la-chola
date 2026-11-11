# Prompt: tabla de escaños por elección (Congreso y Senado elegido), desde la Junta Electoral Central en el BOE

Objetivo: una tabla con fuente oficial para calcular mayorías de 3/5 y 2/3. No atribuyas nada: solo cuenta escaños.

Entrada: `docs/etl/sprints/DEMOCRACIA-SISTEMA-20261111/worklists/seats_jec_windows.json`, una fila por elección
(1989-2023) con el acuerdo de la JEC en el BOE (`boe_ref`, `pdf_url`) y, ya extraído:
- 2011-2023: `congress_count_from_list` y `senate_elected_count_from_list` (recuento de electos por candidatura de la
  relación nominal; `_unparsed` = líneas que el script no supo leer: resuélvelas con `kit grep`).
- 1989-2008: `total_windows`, texto de las filas «Total estatal» de los cuadros (PDF escaneado con ruido de OCR).
  1996 no tiene ventanas y 2008 tiene la lista incompleta (197 diputados): lee esos dos con `kit grep`.
Herramientas: `python3 scripts/export_public_viz_democracy.py kit grep <pdf_url> "<regex>" --context 400 --max 3`
(caché local, pdftotext). Las correcciones de errores posteriores de la JEC existen (búscalas con
`kit boe-search "corrección de errores resultados elecciones Congreso" --year-from AAAA --year-to AAAA+1`) y prevalecen.
Si el OCR no deja leer una cifra, usa la corrección de errores o el cuadro por circunscripciones; si aun así no, deja
la elección con `"status": "incompleta"` y dilo. No uses fuentes no oficiales para las cifras.

Salida: escribe `etl/data/seeds/democracy_safeguards_v1.d/seats.json`:
```json
{"families": {"PSOE": ["PARTIDO SOCIALISTA OBRERO ESPAÑOL", "PARTIT DELS SOCIALISTES DE CATALUNYA (PSC-PSOE)", "…"],
              "PP": ["PARTIDO POPULAR", "PP-UPN …", "…"], "…": ["…"]},
 "elections": [
   {"election": "2023-07-23", "legislature": "XV", "boe_ref": "BOE-A-2023-18907",
    "url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2023-18907", "corrections": ["BOE-A-2023-19537"],
    "congress": {"PP": 137, "PSOE": 121, "…": 0}, "congress_total": 350,
    "senate_elected": {"PP": 120, "…": 0}, "senate_elected_total": 208,
    "status": "completa|incompleta", "notes": "coaliciones y cómo se asignaron a familias"}]}
```
- Familias por marca electoral (PSOE con PSC y federaciones; PP con sus listas regionales y coaliciones en que el PP
  encabeza; UPN, CC, PNV, ERC, Junts/CiU, Bildu/Amaiur/HB, BNG, IU, Podemos/UP, Sumar (y sus listas), Ciudadanos, Vox,
  UPyD, «otros»). Si una coalición mezcla marcas (p. ej. PP-UPN en Navarra, Compromís-Sumar), asígnala a la que la
  encabeza y dilo en `notes`. Conserva el recuento por candidatura en `congress_candidacies` / `senate_candidacies`.
- Legislaturas: 1989 IV, 1993 V, 1996 VI, 2000 VII, 2004 VIII, 2008 IX, 2011 X, 2015 XI, 2016 XII, 2019-04 XIII,
  2019-11 XIV, 2023 XV.
- `congress_total` debe ser 350 y `senate_elected_total` 208 (comprueba; si no cuadra, `status: incompleta`).
- El Senado tiene además senadores designados por las comunidades (fuera de este documento): no los inventes.

Presupuesto: ≤ 40 llamadas, nunca más de 3.000 caracteres por salida, sin WebSearch. Informe final ≤ 5 líneas, con las
elecciones incompletas y «qué herramienta o dato me habría ahorrado turnos».
