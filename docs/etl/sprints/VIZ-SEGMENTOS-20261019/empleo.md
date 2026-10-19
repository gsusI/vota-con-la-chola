# Empleo: dimensiones que parten la realidad y casos tipo

<!--
Sprint: VIZ-SEGMENTOS-20261019 · vertical: empleo (`/visualizaciones/empleo/`)
Fecha: 2026-10-19. Autor: sesión de auditoría de empleo (solo informe; no toca código, datos ni UI).
Sondeos: API JSON de Eurostat y API Tempus del INE, consultados el 2026-10-19. Las cifras «derivadas» se calculan
aquí a partir de esas tablas y se marcan como tales. Todas las tasas EPA de Eurostat 2025 llevan la marca `d`
(definición distinta por la EPA 2021); ninguna cifra citada lleva la marca `u` (baja fiabilidad).
-->

**Dónde estamos.** La página ya tiene más segmentación que la media de las verticales: regiones NUTS 2 (cap. 4),
deciles salariales EPA, salario a composición fija, paro por nacionalidad y contrafactual educativo, productividad y
salario por comunidad (cap. 7). Pero cada corte va **suelto y a escala nacional**: ninguna figura cruza edad,
formación y territorio, y las cifras destacadas (`.vizStat`) son medias nacionales. **A dónde vamos:** una figura
consolidada que muestre que el paro del 10,5 % es la media de realidades que van del 2,7 % al 41,6 %, y cinco o seis
casos tipo con sus cifras. **Siguiente:** la sección 5 (dos cambios priorizados).

## 1. Inventario: dónde la media engaña

| Elemento (archivo) | Cifra nacional | ¿Engaña? | A quién deja fuera / dispersión |
|---|---|---|---|
| `.vizStat` «Paro en 2025» ([page.js](ui/site/app/visualizaciones/empleo/page.js)) | 10,5 % frente a 6,0 % UE-27 | **Sí, mucho.** No describe a casi nadie | Por edad × formación × comunidad (Eurostat `lfst_r_lfu3rt`, 2025): del **2,7 %** (universitarios de 45–54 años, País Vasco) al **41,6 %** (15–24 sin bachillerato, Andalucía). Por comunidad (20–64): 7,2 % País Vasco – 15,0 % Andalucía (×2,1); Ceuta y Melilla, 24 %–25 % (15–74) |
| `.vizStat` «×1,89 desde 1980» y figura «dato mata el relato» 1 (brecha estructural, [relato.js](ui/site/app/visualizaciones/empleo/relato.js)) | 7,0 de 7,85 puntos estructurales | No: es una afirmación sobre el país | Pero «estructural» no dice *de quién*: la parte persistente se concentra en baja formación y en el sur (ver sección 2). Falta esa lectura |
| `.vizStat` «Asalariados temporales 15,4 %» y figura «dato mata el relato» 2 (contratos 2019–2026) | 25,4 % (2021) → 15,4 % (2025) | **Sí.** La caída es casi toda privada | Derivado de INE EPA tabla [65980](https://www.ine.es/jaxiT3/Tabla.htm?t=65980) + series EPA de la página: **privado 23,7 % → 12,5 %; público 31,2 % → 27,4 %** (2021→2025). El sector público tiene el 18,7 % de los asalariados y el **33,6 % de los temporales** (25,4 % en 2021). Públicos de 25–29 años: **66,0 %** temporales; de 30–39: 42,2 %. Por edad (Eurostat `lfsa_etpgan`, 2025): 15–24, 44,4 % (UE 47,2 %: aquí España no es anómala); 25–54, 14,2 % (UE 10,3 %). Extranjeros 20,2 % frente a 14,5 % nacionales |
| Titular «paro de los jóvenes activos 24,9 %» ([ch4_calidad.js](ui/site/app/visualizaciones/empleo/ch4_calidad.js)) | 24,9 % frente a 15,2 % UE | A medias: es correcto («activos»), pero se lee como «uno de cada cuatro jóvenes» | Sobre toda la población de 15–24 años los parados son el **8,4 %** (UE 6,2 %; Eurostat `yth_empl_140`, 2025). El salto de edad está antes de los 25: 25–29 años, 13,7 %; 30–34, 9,6 % (`lfsa_urgan`) |
| Titular «Trabaja el 72,4 % de 20–64» ([ch5_productividad.js](ui/site/app/visualizaciones/empleo/ch5_productividad.js)) | 72,4 % frente a 76,1 % UE | Parcialmente | Mujeres 67,6 %, hombres 77,1 %; 20–24, 43,7 %; 55–64, 62,4 % (UE 66,4 %) (`lfsa_ergan`, 2025). La brecha con la UE está sobre todo en 20–24 (−9,8 p.) y 55–64 (−4,0 p.) |
| Capítulo 6 «neto de un soltero con el salario medio» ([capacidad.js](ui/site/app/visualizaciones/empleo/capacidad.js)) | OCDE «average wage» | **Sí.** La propia nota lo admite («no el mediano ni el más frecuente») | Media 29.540 €/año frente a mediana 24.497 € (INE EAES 2024, tabla [28191](https://www.ine.es/jaxiT3/Tabla.htm?t=28191)): la media está un 21 % por encima. El decil 6 (2.130 €/mes) aún cobra menos que la media EPA (2.386 €): más de la mitad de los asalariados cobra menos que el «trabajador medio» (INE EPA tabla [66237](https://www.ine.es/jaxiT3/Tabla.htm?t=66237), 2024) |
| Titular «11,2 % de los ocupados en riesgo de pobreza» (capacidad.js) | 11,2 % frente a 8,3 % UE | Parcialmente | Temporales 14,7 %, indefinidos 8,1 % (`ilc_iw05`, 2025). Por edad casi no cambia (18–24, 12,2 %; 25–54, 11,8 %; 55–64, 9,1 %; `ilc_iw01`) porque se mide por hogar: muchos jóvenes viven con sus padres. La edad no sirve aquí; el contrato sí |
| Salario real por asalariado (AMECO, cap. 5) y deciles (cap. 7, [composicion.js](ui/site/app/visualizaciones/empleo/composicion.js)) | Media | Ya matizado (IPT, deciles) | Falta la edad: 16–24 años, 1.373 €/mes (58 % de la media); 25–34, 2.132 € (89 %); 55 y más, 2.681 € (INE EPA tabla [66239](https://www.ine.es/jaxiT3/Tabla.htm?t=66239), 2024) |
| Bloque «Lo que estos datos no pueden decir» ([sections.js](ui/site/app/visualizaciones/empleo/sections.js)) | — | **Desfasado** | Dice «Son series nacionales: el paro varía mucho entre comunidades autónomas y aquí no se ve», pero los capítulos 4 y 7 ya muestran las comunidades. Hay que reescribirlo (corrección pequeña) |
| Productividad por hora, cuña fiscal, salario mínimo/mediano, gasto en políticas | Agregados de país | No | Son comparaciones entre países; la productividad por comunidad ya está en el cap. 7. No se proponen cambios |

## 2. Dimensiones: cuáles parten la realidad

Medida: cuánto se separan los grupos extremos de una dimensión frente a la media nacional, en paro, salario y
calidad del contrato. Fuentes: Eurostat `lfst_r_lfu3rt`, `lfsa_urgan`, `lfsa_urgaed`, `lfsa_etpgan`, `lfsa_eppga`,
`lfsa_eppgai`, `ilc_iw05`, `lfst_r_urgau`, `met_lfu3rt`; INE EPA salarios por decil 2024 (tablas 66237–66250) y
asalariados del sector público por contrato y edad (tabla 65980), 2025.

| Dimensión | Paro (extremos) | Salario medio EPA 2024, €/mes (extremos) | Calidad del empleo | Veredicto |
|---|---|---|---|---|
| **Edad** | 15–24: 24,9 %; 25–34: 11,5 %; 45–54: 8,1 % (×3,1) | 16–24: 1.373; 55+: 2.681 (×1,95) | Temporalidad 15–24 44,4 % frente a 55–64 9,2 %; pública 25–29 66 % | **Se queda** |
| **Nivel de formación** | 20–64: hasta ESO 15,3 %; superior 6,4 % (×2,4) | Primera etapa de secundaria 1.763; superior 2.983 (×1,7) | — | **Se queda** (ya está a escala nacional en el cap. 3; lo nuevo es cruzarlo) |
| **Territorio (comunidad)** | 20–64: País Vasco 7,2 %; Andalucía 15,0 % (×2,1); Ceuta y Melilla, 24 %–25 % | Canarias 2.052; País Vasco 2.810 (×1,37). Mediana anual EAES 2024: Canarias 20.632 €; País Vasco 31.912 € (×1,55) | — | **Se queda** |
| **Relación laboral** (contrato × jornada × sector público) | — | Parcial 1.007 frente a completa 2.618 (×2,6); temporal 1.873 frente a indefinido 2.485 (×1,33); público 3.232 frente a privado 2.182 | Pobreza laboral: temporal 14,7 % frente a indefinido 8,1 % (×1,8). Parcial involuntaria: 45,7 % de quienes trabajan a tiempo parcial (UE 17,8 %) | **Se queda** como atributo del caso tipo (no es una población fija: es la situación de la persona) |
| Sexo | Mujeres 11,9 %; hombres 9,3 % (×1,3) | 2.163 frente a 2.593 (×1,2), sobre todo por la jornada: parcial mujeres 21,3 %, hombres 6,7 % | Tasa de empleo 67,6 % frente a 77,1 % | Se descarta como eje; la parte que pesa (parcialidad) ya la recoge «relación laboral». Se usa en un caso tipo |
| Origen (nacionalidad) | Extranjeros 15,4 %; nacionales 9,5 % (×1,6) | 1.846 frente a 2.508 (×1,36) | Temporalidad 20,2 % frente a 14,5 % | Secundaria: ya publicada (cap. 7) y en buena parte explicada por la edad, la formación y el sector. No es eje |
| Grado de urbanización / gran ciudad | Ciudades 10,0 %; pueblos y ciudades pequeñas 11,4 %; rural 10,5 % (`lfst_r_urgau`, 2025). Metro Madrid 10,0 %; metro Barcelona 9,1 %; resto no metropolitano 12,8 % (`met_lfu3rt`, 2023) | Sin dato oficial de salario por gran área urbana en la EPA publicada | — | **Se descarta para paro**: lo que lo separa es la comunidad (Cádiz metro 22,3 %, Vitoria 7,2 %). Madrid/Barcelona importan por el **coste** (vivienda), no por el empleo: es un eje de la vertical de vivienda y de la lente de capacidad |
| Sector de actividad | Ya en el cap. 2 (construcción: 51 % de los empleos perdidos en 2007–2013) | — | — | Se descarta como eje de casos: explica el ciclo, no compartimentos de personas |
| Tamaño de empresa | — | 1–10 empleados 1.713; 250 o más 3.236 (×1,9) | — | Se descarta: separa mucho, pero no es algo con lo que la gente se identifique; ya está en el cap. 3 |
| Asalariado / autónomo | La EPA no publica ingresos de los autónomos | — | — | Hueco honesto (sección 4) |

**Lo que el cruce enseña y ninguna dimensión sola dice** (Eurostat `lfst_r_lfu3rt`, 2025, paro en %):

| 35–44 años | Hasta ESO | Superior |
|---|---|---|
| Andalucía | 19,9 | 8,1 |
| Madrid | 10,2 | 3,3 |
| País Vasco | 16,4 | 2,9 |
| España | 14,0 | 5,1 |

- La región pesa poco entre quienes tienen baja formación (Andalucía 19,9 % frente a País Vasco 16,4 %) y mucho
  entre los universitarios (8,1 % frente a 2,9 %, ×2,8). La formación pesa en todas partes, pero más en el norte
  (×5,7 en el País Vasco, ×2,5 en Andalucía).
- Los dos relatos fáciles, «es la formación» y «es el sur», solo funcionan juntos: ninguno basta solo.
- Un universitario de 35–44 en Madrid o el País Vasco tiene un paro de nivel alemán (≈3 %). Un joven de 25–34 sin
  bachillerato en Extremadura está en el 25,9 %, y en Andalucía en el 22,2 %.

## 3. Casos tipo

Cifras de 2025 (paro, temporalidad) y de 2024 (salarios EPA, salario medio bruto mensual del empleo principal).
Al lado, la cifra nacional que da hoy la página.

| Caso | Paro | Salario medio EPA (€/mes) | Contrato / riesgo | Cifra nacional que da la página |
|---|---|---|---|---|
| **A. Joven sin bachillerato en el sur.** 25–34 años, hasta ESO, Extremadura (o Andalucía) | **25,9 %** (Andalucía 22,2 %) | ~1.763 (formación hasta ESO, nacional; no hay cruce con la región) | Temporalidad 25–54: 14,2 % (sin cruce con la región) | Paro 10,5 % |
| **B. Joven universitaria en Madrid.** 25–34, estudios superiores, Comunidad de Madrid | **6,2 %** | 2.132 (25–34, nacional); media de Madrid 2.762 | Su problema no es el paro, sino lo que cuesta vivir: hay que cruzarlo con el alquiler (vertical de vivienda) | Paro 10,5 %; «neto del salario medio» |
| **C. Interino en el sector público.** 30–39 años, sanidad o educación | Bajo (no publicado por sector) | Público 3.232 (media; con más universitarios) | **Temporalidad 42,2 %** (25–29: 66,0 %) frente a 12,5 % en el sector privado | Temporales 15,4 % «tras la reforma» |
| **D. Adulto cualificado del norte.** 45–54 años, universitario, indefinido, País Vasco | **2,7 %** (UE-27, toda la población: 6,0 %) | 2.592 (45–54); País Vasco 2.810; superior 2.983 | Pobreza laboral de los indefinidos: 8,1 % | Paro 10,5 %; ×1,75 la UE |
| **E. Jornada parcial que no eligió.** Mujer, 30–50 años, servicios, Canarias | Canarias 13,3 % (20–64) | **1.007** (jornada parcial; 42 % de la media) | El 45,1 % de las mujeres a tiempo parcial no encuentra jornada completa (UE 16,5 %); pobreza laboral de los temporales 14,7 % | Salario medio 2.386 |
| **F. Mayor de 55 con baja formación en el sur.** 55–64 años, hasta ESO, Andalucía | **21,2 %** | ~1.763 (formación, nacional) | El 32,1 % de los parados lleva más de un año (nacional) | Paro 55–64: 10,1 % |

Fuentes: paro, Eurostat `lfst_r_lfu3rt` 2025 (A, B, D, F y E por región); temporalidad, INE tabla 65980 y Eurostat
`lfsa_etpgan`; salarios, INE tablas 66237–66250 (2024); parcialidad involuntaria, Eurostat `lfsa_eppgai`; pobreza
laboral, Eurostat `ilc_iw05`; larga duración, `empleo.json` (`long_term.share`). Los salarios de A, E y F no son del
cruce exacto: la EPA publicada no cruza el salario por edad × región × formación (sección 4).

Con los casos A y D la diferencia es de ×9,6 en paro. Con B y E, de ×2,1 en salario (antes de la vivienda).

## 4. Disponibilidad de datos

| Dimensión o cruce | Tabla oficial | Años | Granularidad | ¿En staging? | Huecos |
|---|---|---|---|---|---|
| Paro por edad × formación × comunidad | Eurostat `lfst_r_lfu3rt` (dimensiones `age`, `isced11`, `sex`) | 1999–2025 (EPA 2021: marca `d`) | NUTS 2; edades 15–24, 15–29, 25–34, 35–44, 45–54, 55–64, 20–64 | Solo 15–74 total | Algunas celdas vacías o con marca `u` (p. ej. Cantabria, superior, 15–24); se publican vacías, nunca imputadas |
| Paro, empleo por edad × sexo | Eurostat `lfsa_urgan`, `lfsa_ergan` | 1983–2025 | Nacional | Solo totales y 15–24 | — |
| Ratio de paro juvenil sobre la población | Eurostat `yth_empl_140` | 2000–2025 | Nacional | No | — |
| Temporalidad por edad, nacionalidad | Eurostat `lfsa_etpgan` | 1987–2025 | Nacional | Solo 15–64 | — |
| Temporalidad pública por edad y sexo | INE EPA tabla 65980 (anual) | 2018–2025 (consultado `nult=8`) | Nacional | No | Lo privado sale por diferencia con las series EPA de la página (derivado): haría falta la tabla gemela privada o la de asalariados por sector y contrato |
| Temporalidad por comunidad | INE EPA (tablas de asalariados por contrato y comunidad) | — | — | No | **No sondeado** en esta auditoría |
| Salario EPA por edad, sexo, nacionalidad, comunidad, formación, contrato, tamaño, sector público/privado, jornada | INE tablas 66237–66251 (deciles del empleo principal) | 2024 (la 66237 ya está en staging como `INE_66237`) | Una dimensión por tabla | Solo 66237 | **Sin cruces** (edad × comunidad, etc.). Media, no mediana (los deciles permiten aproximar). Excluye a los autónomos |
| Mediana y percentiles del salario por comunidad | INE EAES tabla 28191 | 2008–2024 | Comunidad | Sí (`INE_28191`) | Anual, sin edad |
| Cruces de salario edad × comunidad × contrato × jornada | Microdatos de la EES 2022 (cuatrienal, descarga libre del INE) y microdatos de la EPA (trimestrales, libres) | 2022 / trimestral | Persona | No | Muestra pequeña en celdas finas (Ceuta, Melilla, La Rioja); hace falta un umbral mínimo de muestra antes de publicar |
| Paro por área metropolitana | Eurostat `met_lfu3rt` | Hasta 2023 | Áreas metropolitanas (≈ provincias; Madrid ≈ Comunidad) | No | Va dos años por detrás; sin salarios |
| Paro por grado de urbanización | Eurostat `lfst_r_urgau` | 2025 | Nacional | No | No separa (ver sección 2) |
| Pobreza laboral por contrato y por edad | Eurostat `ilc_iw05`, `ilc_iw01` | 2025 | Nacional | Solo `ilc_iw01` total | Se mide por hogar; `ilc_iw07` (por jornada) devolvió vacío para 2024–2025 |
| Parcialidad e involuntaria por sexo/edad | Eurostat `lfsa_eppga`, `lfsa_eppgai` | 2025 | Nacional | No | — |
| Ingresos de los autónomos | — | — | — | — | **Sin fuente comparable** en la EPA; la AEAT publica rendimientos por estimación, pero no por persona ni por edad × región |
| Días trabajados al año por fijo discontinuo | Muestra Continua de Vidas Laborales | — | Persona | No | Ya registrado como hueco en la página |

## 5. Recomendación priorizada

**1. Nueva figura consolidada «el dato mata el relato»: paro por edad × formación × comunidad** (prioridad máxima).
- Forma: un gráfico de puntos ordenado (o un mapa de calor) con 4 edades × 3 niveles de formación en filas y un punto
  por comunidad. Encima, la línea de la media española (10,5 %) y la de la UE-27 del mismo grupo: la UE está en
  `lfsa_urgaed` por edad y formación, así que la comparación es con pares y no solo entre comunidades. Una sola
  escala, cero en el eje.
- Va delante de la figura de la brecha estructural, o justo después, y responde «estructural, ¿de quién?».
- Titular propuesto (comprobar con los datos exportados): «El paro va del 2,7 % de un universitario de 45–54 años en
  el País Vasco al 25,9 % de un joven de 25–34 sin bachillerato en Extremadura: el 10,5 % de media no describe a casi
  nadie».
- Relatos que zanja: «el paro es por la formación», «el paro es del sur» y «en España no hay paro de cualificados».
- Lo que no zanja: si es la región o lo que se hace en la región (sector, turismo), porque la tabla no cruza sector.
  Y que la EPA mide dónde vive cada persona, no dónde trabaja.
- Datos: una sola tabla de Eurostat (`lfst_r_lfu3rt`) que ya usa el pipeline, ahora con todas las edades y
  formaciones: un cambio pequeño en `scripts/ingest_employment_es.py`.
- Debajo, los seis casos tipo de la sección 3 como fichas (`.vizStat` teñidas), cada una con la media nacional al
  lado.

**2. Reescribir la temporalidad: el `.vizStat`, el titular del cap. 4 y la figura consolidada 2**, separando lo
público de lo privado y por edad.
- Titular propuesto: «La temporalidad privada bajó del 23,7 % al 12,5 % entre 2021 y 2025; en el sector público
  sigue en el 27,4 %, y dos de cada tres asalariados públicos de 25 a 29 años son temporales».
- Cambia la lectura de la reforma de 2022: la ley apenas tocó al sector público, que hoy tiene uno de cada tres
  temporales.
- Datos: INE tabla 65980 (anual), más su gemela privada o la tabla de asalariados por sector y contrato (pendiente de
  localizar).

Correcciones pequeñas que van con lo anterior (no son figuras nuevas):
- Junto al 24,9 % de paro juvenil, la ratio sobre la población (8,4 %).
- En el capítulo 6, el caso con el 67 % del salario medio (`single_aw67`, ya en los datos) y una línea que diga que
  más de la mitad cobra menos que la media.
- Corregir la frase desfasada sobre las regiones en el bloque «Lo que estos datos no pueden decir».

## 6. Dimensiones compartidas (para armonizar con las demás verticales)

**Edad.** Para empleo propongo **16–24 / 25–34 / 35–54 / 55–64** (más 65+ si una vertical lo necesita), que se agrupa
sin pérdida en la banda común **16–34 / 35–64 / 65+**.
- Motivo: el salto del paro está a los 25 años (24,9 % → 13,7 %) y el del salario y la temporalidad pública a los 35
  (25–29: 66 % temporales; 40–49: 24 %). Partir en 16–34 esconde que 16–24 es otro mundo (muchos estudian, la tasa
  sobre activos engaña).
- Compatibilidad: Eurostat regional da 15–24, 25–34, 35–44, 45–54 y 55–64. Las tablas salariales del INE dan 16–24,
  25–34, 35–44, 45–54 y 55+. La EPA del INE da bandas de cinco años.
- 16–34 se obtiene sumando *efectivos*, no promediando tasas. 65+ no aporta en empleo (casi nadie trabaja).

**Territorio.** La base es la **comunidad autónoma** (NUTS 2, 19 unidades, que es lo que publican Eurostat y el INE
con cruces). Para los casos tipo, tres grupos por paro de 20–64 años (2025) y salario mediano (2024):
- Bajo paro y salario alto: País Vasco, Navarra, Madrid y Cataluña.
- Bajo paro y salario medio: Cantabria, Aragón, La Rioja, Castilla y León, Galicia, Asturias y Baleares.
- Paro alto: Andalucía, Extremadura, Canarias, Murcia, Castilla-La Mancha y Comunitat Valenciana.
- Ceuta y Melilla, aparte (24 %–25 %; muestras pequeñas).

**Madrid y Barcelona metropolitanas frente al resto.** En empleo no separa el paro (Madrid 10,0 %, Barcelona 9,1 %,
resto no metropolitano 12,8 % en 2023, y otras áreas metropolitanas como Cádiz están en el 22,3 %). Lo recomiendo
como eje de **coste** (vivienda, capacidad): ahí es donde «la vida cómoda en provincia es pobreza en Madrid».
- Para empleo bastan la Comunidad de Madrid y la provincia de Barcelona, que es como Eurostat las aproxima.
- Si la coordinadora lo adopta, empleo puede aportar el salario medio de Madrid (2.762 €/mes) y de Cataluña
  (2.530 €/mes), más la mediana EAES por comunidad, para cruzarlos con el alquiler.

<!-- Fuentes de los sondeos (2026-10-19):
Eurostat API: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{lfst_r_lfu3rt,lfsa_urgan,lfsa_ergan,lfsa_etpgan,lfsa_eppga,lfsa_eppgai,ilc_iw01,ilc_iw05,lfst_r_urgau,met_lfu3rt,yth_empl_140}
INE Tempus: https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{66237..66251,65980}
Datos de la página: ui/site/public/visualizaciones/data/empleo.json (headline, regions, composition.territory, narratives.reform.annual, long_term).
Búsqueda de la tabla 65980: catálogo datos.gob.es «asalariados del sector público por tipo de contrato o relación laboral, sexo y grupo de edad (EPA), identificador API 65980». -->
