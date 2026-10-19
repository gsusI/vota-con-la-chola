# Segmentos en educación: dimensiones que separan realidades y casos tipo

Vertical: `/visualizaciones/educacion/` · Fecha: 2026-10-19 · Alcance: auditoría y propuesta. No cambia código ni datos.

- **Dónde estamos.** La página contrasta gasto y PISA con medias nacionales y de comunidades, y ya tiene varios cortes: brecha por ISEC (una sola cifra), alumnado inmigrante, abandono según los estudios de la madre y por comunidad, gasto familiar por quintil (EPF) y PIAAC por edad.
- **Adónde vamos.** Que los titulares y la figura consolidada enseñen *dónde* están las diferencias (origen social, comunidad, generación y, de forma secundaria, origen migratorio), no solo la media.
- **Qué sigue.** Dos cambios, por orden (sección 5): una figura «dónde está la diferencia», que sería la segunda pieza de «el dato mata el relato», y reescribir el titular de abandono con su efecto de composición.

Fuentes que se citan aquí (consultadas el 2026-10-19):

- **INEE, PISA 2022. Informe español (2023)**: `etl/data/raw/education/docs/inee_pisa2022_informe_espanol.pdf`, landing en `ui/site/public/visualizaciones/data/educacion.json` → `sources.vclc_education_curated.documents`.
- **OCDE, PISA 2022, nota de país España** (copia del INEE): `etl/data/raw/education/docs/oecd_pisa2022_country_note_es.pdf`.
- **INEE, PIAAC 2023. Informe español (2024)**: `etl/data/raw/education/docs/inee_piaac2023_informe_espanol.pdf`.
- **Eurostat**, API JSON `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<código>`, con su página en `https://ec.europa.eu/eurostat/databrowser/view/<código>/default/table`.
- **Ministerio de Educación, EDUCAbase** (explotación de la EPA): abandono según los estudios de la madre, tabla `aban_1_08`, ya cargada en `etl/data/staging/education-es.db`.

---

## 1. Inventario: medias que se leen como si describieran a todos

| Elemento de la página | Cifra media | ¿Engaña? | Separación entre grupos (fuente, año) |
|---|---|---|---|
| `.vizStat` y «Lo esencial» 2: PISA matemáticas | 473 (2022); 485 en 2003 | **Sí.** El debate se hace sobre los 12 puntos perdidos y la distancia con la OCDE (473 frente a 472), mientras dentro de España la distancia es 7 veces mayor. | Cuartil ISEC alto frente a bajo: **86 puntos** (INEE PISA 2022, §3.5.1.3; nota de país, p. 5). Entre comunidades: 52 (Castilla y León 499, Canarias 447), y 104 si se cuentan Ceuta y Melilla (395). Pública 462 y privada (concertada más privada) 497: 35 puntos, que bajan a **19** al descontar el ISEC del alumno y a **5** al descontar también el del centro (INEE, Tabla 3.3.a y Fig. 3.4.b1). Inmigrante frente a nativo: 33, que bajan a 7 a igual ISEC (nota de país). Chicos frente a chicas: +10 en matemáticas y −25 en lectura (nota de país). |
| `.vizStat` y titular de abandono: «12,8 % en 2025» | 12,8 % (18-24) | **Sí, y mucho.** Promedia realidades que van del 2 % al 33 %. | Según los estudios de la madre: **2,4 %** con superiores frente a **32,9 %** con Primaria o menos, 14 veces más (EDUCAbase `aban_1_08`, 2025; ya en el JSON: `distribution.leavers_by_mother`). Nacidos en España **9,6 %**, nacidos fuera **27,4 %** (Eurostat `edat_lfse_02`, 2025). Hombres 15,9 % y mujeres 9,5 % (`edat_lfse_14`, 2025). País Vasco 3,6 % y Murcia 20,6 % (`edat_lfse_16`, 2025). |
| «Lo esencial» 3: «mucho menos abandono» (del 30,9 % de 2002 al 12,8 %) | −18 puntos | **Sí: efecto de composición sin separar.** Dentro de cada grupo de madre el abandono bajó poco. | Madre con Primaria o menos: 38,8 → 32,9 (−6). Primera etapa de Secundaria: 24,6 → 17,5 (−7). Segunda etapa: 10,5 → 8,7 (−2). Superiores: 4,5 → 2,4 (−2). Total: 30,9 → 12,8 (−18) (EDUCAbase `aban_1_08`, 2002-2025). Ningún grupo cae lo que cae el total, así que buena parte de la mejora viene de que las madres de hoy tienen más estudios. Cautela: el grupo «No consta» (49 → 28,8 %) pesa y la descomposición exacta pide los pesos de cada grupo (sección 4). |
| `.vizStat` de gasto por alumno (+26 % desde 2000; 87 % de la OCDE) | 9.557 $ PPA (2022) | Algo. Es una media de sistemas que financian las comunidades. | Gasto de la consejería por alumno no universitario en 2022: Madrid **3.634 €** y País Vasco **7.507 €**, el doble (JSON `regions_pisa.rows`; Ministerio). Ojo: Madrid tiene un 47 % de alumnado en centros privados o concertados (INEE, Fig. 3.4.b), lo que baja el cociente. Ya se muestra en `#regiones`. |
| `.vizStat` de sobrecualificación: 34,0 % (UE 21,4 %) | 34,0 % (20-64) | Poco por edad, bastante por origen. | Extranjeros 46,4 % y españoles 32,7 %; de 25 a 34 años, 32,5 % (Eurostat `lfsa_eoqgan`, 2025). Mujeres 35,0 % y hombres 32,9 %. La edad apenas cambia la cifra; la nacionalidad, 14 puntos. |
| «Lo esencial» 5 y `#titulacion`: reloj de arena 25-34 (52,5 % superiores, 24,5 % como mucho ESO) | Media nacional de 25-34 | Sí, en territorio. | Superiores de 25 a 34 años: País Vasco **68,6 %**, Canarias **43,7 %**. Como mucho ESO: País Vasco 12,3 % y Andalucía 32,0 % (Eurostat `edat_lfse_04`, NUTS 2, 2025). Ciudades 56,9 %, pueblos 47,3 % y zonas rurales 43,8 % de titulados superiores (`edat_lfs_9913`, 2025). |
| `#adultos`: PIAAC lectura 247 (OCDE 260) | Media 16-65 | Sí: mezcla generaciones y niveles educativos. | De 16 a 24 años, 257; de 55 a 65, 235 (22 puntos; INEE PIAAC, Cuadro 2.1). Titulados superiores 271 y sin Secundaria superior 218 (**53 puntos**). Por estudios de los padres, la brecha española es la más baja del estudio: 24 puntos en lectura (INEE PIAAC, §2.3.5). Nativos frente a inmigrantes: 36 en lectura (§2.3.4). |
| `#adultos` y nivel educativo de la población adulta (no destacado) | — | Es la dimensión que falta. | Como mucho ESO: 24,5 % de 25 a 34 años, 32,5 % de 35 a 44, 35,3 % de 45 a 54 y **43,6 %** de 55 a 64 (UE: 13,5 / 16,0 / 19,8 / 24,9). Superiores: 52,5 / 44,7 / 42,2 / 32,6 % (Eurostat `edat_lfse_03`, 2025). De 55 a 74 años, el 49,8 % no pasó de la ESO (`edat_lfs_9913`). |
| `#familias`: el gasto de los hogares en educación (570 € al año, 1,63 % del gasto) | Media por hogar | Ya segmentado. | Quintil 1: 190 € (1,06 %); quintil 5: 1.144 € (1,90 %) (INE EPF `t73828`, 2025). Se mantiene como está. |
| `#dato-relato` (figura consolidada) | Gasto frente a PISA de España, países y 17 comunidades | En parte. Ya colorea las comunidades por ISEC y da R² del ISEC = 81 % frente a 6 % del gasto, pero **no enseña la dispersión dentro de cada comunidad**, que es mayor que la que hay entre ellas. | Grupo de comunidades con ISEC por encima de la OCDE: media 492; resto: 469 (≈23 puntos; cálculo con `regions_pisa.rows` y la lista del INEE). Dentro de España, el cuartil ISEC separa 86 puntos. La brecha por ISEC va de 59 en Cantabria a 96 en Cataluña (INEE, Fig. 3.7.b). |

Lo que ya está bien y no hay que reproponer: abandono por madre y por comunidad (`#abandono`), equidad e inmigración (`#equidad`), la descomposición de la caída por composición en PISA (1,7 de 11 puntos), EPF por quintil y PIAAC por edad (tracker, fila «Visualizaciones: educación»).

## 2. Dimensiones: cuáles quedan y por qué

Criterio: cuánto separa a los grupos comparado con la media, y si el corte sigue diciendo algo a igual origen social. Si al descontar el ISEC la diferencia casi desaparece, el corte es en realidad un indicador indirecto del ISEC.

### Elegidas

1. **Origen social de la familia** (ISEC en PISA; estudios de la madre o de los padres en la EPA y en PIAAC). **Es la dimensión maestra.** En PISA separa 86 puntos, contra 12 perdidos desde 2003 y 1 de distancia con la OCDE. Explica el 81 % de las diferencias de PISA entre comunidades (R² del INEE con 19 territorios) y casi toda la ventaja de la concertada y la privada (35 → 5) y de los nativos (33 → 7). En abandono separa del 2,4 % al 32,9 %. En adultos separa menos (PIAAC: 24 puntos, la brecha más baja del estudio), porque en las generaciones mayores casi todos los padres tenían pocos estudios.
2. **Comunidad autónoma.** Es donde se decide y se financia la enseñanza, y la diferencia sigue siendo grande después de PISA: abandono del 3,6 % al 20,6 %, superiores de 25 a 34 años del 43,7 % al 68,6 %, gasto por alumno del simple al doble. En PISA, en cambio, la comunidad es sobre todo composición social (R² 81 %): **hay que presentarla siempre junto al ISEC**, nunca sola.
3. **Generación**, para la población adulta. El nivel educativo adulto es un promedio de cohortes muy distintas: 43,6 % sin pasar de la ESO a los 55-64 años y 24,5 % a los 25-34. Cualquier cifra adulta (PIAAC, titulación, rendimiento laboral) sin edad mezcla a quien estudió en 1975 con quien estudió en 2015. Ojo, la brecha con la OCDE no se cierra con la edad: es de 14 puntos a los 16-24 años y de 6 a los 55-65.
4. **Origen migratorio**, secundaria y solo después de la etapa obligatoria. A los 15 años casi todo es ISEC (33 → 7). Después pesa por sí mismo: abandono del 27,4 % entre los nacidos fuera frente al 9,6 %, sobrecualificación del 46,4 % frente al 32,7 %, PIAAC −36. Es además el grupo que más crece (3,4 % del alumnado de 15 años en 2003 y 15 % en 2022; la mitad está en el cuartil ISEC bajo).

### Descartadas (con motivo)

- **Titularidad del centro** (pública, concertada, privada): la brecha bruta de 35 puntos baja a 5 a igual ISEC de alumno y centro (INEE, Fig. 3.4.b1; La Rioja llega a −13 a favor de la pública). Es un indicador indirecto del origen social. Merece una frase y un dato dentro del corte por ISEC, no un eje propio. Hueco: no hay gasto por alumno de la concertada frente a la pública en el JSON.
- **Sexo**: diferencias estables y moderadas (PISA +10 en matemáticas y −25 en lectura; abandono 15,9 frente a 9,5 %; sobrecualificación 35,0 frente a 32,9 %). No describe realidades distintas en el sentido del encargo. Puede quedar como segunda línea en el panel de abandono, donde el dato ya existe (`edat_lfse_14`).
- **Rural o urbano** (grado de urbanización): abandono del 11,2 % en ciudades, 15,3 % en pueblos y 13,5 % en zonas rurales (`edat_lfse_30`, 2025), menos que entre comunidades. Superiores de 25 a 34 años: 56,9 / 47,3 / 43,8 %, pero esto es en buena parte quién emigra a la ciudad al titularse, no el sistema educativo local. PISA no publica ese corte para España. Sirve como sustituto de lo metropolitano (sección 6), no como dimensión.
- **Generación en el alumnado** (cohortes PISA): ya está en la página como serie temporal.

## 3. Casos tipo

Cifras verificadas, con la media nacional al lado. En PISA no hay puntuaciones publicadas por cuartil de ISEC en texto, solo en figura y en tablas de oecd.org, que bloquea la descarga (sección 4). Por eso los casos de 15 años se anclan en celdas publicadas (comunidad × titularidad) y en la brecha de 86 puntos entre cuartiles, y lo dicen.

| # | Caso | Cifras clave | Media nacional | Salto |
|---|---|---|---|---|
| 1 | **15 años, familia desfavorecida, centro público en Canarias o Andalucía** | PISA matemáticas en la pública: Canarias **439**, Andalucía **448** (INEE, Tabla 3.3.b). En España, el cuartil ISEC bajo saca 86 puntos menos que el alto. Si además es inmigrante (la mitad del alumnado inmigrante está en el cuartil bajo), 33 puntos menos que un nativo, 7 a igual ISEC. | 473 | −25 a −34 solo por comunidad y titularidad, antes de sumar el cuartil ISEC |
| 2 | **15 años, familia favorecida, concertada o privada en Castilla y León, Asturias o Madrid** | Privada: Asturias **523**, Castilla y León **516**, Madrid **512**. El 36 % del alumnado español en el quintil ISEC internacional más alto saca **511** (nota de país). | 473 | +39 a +50 |
| 3 | **Joven de 18-24 años, madre con Primaria o menos (o nacido fuera), hombre** | Abandono **32,9 %** con madre de Primaria (EDUCAbase 2025), **27,4 %** si nació fuera (`edat_lfse_02`), **15,9 %** si es hombre (`edat_lfse_14`). En Murcia, **20,6 %** de media (`edat_lfse_16`). | 12,8 % | ×2,6 por madre; frente a hijos de madre universitaria (2,4 %), ×14 |
| 4 | **Joven de 18-24 años, madre universitaria, País Vasco** | Abandono **2,4 %** con madre universitaria y **3,6 %** de media en el País Vasco. | 12,8 % | ÷5 |
| 5 | **Titulado superior de 25-34 años, con nacionalidad extranjera, en un empleo que no pide su título** | Sobrecualificación: extranjeros **46,4 %** (20-64 años), españoles 32,7 %, de 25 a 34 años 32,5 % (`lfsa_eoqgan`, 2025). | 34,0 % (UE 21,4 %) | +12 puntos por origen; la edad apenas mueve la cifra |
| 6 | **Adulto de 55-64 años** frente a **joven de 25-34** | Como mucho ESO: **43,6 %** frente a **24,5 %**; superiores 32,6 % frente a 52,5 % (`edat_lfse_03`, 2025). PIAAC lectura: 235 (55-65 años) frente a 254 (25-34) (INEE PIAAC). | Como mucho ESO de 25-64: 34,6 % (`edat_lfs_9913`) | 19 puntos de diferencia entre generaciones; la brecha con la UE es la misma (+19 y +11) |

Si solo caben tres: **1 frente a 2** (el abanico de PISA, de 439 a 523 alrededor de 473), **3 frente a 4** (abandono del 2 % al 33 % alrededor de 12,8 %) y **6** (la población adulta son dos países).

## 4. Disponibilidad de datos por dimensión y cruce

| Dimensión o cruce | Indicador | Fuente y código | Años y granularidad | ¿En staging o en el JSON? | Huecos |
|---|---|---|---|---|---|
| ISEC (cuartiles), España | PISA por cuartil | OCDE *PISA 2022 Results* Vol. I y II, tablas por cuartil; INEE Fig. 3.7.a | 2012-2022 | Solo la brecha (86) y R² (14 %) (`equity`) | Las puntuaciones Q1 y Q4 solo están en figura (imagen) o en oecd.org, que da `403` con desafío Cloudflare (incidente `nso-2026-10-oecd-cf-challenge`). Alternativas: microdatos PISA (descarga grande, fuera de este alcance) o informes regionales con texto (p. ej., el de Castilla y León, educa.jcyl.es). |
| ISEC × comunidad | Brecha Q4−Q1 y R² por comunidad | INEE Fig. 3.7.b y 3.8.b (texto parcial: Cantabria 59, Cataluña 96, Madrid 91, Murcia 93, Asturias 93, Melilla 88; R² del 7,5 % en Cantabria al 17,7 % en Asturias) | 2022, 19 territorios | No | Faltan las 19 brechas en texto. Las comunidades tienen muestra ampliada completa en 2015, 2018 y 2022; en 2009 y 2012 solo una parte. PISA 2018 no publicó lectura para España (anomalías de respuesta). |
| Titularidad × comunidad | PISA bruto | INEE Tabla 3.3.a/b (texto) | 2022 | No (curable con cita, como el resto de `pisa_curated_es.json`) | Ajustado por ISEC solo para España y unas pocas comunidades en texto. |
| Titularidad × ISEC | Brecha ajustada | INEE Fig. 3.4.b1: 35 → 19 → 5 | 2022 | No | — |
| Origen migratorio, 15 años | Brecha bruta y ajustada | Nota de país OCDE | 2022 | Sí (`equity.composition`) | — |
| Origen × abandono | Abandono por país de nacimiento | Eurostat `edat_lfse_02` | 2002-2025 anual, nacional | **No** | No hay cruce por comunidad. |
| Madre × abandono | Abandono por estudios de la madre | EDUCAbase `aban_1_08` | 2002-2025 | Sí (`distribution.leavers_by_mother`) | Faltan los **pesos** de cada grupo para separar composición de mejora dentro de cada grupo. Buscar la tabla de distribución de jóvenes de 18 a 24 años por estudios de la madre en la misma explotación EPA de EDUCAbase, o calcularla con microdatos de la EPA del INE. «No consta» es grande (28,8 %). |
| Sexo × abandono | | Eurostat `edat_lfse_14` (sex) | 1992-2025 | Solo el total | Barato: misma consulta con `sex=M,F`. |
| Comunidad × abandono | | Eurostat `edat_lfse_16` | 2000-2025, NUTS 2 | Sí | Rupturas EPA 2005, 2014 y 2021 ya marcadas. Muestra pequeña en Ceuta, Melilla y La Rioja (marca de fiabilidad baja). |
| Comunidad × titulación 25-34 | | Eurostat `edat_lfse_04` (NUTS 2) | 2000-2025 | **No** (solo nacional, `edat_lfse_03`) | — |
| Generación × titulación | | Eurostat `edat_lfse_03` (25-34 … 55-64); `edat_lfs_9913` (55-74) | 1992-2025 | Solo 25-34 | 65 años o más no está en `edat_lfse_03`; usar `edat_lfs_9913` (55-74) o el INE (EPA, nivel de formación por edad). |
| Urbanización × abandono y titulación | | Eurostat `edat_lfse_30`, `edat_lfs_9913` (`deg_urb`) | 2012-2025 | No | No distingue Madrid y Barcelona metropolitanas. |
| Origen y edad × sobrecualificación | | Eurostat `lfsa_eoqgan` (`citizen`, `age`, `sex`) | 1995-2025 (rupturas) | Solo el total | No encontré tabla regional de sobrecualificación en Eurostat; no verificado. |
| Edad, estudios propios y de los padres × PIAAC | | INEE PIAAC 2023, Cuadro 2.1 y §2.3.4-2.3.5 | 2023 (una sola ronda comparable) | Edad y estudios propios sí; padres y origen no | Sin comunidad (España no amplió muestra regional en PIAAC 2023, según lo que muestra el informe). |
| Gasto por comunidad | Gasto de la consejería por alumno | Ministerio (Estadística del Gasto) | 2022 en la página | Sí | Sin desglose pública/concertada por alumno. |

## 5. Recomendación priorizada

**1. Nueva figura consolidada «¿Dónde está la diferencia?»**, colocada justo después de `#dato-relato` o integrada en ella como segundo panel. Es la que más cambia la lectura de la página. Forma: un dumbbell ordenado de brechas de PISA matemáticas 2022, cada fila con su brecha bruta y la ajustada por ISEC cuando exista:

- cuartil ISEC alto frente a bajo: 86;
- máxima entre comunidades: 52 (y la parte que explica el ISEC: R² 81 %);
- privada y concertada frente a pública: 35 → 19 → 5;
- nativo frente a inmigrante: 33 → 7;
- chicos frente a chicas: 10;
- caída de España 2003-2022: 12;
- España frente a OCDE: 1.

Mismo eje en puntos, que empieza en cero. Zanja tres relatos con una sola imagen: «la concertada lo hace mejor», «los inmigrantes bajan la media» y «el problema es la comunidad X». También pone la caída de 12 puntos en su escala. Debe decir qué queda abierto: el ajuste por ISEC no es causal; la brecha que queda de 5 puntos en la titularidad puede ser selección. Titular propuesto: «Dentro de España, el origen familiar separa 86 puntos de PISA: siete veces lo que ha caído la nota desde 2003, y más que cualquier diferencia entre comunidades o entre pública y concertada». Datos: todo verificable con cita del INEE y la OCDE en `pisa_curated_es.json`, salvo las Q1/Q4 absolutas (sección 4), que no hacen falta para esta forma.

**2. Reescribir el titular y la tarjeta de abandono con la composición a la vista.** La tarjeta `.vizStat` pasa de «12,8 %» a «12,8 %: 2,4 % si la madre es universitaria y 32,9 % si tiene Primaria». En «Lo esencial» 3 y en la conclusión hay que corregir «mucho menos abandono» y añadir que dentro de cada grupo de madre la caída es de 2 a 7 puntos, frente a 18 del total: la mejora viene sobre todo de que las madres tienen más estudios. El panel de madre ya existe; hay que convertirlo en dumbbell 2002 → 2025 por grupo más el total, sumar el corte por país de nacimiento (`edat_lfse_02`) y calcular la descomposición dentro de los grupos frente a composición en cuanto estén los pesos. Hasta entonces, decirlo como hipótesis («ningún grupo cae lo que cae el total»), no como cifra.

Lo demás es menor y puede ir después: la generación en `#titulacion` y `#adultos` (añadir las filas de 35-44, 45-54 y 55-64 de `edat_lfse_03`), titulación de 25-34 años por comunidad (`edat_lfse_04`) y sobrecualificación por nacionalidad en su tarjeta.

## 6. Dimensiones compartidas (para armonizar con las otras verticales)

- **Edad.** Educación no puede usar 16-34 años como bloque: los indicadores oficiales vienen con edades fijadas por definición. Propuesta:
  - **15 años** (PISA), solo en esta vertical;
  - **18-24** (abandono, definición UE);
  - **25-34** como banda «joven adulto» compartida (titulación, sobrecualificación, PIAAC; Eurostat la publica en todas las tablas de nivel educativo);
  - **35-64** como adulto, desglosable en **35-44 / 45-54 / 55-64** cuando la generación importe;
  - **65 o más**, solo para el nivel educativo de la población (usar 55-74 de `edat_lfs_9913` o la EPA del INE).

  Si la coordinadora fija 16-34 / 35-64 / 65+, educación puede casar 25-34 dentro de 16-34 y 35-64 tal cual, señalando que 18-24 se publica aparte.
- **Territorio.** **Comunidad autónoma (NUTS 2)** como corte común: está en PISA (17 comunidades más Ceuta y Melilla en 2022), en abandono y en titulación. **Madrid y Barcelona metropolitanas: no hay dato educativo** en esa escala (PISA no la publica; la EPA educativa de Eurostat llega a NUTS 2). El sustituto disponible es el **grado de urbanización de Eurostat** (ciudades, pueblos y periferias, zonas rurales) para abandono y titulación, a escala nacional. Propongo que la coordinadora acepte «comunidad autónoma + grado de urbanización» como corte común cuando no haya dato metropolitano.
- **Origen social** (propuesta de dimensión compartida): educación de la madre o de los padres (EPA, PIAAC) o ISEC (PISA), con quintiles de renta en las verticales de renta y vivienda. Así, «familia de origen con estudios bajos» puede ser el mismo caso tipo en educación, empleo y vivienda.
