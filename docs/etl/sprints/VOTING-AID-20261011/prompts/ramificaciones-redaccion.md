# «Ramificaciones» — instrucciones para redactar a quién afecta una votación y qué puede pasar después

Proyecto: ayuda al voto «¿Con quién coincides?» (votaconlachola.org). Una ley describe una regla, pero para juzgarla hace falta
saber a cuánta gente toca y qué consecuencias de primer y segundo orden puede tener. Sin eso, cada cual se queda con lo que le suena.
Tu trabajo: para cada votación del lote, rellenar las tres capas de `etl/data/seeds/voting_aid_vote_impacts_v1.json`,
cada una con su grado de certeza a la vista.

Piloto (2026-10-13): lo redactó el agente principal (Claude Opus 5.5) para 5 votaciones de vivienda, siguiendo exactamente estas reglas.
El validador es `scripts/export_voting_aid_vote_impacts.py` (test `tests/test_export_voting_aid_vote_impacts.py`).

## Entrada
- La votación (`vote_event_id`), sus viñetas «Qué se votaba» ya revisadas (`voting_aid_vote_bullets_v1.json`) y el texto oficial (BOCG/BOE).
- El Diario de Sesiones del Pleno con el debate de esa votación (`https://www.congreso.es/public_oficiales/L15/CONG/DS/PL/DSCD-15-PL-<n>.PDF`;
  el número del Diario no coincide con el de la sesión: comprueba la fecha en la primera página. El Congreso solo sirve los PDF con
  un User-Agent de navegador, como las cabeceras del ETL).
- Las fuentes oficiales de cifras del tema (INE, Banco de España, ministerios, CGPJ, BOE, respuestas parlamentarias del Gobierno…).

## Capa 1 — `facts`: a quién afecta y cuántos son
1. **Solo cifras oficiales**, comprobadas en la fuente (descarga la tabla, el PDF o la API; no copies cifras de prensa).
   Cada dato lleva `text`, `period`, `source` (con tabla o página) y `url`. Nunca escribas un número de memoria.
2. 1 a 3 datos por votación, los que dan escala: cuántos hogares, viviendas, contratos o casos toca, y dónde se concentran.
3. Si la cifra mezcla cosas distintas, sepáralas (p. ej., allanamiento de morada frente a usurpación de pisos vacíos):
   esa distinción suele ser lo que la gente no sabe.
4. Si un dato posterior a la votación cambia su alcance (una sentencia que anula una pieza en la que se apoya), añádelo como dato con su fuente.

## Capa 2 — `direct_effects`: qué cambia para cada colectivo
1. Máx. 4, uno por colectivo (`actor`): inquilinos, propietarios, plataformas, administraciones, ocupantes…
2. Solo lo que dice la parte dispositiva, con `locator` (los mismos artículos que en «Qué se votaba»). Condicional en proposiciones.
3. Incluye siempre al colectivo que sale peor parado, no solo al que la norma quiere proteger.

## Capa 3 — `indirect_effects`: efectos de segundo orden
> **Cerrada (2026-10-13):** no se publica ni se redacta más. Dos revisiones por muestra fallaron (4/20 y 2/10 votaciones);
> ver `docs/etl/sprints/VOTING-AID-20261011/evidence/impacts-review-20261013.json`. Lo ya redactado queda en las semillas.

1. Máx. 6. Cada uno es `beneficio_esperado` o `riesgo_senalado`. **Si hay alguno, tiene que haber de los dos tipos**: si solo
   encuentras argumentos de un lado, no publiques esta capa.
2. Cada efecto lleva su evidencia, por este orden de preferencia:
   - `organismo_publico`: memoria de análisis de impacto normativo (solo en proyectos del Gobierno), AIReF, Banco de España, CNMC,
     Consejo de Estado, CGPJ… con página.
   - `estudio`: evaluación empírica publicada (DOI) de una medida igual o muy parecida; di dónde y cuándo se midió.
   - `debate`: argumento dicho en el debate del Pleno, con `locator` = página del Diario de Sesiones.
3. **No nombres al grupo ni a quien habló** (se muestra antes de responder); resume el mecanismo en una frase llana
   («Si los propietarios se sienten menos seguros, parte de las viviendas podría retirarse…»). El enlace al Diario permite comprobarlo.
4. Escribe previsiones como previsiones («podría», «se espera»), nunca como hechos. No añadas efectos que nadie haya defendido con fuente.
5. Descarta insultos, datos sin fuente y acusaciones; quédate con mecanismos (oferta, precios, plazos, acceso a servicios, conflictos
   de competencias, privacidad, disuasión…).

## `gaps`: lo que no se sabe
Una frase: si es proposición de ley (no lleva memoria oficial de impacto), qué cifra clave no existe, o si el estudio mide otro lugar o época.

## Revisión
`review.status = draft` hasta que otra mano (IA y después persona) compruebe cada dato en su fuente y cada argumento en su página.
Ejecuta `python3 -m scripts.export_voting_aid_vote_impacts` y `python3 -m unittest tests.test_export_voting_aid_vote_impacts`.

## Cobertura total: «A quién afecta» en todas las preguntas (2026-10-13)
Cada pregunta agrupada (`statements`, v1 y v2) y cada votación concreta (`votes`: las que resume cada pregunta de la v2,
las de la v1 y las del modo infinito) tiene que decir a quién afecta. Se redacta **una pregunta por subagente**
(Claude Sonnet 5.5), cada uno en su fragmento `etl/data/seeds/voting_aid_vote_impacts_v1.d/<unidad>.json`
(misma forma que la semilla: `facts`, `statements`, `votes`). El exportador fusiona los fragmentos y
`--require-complete` falla mientras falte alguna.

- Pregunta agrupada: `statements.<statement_id>.facts` = 1 a 3 cifras oficiales que dan la escala del tema.
- Votación concreta: `votes.<vote_event_id>` con `facts` (1 a 3, las que dan escala a *esa* votación; reutiliza las del
  tema si encajan, añade una específica si la medida toca a un colectivo concreto), `direct_effects` (obligatorios si la
  votación tiene viñetas «Qué se votaba»: mismos localizadores; si no las tiene, solo si abres el texto oficial),
  `review.status = draft`. Los efectos indirectos no son obligatorios en esta pasada.
- Ids de cifras nuevas con el prefijo de la unidad (`<unidad>--<fuente>-<periodo>-<tema>`); reutiliza por id cualquier
  cifra de la semilla o de otro fragmento ya escrito. Mismo id = mismo contenido exacto.
- Validar el fragmento: `python3 -m scripts.export_voting_aid_vote_impacts --part <fragmento> --out <scratch>/x.json`.

## Eficiencia de los subagentes (lecciones de la primera tanda, 2026-10-13)
El coste lo dominaba releer el contexto en cada turno (10–25 M tokens de caché por agente, 85–160 turnos; la salida
era <3 k). Los agentes reinventaban lo mismo: leer la semilla, el exportador y todos los fragmentos; buscar en la web
cifras que otro ya tenía; reintentar hosts bloqueados; volcar PDFs enteros (o leerlos como imágenes) en el contexto.
- `python3 -m scripts.voting_aid_impacts_kit`: `catalog` (cifras ya verificadas, para reutilizar por id), `fetch`
  (caché compartida en `etl/data/raw/voting_aid_sources/`, PDF→texto con páginas, salida filtrada y recortada,
  hosts bloqueados conocidos), `vote` (expediente y punto votado del JSON de la votación), `ine`, `eurostat`.
- Prompt autocontenido con las reglas, lista de trabajo compacta (viñetas, punto votado, texto oficial ya cacheado)
  y un esqueleto de fragmento con todas las claves: el agente edita, no construye.
- Presupuesto: ≤4 WebSearch, nada de Read sobre PDF/imágenes, rellenar todas las votaciones de una vez, validar al final.
