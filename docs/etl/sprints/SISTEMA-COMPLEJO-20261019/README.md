# Simulador del sistema: pensiones, impuestos, vivienda, empleo, sanidad y educación como un solo sistema

Fecha: 2026-10-19. Diseño (§1–§10), **corte 0** (§11) y **corte 1** (§12) publicados; **corte 2** (vivienda, §13) en `main`;
**corte 3** (empleo e inmigración, con la capacidad sanitaria del corte 4, §14) en `main` el 2026-11-11, sin desplegar.

- **Dónde estamos.** Cinco verticales en `/visualizaciones/` (carga fiscal, empleo, educación, sanidad, vivienda), cada una
  con su exporter, sus fuentes con sha256 y cinco casos tipo compartidos ([VIZ-SEGMENTOS](../VIZ-SEGMENTOS-20261019/README.md)).
  El test de voto v2 tiene 29 afirmaciones respaldadas por 1.023 votaciones. Las piezas se leen por separado: nadie ve qué
  le pasa a la vivienda cuando se tocan las pensiones.
- **A dónde vamos.** Un simulador en `/visualizaciones/sistema/` donde el lector mueve palancas de política («subir las
  pensiones», «limitar el alquiler», «copago sanitario») y ve, en tiempo real, cómo se propaga el cambio por un mapa causal,
  cuánto cuesta, quién lo paga, qué les pasa a los cinco casos tipo y con qué incertidumbre. Cada palanca enlaza a cómo
  votó cada partido.
- **Qué sigue.** Cortes 0–3 hechos (§11–§14): pensiones, cuentas públicas, impuestos con reparto por quintil, vivienda
  (obra, suelo, tope, turísticos, crédito; bucles B2 y R2), empleo (SMI, jornada, cuota de autónomos), inmigración como
  palanca y contexto, y la sanidad como servicio que no escala (médicos con retardo, lista de espera como stock).
  Siguiente (§14.6): educación y atención primaria como capacidad, y escenarios por partido desde lo votado (corte 5).

## 1. Qué tipo de modelo, y por qué

| Enfoque | Para qué sirve | Por qué sí o no aquí |
|---|---|---|
| **Dinámica de sistemas** (stocks y flujos, Forrester/Sterman) | Acumulaciones, retardos y bucles de realimentación | **Motor principal.** Es lo que usa En-ROADS (Climate Interactive/MIT), la referencia de simulador de políticas en el navegador: cientos de variables, resultados al mover el deslizador. |
| **Sistemas mínimos complejos** (MicroDYN, Funke/Greiff; Tailorshop, Dörner) | Ecuaciones lineales con entradas, salidas, inercia propia y efectos secundarios: el formato con el que la disciplina de *complex problem solving* mide cómo la gente explora y controla un sistema | **Forma de las ecuaciones y de la experiencia**: explorar la estructura primero, después intentar alcanzar objetivos (§5, modo reto). |
| **Microsimulación de impuestos y prestaciones** (EUROMOD de la JRC, calculadora TaxBEN de la OCDE) | Quién gana y quién pierde con un cambio de reglas, con hogares reales | **Capa de distribución, calculada fuera de línea**: tablas de incidencia por caso tipo y por celda edad × tenencia × quintil (los microdatos de la ECV ya están en la caché). |
| Mapas cognitivos difusos | Relaciones cualitativas | No como motor: los pesos no salen de datos. Sí para dibujar relaciones que aún no tienen número (aristas «sin cuantificar», §4). |
| Modelos de agentes, DSGE | Comportamiento emergente; equilibrio general | Fuera: no son trazables arista por arista ni corren en un navegador con rangos. Sus resultados publicados sirven para **calibrar** aristas. |

Decisión: **modelo modular de forma reducida**. Cada vertical es un submodelo pequeño de stocks y flujos con parámetros
calibrados (elasticidades, retardos) y su rango; los submodelos se conectan por unas pocas variables compartidas; la
distribución se resuelve con tablas precalculadas. El modelo no predice: muestra **diferencias frente a una línea base
oficial** documentada.

## 2. Arquitectura del sistema

### 2.1 El bus: las variables que conectan los módulos

Pocas variables compartidas, para que el acoplamiento sea legible:

- **Demografía**: población por etapa (16–29 / 30–44 / 45–64 / 65+), inmigración neta, hogares formados.
- **Trabajo**: ocupados, paro, salario medio real, horas.
- **Precios**: IPC, alquiler, precio de la vivienda, tipo de interés (el del BCE es contexto, no palanca).
- **Cuentas públicas**: ingresos por figura (IRPF, IVA, cotizaciones, sociedades, resto), gasto por función (COFOG),
  saldo, deuda, intereses.
- **Actividad**: PIB real (solo como denominador y para un multiplicador de corto plazo con rango; no hay modelo de
  crecimiento).

### 2.2 Los módulos

| Módulo | Stocks (lo que se acumula) | Flujos y relaciones clave | Datos ya en el repo |
|---|---|---|---|
| Pensiones | número de pensionistas, pensión media, fondo de reserva | altas por edad de jubilación, revalorización (se acumula: un punto de más se arrastra todos los años), cotizaciones y MEI | `carga-fiscal.json` (COFOG, ESSPROS por pensionista) |
| Cuentas públicas | deuda | saldo = ingresos − gasto; intereses = tipo medio × deuda (bucle que se refuerza) | `carga-fiscal.json` (`debt_interest`, composición) |
| Impuestos | — | recaudación estática por tipo × base; respuesta de la base con elasticidad y rango; incidencia por quintil | `carga-fiscal.json`, cuña fiscal en `empleo.json` |
| Vivienda | parque de viviendas, viviendas en alquiler (mercado / social / turístico), hogares, jóvenes no emancipados | obra iniciada → terminada (retardo 2–4 años), precio y alquiler frente a parque/hogares, crédito (LTV/LTI) → demanda, emancipación latente | `vivienda.json` (precio, esfuerzo, obra terminada, tipos), microdatos ECV |
| Empleo | ocupados por edad y formación, contratos temporales | coste laboral (SMI, cotizaciones, jornada) → empleo con elasticidad y rango; inmigración → población activa | `empleo.json` |
| Sanidad | médicos (MIR: retardo de 6–11 años), personas en lista de espera, cobertura | lista = entradas − salidas, salidas limitadas por capacidad; copago → uso (también del necesario); cobertura → necesidad no cubierta | `sanidad.json` (gasto, esperas, médicos, primaria) |
| Educación | cohortes por nivel, abandono, nivel formativo de la población | gasto/ratio → resultados (evidencia débil, rango ancho); 0–3 → empleo de las madres (corto plazo); formación → empleo y salarios (15–20 años) | `educacion.json` |

### 2.3 Cómo se ve el núcleo (ejemplo de bucles)

```mermaid
flowchart LR
  REV[Revalorización pensiones] -->|+| GP[Gasto en pensiones]
  GP -->|+| DEF[Déficit]
  DEF -->|+| DEU[Deuda]
  DEU -->|+| INT[Intereses]
  INT -->|+ R1| DEF
  DEF -.->|cierre: cotizaciones| COT[Cotizaciones]
  COT -->|+| CL[Coste laboral]
  CL -->|−| EMP[Empleo]
  EMP -->|+ B1| COT
  INM[Inmigración neta] -->|+| EMP
  INM -->|+| HOG[Hogares]
  HOG -->|+| ALQ[Alquiler]
  OBRA[Viviendas terminadas] -->|+| PAR[Parque]
  PAR -->|−| ALQ
  ALQ -->|−| EMAN[Emancipación]
  EMAN -->|+ B2| HOG
  CRED[Crédito LTV/LTI] -->|+| PRE[Precio vivienda]
  PRE -->|+ R2| CRED
```

Bucles con nombre (R = se refuerza, B = se equilibra), que la interfaz rotula:
- **R1 deuda–intereses**: el déficit de hoy paga intereses mañana.
- **B1 cotizaciones–empleo**: financiar con cotizaciones encarece el empleo y devuelve parte de lo recaudado.
- **B2 demanda latente**: construir abarata, abaratar emancipa, emancipar crea hogares que absorben parte de lo
  construido (en España, la mitad de los de 25–34 vive con sus padres: el efecto sobre el precio es menor que el ingenuo).
- **R2 crédito–precio**: con oferta rígida, el crédito fácil se capitaliza en precio, y el precio sube la garantía.
- **Inmigración** une pensiones y vivienda en sentidos opuestos: más cotizantes, más hogares.

## 3. Cómo opera en tiempo real: las simplificaciones

No se recalcula la economía. Se separa lo caro (fuera de línea) de lo barato (en el navegador):

**Fuera de línea (Python, en el exporter):**
1. Línea base anual 2025–2050 desde proyecciones oficiales: población del INE, gasto en pensiones del Ageing Report de la
   Comisión y de la AIReF, cuentas de AMECO/IGAE. Cada serie con su URL y sha256, como en las verticales.
2. Calibración: cada arista con elasticidad central, baja y alta, retardo y fuente (§4).
3. Incidencia: tablas de cuánto cambia en euros al mes cada caso tipo y cada celda edad × tenencia × quintil por unidad de
   cada palanca (IRPF, IVA, cotizaciones, pensión, alquiler, copago), a partir de las reglas fiscales y de los microdatos.
4. Un JSON acotado (`system-model.json`, objetivo < 1 MB) con variables, ecuaciones, parámetros, palancas y tablas.

**En el navegador (JavaScript, en un web worker):**
- Pasos anuales; las ecuaciones trabajan en **desviaciones logarítmicas frente a la línea base**
  (`Δy_t = Σ ε · Δx_{t−retardo}`), los stocks integran sus flujos.
- No linealidades solo donde se conocen y cambian el resultado: intereses sobre deuda, techo de capacidad de la obra,
  colas de espera con capacidad máxima, suelos en cero.
- Incertidumbre: 200 simulaciones con los parámetros muestreados en su rango (hipercubo latino, semilla fija para que un
  enlace reproduzca el mismo resultado). ~50 variables × 25 años × 200 simulaciones ≈ 250.000 evaluaciones: decenas de
  milisegundos.
- La distribución no se simula: se leen las tablas de incidencia y se multiplican por el cambio de cada palanca y de
  cada variable del bus (precios, alquiler, empleo).

**Simplificaciones que se dicen en la página:**
- Economía pequeña y abierta: tipos del BCE, crecimiento europeo y productividad son escenarios, no resultados.
- Forma reducida: las elasticidades medidas con unas reglas pueden no valer con reglas muy distintas (crítica de Lucas);
  por eso cada palanca tiene un **rango de validez** y fuera de él la interfaz avisa.
- Linealidad cerca de la línea base: cambios grandes (bajar las pensiones un 30 %) se marcan como fuera de rango.
- Sin equilibrio general completo: solo los efectos que pasan por el bus.
- Casos tipo y celdas, no microdatos, en el navegador.

### 3.1 Tres capas de certeza (la regla más importante)

Cada resultado se descompone y se pinta con peso distinto:
1. **Aritmética contable** (casi cierta): un punto más de revalorización cuesta X € el primer año y se arrastra.
2. **Respuesta de comportamiento estimada** (rango): cuánto cae el uso con un copago, cuánto empleo con más cotización.
3. **Efectos de segunda ronda** (hipótesis): multiplicadores, emancipación inducida, formación → salarios en 20 años.

Y un **indicador de robustez** por resultado: «el signo es el mismo en todas las hipótesis» frente a «depende de la
elasticidad X (enlace al debate)». Así el simulador separa lo que el dato zanja de lo que sigue en disputa, que es la
misma idea que la figura consolidada de cada vertical.

## 4. La pieza que hacen los agentes: el catálogo de aristas

Cada relación causal es una ficha verificable (estimación: 50 variables, 120–150 aristas):

```yaml
id: alquiler_tope__oferta_alquiler
de: tope_alquiler_zonas_tensionadas
a: viviendas_en_alquiler_mercado
signo: "-"
forma: log-lineal
elasticidad: {baja: ..., central: ..., alta: ...}
retardo_anios: 1-3
fuente_principal: {url, cita, pais, periodo, metodo}
evidencia_espana: si | no | parcial
grado: A (cuasi-experimento en España) | B (estudio fuera de España) | C (consenso de manuales) | D (supuesto)
evidencia_en_contra: [...]
debate: alquiler_tope   # si es un parámetro disputado, la interfaz deja elegir escuela
```

- **Parámetros disputados** (tope del alquiler, elasticidad de la renta gravable, efecto empleo del SMI, efecto del
  gasto educativo) no se resuelven a escondidas: la ficha guarda cada escuela con su fuente y el lector elige o ve todas.
- La línea del mapa codifica el grado: continua (A), discontinua (B/C), punteada (D), y sin número si no hay cuantía.
- Producción con el bucle obligatorio de `AGENTS.md`: lista de trabajo por módulo con las aristas precargadas, piloto de
  un agente con 5 aristas variadas, medir, arreglar la herramienta, olas de ~5 aristas por agente agrupadas por fuente,
  validador mecánico (esquema, rangos ordenados, URL y cita presentes) y **revisión de calidad de 15 aristas al azar
  contra la fuente con regla de decisión fijada antes** (la lección de los efectos indirectos del test de voto).

## 5. Qué ve y qué puede hacer el lector

### 5.1 Palancas (lo que pidió el mantenedor, más las que lo hacen comparable)

| Área | Palancas | Afirmación del test v2 que enlaza |
|---|---|---|
| Pensiones | revalorización (IPC −2 … IPC +2), edad efectiva de jubilación, pensión mínima, MEI, destope de la base máxima | «Hay que ampliar las prestaciones sociales…» |
| Impuestos | tipos de IRPF por tramo, IVA general y reducido, cotizaciones, sociedades, patrimonio/sucesiones | «Antes que bajar impuestos, hay que mantener la recaudación…» |
| Vivienda | viviendas públicas/año, suelo liberado, LTV/LTI máximos, tope del alquiler (cobertura y %), límite al alquiler turístico, deducciones | «El Estado debería intervenir más en el alquiler…» |
| Sanidad | cobertura (incluidas personas en situación irregular), copago por visita o farmacia, dental público, plazas MIR, gasto por persona | «El derecho al aborto y a la eutanasia…» (parcial); sin afirmación directa de cobertura: se dice |
| Empleo | SMI, jornada máxima, cuota de autónomos, políticas activas | «Para crear empleo es mejor rebajar costes…», «Los autónomos que ganan menos del SMI…» |
| Educación | gasto por alumno, 0–3 gratuito, ratio, becas, FP, concierto | «Las familias deberían poder elegir centro…» |
| Contexto (no son política) | tipo del BCE, inmigración neta, crecimiento de la UE, productividad | «España debería endurecer su política migratoria…» (la inmigración es contexto y palanca) |

**Cierre presupuestario obligatorio.** Toda palanca con coste pide «¿cómo se paga?»: deuda (por defecto, y se dice),
IRPF, IVA, cotizaciones o recorte de otra función. Es la lección central del sistema: subir las pensiones con deuda, con
IVA o con cotizaciones son tres políticas distintas con ganadores distintos.

### 5.2 Vistas

1. **Mapa causal** (entrada): ~6 grupos (los módulos) que se abren a sus variables. Al mover una palanca el cambio viaja
   por las aristas, los nodos se colorean por su desviación y los bucles activos se rotulan. Clic en una arista: su ficha.
2. **Series**: línea base frente a escenario con banda de incertidumbre, 1–25 años; la «aritmética» y el «comportamiento»
   separados.
3. **Personas**: los cinco casos tipo compartidos (joven inquilina en Madrid, pareja con hijos, adulto con poca formación
   en el sur, pensionista propietario, profesional) con su cambio en euros al mes después de impuestos, vivienda y
   servicios, y la media nacional al lado.
4. **Presupuesto**: de dónde sale y adónde va cada euro del escenario; saldo y deuda.
5. **Votos**: para cada palanca movida, cómo votó cada partido en la dirección elegida, con las votaciones concretas.
6. **Reto** (complex problem solving): un objetivo y restricciones («bajar al 30 % lo que la persona 1 dedica al alquiler
   en 10 años sin subir la deuda»); el lector explora y la página puntúa. Retos curados, no generados.

### 5.3 Comparar y compartir
- Escenario A frente a B en la misma vista.
- Escenarios por partido **solo desde lo votado** (dirección y, si el texto votado la fija, magnitud: p. ej. el índice de
  actualización de rentas de una ley), nunca desde programas sin votación detrás.
- Estado en el **fragmento** de la URL (`#…`), nunca en la query.

## 6. Tres ejemplos de cómo responde

- **Subir las pensiones** (un punto por encima del IPC): la aritmética es casi cierta y se arrastra; el resto depende del
  cierre. Con deuda: R1 empieza a pesar a 10–15 años. Con cotizaciones: B1 devuelve parte y la persona 1 pierde neto. Con
  IVA: sube el IPC y el pensionista recupera menos de lo que parece. La persona 4 gana en todos; la 1 pierde en dos de tres.
- **Construir más**: retardo de 2–4 años; el alquiler baja menos de lo que dice el cociente parque/hogares porque B2 crea
  hogares; la emancipación sube, que también es un resultado.
- **Limitar el alquiler**: baja lo que pagan quienes ya alquilan (aritmética) y, según la escuela elegida, se reduce la
  oferta de alquiler de mercado y sube el acceso para quien busca. Separa al inquilino con contrato del joven que busca,
  y el indicador de robustez dice qué parte del resultado depende del debate.

## 7. Reglas de rigor propias del simulador

Las de `/visualizaciones/` siguen valiendo; además:
- Rótulo fijo: «Escenario de un modelo con supuestos visibles, no una predicción».
- Las frases causales llevan su fuente: «en el modelo, X empuja Y según [estudio]», con el grado de la arista.
- Ninguna cifra sin rango, salvo la capa contable.
- Cada palanca tiene rango de validez; fuera de él, aviso.
- La línea base es oficial y está enlazada; el simulador solo añade desviaciones.

## 8. Puertas de calidad (antes de publicar cada módulo)

1. **Identidades cierran**: presupuesto, población, parque de viviendas, en cada año y cada simulación.
2. **La línea base reproduce** las proyecciones oficiales que usa (p. ej. gasto en pensiones en % del PIB del Ageing
   Report) dentro de una tolerancia fijada.
3. **Vuelta atrás**: el módulo, puesto en un año pasado, reproduce el signo y el orden de magnitud de episodios conocidos
   (IVA del 18 al 21 % en 2012; SMI +22 % en 2019; revalorización del 8,5 % en 2023; tope catalán del alquiler de 2020;
   reforma de pensiones de 2013). Si no, se dice en la página.
4. **Catálogo**: todas las aristas con fuente y grado; revisión de calidad de la muestra aprobada.
5. **Rendimiento**: simulación completa con incertidumbre < 100 ms en un móvil medio; JSON < 1 MB.
6. Puerta de privacidad de siempre (`just site-artifact-gate`).

## 9. Por dónde empezar: cortes finos

| Corte | Contenido | Por qué en este orden |
|---|---|---|
| **0. Pensiones + cuentas públicas** | revalorización, edad, MEI; cierre por deuda/cotizaciones/IVA; R1 y B1; personas 1 y 4; vuelta atrás 2013 y 2023 | Mejor dato, mecánica limpia, ya hay pensión por pensionista en `carga-fiscal.json`. Construye toda la máquina (motor, catálogo, exporter, mapa, personas) con un solo módulo. |
| 1. Impuestos | IRPF, IVA, cotizaciones, sociedades con incidencia por quintil y caso | Reutiliza el cierre del corte 0. |
| 2. Vivienda | obra, crédito, tope, turístico, emancipación (B2, R2) | La más pedida y la más disputada: necesita el mecanismo de debates ya probado. |
| 3. Empleo e inmigración | SMI, jornada, cuota de autónomos, inmigración como contexto | Une pensiones (cotizantes) con vivienda (hogares). |
| 4. Sanidad y educación | copago, cobertura, MIR, colas; 0–3, gasto, abandono | Retardos largos y evidencia más débil: mejor con la máquina madura. |
| 5. Capa de votos y retos | escenarios desde lo votado, retos curados | Necesita palancas estables. |

**DoD del corte 0**: página `/visualizaciones/sistema/` con mapa, series, personas y presupuesto para 4 palancas; catálogo
de ~20 aristas con revisión de calidad; línea base dentro de tolerancia; dos vueltas atrás documentadas; tests del motor
ejecutados con Node sobre el mismo código del navegador; JSON con fuentes y sha256; publicado con `just site-publish`.

**Implementación técnica propuesta (KISS):**
- Especificación del modelo como datos (YAML en el repo: variables, ecuaciones en una mini-notación, parámetros, palancas,
  enlaces a afirmaciones y votaciones) → `scripts/export_public_viz_system.py` → `system-model.json`.
- Un solo motor en JavaScript, sin dependencias, ejecutado en el navegador (web worker) y en Node para los tests.
- Alternativa descartada por ahora: escribir el modelo en XMILE/Vensim y compilarlo con SDEverywhere (lo que usa En-ROADS)
  y PySD para pruebas en Python. Da herramientas maduras, pero el formato es menos legible para revisar aristas una a una y
  añade una cadena de compilación.

## 10. Lo que el simulador no puede decir

- Cuánto crecerá la economía, ni qué pasará con los tipos del BCE: son escenarios.
- Efectos de cambios de reglas muy alejados de lo observado (fuera del rango de validez).
- Comportamientos que no tienen estimación (aristas «D»): se muestran, pero se dicen supuestos.
- Resultados políticos o electorales de las medidas.

## 11. Corte 0: pensiones y cuentas públicas (hecho, 2026-10-19)

- **Página**: `/visualizaciones/sistema/` (`ui/site/app/visualizaciones/sistema/`). Palancas: revalorización sobre el IPC,
  edad efectiva de jubilación, cotización extra; cierre por deuda, cotizaciones o IVA; contexto de inmigración (sensibilidades
  oficiales) y tipos de mercado; supuesto en disputa (incidencia de la cotización empresarial). Vistas: figura consolidada
  «tres formas de pagar lo mismo», mapa causal (con la lista de relaciones activas en texto para móvil), series con banda,
  dos casos tipo (1 y 4), capas de certeza con robustez y supuesto clave, votaciones del Congreso por palanca, catálogo y
  pruebas. Estado en el fragmento de la URL.
- **Datos**: `scripts/export_public_viz_system.py` → `ui/site/public/visualizaciones/data/sistema.json` (98 KB) y `sistema.csv`.
  Línea base: anexo estadístico del Ageing Report 2024 (xlsx en `etl/data/raw/system_model/`, sha256 en el JSON) y cuentas
  de 2025 (EDP de Eurostat en `public-finance-es.db`); el resto del presupuesto constante en % del PIB. Casos tipo leídos de
  `carga-fiscal.json` (sha256), nunca recalculados.
- **Motor**: `engine.mjs`, sin dependencias; el navegador y `node --test` ejecutan el mismo código. 200 simulaciones en
  hipercubo latino con semilla fija: ~35 ms, así que no hizo falta un web worker. Los impuestos de cierre cubren el coste
  antes de los efectos de segunda ronda (como un presupuesto); estos van al déficit. Con todo lo demás dentro del año, el
  punto fijo divergía en sorteos extremos (traslado salarial alto + multiplicador alto).
- **Catálogo**: 24 fichas en `etl/data/manual/system_model/edges/` (2 propias, 22 de agentes), validadas y fusionadas
  con `scripts/system_model_kit.py`; revisión de calidad de 15 al azar con regla fijada antes: 5 bien, 10 corregidas
  con corrección exacta, 0 sin respaldo (`reviews/`, aplicadas con `apply-reviews`). Correcciones con efecto: multiplicador
  de transferencias 0,5 → 0,8; la prima de riesgo de la Comisión solo vale en su escenario de tensión.
- **Puertas** (`just system-model-refresh`; el test también corre en `site-build-frozen`): identidades de la deuda, cierre
  por impuestos, convergencia en todos los sorteos, capa contable sin comportamiento, determinismo y tiempo, fragmento de la
  URL, y 4 pruebas con tolerancia fijada antes: coste de la revalorización de 2023 (+13 % frente a la cifra del Gobierno,
  que no incluye clases pasivas; tolerancia ±15 %), IRP 2014–2017 (+0,15 % con el IPCA frente a −0,08 % con el IPC),
  deuda de 2034 sin cambios (109,3 % frente al 109,5 % del Debt Sustainability Monitor 2024) y sensibilidad de inmigración.
- **Resultado principal** (valores centrales): un punto de revalorización sobre el IPC desde 2026 suma 34 puntos de deuda
  en 2050; pagado con cotizaciones, el caso 1 pierde unos 32 € al mes en 2035 (de 17 a 51) y hay unos 62.000 empleos menos;
  con IVA, unos 16 €. El caso 4 gana unos 143 € al mes en 2035 en los tres casos.
- **Coste de los agentes**: piloto de 5 fichas, 5,7 M de tokens de entrada (61 turnos); tras los arreglos (lista en el
  prompt, hosts bloqueados en el kit, URL que funcionan), 0,5–1,2 M por ficha (2,9–7,0 M por agente de 5–6 fichas);
  revisor de 15 fichas, 28 herramientas. Lo que más turnos ahorraría la próxima vez: URL de documentos de trabajo del
  Banco de España ya comprobadas, una ayuda del kit que saque los enlaces PDF de una página de publicación de la Comisión,
  respaldo con curl cuando falla el TLS de Python (tesoro.es) y que `catalog` acepte `(?i)`.
- **Límites que la página dice**: la edad efectiva tiene efectos menores que la sensibilidad oficial de congelar la edad
  legal (+2,9 puntos en 2040), porque esa mueve la participación de todo el tramo de 55 a 74 años; el multiplicador de
  impuestos (0,5) y su persistencia son supuestos con rango ancho; no hay estimación española de la incidencia de la cotización.
- **Siguiente**: corte 1 (impuestos: IRPF, IVA y cotizaciones con incidencia por quintil, reutilizando el cierre), luego
  vivienda con el mecanismo de debates.

## 12. Corte 1: impuestos con reparto por quintil (hecho, 2026-10-19)

- **Palancas nuevas**: IRPF en todos los tramos, IRPF por encima de 60.000 €, IVA general, IVA reducido e Impuesto sobre
  Sociedades; el IRPF es además una cuarta forma de pagar (cierre). Las cotizaciones ya estaban.
- **Recaudación** (fichas T01–T07, agentes): por punto, IRPF 0,26 % del PIB (AEAT 2023), tramo alto 0,03 %, IVA reducido
  0,14 % (Memoria de Beneficios Fiscales), Sociedades 0,13 % (AEAT); reacción con la elasticidad de la renta gravable
  (general y alta, esta en disputa), la semielasticidad de la base de Sociedades y el traslado de Sociedades a salarios
  (en disputa). Con el valor central de la reacción de las rentas altas, subir el tramo alto no recauda: se dice en la
  página y se deja elegir la escuela.
- **Reparto** (`scripts/system_model_incidence.py`, sin red, reglas fijadas en su cabecera): quintiles de personas por
  renta disponible equivalente con los microdatos de la ECV 2025; base del IRPF por persona con las reglas generales de
  2024 (simplificadas); IVA con la estructura de gasto por quintil de la EPF de Eurostat (2015, antes de la pandemia;
  2020 como contraste) y el tipo de la Ley 37/1992 por grupo COICOP; cotizaciones por salarios; Sociedades entre capital
  y salarios; pensiones por pensiones. El navegador multiplica las cuotas por la recaudación del motor: la vista por
  quintil es la carga legal (antes de reaccionar), en euros al mes por hogar y en % de la renta disponible.
- **Casos tipo**: se añaden el 2 (pareja con hijos, dos sueldos) y el 5 (profesional), con la misma renta que en las demás
  páginas; ninguno llega al tramo de 60.000 €.
- **Puertas nuevas**: la cuota de gasto al tipo general (EPF + ley) frente a la ficha del IPCA (diferencia 0,05, tolerancia
  0,1); la concentración de la base (20 % superior: 48,3 % en la microsimulación frente al 50,9 % de la AEAT, ±10 puntos);
  el IVA es regresivo en el modelo y en la estadística experimental de Eurostat; el reparto suma exactamente la carga.
- **Resultado principal**: un punto más de IRPF en todos los tramos recauda unos 3.500 millones tras la reacción y pesa
  unas 5 veces más (en % de la renta) en el quintil más rico que en el más pobre; uno de IVA general, unos 4.800 millones,
  del 0,84 % al 0,54 % de la renta del primer al quinto quintil.
- **Límites**: la ECV recoge peor las rentas más altas (el reparto del IRPF sale algo menos progresivo); la EPF de 2015
  puede no reflejar el gasto actual; no hay declaración conjunta, mínimos familiares ni escalas autonómicas concretas.

## 13. Corte 2: vivienda (hecho, 2026-10-19)

- **Palancas**: vivienda pública en alquiler (miles al año, decidida desde 2026), suelo finalista liberado (viviendas
  posibles al año), límite al préstamo sobre el precio (LTP 90/80/70 %, la medida del Banco de España) y sobre la renta
  bruta (LTI 6 y 4,5), tope del alquiler en zonas tensionadas (cobertura y rebaja exigida) y retirada de viviendas
  turísticas. La inmigración del corte 0 (variantes ±33 % del Ageing Report) mueve ahora también los hogares. El coste
  neto de la vivienda pública entra en el cierre («¿Cómo se paga?»): con IVA, el caso 1 paga menos de 1 € al mes en 2035
  por 20.000 viviendas al año y su alquiler de un contrato nuevo baja unos 6 €.
- **Datos** (`scripts/system_model_housing.py`, reglas en su cabecera): hogares de la Proyección de Hogares del INE
  (tabla 54562, caché con sha256; después de 2040 crecen con la población del Ageing Report), obra terminada constante en
  la media 2023–2025 (94.700 al año: supuesto, nadie la proyecta), parque del Censo 2021 más lo terminado, viviendas
  turísticas (INE experimental, 1,28 %), inquilinos de mercado de la celda de la ECV, jóvenes de 25–34 en casa
  (Eurostat) y los casos tipo con los alquileres del SERPAVI de `vivienda.json` (sha256), sin recalcular. Puertas: hogares
  del INE frente a la EPA, viviendas por hogar entre 1,2 y 1,5, inquilinos de mercado entre el 12 % y el 25 %.
- **Motor** (`engine.mjs`, el mismo en el navegador y en `node --test`): el alquiler de mercado se mueve con las viviendas
  por hogar (elasticidad inversa de la demanda); los hogares latentes de jóvenes se emancipan al bajar el alquiler y
  recorren la mitad del camino cada año (B2); el precio sigue al alquiler y al saldo de crédito, y el crédito nuevo sigue al
  precio (R2); la obra privada responde al precio de dos años antes (B3) y la pública la desplaza en parte; el tope rebaja
  los contratos cubiertos (con su cumplimiento), saca pisos del alquiler y sube los no cubiertos; los inquilinos con
  contrato se acercan al mercado al renovar. Nuevas salidas `hs_*`, `p1_rent_*`, `p2r_rent_*`, `p2b_*`.
- **Catálogo**: 21 fichas nuevas (18 relaciones y 3 pruebas), 54 en total. Tres debates: salida de oferta con el tope
  (Cataluña sin caída de oferta, 0; Cataluña en contratos nuevos, ≈2; San Francisco, ≈0,6 con una rebaja supuesta),
  traslado de la escasez al alquiler no cubierto (0,85 San Francisco frente a 0 Cataluña) y desplazamiento de la obra
  privada (0,115 frente a 0,67). Grado D a la vista: coste total por vivienda pública (solo la ayuda, 39.800 €, está
  publicada), alquiler social, suelo que se construye, pisos turísticos que vuelven, crédito que desaparece con un límite,
  paso a alquilar, los umbrales de LTI y LTP distintos del 80 %.
- **Bucle de agentes** (AGENTS.md): piloto de 4 fichas, 61 turnos y 5,9 M de tokens de entrada (los mismos que en el corte
  0), casi todo buscando PDF. Arreglos: lista de URL comprobadas, regla de parar tras 3 intentos, ventana de texto en una
  llamada. Segunda ola (2 agentes): 35 y 59 turnos, 3,3 y 6,3 M; tercera (2): 45 y 50 turnos, 4,3 y 4,5 M (≈1 M por
  ficha). Lecciones: la lista de URL solo comprobaba el código HTTP y dos entradas eran otro documento (NBER w9255 y el DO
  2415 del Banco de España); el esqueleto no traía `extra_parameters` aunque el prompt los pedía. Lo que más turnos
  ahorraría: un buscador de mangos de `repositorio.bde.es` por número de documento, un `bde` para las tablas del Boletín
  Estadístico y un buscador de tablas del INE.
- **Revisión de calidad** (regla fijada antes; 10 de 21 sorteadas con semilla 20261019, publicable con ≥ 8 bien o
  corregidas y ninguna sin respaldo): 3 bien, 7 corregidas, 0 sin respaldo. Correcciones con efecto en la lectura: la
  rebaja de San Francisco (25 %) es nuestra, no del artículo; el 43,8 % de hipotecas con LTP > 80 % es de operaciones, no de
  volumen (el motor lo usa como volumen y se dice); el coste por vivienda es coste total, con la parte pública aparte.
  Los grados pueden ir ahora por parámetro (`extra_parameters[].grade`), porque varias fichas mezclan un dato publicado con
  supuestos.
- **Pruebas** (tolerancias fijadas el 2026-10-19 antes de rellenar las fichas, `backtests.mjs`): tope catalán de 2020
  (−4,0 % en el modelo frente al −5,0 % medido; ±50 %; no independiente: el cumplimiento sale del mismo estudio), burbuja
  2000–2007 (el término de crédito da cuenta del 46 % de la subida del precio en años de salario, frente a 30–100 % en los
  estudios, ±15 puntos; prueba débil porque la referencia es D; el canal de parque por hogar apunta al revés: se terminaron
  0,82 millones de viviendas más que hogares nuevos) y pisos turísticos en Barcelona (0,66 % por punto del parque en el
  modelo frente a 1,25 % en el cuasi-experimento; entre un tercio y el triple). Seis pruebas nuevas del motor: identidad
  del parque, B2 amortigua, el tope en la capa contable es exactamente la ley, R2 amplifica, convergencia en todos los
  sorteos, inmigración y alquiler.
- **Resultado principal** (2035, valor central y 5–95 %): 20.000 viviendas públicas más al año suman 96.000 viviendas
  (0,4 % de los hogares) y bajan el alquiler de un contrato nuevo un 0,7 % (0,4–0,9; 2,4 % en 2050) por unos 770 millones
  al año; los jóvenes que se emancipan ocupan un 3 % de lo construido, así que B2 resulta pequeño con estas fichas (la
  elasticidad de la demanda ya incluye parte de la formación de hogares). Un tope del 10 % sobre la mitad del alquiler de
  mercado baja un 4,0 % (3,0–5,4) el contrato cubierto y sube un 1,7 % (0,3–3,6) el no cubierto, con 66.000 pisos menos
  de alquiler; según la escuela, de ningún piso menos y ningún cambio fuera del tope (Cataluña, oferta total) a −132.000 pisos y +3,4 % (Cataluña, contratos nuevos).
  Retirar la mitad de los pisos turísticos: −0,5 %. Limitar la hipoteca al 80 % del precio y a 4,5 veces la renta: precio
  −5,5 % (−1,3 a −9,5), de los que R2 multiplica por 1,17; el alquiler sube un 1,0 % porque parte de los compradores
  alquila (supuesto D). Un tercio más de inmigración: alquiler +2,2 %.
- **Límites que la página dice**: un solo mercado nacional (sin barrios ni comunidades); los pisos que salen del alquiler
  con el tope no cambian el parque total; LTP y LTI independientes; la obra pública no tiene multiplicador; el esfuerzo por
  edad aplica el cambio del alquiler a todo el gasto en vivienda de la celda.
- **Siguiente**: corte 3, empleo e inmigración (SMI, jornada, cuota de autónomos), que une cotizantes y hogares. La capa
  de presentación se está rediseñando (escena ilustrada) en otra sesión sobre este corte.


## Rediseño ilustrado de la página (2026-10-19)

- **Por qué**: el mantenedor juzgó que el mapa de cajas no comunicaba. La página se rehízo de principio a fin con dibujos.
- **Qué hay ahora** (`ui/site/app/visualizaciones/sistema/scene/`): una escena ilustrada (tiendas, empresas, quien trabaja, la
  hucha pública, quien cobra pensión, servicios públicos, la pila de deuda, quien presta y la vivienda) con el dinero circulando
  en monedas animadas; el grosor de cada flujo es su peso en % del PIB y el número de color, el cambio del escenario; cada figura
  es un millón de personas y cada moneda de la pila, 10 puntos de deuda. Una línea de tiempo 2025–2050 con reproducción. Las
  palancas son tarjetas con icono en pestañas (pensiones, impuestos, vivienda), «¿Quién paga?» con cuatro opciones dibujadas y
  escenarios de ejemplo. Debajo: cuatro vecinos con cara que reacciona (Lucía, Ana y Javi, Carmen y Laura, los casos 1, 2, 4 y 5),
  la escalera de rentas con una casa por quintil, la cadena de causas paso a paso con la fuerza de su evidencia y su ficha, y las
  comparaciones de pensiones, impuestos y vivienda con iconos. Gráficos, tabla de capas de certeza y supuestos en disputa quedan
  plegados en «Los números».
- **Dos composiciones** de la escena (ancha y estrecha) para que en el móvil se lea sin encoger; respeta `prefers-reduced-motion`.
- El mapa de cajas (`CausalMap.js`, `HousingMap.js`) queda solo como fuente de los nodos y relaciones de la cadena.

## 14. Corte 3: empleo e inmigración, y capacidad sanitaria (hecho, 2026-11-11)

Pregunta del mantenedor: qué hicieron los votos de cada partido por el empleo, los autónomos, la sanidad y los servicios
que no escalan cuando crece la población. Este corte da la parte del simulador; las otras porciones del programa (riesgo
democrático) van en otras sesiones.

### 14.1 Diseño (fijado antes de calcular)

- **Palancas de empleo**: SMI (subida real, %), jornada máxima (horas menos sobre 40, con el sueldo mensual mantenido),
  cuota de autónomos (euros al mes) y las cotizaciones que ya había. Cada una mueve el empleo del grupo afectado con una
  elasticidad con rango (el SMI y la jornada, con escuelas) y las cuentas públicas por salarios, cotizaciones e IRPF.
- **Inmigración como palanca y como contexto**: inmigración neta en múltiplos de la variante oficial (Eurostat EUROPOP2023
  `HMIGR`/`LMIGR`, la misma que usa el Ageing Report; escalado lineal, que es un supuesto). Da población por etapa
  (0–15 / 16–29 / 30–44 / 45–64 / 65+), ocupados con la tasa de empleo de los extranjeros de cada edad (EPA de Eurostat),
  cotizantes, hogares (módulo de vivienda) y demanda de servicios.
- **Sanidad que no escala**: demanda = población × perfil de gasto por edad (Funcas, DT 673) × uso relativo por origen
  (estudio español; si no hay, se dice); oferta = médicos (retardo de formación con rango) y dinero (lo que el dinero compra
  sin médicos, supuesto D); lista de espera quirúrgica como stock (entradas − salidas, salidas topadas por la capacidad;
  flujo anual por la ley de Little con los datos del SISLE). Línea base: el gasto del Ageing Report y una lista estable.
- **Figura consolidada**: lo que suma la inmigración (por etapa, 2035 y 2050, con rangos) en ingresos (cotizaciones,
  IRPF, impuestos al consumo) frente a lo que añade en demanda (sanidad, escuela, pensiones, otros servicios, hogares)
  y en capacidad (médicos y lista de espera si el gasto sigue o no a la población).

### 14.2 Puertas y pruebas, con la tolerancia fijada antes de rellenar las fichas

| Puerta | Qué se compara | Tolerancia |
|---|---|---|
| Población base | EUROPOP2023 `BSL` frente a la población del Ageing Report, 2025–2050 | ≤ 0,5 % cada año |
| Identidad de población | las etapas suman el total en cada año, base y variantes | exacta (redondeo) |
| Identidad de la lista | `S_t = S_{t−1} + entradas − salidas`, `S ≥ 0`, en cada sorteo | exacta |
| Demografía de la demanda sanitaria | crecimiento del gasto en % del PIB 2025–2050 solo por edad (perfil × población) frente al «escenario demográfico» del Ageing Report | ± 5 puntos de crecimiento |
| Inmigración y gasto ligado a la edad | cambio en % del PIB de sanidad + educación con la variante alta frente al del Ageing Report (gasto total ligado a la edad menos pensiones) | mismo signo y dentro de ×3 |
| Vuelta atrás SMI 2019 | empleo perdido con +22,3 % en el modelo frente al rango publicado (AIReF, Banco de España, estudios sin efecto) | mismo signo y dentro de [mín/2, máx×2] del rango publicado |
| Vuelta atrás inmigración 2019–2024 | ocupados extranjeros nuevos por cada residente extranjero nuevo de 15–64 (EPA) frente a la tasa de empleo que usa el modelo | ± 10 puntos |

### 14.3 Regla de la revisión de calidad (fijada antes de sortear)

15 fichas nuevas de este corte sorteadas con la semilla 20261111 (propias y de agentes). El revisor recibe solo la ficha
y sus URL. Veredicto por ficha: bien, corregida (con la corrección exacta) o sin respaldo. Publicable si al menos 12 son
bien o corregidas con corrección exacta. Las corregidas se aplican; las sin respaldo se corrigen a mano, bajan a D
(supuesto, mostrado como tal) o se quitan. El resultado se publica tal cual en este README.

### 14.4 Lo que se hizo y lo que salió

- **Datos** (`scripts/system_model_labour.py`, reglas en su cabecera, caché sin red con sha256 en el JSON): EUROPOP2023
  (`proj_23np`, `proj_23nanmig`), EPA de Eurostat (`lfsa_ergan`, `lfsa_pganws`), asalariados y autónomos (`nama_10_pe`),
  hoja ESc del anexo del Ageing Report (sanidad, dependencia, educación, alumnos, sensibilidades del gasto total), perfil de
  gasto sanitario por edad de Funcas (DT 673) y médicos y lista de espera del SISLE a través de `sanidad.json`.
  `sistema.json` pasa de 281 KB a 447 KB.
- **La variante oficial**: el «+33 %» del Ageing Report es un tercio más de inmigración de **fuera de la UE**; sube la
  inmigración neta un 46,5 % acumulado 2026–2050 (la baja, −46,2 %). La palanca escala esa variante (multiplicador −2…+2).
  Corrección de paso: el corte 2 movía los hogares con un tercio de la inmigración neta; ahora usa la diferencia real de
  la variante (el efecto en el alquiler de «más inmigración» es mayor que el publicado en el corte 2).
- **Motor** (`engine.mjs`; salidas `lb_*`, `mig_*`, `hl_*`): empleo de los afectados con elasticidad y ajuste a mitad de
  camino por año; ingresos de quien llega con el baremo de la OCDE a su salario relativo, impuestos al consumo y el resto
  de ingresos en proporción al PIB que añade; usos por etapa (sanidad por perfil y origen, escuela por alumno, dependencia,
  pensiones de quien llega a los 65 antes de 2050 y una parte del resto de servicios, en disputa); interruptor «¿crecen los
  servicios con la población?»; capacidad sanitaria = ω·dinero + (1−ω)·min(dinero, médicos), lista de espera como stock
  con entradas que bajan cuando la espera sube. La pensión de la inmigración deja de ser la sensibilidad del Ageing Report
  (un cociente sobre el PIB) y pasa a euros por persona; la sensibilidad oficial queda como prueba.
- **Catálogo**: 25 fichas nuevas (79 en total): 16 de agentes (piloto 4, segunda ola 3 × 4–5) y 9 propias. Debates nuevos:
  efecto del SMI sobre el empleo (Banco de España −0,40, AIReF −0,17 tras la revisión, sin efecto 0), de la jornada
  (Crépon-Kramarz −1,2, Chemin-Wasmer 0, Raposo-van Ours 0, Hunt +0,2) y coste del resto de servicios por residente
  (coste medio 1,0, coste marginal 0,32). Grado D a la vista: elasticidad de los autónomos a la cuota, cuota media, pensión
  relativa de quien llega, capacidad que compra el dinero sin médicos.
- **Puertas** (tolerancias de §14.2): población EUROPOP frente al Ageing Report, desfase máximo 0,21 % (≤ 0,5);
  identidades de etapas y de la lista exactas en todos los sorteos; demografía de la demanda sanitaria +15,5 % frente a
  +16,9 % del Ageing Report (±5 puntos); SMI 2019, 43 mil empleos en el modelo frente a 0–143 mil publicados (mediana 38);
  inmigración y empleo 2019–2025, 59 ocupados por cada 100 residentes nuevos de 16–64 en el modelo frente a 69 en la EPA
  (±10); inmigración y gasto ligado a la edad, −0,22 puntos de PIB en 2050 frente a −0,21 del Ageing Report (mismo signo,
  ×3). **Esta última falló en la primera pasada** (+0,07 frente a −0,21): el modelo subía el PIB con la elasticidad de corto
  plazo (0,65, capital fijo) mientras el Ageing Report deja crecer el capital con el empleo («capital rule» del Ageing
  Working Group, Havik et al. 2014, pág. 77). Se añadió esa regla como ficha (M08, grado C, 10 años, 5–15) solo para el
  empleo de quien llega; la revisión confirmó la cita. En pensiones el modelo da −0,86 puntos frente a −1,02 oficiales
  (sin tolerancia: el modelo no cuenta las pensiones que se generan después de 2050). 29 pruebas de Node pasan
  (6 nuevas del motor, entre las de motor y escenarios).
- **Revisión de calidad** (§14.3; 15 de 25 sorteadas con la semilla 20261111, lista en `review_sample_corte3.json`,
  revisores con solo la ficha y sus URL, una ficha por archivo en `reviews/`): **7 bien, 8 corregidas con corrección
  exacta, 0 sin respaldo**: publicable. Correcciones con efecto: una cita de AIReF atribuida a un artículo de prensa no
  estaba en él (la ficha L02 pasa a 45.000–54.000 empleos y la escuela de AIReF de −0,16 a −0,17); el alto de la
  elasticidad de la jornada pasa de +0,3 a +0,8 (Hunt leído al revés); título y autores de DO 2113 corregidos; la
  ficha propia M01 decía «sobre todo de 16 a 44» (es el 72 % de 16 a 64); el escenario demográfico del Ageing Report era
  el de 2049. Las demás fueron de redacción o de rango.
- **Segunda pasada de revisión** (2026-11-11, a petición del coordinador, porque la muestra corrigió 8 de 15): las otras
  10 fichas nuevas, mismo revisor y misma regla: **3 bien, 7 corregidas con corrección exacta, 0 sin respaldo**. En total,
  las 25 fichas nuevas revisadas: 10 bien, 15 corregidas, 0 sin respaldo. Correcciones: autores de DO 2113 (L01),
  «RETA y SETA» en la unidad (L07), el retardo de formación de un médico baja de grado A a C porque el central de 9 años
  es un juicio y las 9.276 plazas MIR se comparan con las plazas de entrada de hasta 2020 (S01), el resumen de la OCDE no
  dice que el efecto del dinero no dure sin más oferta (S04), el −0,5 de la respuesta de la demanda a la espera es un
  supuesto propio (S05), se quita el corte de 2018 que ninguna fuente citada da y se repunta la definición de espera
  media (S07), y Eurostat da el número de médicos en ejercicio directamente (226.667 en 2024; S08). **Ninguna cifra de la
  página cambia**: comparadas antes y después las 108 cifras de cabecera (inmigración con y sin servicios que crecen,
  SMI, jornada, cuota, MIR; 2035 y 2050; central y rango), son idénticas, porque las correcciones tocan fuentes,
  redacción y grados, y el motor calcula los médicos con la tasa por 100.000 y la población de EUROPOP (225.600, un 0,5 %
  menos que la cifra de la ficha). Siguen valiendo los titulares de `#inmigracion`: 1,33 millones de residentes más,
  15,6 mil millones pagados, 10,0 usados, espera de 122 a 126 días (130 con el mismo dinero).
- **Página**: pestañas Empleo y Sanidad, inmigración en múltiplos de la variante oficial y el interruptor de servicios;
  panel en vivo «Empleo, inmigración y servicios» (por etapa: residentes, pagan, usan; espera y pacientes que dejan de
  apuntarse); cadena de causas con 20 relaciones nuevas; votaciones por palanca desde el atlas (ejes `empleo_derechos`,
  `autonomos_empresa`, `inmigracion`, `sanidad_publica`, XV legislatura) con la dirección media de cada partido; figura
  consolidada `#inmigracion`, tabla de médicos y espera, figura `#empleo` con escuelas; 4 escenarios nuevos o rehechos
  (`subir-salario-minimo`, `jornada-37-5-horas`, `mas-inmigracion`, `menos-inmigracion`), 20 en total.
- **Resultado principal** (variante alta, valor central y 5–95 %): en 2035 viven 1,33 millones de personas más, 637 mil
  trabajan; pagan 15,6 mil millones al año (13,8–17,2) y usan 10,0 (9,0–13,6) si los servicios crecen con ellas; saldo
  +5,6 mil millones (+1,1 a +7,3), un 2 % del gasto en pensiones de ese año; en 2050, +15,0 (+2,1 a +20,4). Según la escuela
  del resto de servicios, el saldo de 2035 va de +0,7 (coste medio) a +7,4 mil millones (coste marginal). La espera
  quirúrgica pasa de 122 a 126 días en 2035 (134 en 2050) con servicios que crecen y a 130 (143) con el mismo dinero, con
  28 mil (78 mil) pacientes al año que dejan de apuntarse; el gasto en servicios por persona baja un 2,6 % (5,9 %). El
  alquiler de un contrato nuevo sube un 3,3 % (2,6–4,4). Empleo: SMI +10 % real, −37 mil empleos en 2035 (−97 a −15),
  +624 millones netos al año; 37,5 horas, de −855 mil a +142 mil según la escuela, coste por hora de los afectados +6,0 %,
  PIB −2,2 %; cuota de autónomos +50 € al mes, −52 mil autónomos y +914 millones.
- **Límites que la página dice**: quién llega en concreto (formación, origen, inmigración irregular), efectos sobre
  salarios y empleo de quien ya vive aquí (supuestos nulos), saldo de una vida entera (pensiones después de 2050), presión
  local (barrios, comunidades), reparto del coste de la jornada entre beneficios, precios y salarios. Ninguno de los casos
  tipo cobra el SMI.
- **Coste de los agentes** (`scripts/subagent_usage_report.py`): piloto de 4 fichas, 95 turnos y 11,4 M de tokens de
  entrada (2,8 M por ficha, casi todo buscando enlaces de la Seguridad Social y probando hosts caídos); segunda ola con
  URL comprobadas, hosts bloqueados (airef.es, inclusion.gob.es) y tope de 35–40 llamadas: 50–62 turnos y 4,8–6,1 M por
  agente (1,1–1,5 M por ficha); revisores, 3,4–4,8 M por 5 fichas. Total 40,2 M. Lo que más turnos ahorraría: hosts
  bloqueados también oecd.org, sciencedirect y e-spacio de la UNED; un `kit boe` que resuelva el id de una orden; que
  `fetch -g` dé la página de cada coincidencia; un lector de xlsx desde la caché; una ayuda que devuelva el resumen de
  RePEc de un artículo por título.

### 14.5 Dónde estamos y a dónde vamos

- **Dónde estamos**: el simulador responde ahora a «qué añade la inmigración en ingresos y en demanda de servicios, por
  edad, hasta 2050» con rangos, y separa el dinero (que llega) de la capacidad (que tarda): la sanidad no escala porque
  los médicos tardan unos 9 años. Las palancas de empleo muestran sus debates. Cada palanca enlaza las votaciones del
  Congreso del eje que le corresponde con la dirección media de cada partido.
- **A dónde vamos**: que la porción 1 del programa responda por partido qué hicieron sus votos por el empleo, los
  autónomos, la sanidad y los servicios bajo presión migratoria, con los escenarios del simulador construidos solo desde
  lo votado (corte 5).

### 14.6 Qué sigue

1. Educación y atención primaria como capacidad (plazas, ratios, médicos de familia por zona), con la misma lógica de
   stock y retardo; la escuela hoy solo cuesta por alumno medio.
2. Escenarios por partido desde lo votado (corte 5): traducir las votaciones con magnitud (SMI, jornada, cuota) a
   palancas, sin programas sin voto detrás.

