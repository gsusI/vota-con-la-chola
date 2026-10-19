# Segmentos: fiscalidad (`/visualizaciones/carga-fiscal/`)

Auditoría de las medias nacionales de la vertical fiscal y propuesta de dimensiones y casos tipo. Fecha: `2026-10-19`.
Solo informe: no se ha tocado código, datos ni builds. Sondeos hechos el `2026-10-19` (Eurostat JSON, INE Tempus,
OCDE Taxing Wages vía DBnomics); cada cifra lleva su tabla. Cálculos propios marcados con «≈» y explicados en §3.

**Dónde estamos.** La página ya parte el IRPF por tramos, la redistribución OCDE (total frente a 18–65), la cuña fiscal a
tres niveles de salario, los tipos máximos por comunidad y la sobrecarga de vivienda de los inquilinos. Pero todo lo que
habla de «los hogares» (renta, lo que les queda, la vivienda, el gasto) sigue siendo una media o una mediana nacional, y
la base de staging solo guarda totales nacionales (ningún indicador por edad, tenencia, tipo de hogar ni quintil).

**Adónde vamos.** Cuatro dimensiones (edad, tenencia de vivienda, nivel de renta, hijos/tipo de hogar) y cinco casos tipo
que muestren cuánto pagan, cuánto reciben y cuánto les queda tras impuestos y vivienda, al lado de la mediana.

**Qué sigue.** §5: reescribir el lado «renta» de `#bolsillo` por edad (y tenencia) y añadir una figura de casos tipo en
cascada. Lo demás es secundario.

---

## 1. Inventario: dónde la media se presenta como representativa

| # | Dónde | Cifra actual | ¿Engaña? | A quién deja fuera, con números |
|---|---|---|---|---|
| 1 | `.vizStat` «Recaudación real por habitante» y `#por-habitante` | ×9,4: `1.270 €` (1965) → `11.972 €` (2024) por habitante | **Sí, si se lee como «lo que paga cada uno».** Incluye sociedades, cotizaciones de empresa e IVA de turistas | La cuota media del IRPF es `4.906 €` por declaración (AEAT 2023: `117.674 M€` / `23,99 M` declaraciones). El `54,5 %` de las declaraciones (hasta `21.000 €`) aporta el `6,8 %` de la cuota; el `5,6 %` de más de `60.000 €`, el `42,2 %` (`distribution.irpf` en `ui/site/public/visualizaciones/data/carga-fiscal.json`). |
| 2 | `.vizStat` y título de `#bolsillo`: «desde 2000, impuestos +29,8 %, renta de los hogares +20,3 % por habitante» | Renta disponible ajustada por habitante (contabilidad nacional, Eurostat `nasa_10_ki`) | **Sí: es la media de un reparto muy desigual por edad.** | Renta mediana equivalente real 2008→2025 (EU-SILC `ilc_di03`, € deflactados con IPCA `prc_hicp_aind` 2007→2024): **65+ `+28,7 %`**; 16–24 `+2,9 %`; 25–49 `−0,7 %`; 50–64 `−3,3 %`; total `+4,9 %`. Los mayores pasan del `86 %` de la mediana total (2008) al `105 %` (2025). Ojo: posible ruptura de serie en 2013 (el INE pasó a rentas de registros); hay que leer las banderas de Eurostat antes de publicar el cambio. |
| 3 | Relato «El contribuyente está asfixiado» y `#quien-carga`: cuña fiscal del **soltero sin hijos con salario medio** (`41,4 %`, 2025) | OCDE AW = `32.678 €` brutos (2025) | **Sí: el «salario medio» OCDE no es el típico, y el soltero no es el hogar típico.** | La mediana salarial es `24.497 €` (INE EAES 2024, tabla 28191) = `75 %` del AW; un asalariado de 25–29 años gana de media `22.723 €` (tabla 28189). Por tipo de hogar (OCDE `DF_TW_COMP`, 2025, cuña media): soltero 100 % `41,4`; pareja 1 sueldo + 2 hijos `36,8`; monoparental 67 % + 2 hijos `28,5`. El alivio por hijos en España es pequeño: soltero → pareja con 2 hijos y un sueldo, `−4,6` puntos, frente a `−14,4` en Alemania, `−11,8` Portugal, `−11,5` Italia, `−8,1` Francia. Tipo neto personal de una monoparental con 67 %: España `+6,7 %`, Francia `−6,9 %`, Portugal `−4,6 %`, Italia `−0,6 %` (reciben más de lo que pagan). |
| 4 | `#mediana-vivienda`: «el hogar mediano… los gastos de vivienda son el 16 % de la renta» | Eurostat `ilc_mded01`, total | **Sí: es la media entre quien no paga vivienda y quien paga casi la mitad.** La página ya lo matiza con los inquilinos (`26,8 %` sobrecargados) | Por tipo de hogar (`ilc_mded01`, 2025): dos adultos con al menos uno de 65+ `12,4 %`; adulto solo <65 `28,9 %`; monoparental `28,8 %`; bajo el umbral de pobreza `33,0 %` (solo <65 bajo el umbral: `53,3 %`). Sobrecarga por tenencia (`ilc_lvho07c`): propietario sin hipoteca `1,9 %`, con hipoteca `3,4 %`, alquiler de mercado `26,8 %`. Tenencia por edad de la persona de referencia (INE ECV tabla 9994, 2025): 65+ `82,4 %` propiedad sin hipoteca y `5,5 %` alquiler de mercado; 16–29 `14,1 %` y `49,8 %`. |
| 5 | Mismas cifras de vivienda por edad (`ilc_lvho07a`) si se usaran | Sobrecarga 25–29: `8,9 %`, menor que la de 18–64 | **Sí, por selección:** quien no puede pagar no se emancipa | Jóvenes de 25–29 que viven con sus padres: `51,1 %` (2008) → `69,8 %` (2025) (`ilc_lvps08`); 25–34: `36,6 %` → `50,2 %`. La sobrecarga juvenil «baja» de `14,3 %` a `8,9 %` porque se mide solo a los que se van. |
| 6 | Relato «Al español medio le queda mucho menos que al europeo» (mediana EU-SILC `22.408` PPS) | Mediana sin alquiler imputado | **En parte**: la renta mediana no ve que el 73 % es propietario | Con alquiler imputado, el propietario sin hipoteca gana `+4.455 €` por unidad de consumo (`24.523` → `28.978`); el inquilino de mercado se queda en `18.013 €` (INE ECV tabla 59949, 2025): `−27 %` frente al propietario antes de pagar el alquiler. |
| 7 | `.vizStat` «Gasto en pensiones +4,0 pts desde 1995» y `#destino` (pensiones `12,6 %` del PIB frente a sanidad `6,5 %` y educación `4,1 %`) | Gasto por función en % del PIB | **No engaña como agregado, pero no dice a quién llega.** | Por beneficiario: `21.754 €` por pensionista (2024, `spending.pension_composition`). Saldo fiscal neto por edad (impuestos pagados − transferencias y servicios recibidos, NTA 2024, EsadeEcPol jun. 2026, según su resumen, sin verificar en la fuente): máximo ≈ `+11.000 €`/año hacia los 50; ≈ `−16.000 €` a los 70; `41 %` de la población contribuye en neto (`68 %` entre 25 y 64). |
| 8 | `#territorio`: tipo máximo del IRPF `45 %` (Madrid) a `54 %` (C. Valenciana) | Tipo marginal del último tramo | **Sí, si se lee como «en Valencia se paga más»:** el último tramo empieza entre `53.407 €` (CyL) y `334.344 €` (Navarra) | Afecta al `5,6 %` de declaraciones que pasa de `60.000 €`. Lo que pesa para el resto es renta y coste de vivienda: renta media por UC Madrid `27.136 €` frente a Extremadura `18.852 €` (`+44 %`, ECV tabla 9947, 2025); alquiler mediano `800 €` frente a `425 €`/mes (`+88 %`, MIVAU/SERPAVI 2024, ya en `vivienda.json`). El «IRPF medio `17,0–22,3 %` de la base» por comunidad es sobre todo composición de renta, no tipos. |
| 9 | `#quien-carga`: redistribución OCDE | Gini mercado `47,7` → disponible `31,2` (2023) | **Bien planteado, mal explotado**: ya trae 18–65 | Las transferencias reducen el Gini `12,6` puntos en el total y `6,5` en 18–65 (`distribution.redistribution`): **la mitad de la redistribución por transferencias es entre edades (pensiones)**, no entre ricos y pobres de la misma edad. No se dice en el texto. |
| 10 | Nada sobre impuestos indirectos por renta | — | **Hueco**: la página solo reparte IRPF y cuña | IVA pagado en % de la renta bruta, mediana por quintil (Eurostat experimental `icw_tax_03`, 2020): Q1 `10,6 %`, Q2 `8,0`, Q3 `7,0`, Q4 `5,9`, Q5 `4,4`; en 2010 `11,3` → `5,6`. Por tipo de hogar (`icw_tax_02`, 2020): monoparental `9,5 %`, pareja sin hijos `6,3 %`. Por edad (`icw_tax_01`, 2020): <30 `9,3 %`, 65–74 `6,4 %`. Ahorro mediano Q1 `−6,7 %` de la renta, Q5 `+53,9 %` (`icw_sr_03`, 2020): el IVA es regresivo sobre la renta corriente porque los de abajo gastan todo. Funcas lo encuentra ligeramente progresivo sobre el gasto (proxy de renta permanente): hay que decir las dos cosas. 2020 es año de pandemia y 2015 da valores ~2× los de 2010 y 2020: no usar 2015 sin explicarlo. |

**Hallazgo central.** La renta disponible equivalente apenas separa edades (mediana 2025: 65+ `21.409 €`, 18–64 `20.828 €`,
16–24 `18.705 €`, `ilc_di03`): el sistema iguala bastante las rentas por edad a través de las pensiones. La separación
reaparece en **dos sitios que la página no mira**: (a) la vivienda (quién es propietario sin hipoteca y quién alquila) y
(b) la trayectoria (los mayores han ganado `+29 %` real desde 2008; los de 25–64, nada). Y el sistema fiscal trata a
los hogares con hijos peor que los vecinos.

## 2. Dimensiones: cuáles separan realidades

Criterio: dispersión entre grupos frente a la media, en la variable que importa («cuánto queda»), y que exista dato oficial.

| Dimensión | Dispersión medida | Decisión |
|---|---|---|
| **Edad / etapa vital** (persona o persona de referencia del hogar) | Saldo fiscal neto ≈ `+11.000 €` (50 años) a ≈ `−16.000 €` (70) (NTA). Cambio real de la renta mediana 2008→2025: `+28,7 %` (65+) frente a `−0,7 %` (25–49). Propiedad sin hipoteca `82,4 %` (65+) frente a `14,1 %` (16–29). Emancipación 25–29: solo `30 %` | **Elegida (1.ª).** Es la que más separa quién paga y quién recibe y la trayectoria. Absorbe «fuente de renta» (salario frente a pensión). |
| **Tenencia de vivienda** | Renta por UC: propietario `24.734 €` frente a inquilino de mercado `18.013 €` (`−27 %`); con alquiler imputado `28.978` frente a `18.013` (`−38 %`). Sobrecarga `1,9 %` frente a `26,8 %` (×14). Inquilinos de mercado: `17,9 %` del primer decil, `4,7 %` del décimo (ECV 59953) | **Elegida (2.ª).** Es lo que convierte una renta disponible parecida en «lo que queda» muy distinto. Cruza con edad (tabla 9994) y con territorio (alquiler). |
| **Nivel de renta (quintil/decil)** | IRPF efectivo `3,2 %` (6–12 mil €) a `34,3 %` (>601 mil €) (AEAT 2023); IVA `10,6 %` (Q1) frente a `4,4 %` (Q5) de la renta bruta | **Elegida (3.ª).** Imprescindible para «quién paga» (directos progresivos, indirectos regresivos). Ya está a medias: falta el IVA y unir las dos capas. |
| **Hijos / tipo de hogar** | Renta por UC monoparental `15.708 €` frente a pareja sin hijos `26.028 €` (`−40 %`, ECV 9946); vivienda `28,8 %` frente a `12,4 %` (pareja con 65+); alivio fiscal por hijos `−4,6` pts frente a `−8` a `−14` en los vecinos | **Elegida como modificador (4.ª)**, en los casos tipo, no como eje de cada figura. Da el contraste con Europa que la página ya hace para el soltero. |
| Territorio (comunidad) | Renta por UC `+44 %` Madrid/Extremadura; salario mediano `28.038 €` frente a `20.632 €` (Canarias), `+36 %`; alquiler `+88 %`. Pero tras impuestos y alquiler, el asalariado mediano que alquila a precio mediano se queda con ≈ `12.400 €` (Madrid) frente a ≈ `11.950 €` (Extremadura): el `+34 %` de salario se queda en `+4 %` | **No como dimensión fiscal propia**: los impuestos apenas cambian por comunidad a rentas medianas (el tipo máximo solo toca al ~5 %). Se usa como **coste de vida a través del alquiler** en los casos, y foral frente a común como nota. Ciudad frente a rural (`ilc_di17`, grado de urbanización): mediana `21.940 €` frente a `18.549 €` (`+18 %`); sobrecarga `8,2 %` frente a `3,9 %` (`ilc_lvho07d`). |
| Fuente de renta (autónomo, capital) | No sondeado a fondo; la renta de autónomos en IRPF está infradeclarada y el RETA va por tramos de rendimientos | **Descartada como eje**; salario frente a pensión ya va dentro de la edad. El capital se ve en el IRPF por tramos (base del ahorro en los tramos altos). |
| Sexo, nacionalidad | Existen (ECV 9945, 9995) | Descartadas para esta vertical: no cambian el diagnóstico fiscal más que las cuatro elegidas. |

## 3. Casos tipo (lo que pagan, reciben y les queda)

Método (≈, reproducible): impuestos directos con los tipos de la OCDE Taxing Wages 2025 (`DSD_TAX_WAGES_COMP@DF_TW_COMP`,
`NPATR` = IRPF + cotización del trabajador − prestaciones en efectivo, en % del bruto; interpolado linealmente entre 67 %
y 100 % del AW para otros sueldos; cotización de empresa desde la cuña `AV_TW`). La OCDE usa una escala autonómica de
referencia, no la de cada comunidad. IVA: mediana de `icw_tax` 2020 para su edad o tipo de hogar (indicativo, no se resta
dos veces: ya sale del gasto). Vivienda: alquiler mediano MIVAU/SERPAVI 2024 por comunidad (contratos vivos declarados
en IRPF, por debajo del precio de los contratos nuevos) o peso de la vivienda por tipo de hogar (`ilc_mded01`, 2025).
«Por UC»: escala OCDE modificada (1 + 0,5 por adulto + 0,3 por menor).

| Caso | Bruto | Impuestos directos (trabajador) | + cotización empresa | IVA ≈ | Transferencias | Neto | Vivienda | **Queda tras impuestos y vivienda (por UC)** | vs mediana |
|---|---|---|---|---|---|---|---|---|---|
| **Mediana nacional** (ECV 2025) | — | — | — | — | — | `20.367 €`/UC | `16 %` | ≈ `17.100 €` | 100 % |
| **A. 28 años, asalariado, soltero, inquilino en Madrid** | `22.723 €` (EAES 25–29) | ≈ `4.370 €` (`19,2 %`) | ≈ `6.660 €` | ≈ `2.100 €` (`9,3 %`) | ninguna en dinero | ≈ `18.360 €` | `9.600 €` (`800 €`/mes = `52 %` del neto) | ≈ **`8.760 €`** | **51 %** |
| **B. Pareja de 40 años, dos sueldos (100 % + 67 % AW), 2 hijos, hipoteca, C. Valenciana** | `54.573 €` | `10.871 €` (`19,9 %`) | ≈ `16.680 €` | ≈ `3.930 €` (`7,2 %`) | 2 plazas escolares públicas (en especie; cifra por alumno: vertical educación) | `43.702 €` | ≈ `6.560 €` (`15,0 %`) | ≈ **`17.690 €`** | 103 % |
| **C. Monoparental de 35 años, 67 % AW, 2 hijos, inquilina** | `21.895 €` | `1.466 €` (`6,7 %`; en Francia cobraría `6,9 %` neto) | — | ≈ `2.080 €` (`9,5 %`) | deducciones y prestaciones ya netas en el `6,7 %` | `20.429 €` (`12.768 €`/UC, ≈ umbral de pobreza `12.220 €`) | ≈ `5.880 €` (`28,8 %`, media de tenencias; más si alquila a mercado) | ≈ **`9.090 €`** | **53 %** |
| **D. Pensionista de 70 años, propietario sin hipoteca, Asturias** | `21.754 €` (pensión media por pensionista, 2024) | ≈ `2.680 €` (IRPF sin cotización) | — | ≈ `1.390 €` (`6,4 %`) | pensión + sanidad en especie (saldo ≈ `−16.000 €` a los 70, NTA) | ≈ `19.080 €` | ≈ `3.850 €` (`20,2 %`, solo 65+; `12,4 %` si es pareja) | ≈ **`15.220 €`** | 89 % |
| **E. Profesional de 50 años, soltero, 167 % AW, Madrid, hipoteca** | `54.573 €` | `16.221 €` (`29,7 %`) | ≈ `16.680 €` | ≈ `2.400 €` (`4,4 %`, Q5) | ninguna | `38.352 €` | ≈ `6.100 €` (`16 %`, sin dato propio por tenencia) | ≈ **`32.200 €`** | 188 % |

Qué enseñan juntos:
- **A frente a D**: con rentas brutas casi iguales (`22.723` y `21.754 €`), al joven inquilino le queda ≈ `8.760 €` y al
  pensionista propietario ≈ `15.220 €` (×1,7). El IRPF apenas los distingue; los separa la vivienda y la cotización.
- **C frente a B**: la monoparental está en la mitad de la mediana tras la vivienda; España la trata fiscalmente mucho
  peor que Francia, Portugal o Italia (tipo neto `+6,7 %` frente a `−0,6 %` a `−6,9 %`).
- **E** es quien sostiene el saldo: ~`33.000 €` de impuestos y cotizaciones directos (trabajador + empresa) al año, en la
  edad de máxima contribución neta.
- **Territorio**, misma persona mediana que alquila a precio mediano: Madrid ≈ `12.400 €`, Andalucía ≈ `10.920 €`,
  Extremadura ≈ `11.950 €` tras impuestos y alquiler (salarios medianos EAES 28191 y alquiler SERPAVI). Lo que en
  provincia es la vida de la mediana, en Madrid exige el salario mediano de Madrid; con el de 25–29 se queda en la mitad.

Avisos que deben ir en la página: son casos ilustrativos, no hogares observados; mezclan años (salarios 2024, tipos
2025, IVA 2020); el alquiler SERPAVI es de contratos vivos; el IVA ya está dentro del gasto (no se resta del neto).

## 4. Disponibilidad de datos

| Dimensión / cruce | Tabla oficial | Años | Granularidad | ¿En staging? | Hueco honesto |
|---|---|---|---|---|---|
| Renta por edad | Eurostat `ilc_di03`; INE ECV 9942 / 76844 | 2004/2008–2025 | 16–24, 25–49, 50–64, 65+, 75+ (Eurostat); 16–29, 30–44, 45–64, 65+ (INE) | Solo total (`ilc_di03` TOTAL) | Ruptura 2013 a verificar |
| Tenencia × edad | INE ECV 9994 | 2004–2025 | 4 bandas de edad de la persona de referencia | No | — |
| Tenencia × renta | INE ECV 59953, 59949 | 2008–2025 | Decil; renta media con y sin alquiler imputado | No | — |
| Tenencia × tipo de hogar | Eurostat `ilc_lvho02` | 2005–2025 | 17 tipos de hogar | No | — |
| Peso de la vivienda × tipo de hogar × pobreza | Eurostat `ilc_mded01` | 2005–2025 | 17 tipos | Solo TOTAL y B_60 | **No hay peso de la vivienda por tenencia** (solo sobrecarga `ilc_lvho07c`, ya en staging) |
| Sobrecarga × edad / urbanización | `ilc_lvho07a`, `ilc_lvho07d` | 2005–2025 | Edad fina; DEG1–3 | No | — |
| Emancipación | `ilc_lvps08` | 2004–2025 | 25–29, 25–34… | No | — |
| Renta × comunidad | INE ECV 9947, 49145 | 2008–2025 | 17 CCAA + Ceuta y Melilla | No | Sin área metropolitana; muestra pequeña en CCAA chicas |
| Renta × urbanización | `ilc_di17`; INE 59947 | 2008–2025 | DEG1–3 × edad | No | Proxy de «gran ciudad» |
| Salario × edad, × comunidad | INE EAES 28189, 28191 | 2008–2024 | 5 años de edad; CCAA (media y mediana) | No | No hay salario mediano por edad × comunidad en EAES (sí en AEAT «Mercado de trabajo y pensiones en las fuentes tributarias», no sondeado) |
| Impuesto directo × tipo de hogar | OCDE Taxing Wages (`DF_TW_COMP`, DBnomics) | 2000–2025 | 8 hogares tipo × 3 niveles de salario | Solo S_C0 (soltero) | Escala autonómica única; no hay foral |
| IRPF × tramo × comunidad | AEAT declarantes (`etl/data/manual/public_finance/irpf_by_bracket_es.json`) | 2023 | Tramos de rendimiento; 15 CCAA comunes | Sí | **Sin edad** (AEAT no publica tramo × edad en esta estadística; búsqueda sin resultado). Excluye forales. Declaraciones conjuntas mezclan personas y hogares |
| IVA × quintil, edad, tipo de hogar | Eurostat experimental `icw_tax_01/02/03`, `icw_sr_03` | 2010, 2015, 2020 | Quintil, 12 bandas de edad, tipos de hogar | No | Experimental, 3 años, 2015 atípico; sin impuestos especiales; no hay estadística oficial española de incidencia del IVA (AIReF y Funcas: estudios) |
| Saldo fiscal neto por edad (impuestos − transferencias − especie) | NTA: FEDEA EEE 2026/09 (2022), EsadeEcPol (2024) | 2022, 2024 | Edad simple | No | **No es estadística oficial**; cifras de estudios. Sanidad y educación en especie por edad: no hay tabla oficial abierta (AIReF usa perfiles propios) |
| Pensión por pensionista | Eurostat `spr_pns_ben` + gasto | 2024 | Nacional | Sí | Media de todas las pensiones (incluye viudedad); falta mediana y reparto |
| Alquiler por comunidad | MIVAU/SERPAVI (vía `vivienda.json`) | 2015–2024 | CCAA (municipio disponible en la fuente) | En la vertical vivienda | Contratos vivos, no nuevos; País Vasco y Navarra sin dato |
| Coste de vida regional | — | — | — | — | **No hay paridades de poder adquisitivo regionales oficiales en España**; solo el alquiler hace de proxy |
| Foral (PV, Navarra) | Haciendas forales | — | — | Tipos máximos sí | IRPF por tramos y cuña forales fuera de AEAT y OCDE |

## 5. Recomendación priorizada

**1. Reescribir el lado «renta» de `#bolsillo` (y su `.vizStat`) por edad y tenencia.** Es la figura consolidada y su
titular («la recaudación crece más que la renta de los hogares») es el que más depende de una media. Cambio:
- Mantener la mitad «recaudación» (es un agregado y está bien).
- Sustituir la barra única «renta de los hogares por habitante» por un *dumbbell* del cambio real de la renta mediana
  2008→2025 por edad (16–24, 25–49, 50–64, 65+; `ilc_di03` + IPCA), con la media como referencia.
- Nuevo relato en `.vizRelatos`: «La renta de los hogares ha crecido: la de los mayores de 65, un 29 % real desde 2008;
  la de 25 a 64 años, nada», y «la vivienda se come lo que queda» con la tenencia por edad (`82 %` sin hipoteca frente a
  `14 %` + `50 %` en alquiler de mercado).
- Titular candidato (verificar cifras con el export): «Desde 2008 la renta real de los mayores de 65 ha subido un 29 % y
  la de los adultos de 25 a 64, nada; la recaudación por habitante, un X %».
- Datos: 2 indicadores Eurostat nuevos (`ilc_di03` por edad, `ilc_lvps08`) e INE 9994; mismo contrato de indicadores.
- Comprobar la ruptura de 2013 antes; si la hay, empezar en 2013 y mostrar 2008–2012 aparte.

**2. Nueva figura «Cinco hogares» (cascada por caso tipo), justo después de `#bolsillo`.** Barras horizontales apiladas
por caso: bruto → impuestos directos → vivienda → lo que queda por UC, con la mediana nacional como línea; color por
concepto y marcador para el IVA estimado. Sustituye como protagonista a la cuña del soltero con salario medio (que pasa a
nota). Datos: ampliar la ingesta OCDE a `HOUSEHOLD_TYPE` S_C2 y C_C2 (ya en la misma llamada DBnomics), `icw_tax_01/02/03`,
`ilc_mded01` por tipo de hogar, EAES 28189/28191, alquiler SERPAVI de la vertical vivienda. Su copia debe zanjar
«los pensionistas viven mejor que los jóvenes» (sí tras vivienda; no en renta disponible) y «España cobra pocos impuestos»
(al soltero sí; a la familia con hijos, en términos relativos no).

`#destino` no cambia de forma ahora: añadir solo una línea en su relato con el reparto por edad (la mitad de la
redistribución por transferencias es entre edades: `12,6` frente a `6,5` puntos de Gini) y el euro por beneficiario
(`21.754 €` por pensionista). Una figura de gasto por edad del receptor necesita perfiles NTA que no son oficiales:
pendiente hasta tener fuente reproducible.

## 6. Dimensiones compartidas (para la coordinadora)

**Edad.** Propongo **16–29 / 30–44 / 45–64 / 65+** en lugar de 16–34 / 35–64 / 65+:
- Es la partición del INE en la ECV (tablas 9942, 9994: renta y tenencia por edad), que es la fuente que más cruza.
- El corte que separa realidades está en 30: alquiler de mercado `49,8 %` (16–29) frente a `32,1 %` (30–44); juntar
  hasta 34 lo diluye. Y 45–64 es la etapa de contribución neta máxima.
- Si hace falta compatibilidad con Eurostat (`ilc_di03`, `ilc_lvho07a`): 16–24 / 25–49 / 50–64 / 65+, documentando la
  diferencia. Si la coordinadora quiere tres bandas: **<30 / 30–64 / 65+**. El corte de 65 es innegociable (pensión,
  propiedad sin hipoteca).
- Para personas en hogares: edad de la persona de referencia cuando la variable es del hogar (tenencia, gasto), edad
  propia cuando es de la persona (renta equivalente, emancipación).

**Territorio.**
- Comunidad autónoma (17 + Ceuta y Melilla), con **régimen foral frente a común** siempre marcado (IRPF propio, sin
  datos AEAT ni OCDE).
- «Madrid y Barcelona metropolitanas frente al resto»: la ECV no lo publica. Proxy oficial disponible: **grado de
  urbanización** de Eurostat/INE (ciudades DEG1, intermedias DEG2, rural DEG3; `ilc_di17`, `ilc_lvho07d`, INE 59947,
  60181). Para alquiler, SERPAVI baja a municipio y permitiría separar Madrid y Barcelona capitales.
- El coste de vida entre comunidades se aproxima solo con el alquiler (no hay PPA regionales oficiales); decirlo.

**Otras comunes que propongo armonizar:** tenencia en 4 categorías (propiedad sin hipoteca, con hipoteca, alquiler de
mercado, alquiler reducido o cesión) y renta por quintil de renta equivalente.

## Fuentes (consultadas el `2026-10-19`)

- Eurostat (API JSON): [`ilc_di03`](https://ec.europa.eu/eurostat/databrowser/view/ilc_di03/default/table),
  [`ilc_di17`](https://ec.europa.eu/eurostat/databrowser/view/ilc_di17/default/table),
  [`ilc_mded01`](https://ec.europa.eu/eurostat/databrowser/view/ilc_mded01/default/table),
  [`ilc_lvho02`](https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho02/default/table),
  [`ilc_lvho07a`](https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07a/default/table),
  [`ilc_lvho07c`](https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07c/default/table),
  [`ilc_lvho07d`](https://ec.europa.eu/eurostat/databrowser/view/ilc_lvho07d/default/table),
  [`ilc_lvps08`](https://ec.europa.eu/eurostat/databrowser/view/ilc_lvps08/default/table),
  [`icw_tax_01`](https://ec.europa.eu/eurostat/databrowser/view/icw_tax_01/default/table),
  [`icw_tax_02`](https://ec.europa.eu/eurostat/databrowser/view/icw_tax_02/default/table),
  [`icw_tax_03`](https://ec.europa.eu/eurostat/databrowser/view/icw_tax_03/default/table),
  [`icw_sr_03`](https://ec.europa.eu/eurostat/databrowser/view/icw_sr_03/default/table),
  [`prc_hicp_aind`](https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_aind/default/table).
- INE ECV 2025 (rentas 2024): tablas [9942](https://www.ine.es/jaxiT3/Tabla.htm?t=9942),
  [9946](https://www.ine.es/jaxiT3/Tabla.htm?t=9946), [9947](https://www.ine.es/jaxiT3/Tabla.htm?t=9947),
  [9994](https://www.ine.es/jaxiT3/Tabla.htm?t=9994), [59949](https://www.ine.es/jaxiT3/Tabla.htm?t=59949),
  [59953](https://www.ine.es/jaxiT3/Tabla.htm?t=59953). INE EAES 2024: [28189](https://www.ine.es/jaxiT3/Tabla.htm?t=28189),
  [28191](https://www.ine.es/jaxiT3/Tabla.htm?t=28191).
- OCDE Taxing Wages 2025 vía [DBnomics `DSD_TAX_WAGES_COMP@DF_TW_COMP`](https://db.nomics.world/OECD/DSD_TAX_WAGES_COMP@DF_TW_COMP)
  (oecd.org bloquea el acceso por script, ver `scripts/ingest_public_finance_es.py`).
- AEAT, declarantes del IRPF 2023 y MIVAU/SERPAVI 2024: ya en `ui/site/public/visualizaciones/data/carga-fiscal.json`
  y `ui/site/public/visualizaciones/data/vivienda.json`.
- Saldo fiscal por edad (estudios, no estadística oficial): [EsadeEcPol, transferencias intergeneracionales](https://www.esade.edu/ecpol/en/publications/las-transferencias-intergeneracionales-y-el-reto-demografico/)
  (la página devuelve `403` a scripts; cifras tomadas del resumen del buscador, verificar en el
  [brief](https://itemsweb.esade.edu/wi/research/ecpol/brief_cuentasfiscales_final.pdf) antes de publicar) y
  [FEDEA EEE 2026/09](https://documentos.fedea.net/pubs/eee/2026/eee2026-09.pdf) (NTA 2022).
- Progresividad del IVA sobre el gasto: [Funcas, PEE 154](https://www.funcas.es/wp-content/uploads/Migracion/Articulos/FUNCAS_PEE/154art11.pdf).
