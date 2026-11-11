# `/visualizaciones/democracia/`: dónde puede romperse la separación de poderes en España

Fecha de inicio: 2026-11-11. Rebanada 3 del programa de cuatro sesiones paralelas (coordinador aparte).
Ficheros propios: `ui/site/app/visualizaciones/democracia/` (salvo `partidos/`, de la sesión hermana),
`etl/data/seeds/democracy_safeguards_v1.json` (+ `democracy_safeguards_v1.d/`), `scripts/export_public_viz_democracy.py`,
`ui/site/public/visualizaciones/data/democracia.{json,csv}`, `scripts/validate_democracy_safeguards.py`,
`tests/test_democracy_safeguards.py` y esta carpeta.

## 0. Método (escrito antes de recoger ningún dato)

### Pregunta
Las democracias occidentales dependen cada vez más de la buena voluntad de quien gobierna: si no quiere cumplir una
regla, a menudo nadie puede obligarle. ¿Qué salvaguardas de la separación de poderes en España están en ese caso, cuánto
tarda el remedio cuando lo hay, y cómo resuelven el mismo bloqueo Alemania, Francia, Italia y Portugal?

### Unidad: la salvaguarda
Una regla escrita (artículo de la Constitución, ley orgánica, ley o reglamento parlamentario, con enlace oficial al BOE o
al reglamento) que limita o somete a plazo a un poder. Para cada una se registra:

| Campo | Contenido |
|---|---|
| `rule` | Qué ordena, artículo, enlace oficial (BOE/ELI, Congreso, TC). |
| `obligated` | Quién debe cumplirla (Gobierno, Cortes con mayoría de 3/5, Mesa del Congreso, CGPJ…). |
| `enforcer` | Quién puede hacerla cumplir: un tercero que obliga o sustituye, uno que solo declara, o nadie. |
| `sanction` | Qué pasa si se ignora (anulación, derogación automática, prórroga, ninguna). |
| `remedy_delay` | Cuánto tarda el remedio, con su fuente (días, mediana o caso documentado). |
| `episodes` | Cada incumplimiento o tensión desde 1978: fechas de inicio y fin, qué pasó, **quién tenía el poder relevante** en ese momento (Gobierno y su partido; mayoría de la Mesa; mayoría que bloqueaba), fuente primaria. |
| `peers` | Cómo resuelven el mismo bloqueo DE, FR, IT y PT (norma y enlace oficial o informe de la Comisión de Venecia / Comisión Europea). |
| `classification` | Una de las tres clases de abajo, con la razón. |

### Clasificación (criterio fijado de antemano)
1. **`tercero_a_tiempo`** («un tercero la hace cumplir a tiempo»): un órgano distinto del obligado puede obligar,
   anular o sustituir el acto **y** el efecto llega antes de que el incumplimiento se consume (antes de que el acto
   agote sus efectos o en ≤ 6 meses si el incumplimiento es continuado). Incluye las consecuencias automáticas fijadas
   por la norma (p. ej. derogación de un decreto-ley no convalidado en 30 días, disolución a los dos meses de la primera
   investidura fallida).
2. **`tercero_tarde`** («se hace cumplir tarde»): un tercero puede anular u obligar, pero el remedio típico llega
   después de que el acto haya producido sus efectos o tarda más de 6 meses (p. ej. una sentencia del TC sobre un estado
   de alarma ya terminado).
3. **`buena_voluntad`** («depende de la buena voluntad»): nadie puede obligar ni sustituir; la única consecuencia es
   política (elecciones, moción de censura, reproche público) o una declaración sin efecto ejecutivo.

Si una salvaguarda tiene dos vías (p. ej. control político a tiempo y judicial tarde), se clasifica por la vía que
**protege el bien que la regla defiende** y se dice la otra en la razón. Ante la duda entre dos clases, la más débil.

### Atribución (misma vara para todos)
- Cada episodio se atribuye a quien **tenía el poder relevante** en la fecha: el Gobierno (presidente y partido o
  coalición) para actos del Ejecutivo; la mayoría de la Mesa para actos de la Mesa; para renovaciones que exigen 3/5,
  se registra qué grupos sumaban la minoría de bloqueo y qué posición pública consta, sin imputar motivos.
- Ninguna valoración de intención. Hechos con fecha y documento; si la fuente no fija la responsabilidad, se dice.
- Se registran también las sentencias **favorables** al poder controlado (un recurso desestimado es un dato).

### Series reproducibles
1. Decretos-leyes frente a leyes (ordinarias y orgánicas) por año y legislatura desde 1979: inventario ELI del BOE
   (`/eli/es/{rdl,l,lo}/AAAA/MM/DD/N`), payload crudo guardado con sha256; control: el número oficial más alto de cada
   año debe coincidir con el recuento (numeración correlativa).
2. Días con mandato caducado por órgano constitucional (CGPJ, TC, Defensor del Pueblo, Tribunal de Cuentas, consejo de
   RTVE…): fechas de fin de mandato y de toma de posesión del sustituto, cada una con su BOE.
3. Años sin presupuesto nuevo (prórroga del art. 134.4): Leyes de Presupuestos Generales del Estado por ejercicio (BOE).
4. Retraso del TC: días entre la publicación de la norma y la sentencia, en los casos del inventario (sentencia en BOE).
5. Congelador de la Mesa: ampliaciones semanales del plazo de enmiendas por iniciativa legislativa en la XV legislatura
   (base del proyecto, `parl_initiatives.deadlines_text`), por autor.
6. Pares: V-Dem (democracia liberal, límites judiciales y legislativos al Ejecutivo) para ES, DE, FR, IT, PT, PL y HU;
   independencia judicial percibida (EU Justice Scoreboard / Eurobarómetro); World Justice Project y EIU solo si la
   licencia lo permite. Fuente oficial primero; si se usa un espejo, se dice.

### Pregunta amplia (democracias que dependen de la buena voluntad)
Solo con índices e informes oficiales (Comisión de Venecia, Informes sobre el Estado de Derecho de la Comisión Europea):
qué se erosionó primero en los casos documentados (Polonia 2015–2023, Hungría desde 2010) y cuáles de esas salvaguardas
deja España a la buena voluntad. Sin previsiones.

### Lo que no puede decir
- Los índices son juicios de expertos, no medidas directas.
- Una regla nunca incumplida no está probada como fuerte: puede que nadie la haya puesto a prueba.
- Los recuentos dependen de lo que se recurrió y de lo que llegó a juicio.

### Puertas de calidad
- **Piloto**: 5 salvaguardas de clases distintas documentadas por completo + una serie completa (decretos-leyes).
  Revisor independiente (subagente) que recibe solo cada ficha y sus URL y comprueba fechas, atribución, texto legal y
  cifras. **Regla de decisión (fijada antes de revisar): al menos 4 de 5 verificadas por completo y ningún error de
  atribución.** Si falla, se para y se informa en vez de escalar.
- **Tras escalar**: muestra aleatoria de 10 salvaguardas revisadas igual (misma regla proporcional: ≥ 8/10 y ningún
  error de atribución; las que fallen se corrigen o se retiran antes de publicar).
- **Validador mecánico** (`scripts/validate_democracy_safeguards.py`): esquema, enlaces presentes, fechas ordenadas,
  clase en los tres valores, series reproducibles desde el payload crudo con sha256.

## 1. Piloto (2026-11-11)

### Serie completa: decretos-leyes frente a leyes (BOE ELI)
- Inventario de `/eli/es/{rdl,l,lo}/AAAA/MM/DD/N` de 1979 a 2026 (751 decretos-leyes, 1.566 leyes, 397 leyes orgánicas),
  payload crudo `raw/boe_eli_inventory.json.gz` con sha256 de cada página de listado. **Control superado**: en todos los
  años el recuento coincide con el número oficial más alto (numeración correlativa, sin huecos).
- Por gobierno (decretos-leyes al mes / leyes al mes): Suárez 1,59 / 5,61 · Calvo-Sotelo 1,75 / 5,86 · González
  0,80 / 3,81 · Aznar 1,33 / 4,32 · Zapatero 1,17 / 3,34 · Rajoy 1,38 / 2,40 · Sánchez 1,99 / 1,72. El peso de los
  decretos-leyes sube sobre todo porque bajan las leyes al mes: se publican las dos tasas, no solo el porcentaje.
- Publicada en `etl/data/seeds/democracy_safeguards_v1.d/decree_laws_series.json` (commit `0557315fa1`) para la sesión
  hermana `democracia-partidos`.

### Cinco salvaguardas de clases distintas
`decretos_ley` (tarde), `cgpj_renovacion` (buena voluntad), `presupuesto_presentacion` (buena voluntad), `estado_alarma`
(tarde), `investidura_plazo` (a tiempo). Redactadas por un agente con fuentes primarias (BOE, BOCG, Diario de Sesiones, TC).
Coste: 133 turnos y 23,6 M tokens de entrada (≈ 4,7 M por ficha), demasiado para escalar sin cambios.

### Revisión independiente (regla fijada antes: ≥ 4/5 verificadas y ningún error de atribución)
| Ficha | Veredicto | Error más grave |
|---|---|---|
| decretos_ley | verificada (42 episodios, mediana 1.610 días recalculada) | menor: STC 31/2011 anuló solo el art. 43 del RDL 6/2000 |
| cgpj_renovacion | **errores (4 mayores)** | **atribución**: «PSOE y PP indispensables» no se sostiene escaño a escaño (en 2001 y 2013 el PP con otros grupos llegaba a 3/5 sin el PSOE); LO 8/2022 atribuida al Gobierno cuando fue proposición del Grupo Socialista |
| presupuesto_presentacion | verificada | menor: redacción de `limits` |
| estado_alarma | verificada, sin errores | — |
| investidura_plazo | verificada | menor: 29-09-2023 fue 172-177 con un voto nulo |

**Resultado: el piloto NO supera la regla** (4/5 verificadas, pero hay errores de atribución). Según el método, no se
escala; se corrige y se informa.

### Correcciones aplicadas
- `cgpj_renovacion`: los plazos vencidos ya no atribuyen el bloqueo a ningún partido (nota: hace falta un recuento de
  escaños por cámara y legislatura con fuente); LO 8/2022 atribuida a las Cortes como la LO 4/2021; añadido el episodio
  de 1990 (21 días). Resto de errores menores corregidos. Revisión de lo corregido (`review/pilot-recheck/`): las 5 fichas quedan verificadas, sin errores mayores; los dos menores que señaló se corrigieron.
- Lección para escalar: **atribuir un bloqueo de 3/5 exige una tabla de escaños por cámara y legislatura con fuente**
  (resultados oficiales de la JEC en el BOE y composición del Senado). Sin ella, la regla es no atribuir a partidos.

### Ajustes antes de escalar (si se aprueba)
- Kit compartido en el exportador: `kit boe-search` (títulos del BOE, sección T = TC, sección 2 = nombramientos),
  `kit boe-doc`, `kit grep` (páginas y PDF), `kit peers` (enlaces oficiales de DE/FR/IT/PT ya comprobados y hosts que
  bloquean scripts), `kit govs`.
- Brief con presupuesto (≤ 60 llamadas, ≤ 3.000 caracteres por salida, ≤ 15 episodios) y campos cortos para el mapa.
- 20 fichas más preparadas (esqueletos con pistas) y un contexto Polonia/Hungría, en 5 agentes por afinidad de fuentes.

## 2. Ola 2 (aprobada por el coordinador con condiciones)

Condiciones: 5 fichas con ≥ 3 que exigen atribuir a quien tenía el poder de bloquear o nombrar; misma regla de revisión;
tabla de escaños con fuente antes de cualquier atribución de una mayoría reforzada; ≤ 0,5 M tokens por ficha.

### Tabla de escaños (`etl/data/seeds/democracy_safeguards_v1.d/seats.json`)
- Fuente: acuerdos de la Junta Electoral Central con el resumen de resultados, en el BOE (una referencia por elección).
  Congreso completo (350) de 2000 a 2023; Senado elegido completo en 2004, 2016, 2019-11 y 2023, con 1-2 electos sin
  leer en 2011, 2015 y 2019-04 y sin recuento en 2000 y 2008; 1989, 1993 y 1996 sin cifras (PDF escaneados ilegibles).
  Las correcciones de errores de la JEC están listadas pero no aplicadas. UPN cuenta aparte del PP.
- **La atribución ya no la escribe nadie a mano**: los episodios de mayoría reforzada llevan `power_holder.majority`
  y el exportador calcula, por legislatura y cámara, quién podía bloquear solo y qué parejas de los cinco mayores podían
  bloquear juntas (Congreso con escaños exactos; Senado solo con elegidos y «no determinado» salvo que un partido supere
  por sí solo 2/5 del Senado máximo, 266). Ejemplo, CGPJ 2018-2024: en la XIV y la XV ningún grupo bloqueaba solo en el
  Congreso; en el Senado, el PP sí en la XII y la XV; en la XIV, no determinado.
- Bloqueo de acceso nuevo: la API de Infoelectoral (Ministerio del Interior) responde con un desafío de Cloudflare
  (2026-11-11), por eso la fuente es el BOE. Pendiente de registrar en el log de bloqueos (fichero compartido).

### Redacción (hojas de trabajo con texto legal consolidado y cronología del BOE ya extraídos)
| Agente | Fichas | Turnos | Tokens de entrada | Por ficha |
|---|---|---|---|---|
| 2A | tc_renovacion, defensor_pueblo, tribunal_cuentas | 58 | 7,70 M | 2,6 M |
| 2B | rtve_consejo, fiscal_general | 65 | 8,79 M | 4,4 M |
| Tabla de escaños | — | 75 | 8,40 M | (compartido) |

Medido con `scripts/subagent_usage_report.py`. **Ola 2: 16,5 M para 5 fichas (3,3 M por ficha), lejos del objetivo de
0,5 M**: el coste lo marca releer un contexto que crece en cada turno (60 turnos × 130 k), no el número de llamadas.

### Revisión independiente de la ola 2 (regla: ≥ 4/5 verificadas y ningún error de atribución)
| Ficha | Veredicto | Error más grave |
|---|---|---|
| tc_renovacion | verificada | menor: una frase sobre qué vacante cubrió un magistrado no la respalda el BOE |
| defensor_pueblo | verificada, sin errores | — (Francia sin verificar: Légifrance bloquea scripts) |
| tribunal_cuentas | verificada, sin errores | — |
| fiscal_general | verificada | menor: la mediana de 413 días contaba una sentencia que no anuló nada |
| rtve_consejo | **errores** | **atribución (mayor)**: dos episodios de elección por 2/3 de las Cortes atribuidos al Gobierno (Rajoy, Sánchez) |

**Resultado: la ola 2 NO supera la regla** (4/5, pero con un error de atribución). Según la instrucción del coordinador,
no se lanza la ola 3. Correcciones aplicadas y revisadas de nuevo (`review/wave2-recheck/`): sin errores mayores; las
10 fichas verificadas (piloto y ola 2) se publican. Para que este error no se repita, el validador ahora rechaza
cualquier episodio con `majority` que lleve `government` (la decisión es de las Cámaras).

### Qué dominó el coste de la ola 2 y qué se ha cambiado
`subagent_usage_report.py`: 58-65 turnos por agente con ~130 k tokens de contexto releídos en cada uno; las salidas
mayores fueron volcados de la hoja de trabajo JSON (12-20 k caracteres) y el brief largo (9 k). Cambios para la ola 3:
- Brief compacto (`prompts/draft-compact.md`, ~3 k) y hojas de trabajo en Markdown de 5-15 k caracteres
  (`worklists/wave3/*.md`) con el texto legal consolidado del BOE (artículos completos), las búsquedas del BOE ya
  hechas (TC en sección T) y el texto oficial de los pares de Alemania e Italia ya extraído; Francia y Portugal,
  `no_signal` salvo que la hoja lo traiga (Légifrance bloquea scripts).
- Pares sin investigación abierta; escritura de cada ficha con una sola llamada de python; ≤ 3 consultas del kit por
  ficha y ≤ 4 WebSearch por agente.
- Ola 3 limitada a las 10 salvaguardas con incumplimientos o tensiones documentados, en 2 agentes de 5 que comparten
  fuentes (Cortes y TC: veto_presupuestario, control_parlamentario, mesa_plazos, tramitacion_reforzada, art155; justicia
  y rendición de cuentas: indultos, amnistia, estado_derecho_sentencias, transparencia, financiacion_partidos), con parada
  si el primero supera 1 M por ficha. Las otras 5 (cnmc_reguladores, cis_presidencia, mocion_censura,
  elecciones_plazos, cgpj_funciones) se publican como «pendiente de documentar» solo con su referencia legal.

## 3. Ola 3 (aprobada agente a agente)

- **Agente 1** (veto_presupuestario, control_parlamentario, mesa_plazos, tramitacion_reforzada, art155), brief compacto y
  hojas de trabajo en Markdown: 54 turnos, **5,92 M tokens de entrada = 1,18 M por ficha** (frente a 3,3 M en la ola 2 y
  4,7 M en el piloto). **Supera el tope de 1 M por ficha fijado por el coordinador: el agente 2 no se lanza.** Sus 5 fichas
  (indultos, amnistia, estado_derecho_sentencias, transparencia, financiacion_partidos) pasan a «pendiente de documentar»
  con su referencia legal, junto a cnmc_reguladores, cis_presidencia, mocion_censura, elecciones_plazos y cgpj_funciones.
- Lo que aún domina: releer el contexto (~110 k de media en 54 turnos) y 4-6 consultas por ficha para sacar el fallo del
  TC y la fecha del acto recurrido. Siguiente palanca (no aplicada): llevar esas dos columnas ya extraídas en cada fila
  de la hoja de trabajo y escribir las 5 fichas en un solo turno de escritura.
- Revisión independiente del agente 1: ver §3.1.
- **Comprobación mecánica añadida** (por instrucción del coordinador para cada patrón de atribución que señalen las
  revisiones): un episodio cuyo órgano es una Cámara, su Mesa o la Diputación Permanente no puede llevar `government`.
  Al activarla encontró 5 episodios ya publicados que la revisión no había visto (tres votaciones de RTVE en las Cortes
  y dos leyes orgánicas del TC); corregidos.
- **Polonia y Hungría** (`context.json`): cuatro filas (tribunal constitucional, consejo judicial, fiscalía, medios) con
  nueve opiniones de la Comisión de Venecia comprobadas en su PDF oficial (título, fecha y pasaje); Polonia/medios sin
  opinión comprobada (`no_signal`). Recomendaciones de los Informes sobre el Estado de Derecho: no incluidas (los PDF de
  la Comisión Europea no respondieron a scripts).

### 3.1 Revisiones de la ola 3
- **Agente 1** (revisión `review/wave3a/`): 4/5 verificadas; mesa_plazos con un error mayor factual (STC 89/2005 trata del
  Fiscal antidroga, no del anticorrupción), corregido. **Supera la regla** (sin errores de atribución). El coordinador
  aceptó 1,18 M por ficha y autorizó el agente 2.
- **Agente 2** (indultos, amnistia, estado_derecho_sentencias, transparencia, financiacion_partidos): 43 turnos,
  **4,95 M = 0,99 M por ficha** (filas del TC con el fallo ya extraído). Antes de revisar: la ficha de transparencia
  atribuía al Gobierno bloqueos técnicos del registro propio (el registro no dice quién los decidió) → `government` nulo
  y comprobación mecánica nueva. Revisión `review/wave3b/`: 4/5 verificadas; transparencia con 2 errores mayores
  factuales (descripción de los incidentes del registro), corregidos contra el propio registro. **Supera la regla.**

### 3.2 Muestra aleatoria de 10 sobre todo lo publicado
Semilla 20261111 sobre las 20 fichas verificadas: art155, defensor_pueblo, financiacion_partidos, fiscal_general,
indultos, investidura_plazo, mesa_plazos, rtve_consejo, tramitacion_reforzada, veto_presupuestario (+ transparencia,
revisada de nuevo por haberse corregido sin revisión). Dos revisores independientes; en cada ficha, texto legal, clase,
toda atribución, cifras de retraso y hasta 6 episodios al azar (`review/sample10/`).

| Resultado | Fichas |
|---|---|
| Verificadas | art155, defensor_pueblo, indultos, investidura_plazo, mesa_plazos, rtve_consejo, tramitacion_reforzada, veto_presupuestario, transparencia |
| Error mayor de texto legal | financiacion_partidos: faltaba el plazo de seis meses del Tribunal de Cuentas (art. 16.4 LO 8/2007) |
| Error mayor de atribución | fiscal_general: la condena penal personal del Fiscal General atribuida al Gobierno |

**8/10 verificadas, con un error de atribución**: según la regla escrita antes de revisar, las fichas que fallan se
corrigen o se retiran antes de publicar. Se corrigieron las dos (y los menores) y se añadió la comprobación mecánica
correspondiente: `government` solo puede ir con un órgano que sea el Gobierno o un ministerio.

**Cada una de las 20 fichas publicadas pasó su propia revisión independiente completa antes de publicarse** (no solo la
muestra): piloto (`review/pilot/` y `pilot-recheck/`: decretos_ley, cgpj_renovacion, presupuesto_presentacion,
estado_alarma, investidura_plazo), ola 2 (`review/wave2/` y `wave2-recheck/`: tc_renovacion, defensor_pueblo,
tribunal_cuentas, rtve_consejo, fiscal_general), ola 3A (`review/wave3a/`: veto_presupuestario, control_parlamentario,
mesa_plazos, tramitacion_reforzada, art155) y ola 3B (`review/wave3b/`: indultos, amnistia, estado_derecho_sentencias,
transparencia, financiacion_partidos). La muestra aleatoria de 10 fue una segunda comprobación sobre ese conjunto. Todas
las revisiones las hicieron agentes de IA distintos del que redactó; ninguna persona ha revisado todavía las fichas, y la
página lo dice en un aviso al principio con el canal de errores del sitio (incidencias de GitHub).

### 3.3 Atribución: comprobaciones mecánicas acumuladas (todas en `scripts/validate_democracy_safeguards.py`)
1. Gobierno vigente en la fecha del episodio (desde el principio).
2. Mayoría reforzada (3/5, 2/3) → la decisión es de las Cámaras: `government` nulo y aritmética calculada (ola 2).
3. Órgano Cortes, Cámara, Mesa o Diputación Permanente → `government` nulo (ola 3; encontró 5 casos publicados).
4. Bloqueo técnico del registro propio → `government` nulo (ola 3B).
5. `government` solo con órgano Gobierno o ministerio (muestra aleatoria).
Lección: cada revisión humana encontró un patrón nuevo; la combinación de revisión independiente y comprobaciones
mecánicas que se activan sobre todo lo publicado detectó 7 errores de atribución que una sola revisión no había visto.

### 3.4 Coste total de redacción (tokens de entrada, `subagent_usage_report.py`)
Piloto 23,6 M (5 fichas) · ola 2 16,5 M (5) · tabla de escaños 8,4 M · ola 3: 5,9 M + 5,0 M (10). Revisiones: entre
0,13 y 0,2 M por agente según el informe del arnés. Coste por ficha: 4,7 M → 3,3 M → 1,2 M → 1,0 M.

## 4. Estado

- **Dónde estamos.** `/visualizaciones/democracia/` (sin enlazar en el índice, sin desplegar) publica 20 salvaguardas
  revisadas de forma independiente (8 dependen de la buena voluntad, 9 se hacen cumplir tarde, 3 a tiempo) y 5 «pendiente
  de documentar» con su referencia legal; series reproducibles (decretos-leyes y leyes 1979-2026, presupuestos 1983-2026,
  ampliaciones de plazos de la XV, V-Dem, mandatos caducados, retrasos del remedio), aritmética de mayorías reforzadas
  con la tabla de escaños de la JEC, y el panel Polonia/Hungría con nueve opiniones de la Comisión de Venecia.
- **A dónde vamos.** Completar las 5 pendientes, los pares sin fuente (13 de 32 comparaciones de las fichas de buena
  voluntad tienen fuente), la tabla de escaños 1989-1996 y el Senado designado, y las recomendaciones de los Informes
  sobre el Estado de Derecho.
- **Qué sigue.** El coordinador añade el enlace del índice, la receta del justfile y la fila del tracker; decide cuándo
  publicar (las Cortes están disueltas y hay elecciones el 29-11-2026).