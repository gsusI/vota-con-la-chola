# Viñetas «Qué se votaba» — instrucciones para cada lote

Proyecto: ayuda al voto «¿Con quién coincides?» (votaconlachola.org). Cada pregunta es una votación real del Congreso.
Antes de responder, el usuario ve un bloque «Qué se votaba» con **hasta 6 viñetas** en lenguaje llano sobre lo que
concretamente contenía el texto votado. Tu trabajo: leer el texto oficial de cada documento del lote y redactar esas viñetas.

## Entrada
Un fichero JSON (lista). Cada elemento es un documento oficial:
- `doc_key`, `url`, `sha256`, `source` (BOE/BOCG): identifican el documento. Cópialos tal cual en la salida.
- `text_path`: texto plano ya extraído del documento oficial. Léelo con la herramienta Read (o `grep -n` para ver la estructura).
  Si `text_chars` > 60000, NO lo leas entero: localiza la estructura con
  `grep -nE "^(TÍTULO|CAPÍTULO|Artículo|Disposición|Sección)" <text_path> | head -200` y lee solo los tramos relevantes (offset/limit).
- `structure_hint`: encabezados literales ya extraídos (títulos/capítulos/artículos). Ayuda, no sustituye a leer el texto.
- `omnibus`/`themes`: si `omnibus` es true, el texto mezcla varios temas.
- `votes`: las votaciones que usan este texto (tipo: toma = toma en consideración de una proposición de ley; final = votación de
  conjunto; rdl = convalidación de real decreto-ley; pnl = proposición no de ley; mocion = moción; curated = pregunta curada).
  El título puede nombrar al grupo proponente: **no lo repitas nunca**.

## Reglas de redacción (obligatorias)
1. **Fundamentado**: cada viñeta resume algo que está en la parte dispositiva/articulado del texto (no en la exposición de motivos
   ni en el preámbulo, que solo sirven para entender). Nada de inventar cifras, plazos ni efectos que el texto no diga.
2. **Localizador obligatorio** por viñeta: dónde está en el texto, tal como lo nombra el documento: `Artículo 3`, `Artículo único, apartado Dos`,
   `Disposición final segunda`, `Título II`, `Capítulo III`, `Punto 2`, `Apartados 1 a 4`… Debe poder encontrarse en el texto.
3. **Neutral**: no nombres ningún partido ni grupo parlamentario ni a quién lo propuso; nada de adjetivos valorativos
   («histórico», «polémico», «necesario»); no digas si se aprobó o se rechazó. Describe lo que el texto haría/pide.
4. **Lenguaje llano**: frases cortas (máx. ~180 caracteres por viñeta), sin jerga cuando se pueda evitar
   (p. ej. «baja el IVA de X al Y %» mejor que «modifica el artículo 91 de la Ley 37/1992»). Si cambia una ley, di qué cambia en la práctica
   según el propio texto; puedes nombrar la ley afectada si ayuda.
5. **Máximo 6 viñetas** (ideal 3–5). Ordena de lo más importante a lo menos. Para textos ómnibus (`omnibus: true` o muchos bloques),
   cubre los bloques principales, una viñeta por bloque, y si hay cambios en disposiciones finales sobre temas ajenos al título,
   dedica una viñeta a ellos.
6. Si el texto está incompleto, ilegible o no corresponde a la votación, no inventes: devuelve `"bullets": []` y explícalo en `notes`.
7. Para PNL y mociones: los puntos «El Congreso de los Diputados insta al Gobierno a: 1… 2…» son el contenido; resúmelos punto a punto
   (si hay más de 6, agrupa los afines y usa localizadores como `Puntos 5 a 7`). Si `text_status` indica que el texto votado era una
   enmienda transaccional no publicada, redacta igualmente a partir del texto disponible: la interfaz ya avisa.

## Salida
Escribe con la herramienta Write el fichero que te indique el encargo: un JSON con esta forma exacta:

```json
[
  {
    "doc_key": "…",
    "url": "…",
    "sha256": "…",
    "bullets": [
      {"text": "Prorroga hasta el 31 de diciembre de 2025 la suspensión de los desahucios de hogares vulnerables.", "locator": "Artículo 1"}
    ],
    "notes": "opcional: dudas, avisos (p. ej. «el documento es la versión inicial, no el texto final»)"
  }
]
```

Un elemento por documento del lote, en el mismo orden. Comprueba al final que el JSON es válido
(`python3 -c "import json,sys; json.load(open(sys.argv[1]))" <fichero>`). No modifiques ningún otro fichero del repositorio.
Responde al final solo con una línea: número de documentos hechos y cualquier incidencia.

## Notas para la fase 2 (PNL, mociones y leyes enlazadas desde la ficha de la iniciativa)
- En PNL y mociones el `text_path` ya contiene solo la parte dispositiva literal (intro + puntos numerados) y una línea
  «Estado del texto». Localizadores: `Punto 1`, `Puntos 2 y 3`, `Punto 4, letra b)`. Si hay un único punto sin número, usa `Parte dispositiva`.
- Si un punto es muy largo, resume lo concreto que pide (qué, a quién, plazo, cifra) sin añadir nada.
- No copies el nombre del grupo que firma ni el de quien presentó enmiendas aunque aparezca en el texto.
