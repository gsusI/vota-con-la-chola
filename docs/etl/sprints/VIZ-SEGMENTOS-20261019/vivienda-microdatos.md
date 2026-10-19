# Vivienda: edad × tenencia × comunidad con los microdatos de la ECV

Cierra el primer hueco de la [síntesis](README.md) §7 («no hay cruce oficial edad × tenencia × comunidad»).

- **Dónde estamos.** `/visualizaciones/vivienda/#quien-paga` tiene, además de las tablas oficiales, una estimación propia
  por celda (edad de la persona de referencia × régimen de tenencia × territorio) hecha con los microdatos transversales
  de la ECV del INE, con tamaño muestral e intervalo del 95 % por celda, y los hogares tipo 1, 2 y 4 llevan al lado la
  celda de la encuesta que se les parece.
- **A dónde vamos.** Que cada hogar tipo de las cinco verticales use la misma celda observada cuando la muestra lo
  permita, y el corte marginal solo cuando no.
- **Qué sigue.** Persona 1 con su definición exacta (25–34, vive sola, alquiler de mercado, Madrid) no llega al mínimo en
  un año: se podría juntar 2024–2025 solo con los hogares nuevos de cada año (la muestra es un panel rotatorio y el
  fichero transversal no dice qué hogares repiten), o pedir al INE el fichero con estratos y secciones.

## Reglas fijadas antes de calcular

Están en el código (`scripts/housing_ecv_microdata.py`, docstring y constantes) y no se tocaron al ver los resultados.

| Decisión | Regla |
|---|---|
| Ficheros | Transversales base 2013 de `https://www.ine.es/ftp/microdatos/ecv/ecv_b2013/datos_<año>.zip`, años 2025 (último), 2024, 2023 y 2019 (antes de la pandemia). Caché bruta `etl/data/raw/housing/apis/ine_ecv_microdatos_<año>.zip` + `.meta.json`; sha256 en `indicator_releases`. |
| Unidad | Hogares, con su factor transversal `DB090`. |
| Edad | La de la persona de referencia (`HB080`, primera responsable de la vivienda) a 31 de diciembre del año anterior (`RB081`): es la que reproduce la tabla del INE t=9994. Bandas 16–29 / 30–44 / 45–64 / 65+. |
| Tenencia | `HH021`: 1 propiedad sin hipoteca, 2 con hipoteca, 3 alquiler de mercado, 4 alquiler inferior al de mercado y 5 cesión juntos (como `ilc_lvho07c`). |
| Territorio | Comunidad (`DB040`), y Madrid y Cataluña frente al resto de España (`ES_RESTO`). |
| Peso de la vivienda | Como Eurostat: (12 × `HH070` − `HY070G`) / (`HY020` − `HY070G`); tope del 100 %; renta no positiva cuenta como 100 %. La renta es la del año anterior a la encuesta. Media y mediana. |
| Sobrecarga | Peso > 40 %. |
| Renta y lo que queda | `HY020` / `HX240` (escala OCDE modificada) y (`HY020` − 12 × `HH070`) / `HX240`, al año. Media y mediana. |
| Umbral | Menos de **50** hogares en la muestra: celda vacía (se publica solo su n). De 50 a 99: se publica marcada como de precisión baja. Nunca se imputa. |
| Error estándar | Linealización de Taylor con el hogar como unidad (con reposición, un estrato), multiplicada por la raíz de un efecto de diseño. Medianas: intervalo de Woodruff. |
| Efecto de diseño | El fichero público no trae estratos ni secciones censales (diseño del INE: secciones estratificadas por comunidad y tamaño del municipio, unas 12 viviendas por sección). Se calibra con los intervalos del 95 % que el INE publicó para la ECV 2023 en «Cambio de base poblacional en las estimaciones de la ECV» (febrero de 2025, `ine_ecv_cambio_base_ic_2023.pdf` en la caché): para cada indicador y grupo (AROPE, riesgo de pobreza, carencia material y social severa y baja intensidad en el empleo, por sexo y edad; 23 intervalos) el cociente entre la varianza del INE y la nuestra. Se usa **el mayor** de los 23, para que los intervalos pequen de anchos. |
| Validación | Cada año, los totales nacionales tienen que reproducir dentro del redondeo: INE t=9994 (hogares por edad y tenencia), t=59956 (renta neta media por hogar y tenencia), Eurostat `ilc_lvho07c` (sobrecarga por tenencia, personas) y `ilc_lvho08a` (mediana del peso, personas). Si no, el ingest se para. |

## Validación (2026-10-19)

- Los cuatro años pasan las 30 comprobaciones contra INE t=9994 y t=59956 y Eurostat `ilc_lvho07c` y `ilc_lvho08a`
  dentro del redondeo (2025: hogares de 16–29 en alquiler de mercado 49,8 %, renta media de los inquilinos de mercado
  31.748 €, sobrecarga de las personas en alquiler de mercado 26,8 %, mediana del peso 10,4 %: idénticos).
- Edad: con `RB082` (edad en la entrevista) las cuotas por edad se desvían hasta 1 punto de t=9994; con `RB081` coinciden.
  2019 no trae `RB081`: se usa su definición, año de encuesta − 1 − año de nacimiento (`RB080`).
- Única diferencia: la media del peso (`ilc_mded01`) sale 0,2–0,4 puntos por encima de Eurostat (2025: 16,21 frente a
  16,0; 2024: 16,96 frente a 16,7; 2023: 17,56 frente a 17,2; 2019: 17,34 frente a 17,1). Depende solo de las personas en
  hogares con renta nula o negativa (0,43 % en 2025): contadas al 100 % sale por encima, fuera sale por debajo (15,85;
  16,55; 17,07; 17,02), y Eurostat queda siempre en medio. La mediana y la sobrecarga, que son las cifras que usa la
  página, coinciden; la media se publica con esa nota.
- Efecto de diseño: 0,94–1,18 en los 23 intervalos del INE (mediana 1,07); se usa 1,18. Las estimaciones del fichero
  2023 coinciden con la columna «censo 2011» del documento, la que lleva intervalos. Está calibrado con indicadores de
  pobreza: si la tenencia se concentra más por secciones que la pobreza, los intervalos de tenencia se quedan cortos
  (se dice en la página).
- `--offline` reproduce byte a byte `vivienda.json` (sin `generated_at`) y `vivienda.csv`.

## Hallazgos (ECV 2025, hogares; intervalo del 95 %)

- Dentro del alquiler de mercado separa la edad: pasa del 40 % el 51 % (41–61) de los hogares de 16–29, el 33 % (30–37)
  de los de 30–44, el 32 % (29–36) de los de 45–64 y el 43 % (37–50) de los de 65 o más.
- El territorio separa poco dentro de cada tenencia: inquilinos de mercado de Madrid 37 % (31–43), Cataluña 32 % (27–36)
  y resto de España 36 % (33–39); sus rentas medianas por unidad de consumo son 19.614, 20.104 y 15.358 €. Entre
  comunidades, el peso mediano de los inquilinos de mercado va del 25,5 % (Canarias) al 37,0 % (Cantabria, 85 hogares),
  con intervalos que se solapan todos (el mayor límite inferior, 30,7 %, queda por debajo del menor límite superior, 31,5 %).
- Hogares de 65 o más en casa pagada: peso mediano 9,0 %, sobrecarga 3,2 %.
- Sobrecarga de los hogares en alquiler de mercado: 43 % en 2019, 37 % en 2023, 35 % en 2024 y 2025 (en personas,
  Eurostat: 37,4 → 26,8 %). Solo se dice que bajó; la página no le atribuye causa.
- Casos tipo: persona 1 con su definición exacta tiene 31 hogares (vacía) y usa «25–34 años, alquiler de mercado, Madrid»
  (85 hogares, precisión baja: 32 % de peso mediano frente al 44 % del cálculo con sueldo modelo y alquiler de la ciudad);
  persona 2a, 73 hogares (29 % frente al 21 % del cálculo con dos sueldos modelo); 2b, 123 hogares (13 %: la encuesta no
  cuenta la amortización y es de quien ya compró); persona 4, 652 hogares (13,8 %, cerca del 14,2 % del cálculo).

## Qué sigue en la página

- Siguen siendo cortes marginales: la ciudad de Madrid frente al resto de su provincia (la ECV no baja de comunidad; solo
  SERPAVI), el alquiler de los contratos nuevos y el sueldo de 25–34 por comunidad.
