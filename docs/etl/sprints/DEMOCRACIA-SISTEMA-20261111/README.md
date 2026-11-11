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

## 1. Estado

- **Dónde estamos.** Método fijado; series de decretos-leyes, presupuestos, V-Dem y ampliaciones de plazos reproducibles;
  piloto de 5 fichas corregido tras no superar la regla de revisión (error de atribución en el CGPJ). Página en borrador
  local, sin publicar.
- **A dónde vamos.** 25 fichas revisadas, mapa de salvaguardas con panel de pares, contexto Polonia/Hungría.
- **Qué sigue.** Decisión del coordinador: escalar con los ajustes (tabla de escaños para mayorías reforzadas incluida)
  o parar aquí.
