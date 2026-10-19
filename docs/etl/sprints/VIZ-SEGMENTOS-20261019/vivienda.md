# Vivienda: dimensiones que parten la realidad y casos tipo

Auditoría de `/visualizaciones/vivienda/` (y del «16 %» de `/visualizaciones/carga-fiscal/#mediana-vivienda`) con el estándar
de `AGENTS.md` («Public Data Visualizations»). Solo informe: no se ha tocado código, datos ni builds.

- Dónde estamos: la página ya separa la sobrecarga por quintil, por edad y por tenencia (inquilinos de mercado frente al total)
  y el alquiler SERPAVI frente a la renta por comunidad. Pero sigue sin cruzar **tenencia × edad × territorio**, que es donde
  se separan de verdad las realidades, y sus denominadores (renta media de *todos* los hogares, salario medio nacional)
  siguen siendo medias que esconden a quien alquila.
- A dónde vamos: 3 dimensiones (tenencia, edad/cohorte, territorio tensionado frente al resto) y 5 casos tipo con su peso
  de la vivienda en la renta y lo que les queda, siempre con la media nacional al lado.
- Qué sigue: la figura de composición «tenencia × edad» como dato consolidado de la parte de capacidad, y rehacer
  `#alquiler-regiones` con renta de inquilinos y ciudad frente a resto de provincia (sección 5).

Sondeos hechos el 2026-10-19 (Eurostat API JSON, INE Tempus, SERPAVI ya descargado en
`etl/data/raw/housing/apis/mivau_serpavi_2011_2024.xlsx`, INE ADRH). Encuesta de condiciones de vida: «ECV 2025» recoge la
renta de 2024; los costes de vivienda y la tenencia son de 2025.

## 1. Inventario: dónde la página usa una media como si describiera a todos

| Elemento (archivo) | Cifra | ¿Engaña la media? A quién deja fuera, y cuánto se separan los grupos |
|---|---|---|
| `.vizStat` «Piso de 90 m² en años de salario bruto medio» (`page.js:185`) | 6,7 años (tasación 2025) | Sí, doblemente. Precio nacional: 9,5 años en Madrid, 11,3 en Baleares, 3,6 en Extremadura y 4,2 en Castilla y León (×3,2 entre extremos; `vivienda.json` `regions.rows[].years_salary`). Y solo afecta a quien compra ahora; el 48,9 % de los hogares ya es propietario sin hipoteca (INE ECV t=9994, 2025). |
| `.vizStat` «Edad media a la que los jóvenes dejan la casa de sus padres» | 30,2 (2025) | Media de edad: oculta que el 50,2 % de los de 25–34 años sigue en casa de sus padres (Eurostat `ilc_lvps08`, 2025) y que solo el 14,5 % de los de 16–29 está emancipado (CJE, Observatorio de Emancipación 2025). |
| Resumen, punto 1 y figura `#capacidad` (`capacity.js:33`) | 8,6 años con el sueldo neto mediano, 8,4 con el de 25–34 (2024) | El salario joven no es el problema: el neto de 25–34 (20.455 €) es casi igual que el mediano (19.961 €) (INE EES t=28191/28201, neto con tipo OCDE). La brecha generacional no está en el sueldo, sino en la tenencia y en dónde se vive; la cifra nacional la borra. |
| `#capacidad`, cuota hipotecaria en % de la renta del hogar mediano | 34,3 % (BdE `si_1_5`, 2025) | Nacional y para el hogar mediano (que ya tiene casa). Con el mismo método (90 m² tasados, 80 % financiado, 25 años al 2,78 %, renta neta media de la comunidad): Madrid 31 %, Baleares 33 %, Cataluña 23 %, Castilla y León 14 %, Extremadura 12 % (cálculo propio con `regions.rows[].price_m2`, `drivers.mortgage_rate_pct` y la renta de la ECV t=9949). Para un joven que compra solo en Madrid, ~59 %. |
| `#sobrecarga`, título (`capacity.js:99`) | «En el conjunto de la población España está en la media (7,2 % frente a 7,7 %)» | La frase pone en primer plano justo la media que engaña. Por tenencia (Eurostat `ilc_lvho07c`, 2025): propietario sin hipoteca 1,9 %, con hipoteca 3,4 %, alquiler reducido 8,4 %, alquiler de mercado 26,8 %: **×14** entre el primero y el último. |
| `#sobrecarga`, dek: «al hogar mediano le quedan 18.823 PPS tras la vivienda» | 18.823 PPS (2025) | Es el hogar mediano, que es propietario. Coste medio mensual de la vivienda (Eurostat `ilc_mded03`, 2025): propietarios 366 PPS, inquilinos 863 PPS (×2,4), con una renta de inquilinos de mercado un 25 % menor que la de los propietarios (31.748 € frente a 42.138 €; INE ECV t=59956). En peso sobre la renta, ~30 % frente a ~9,5 % (calculado: 863 × 0,907 × 12 / 31.203 € de renta media de todos los inquilinos; 366 × 0,907 × 12 / 42.138 €). |
| «16 %» de gasto medio en vivienda (`carga-fiscal/Squeeze.js:266`, `ilc_mded01`) | 16,0 % (2025) | Es la **media** de los cocientes; la **mediana** es 10,4 % (`ilc_lvho08a`). Por tipo de hogar (`ilc_mded01`): una persona sola menor de 65 años, 28,9 %; pareja con al menos un mayor de 65, 12,4 %. Solo el alquiler ya se lleva el 26,7 % de la renta de los inquilinos y el 39,4 % de la de un inquilino que vive solo y tiene menos de 65 años (`ilc_mded02`). |
| `#distribucion`, sobrecarga por edad (`distribution.js`) | 15–29: 7,2 %; 65+: 4,8 % | Los jóvenes salen *bajos* porque la mitad vive con sus padres y se cuentan en el hogar de estos. La página ya lo advierte en una nota, pero la barra transmite lo contrario de la realidad. |
| `#distribucion`, quintiles | Q1 27,7 %, Q5 0,2 % | Correcto, pero en parte es mecánico: la sobrecarga se define sobre la renta, así que se concentra abajo por construcción. No dice quién es el Q1 (inquilinos, personas solas, hogares extranjeros). |
| `#alquiler-regiones` (`distribution.js:162`) | Madrid 20,3 %, Galicia 14,6 % | Tres medias juntas. (1) El denominador es la renta media de todos los hogares; la de los inquilinos es un 19 % menor en España (31.748 € frente a 38.994 €), así que Madrid pasaría de 20 % a ~25 %. (2) Es la comunidad, no la ciudad: alquiler mediano SERPAVI de 2024 en la ciudad de Madrid 869 €, en el resto de la provincia ~739 € (media de las medianas municipales ponderada por contratos); en Barcelona 900 € frente a ~694 €. (3) Son todos los contratos vigentes, no los nuevos. La nota lo dice, pero el titular concluye «en torno al 15–20 %». |
| Tenencia del Censo: «la propiedad bajó al 75,5 %» (`page.js:527`) | 75,5 % (2021) | Media: según la edad de la persona de referencia (ECV t=9994, 2025), es propietario el 88,2 % de los hogares de 65 o más años y el 30,6 % de los de 16–29; alquila a precio de mercado el 5,5 % de los mayores y el 49,8 % de los jóvenes. |
| `#tenencia-jovenes` (EFF) | Menores de 35 propietarios: 69,8 % (2011) → 36,7 % (2024) | Bien: ya está partido por edad y por cohortes. Es la mejor figura de la página para este problema. |

## 2. Dimensiones: cuáles separan y cuáles sobran

Criterio: cuánto se alejan los grupos de la media en sobrecarga o en peso de la vivienda, y si la dimensión añade algo que no
explique ya otra.

| Dimensión | Separación (dato, fuente) | Decisión |
|---|---|---|
| **Régimen de tenencia** (4 grupos: propiedad sin hipoteca / con hipoteca / alquiler de mercado / alquiler reducido o cesión) | Sobrecarga 1,9 / 3,4 / 26,8 / 8,4 % frente a 7,2 % (`ilc_lvho07c` 2025); coste 366 frente a 863 PPS/mes (`ilc_mded03`); peso de la población 45,5 / 28,1 / 17,4 / 9,0 % (`ilc_lvho02`) | **Elegida, la primera.** Es la que más separa (×14) y explica por qué la media es baja: casi la mitad de la población no tiene apenas gasto. |
| **Edad / cohorte** (persona de referencia; más «sigue en casa de sus padres») | Alquiler de mercado: 49,8 % (16–29), 32,1 % (30–44), 15,3 % (45–64), 5,5 % (65+); propiedad sin hipoteca 82,4 % en 65+ (ECV t=9994 2025). Viven con sus padres el 50,2 % de los de 25–34 (`ilc_lvps08`). Propietarios menores de 35: 69,8 % (2011) → 36,7 % (2024) (EFF) | **Elegida.** Actúa sobre todo *a través* de la tenencia, pero añade dos cosas que la tenencia no ve: los no emancipados (invisibles en la sobrecarga) y la cohorte (quien compró antes de 2007 pagó con otros precios y hoy tiene la casa pagada). |
| **Territorio tensionado frente al resto** (Madrid, Barcelona y su área, Baleares; frente a otras ciudades y a zonas rurales) | Años de salario por piso: 9,5 Madrid, 11,3 Baleares, 3,6 Extremadura (×3,2). Alquiler SERPAVI 2024: ciudad de Madrid 869 €, Barcelona 900 €, Palma 800 €; Zamora 410 €, Lugo 404 €, Ourense 410 € (×2,2). Hogares en alquiler de mercado: Cataluña 23,2 %, Madrid 22,6 %, Baleares 21,3 %; Castilla y León 11,2 % (ECV t=9997). Sobrecarga por grado de urbanización: ciudades 8,2 %, zonas intermedias 6,8 %, rurales 3,9 % (`ilc_lvho07d`) | **Elegida.** Multiplica el efecto de la tenencia: el mismo inquilino joven paga el doble en Madrid que en Zamora. Comunidad autónoma no basta: dentro de la provincia la capital se separa del resto (Madrid 869 € frente a ~739 €). |
| Quintil de renta | Q1 27,7 % frente a Q5 0,2 % (`ilc_lvho07b`) | **Se mantiene como figura (ya está), no como dimensión de los casos.** Es en buena parte consecuencia de la tenencia y del tipo de hogar, y es circular (la sobrecarga se mide sobre la renta). |
| Tipo de hogar | Persona sola menor de 65: 28,9 % de peso, 24,4 % de sobrecarga; pareja con un mayor de 65: 12,4 % y 4,2 % (`ilc_mded01`, `ilc_lvho07e`) | **Descartada como eje; se usa dentro de los casos.** Gran parte de la diferencia es edad + tenencia + economías de escala. |
| Origen (nacionalidad) | Alquiler de mercado: hogares españoles 11,3 %, de la UE 47,4 %, de fuera de la UE 63,4 % (ECV t=9995) | **Descartada como eje** (se canaliza por la tenencia y la renta); conviene una frase en el texto, porque explica parte del aumento de inquilinos. |

## 3. Casos tipo

Cinco hogares que cubren la mayor parte de la población y casi todo el problema. Las cifras **publicadas** llevan su tabla;
las **calculadas** dicen su fórmula. «Queda» es la renta neta menos el gasto en vivienda, dividida por unidades de consumo
(escala OCDE modificada: 1 / 0,5 / 0,3), para que hogares de distinto tamaño se puedan comparar con la media.

| Caso | Cuántos hay | Vivienda / renta | Sobrecarga del grupo (>40 %) | Queda tras la vivienda (€/año por unidad de consumo) |
|---|---|---|---|---|
| **Media nacional** | — | 16,0 % de media, 10,4 % de mediana (`ilc_mded01`, `ilc_lvho08a`) | 7,2 % (`ilc_lvho07c`) | ~19.300 (22.943 € por unidad de consumo × 0,84; ECV t=9942) |
| **A. Pareja de 65 o más años, propietaria sin hipoteca, en una provincia de Castilla y León** | El 82,4 % de los hogares de 65+ son propietarios sin hipoteca; Castilla y León es la comunidad con más (58,4 % de todos sus hogares) | ~8 % (calculado: 290 PPS/mes × 0,907 €/PPS = 263 €/mes, `ilc_mded03` propietarios A2_GE1_GE65; sobre 39.042 € de un hogar de 2 adultos sin niños, ECV t=9948). Publicado para todo el grupo: 12,4 % | 4,2 % (pareja con un mayor de 65); 1,9 % (propietarios sin hipoteca) | ~23.900 (calculado) |
| **B. 25–34 años, vive solo, alquiler de mercado en la ciudad de Madrid** | Una minoría: la mitad de los de 25–34 no se ha ido de casa; de los hogares de 16–29, el 49,8 % alquila | Solo el alquiler: 42–51 % (869 €/mes SERPAVI 2024, contratos vigentes; sobre el neto de 25–34, 20.455 € de media nacional, o ~25.000 € con el diferencial salarial de Madrid, ETCL ×1,22). Con un contrato nuevo: 98,7 % del sueldo neto joven (CJE 2025, media nacional). Referencia publicada: el alquiler se lleva el 39,4 % de la renta de los inquilinos solos menores de 65 (`ilc_mded02`) | 26,8 % (inquilinos de mercado); 24,4 % (personas solas menores de 65) | 10.000–14.600 (calculado; con un contrato nuevo, casi nada) |
| **C. Pareja de 30–44 años con un hijo, alquiler de mercado en el área metropolitana (Getafe, L'Hospitalet)** | El 32,1 % de los hogares de 30–44 alquila a precio de mercado | ~27 % solo de alquiler (700–726 €/mes SERPAVI 2024; sobre 31.748 €, renta media de los inquilinos de mercado, ECV t=59956) | 26,8 % | ~12.800 (calculado, 1,8 unidades de consumo) |
| **D. Pareja de 30–44 años que compra hoy 90 m² en la Comunidad de Madrid** | El 37,9 % de los hogares de 30–44 tiene hipoteca | Cuota: 1.228 €/mes = 31 % de la renta media de un hogar madrileño (47.375 €); en Extremadura, con el mismo cálculo, 12 %. Entrada más impuestos: ~86.000 € (20 % + ITP del 6 %), 1,8 años de renta neta íntegra. Quien compró en 2000 empezó con un esfuerzo nacional del 29,1 % y hoy ya ha pagado la casa (BdE `si_1_5`) | 3,4 % (propietarios con hipoteca; Eurostat no cuenta la amortización del capital, así que lo subestima) | ~21.800 (calculado; incluye el ahorro forzoso de la amortización) |
| **E. 25–34 años que vive en casa de sus padres** | 50,2 % de los de 25–34 (`ilc_lvps08`); edad media de emancipación 30,2 (`yth_demo_030`) | ~0 % propio: se cuenta dentro del hogar de los padres, normalmente propietarios | No aparece: tira hacia abajo la sobrecarga de los jóvenes (15–29: 7,2 %, por debajo de la UE, 9,1 %) | Sin dato propio: el coste es no poder irse |

Lectura: entre A y B hay un factor de 5 a 6 en el peso de la vivienda y de 2 en lo que queda, y la media nacional (16 %) se
parece a A, no a B ni a C. Los mayores de 65 tienen ya la renta por unidad de consumo más alta tras los de 45–64 (23.806 €
frente a 21.779 € de los de 16–29; ECV t=9942), y eso **antes** de restar la vivienda.

Supuestos de los cálculos (para reproducirlos): €/PPS = 0,907 (Eurostat `prc_ppp_ind`, A01, 2024); hipoteca: precio = 90 m²
× valor tasado de la comunidad (`regions.rows[].price_m2`, 2025), 80 % financiado, 25 años al 2,78 % (BdE, 2025), cuota
francesa; ITP del 6 % (Madrid, vivienda usada, `taxes.rates`). No se suman los suministros al alquiler en B y C, así que el
peso real es mayor. B y C usan la renta nacional por falta de un cruce oficial de edad × comunidad × tenencia (ver sección 4).

## 4. Disponibilidad de datos por dimensión y cruce

| Cruce | Tabla oficial | Años / detalle | ¿En staging? (`etl/data/staging/housing-es.db`) | Hueco honesto |
|---|---|---|---|---|
| Tenencia (4 grupos) × sobrecarga | Eurostat `ilc_lvho07c` | 2004–2025, país | Parcial: TOTAL, OWN_L, RENT_MKT; faltan OWN_NL y RENT_FR | — |
| Tenencia × coste en PPS × tipo de hogar | Eurostat `ilc_mded03` | 2025, país; solo OWN/RENT | No | No separa propietarios con y sin hipoteca |
| Peso del alquiler en la renta de los inquilinos × tipo de hogar | Eurostat `ilc_mded02` | país | Solo el total | — |
| Tenencia × edad de la persona de referencia | INE ECV t=9994 | 2004–2025, nacional | No | Sin coste ni sobrecarga por edad dentro de cada tenencia: solo con los microdatos de la ECV |
| Tenencia × comunidad | INE ECV t=9997 / t=76845 | 2004–2025 | Solo alquiler de mercado | Muestra de la ECV por comunidad: con unos 15.000 hogares, los inquilinos jóvenes de Madrid son del orden de un centenar; con microdatos hay que publicar intervalos |
| Tenencia × grado de urbanización | INE ECV t=60181; Eurostat `ilc_lvho07d`, `ilc_lvho08b` | 2025 | No | DEGURBA no separa Madrid de Valladolid: las dos son «ciudad» |
| Tenencia × nacionalidad | INE ECV t=9995 | 2025 | No | — |
| Renta por tenencia | INE ECV t=59956 | nacional | No | Ni por comunidad ni por edad |
| Viven con sus padres | Eurostat `ilc_lvps08` | 2004–2025, por edad | No | Sin comunidades (CJE las publica, pero con otra metodología) |
| Propiedad por edad (cohorte) | BdE EFF (curado) | 2002–2024 | Sí (`vclc_housing_curated`) | Solo menores de 35 frente al total |
| Tenencia × edad × municipio, sin error muestral | INE Censo 2021 | 2021 | No | Sin costes; una sola foto |
| Alquiler por municipio, distrito y sección censal | SERPAVI (MIVAU) | 2011–2024 | El xlsx está descargado (`etl/data/raw/housing/apis/mivau_serpavi_2011_2024.xlsx`); solo se ha parseado la hoja CCAA | Alquiler **declarado** de contratos vigentes, no el de los nuevos (oferta); no hay País Vasco ni Navarra |
| Renta por municipio | INE ADRH (Madrid t=31097, Barcelona t=30896, una tabla por provincia) | 2015–2024 | No | Es la renta de todos los hogares, no la de los inquilinos |
| Precio de oferta del alquiler / de los contratos nuevos | Ninguna estadística oficial; el CJE usa portales | — | No | Se nombra como hueco; si se usa el CJE, como fuente secundaria y diciéndolo |

## 5. Recomendación priorizada

1. **Nueva figura consolidada de la parte de capacidad: «Quién paga la vivienda: tenencia × edad»** (sustituye al titular de
   `#sobrecarga` y se coloca en su lugar). Un mosaico (Marimekko): el ancho de cada columna es el peso de cada edad
   (16–29, 30–44, 45–64, 65+); dentro, la altura es el peso de cada tenencia (ECV t=9994); el color, la sobrecarga de esa
   tenencia (`ilc_lvho07c`). Encima, una franja con los de 25–34 que viven con sus padres (`ilc_lvps08`), y los casos A–E
   marcados como puntos. Pone el efecto composición sobre la mesa: el 16 % es bajo porque la columna de 65+ es casi toda
   propiedad pagada. Título propuesto: «La media dice 16 %; quien alquila dedica a la vivienda el triple de su renta que
   quien es propietario, y el 27 % está sobrecargado, frente al 2 % de quien tiene la casa pagada». Le acompaña una tabla con los cinco casos y la media
   nacional al lado (sección 3), con el peso de la vivienda y lo que queda por unidad de consumo. No cambia la figura de
   apertura (el diagrama conectado de construcción y crédito): esa responde al «por qué», y esta al «a quién».
   Lo que deja ambiguo, y la figura debe decirlo: no hay sobrecarga oficial por edad dentro de cada tenencia (hacen falta
   microdatos) y los mayores propietarios no tienen gasto en efectivo, pero sí el coste de oportunidad del alquiler imputado.
2. **Rehacer `#alquiler-regiones`** con dos cambios: (a) el denominador pasa a ser la renta de los inquilinos (ECV t=59956,
   escalada por comunidad) o el sueldo neto de 25–34, en lugar de la renta media de todos los hogares; (b) se añade la
   capital frente al resto de su provincia con la hoja «Municipios» del SERPAVI ya descargada. Titular de ejemplo,
   comprobado con los datos: «En la ciudad de Madrid el alquiler mediano declarado (869 €) se lleva el 51 % del sueldo
   neto medio de un joven de 25–34; en Zamora (410 €), el 24 %».
3. **`.vizStat` y `carga-fiscal`.** Cambiar la primera cifra clave («6,7 años de salario bruto medio») por la sobrecarga
   partida, «26,8 % de los inquilinos de mercado frente al 1,9 % de los propietarios sin hipoteca», o al menos ponerla al
   lado. Y **sí**: el 16 % de `/visualizaciones/carga-fiscal/#mediana-vivienda` debe ir con su desglose en la misma figura
   o en el dek: media 16 % / mediana 10 %; solo el alquiler, 27 % de la renta de los inquilinos y 39 % de la de un
   inquilino que vive solo; sobrecarga 1,9 % (propiedad pagada) frente a 26,8 % (alquiler de mercado).

## 6. Dimensiones compartidas (para armonizar con las otras verticales)

- **Edad:** propongo **16–29 / 30–44 / 45–64 / 65+** (las bandas de la ECV del INE por persona de referencia) en lugar de
  16–34 / 35–64 / 65+. Motivo: en vivienda, 30–44 es la cohorte que compra o alquila con hijos y se separa claramente
  de 45–64 (alquiler de mercado 32,1 % frente a 15,3 %; propiedad sin hipoteca 15,2 % frente a 43,0 %); fundirlas
  borra el caso D. Las tablas oficiales de tenencia no traen 16–34 (solo con microdatos). Equivalencias cuando la fuente
  es Eurostat: jóvenes = `Y15-29` o `Y25-34` (emancipación), adultos = `Y18-64`, mayores = `Y_GE65`. Si la coordinadora
  necesita tres bandas comunes, 16–29 / 30–64 / 65+ se puede sacar de todas las tablas de la ECV sumando columnas.
- **Territorio:** comunidad autónoma como base (es lo que da la ECV) y, cuando haya dato municipal (SERPAVI, ADRH, Censo
  2021), **municipios de Madrid y Barcelona (y Palma) frente al resto de su provincia y al resto de España**. Para las
  tablas de la encuesta que no bajan de comunidad, el grado de urbanización (ciudades / zonas intermedias / rurales,
  DEGURBA) como sustituto de «urbano frente a rural». Añadiría Baleares al grupo tensionado: 11,3 años de salario por un
  piso, más que Madrid.
- **Propuesta añadida:** usar el **régimen de tenencia** como dimensión común con carga fiscal (IBI, alquiler imputado) y con
  pobreza o renta: es la que más separa realidades en esta vertical y probablemente en la de impuestos.

## Fuentes (consultadas el 2026-10-19)

- Eurostat EU-SILC: `ilc_mded01`, `ilc_mded02`, `ilc_mded03`, `ilc_lvho02`, `ilc_lvho07a/b/c/d/e`, `ilc_lvho08a/b`, `ilc_lvps08`,
  `prc_ppp_ind` — https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07c/default/table (cambiando el código).
- INE, Encuesta de Condiciones de Vida 2025: t=9994, 9995, 9997, 60181, 59956, 9948, 9942, 9949 — https://www.ine.es/jaxiT3/Tabla.htm?t=9994 (cambiando el número).
- INE, Atlas de Distribución de Renta de los Hogares: Madrid t=31097, Barcelona t=30896 (renta neta media por hogar, 2024: 53.213 € y 49.915 €).
- MIVAU, SERPAVI 2011–2024, hojas «CCAA» y «Municipios» — https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi
- Banco de España, indicadores del mercado de la vivienda `si_1_5` (esfuerzo teórico, tipo de los préstamos) y EFF (curado en staging).
- Consejo de la Juventud de España, Observatorio de Emancipación 2025 (emancipación del 14,5 %, alquiler del 98,7 % del sueldo neto joven), citado por Euronews el 2026-05-22: https://es.euronews.com/2026/05/22/el-alquiler-consume-el-987-del-salario-juvenil-en-pisos-individuales-y-mas-del-33-en-compa — fuente secundaria (el PDF del CJE no se pudo descargar).
- Datos ya publicados por la página: `ui/site/public/visualizaciones/data/vivienda.json` (`regions`, `territory`, `capacity`, `distribution`, `tenure`).
