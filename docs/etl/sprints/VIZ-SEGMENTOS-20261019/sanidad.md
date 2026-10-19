# Segmentos en sanidad: qué medias engañan y qué casos tipo mostrar

Vertical: `/visualizaciones/sanidad/` (`ui/site/app/visualizaciones/sanidad/page.js`, datos `ui/site/public/visualizaciones/data/sanidad.json`, base `etl/data/staging/health-es.db`). Auditoría del 2026-10-19. No cambia código ni datos: es la base para la implementación.

- **Dónde estamos.** La página compara bien España con la UE y las comunidades entre sí (gasto, esperas, esperanza de vida, fila de sanidad en `docs/etl/e2e-scrape-load-tracker.md`). Ya parte tres cifras por renta o estudios (dentista, renuncia médica, esperanza de vida a los 30) y ajusta el gasto por edad. Pero las cifras destacadas y la figura «el dato mata el relato» siguen hablando de «España» como si fuera una sola persona.
- **Hacia dónde vamos.** Tres dimensiones (renta, edad, tamaño del municipio dentro de la comunidad) y cuatro casos tipo con su cifra al lado de la media.
- **Qué sigue.** Cambio prioritario (§5): un panel de brechas en la figura consolidada y la reescritura del resumen y de las cifras destacadas.

Convención: «Q1» y «Q5» son el 20 % de la población con menos y con más ingresos (renta equivalente, EU-SILC). Los datos de Eurostat se consultaron por la API JSON el 2026-10-19. Los cruces del Barómetro Sanitario salen de la caché ya descargada `etl/data/raw/health/barometro/BS-Total-Oleadas-Estudio_8825.xlsx` (hojas de cruce del CIS, estudio 8825, 2025; [URL oficial](https://www.sanidad.gob.es/estadEstudios/estadisticas/BarometroSanitario/Barom_Sanit_2025/Totales/BS-Total-Oleadas-Estudio_8825.xlsx)).

---

## 1. Inventario: cifras nacionales que se leen como representativas

| Cifra en la página (dónde) | ¿Engaña la media? | A quién deja fuera / cuánto se separan los grupos |
|---|---|---|
| Esperanza de vida `84,0` años (cifra destacada, titular de §1) | **En parte.** Es buena para todos, pero la media tapa el cruce sexo × estudios. | A los 30 años: hombre con primaria `50,2` años más, mujer con estudios superiores `58,2`, media `54,3` (**8,0 años** de distancia; [INE 37663](https://www.ine.es/jaxiT3/Tabla.htm?t=37663), 2023). Por estudios solos, `2,8`; por sexo solo, `5,1`. Por comunidad, al nacer: Madrid `85,6`, Andalucía `82,8`, Ceuta `81,6` ([INE 1448](https://www.ine.es/jaxiT3/Tabla.htm?t=1448), 2024; ya está en `sanidad.json` → `regions.rows`). |
| Años de vida saludable `68,6` frente a `65,2` UE (resumen, titular de §1) | **Sí, y además hay una ruptura de serie.** | El valor de 2024 lleva la marca `b` (ruptura) de Eurostat: España pasa de `62,1` (2023, **por debajo** de la UE, `63,1`) a `68,6` en un año ([hlth_hlye](https://ec.europa.eu/eurostat/databrowser/view/hlth_hlye/default/table)). El gráfico corta la línea en la ruptura (`page.js:43`), pero el titular y el resumen comparan `68,6` con `65,2` sin avisar. Por renta: «salud buena o muy buena» `63,6 %` en Q1 frente a `77,8 %` en Q5; en 45–64 años, `57,2 %` frente a `77,8 %` ([hlth_silc_10](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_10/default/table), 2025). |
| Gasto público por habitante `73 %` de la UE (`74 %` ajustado por edad) (cifra destacada) | **Sí, en el uso.** El dinero va sobre todo a los mayores. | Perfil español de coste público por persona: 25–29 años `572 €`, 80+ `2.610 €`, media `982 €` (euros de 1998, año 2008; `etl/data/manual/health/perfil_gasto_edad.json`, Funcas DT 673, tabla 15): un mayor de 80 cuesta **4,6 veces** lo que alguien de 25–29. El ajuste por edad ya corrige la comparación entre países; lo que falta es decir que «el ciudadano medio» no existe como usuario. |
| Gasto de bolsillo `21,5 %` del gasto sanitario y `3,66 %` del consumo de los hogares | **Sí, va al revés de lo que se espera.** | EPF 2025: sanidad `2,72 %` del gasto del Q1 frente a `4,42 %` del Q5 (`164` frente a `1.232 €` por persona; [INE EPF 75413](https://www.ine.es/jaxiT3/Tabla.htm?t=75413)). Los pobres no gastan menos porque estén mejor cubiertos, sino porque **renuncian**: dentista por coste `8,6 %` del Q1 frente a `0,9 %` del Q5. La media del bolsillo junta al que paga un seguro con al que se queda sin ir. |
| Seguro voluntario `15,3 %` (2020) | **Sí.** Sin desglose por renta en la página. | Barómetro 2025, especialista **solo** en la privada: clase alta y media-alta `32,8 %`, clase baja `7,9 %`, media `14,9 %`; municipio de ≤2.000 habitantes `6,5 %` frente a `20,5 %` en ciudades de más de un millón. Por edad, 18–34 años `≈19 %` frente a `8,1 %` con 75 o más. |
| Renuncia médica por coste, distancia o espera `1,6 %` («apenas depende de la renta») | **No: es cierta y es una fortaleza.** | Q1 `1,6 %` frente a Q5 `1,3 %`; por edad, de `0,7 %` (16–24) a `2,0 %` (65+); por urbanización, ciudad `1,6 %` y rural `1,4 %` ([hlth_silc_08](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_08/default/table), [hlth_silc_21](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_21/default/table), 2025). Hay que conservarla como contraste: lo que cubre el sistema público no separa grupos. |
| Dentista por coste `8,6 %` frente a `0,9 %` (panel 3 de la figura consolidada) | **La media nacional (`4,0 %`) esconde el pico.** | Q1 de 45–64 años `11,1 %`, Q1 de 35–44 años `10,4 %`, Q5 de 16–24 años `0,1 %` ([hlth_silc_09](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_09/default/table), 2025). UE: Q1 `5,5 %`, Q5 `0,8 %`. |
| Médico de familia: `21,8 %` atendido el mismo día o al siguiente; `9,2` días de media | **Sí, mucho. Es la media que más engaña.** | Municipios de ≤2.000 habitantes: `57,3 %` atendido el mismo día o al siguiente, `6,8` días de media. Ciudades de más de un millón: `12,4 %` y `9,7` días. Por comunidad: Navarra `47,6 %`, La Rioja `41,8 %`, Madrid `16,3 %`, Andalucía `14,5 %`, Canarias `11,6 %` (muestras pequeñas, ver §4). Por edad apenas varía (`17,5–25,9 %`). |
| Espera quirúrgica: `93` días en los procesos seleccionados, `122` en toda la lista | **Ya está partida por comunidad** (`47` días en Madrid, `129` en Cataluña, SISLE dic 2025). | Sin desglose por edad ni renta (ver §4). El usuario real es mayor: lista quirúrgica `85,5` por 1.000 personas de 65+ (`sanidad.json` → `waits_per_older`). |
| Salud mental: no aparece en la página | **Hueco.** | Barómetro 2025: necesitó atención de salud mental el `29,5 %` de 18–24, el `26,6 %` de 25–34 y el `9,6 %` de 65–74. De quienes la recibieron, en la privada (con seguro o pagando): `64,2 %` con 18–24, `45,8 %` con 25–34, `19,9 %` con 65–74. La renuncia por coste es baja (`1,2 %`, EHIS 2019, [hlth_ehis_un2i](https://ec.europa.eu/eurostat/databrowser/view/hlth_ehis_un2i/default/table)): los jóvenes no renuncian, **pagan**. |

---

## 2. Dimensiones: las tres que separan realidades (y las que se descartan)

**Criterio:** una dimensión entra si la distancia entre sus grupos extremos es grande respecto a la media nacional en algo que la página afirma.

### Elegidas

1. **Renta (quintil de ingresos).** Separa todo lo que el sistema público **no** cubre o cubre tarde.
   - Dentista: `9,6×` entre Q1 y Q5 (`8,6 %` frente a `0,9 %`; UE `6,9×`).
   - EHIS 2019, renuncia por coste a cualquier servicio: Q1 `19,3 %`, Q5 `3,2 %`; en 35–64 años, Q1 `≈23 %`.
   - Salud percibida buena: `−14` puntos en Q1.
   - Especialista solo en la privada: `4×` entre clase alta y clase baja (Barómetro).

   No separa la atención médica cubierta (`1,6 %` frente a `1,3 %`), y ese contraste es justamente el mensaje.
2. **Edad (16–34 / 35–64 / 65+, con 75+ como subtramo).** No separa el acceso al médico de familia, pero sí:
   - la **necesidad y el coste**: limitación de actividad `40,0 %` con 65+ y `50,5 %` con 75+, frente a `7,9 %` con 25–34 ([hlth_silc_12](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_12/default/table), 2025); coste público `4,6×`;
   - el **canal que llena los huecos**: salud mental en la privada, `64 %` de los jóvenes frente a `20 %` de los de 65–74.

   La enfermedad crónica va casi entera con la edad (enfermedad de larga duración `62,6 %` con 65+, `18,9 %` con 25–34; [hlth_silc_11](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_11/default/table)). Por eso entra como atributo del caso tipo, no como dimensión aparte.
3. **Territorio en dos niveles: comunidad autónoma y tamaño del municipio.**
   - La **comunidad** separa las listas quirúrgicas (`47–129` días, `2,7×`) y la esperanza de vida (`4,0` años entre Madrid y Ceuta). Ese bloque ya existe.
   - El **tamaño del municipio** separa la atención primaria más que la comunidad: `57 %` frente a `12 %` atendidos el mismo día o al siguiente (45 puntos, frente a 36 entre comunidades) y el uso de la privada (`6,5 %` frente a `20,5 %`).

   Ojo: en primaria, **lo rural no está peor, está mejor**. El problema está en las grandes ciudades. El relato de la «España vaciada sin médico» no lo sostiene este indicador. La distancia y el acceso al especialista y a urgencias no están medidos por municipio (ver §4).

### Complementaria (solo para resultados)

- **Sexo × estudios**, para la esperanza de vida: `8,0` años a los 30. Sustituye a la renta, porque no hay esperanza de vida oficial por renta (§4).

### Descartadas

- **Rural/urbano (grado de urbanización de Eurostat) para la renuncia a la atención**: plana (`1,6 / 1,8 / 1,4 %` médica; dentista `4,1 / 4,0 / 3,5 %`, [hlth_silc_22](https://ec.europa.eu/eurostat/databrowser/view/hlth_silc_22/default/table)). Para la cita en primaria se usa el tamaño de municipio del Barómetro, que sí separa.
- **Edad para el acceso al médico de familia**: plano (Barómetro, `17,5–25,9 %` atendidos el mismo día o al siguiente).
- **Enfermedad crónica o dependencia como eje propio**: redundante con la edad (arriba) y sin dato de esperas.
- **Sexo para el acceso**: no se ha encontrado una brecha grande en los indicadores consultados. Solo cuenta en la esperanza de vida.

---

## 3. Casos tipo (con la media nacional al lado)

**Aviso de método:** salvo el dentista (cruce real quintil × edad de EU-SILC), cada cifra viene del **corte marginal** que define al caso: el municipio, la comunidad, la edad o la clase por separado. El Barómetro no publica cruces dobles, así que no son celdas de «mujer de 78 años de un pueblo de Castilla-La Mancha». La página debe decirlo así («personas como ella: de su edad…, de su municipio…»).

| Caso | Indicador | Su grupo | Media España | Fuente |
|---|---|---|---|---|
| **Carmen, 78 años, crónica, pueblo de <2.000 habitantes de Castilla-La Mancha, pensión baja, sin seguro** | Cita con el médico de familia el mismo día o al siguiente | `57,3 %` (municipio ≤2.000) | `21,8 %` | Barómetro 2025, cruce por tamaño de municipio |
| | Espera, procesos quirúrgicos seleccionados | `108` días (Castilla-La Mancha) | `93` | SISLE dic 2025 |
| | Limitación de actividad por salud (75+) | `50,5 %` | `20,2 %` | hlth_silc_12, 2025 |
| | Dentista por coste (Q1, 65+) | `6,2 %` | `4,0 %` | hlth_silc_09, 2025 |
| | Esperanza de vida a los 65 (mujer, primaria) | `23,1` años | `21,7` | INE 37663, 2023 |
| | Coste sanitario público por persona (80+) | `2,7×` la media | `1×` | Funcas DT 673 (2008) |
| **Lucía, 27 años, renta baja, Madrid ciudad, necesita psicólogo y dentista** | Necesitó atención de salud mental (25–34) | `26,6 %` | `19,9 %` | Barómetro 2025, cruce por edad |
| | De ellos, atendidos en la privada (25–34; 18–24) | `45,8 %`; `64,2 %` | `41,9 %` | Barómetro 2025 |
| | Dentista por coste (Q1, 25–34) | `8,4 %` | `4,0 %` | hlth_silc_09, 2025 |
| | Renuncia por coste a cualquier servicio (Q1, 25–34) | `18,9 %` | `10,3 %` | hlth_ehis_un2i, 2019 |
| | Cita con el médico de familia el mismo día o al siguiente (ciudad de más de un millón; Madrid) | `12,4 %`; `16,3 %` | `21,8 %` | Barómetro 2025 |
| | Espera quirúrgica (Madrid; rara vez la necesita) | `47` días | `93` | SISLE dic 2025 |
| **Antonio, 52 años, trabajador manual con estudios primarios, Andalucía, dolor de espalda, sin seguro** | Dentista por coste (Q1, 45–64) | `11,1 %` | `4,0 %` | hlth_silc_09, 2025 |
| | Salud buena o muy buena (Q1, 45–64) | `57,2 %` | `70,1 %` | hlth_silc_10, 2025 |
| | Cita con el médico de familia el mismo día o al siguiente (Andalucía) | `14,5 %` | `21,8 %` | Barómetro 2025, cruce por comunidad |
| | Espera quirúrgica (Andalucía) | `91` días | `93` | SISLE dic 2025 |
| | Esperanza de vida a los 30 (hombre, primaria) | `50,2` años | `54,3` | INE 37663, 2023 |
| | Esperanza de vida al nacer (Andalucía) | `82,8` | `84,0` | INE 1448, 2024 |
| **Laura, 45 años, renta alta, Barcelona, con seguro privado** | Especialista solo en la privada (clase alta) | `32,8 %` | `14,9 %` | Barómetro 2025, cruce por clase |
| | Espera quirúrgica pública que puede esquivar (Cataluña, la más alta) | `129` días | `93` | SISLE dic 2025 |
| | Dentista por coste (Q5, 45–64) | `1,0 %` | `4,0 %` | hlth_silc_09, 2025 |
| | Salud buena o muy buena (Q5, 35–44) | `89,4 %` | `81,2 %` (35–44) | hlth_silc_10, 2025 |
| | Esperanza de vida a los 30 (mujer, superiores) | `58,2` años | `54,3` | INE 37663, 2023 |

**Lo que muestran juntos.** Carmen, la usuaria intensiva, está bien cubierta en primaria y espera a la operación como la media. Lucía y Antonio no renuncian al médico, pero sí al dentista y al psicólogo, o los pagan. Laura compra rapidez en la comunidad con la lista más larga. Entre Antonio y Laura hay **8 años** de vida a los 30 (por sexo y estudios). Ninguno de los cuatro es «el español medio».

---

## 4. Disponibilidad de datos por dimensión y por cruce

| Dimensión o cruce | Tabla oficial | Años | Granularidad | ¿En staging? | Hueco honesto |
|---|---|---|---|---|---|
| Renta × edad, renuncia médica y dental | Eurostat `hlth_silc_08`, `hlth_silc_09` | 2008–2025 anual | Q1–Q5 × 16–24, 25–34, 35–44, 45–64, 65+, 75+ | Parcial: solo 16+ × Q1, Q5 y total (`scripts/ingest_health_es.py`, `UNMET_QUINT`) | Hay que añadir los quintiles 2–4 y las bandas de edad (cambio pequeño en el filtro de la URL). |
| Renta × edad, salud percibida, enfermedad crónica, limitación | `hlth_silc_10`, `_11`, `_12` | 2008–2025 | igual | No | Rareza a revisar: enfermedad crónica 16–24 `29,2 %` > 25–34 `18,9 %` (2025). Comprobar antes de publicarlo. |
| Renta × edad × servicio (salud mental, fármacos, dentista) | `hlth_ehis_un2i`, `hlth_ehis_un1i` (EHIS) | **solo 2019** (la siguiente ola es 2025) | Q1–Q5 × 15–29…75+ | No | Una sola ola. La salud mental mide la renuncia, no el pago privado. |
| Urbanización × renuncia | `hlth_silc_21`, `hlth_silc_22` | 2008–2025 | ciudad / pueblos y periferias / rural | No | Plana: sirve para descartar la dimensión. |
| Edad, municipio, clase, estudios, sexo y comunidad × cita en primaria, privada, salud mental | Barómetro Sanitario (CIS 8825), hojas de cruce | 2022–2025 (la pregunta de la cita existe desde 2022) | 7 tramos de edad, 7 tamaños de municipio, clase subjetiva, 19 comunidades | **En caché bruta, no en staging**: `scripts/ingest_health_es.py:gp_access` solo lee la hoja «Resultados» (totales) | Sin cruces dobles. Muestra por comunidad pequeña (La Rioja n≈48, Cantabria ≈73, Navarra ≈70: margen ±11–14 puntos). La clase es **subjetiva**, no la renta. Solo personas de 18 o más años. |
| Esperanza de vida × estudios × sexo | INE 37663 | 2016–2023 | 4 niveles × sexo × 30 y 65 años | Sí (se publica solo el total por sexos) | **No hay esperanza de vida oficial por renta.** Solo estudios por barrio o municipio (por ejemplo, [Universidad de Sevilla, 2024: hasta 8,8 años entre barrios](https://www.redaccionmedica.com/ultimas-noticias/20240703/un-estudio-concluye-que-vecinos-de-barrios-pobres-viven-hasta-nueve-anos-menos-los-zonas-ricas/120008_0.html)), que no son serie del INE. |
| Esperanza de vida × comunidad | INE 1448 | serie larga | 19 comunidades y ciudades autónomas, ambos sexos | Sí | Falta el sexo por comunidad (está en INE, no se ingiere). |
| Esperas × comunidad | SISLE | dic 2017–2025 | 17 + INGESA | Sí | **Sin desglose por edad, renta ni municipio.** Ni siquiera se publica la lista por tramo de edad. |
| Gasto de bolsillo × quintil | INE EPF 75413 | 2016–2025 | Q1–Q5 | Sí | Sin cruce por edad del sustentador ni comunidad en la tabla ingerida (la EPF los tiene en otras tablas; no se ha comprobado). El gasto catastrófico de la OMS (`7,87 %`, 2019) no está por quintil en staging. |
| Seguro privado × renta | — | — | — | No | **No encontrado** como tabla oficial con renta. Proxy: el Barómetro por clase. La EESE 2020 (INE/Ministerio) podría tenerlo en sus tablas de asistencia sanitaria; no se ha verificado. |
| Coste público × edad | Funcas DT 673 (perfil de 2008) | 1998, 2003, 2008 | 17 tramos quinquenales | Sí (`etl/data/manual/health/perfil_gasto_edad.json`) | Perfil antiguo: vale para la forma de la curva, no para niveles actuales. |

---

## 5. Recomendación priorizada

### 1. Figura «el dato mata el relato»: sustituir el panel 3 por un panel de brechas «¿para quién se cumple?»

La tesis «buenos resultados gastando poco» **se sostiene para lo que el sistema público cubre**: la renuncia médica es plana por renta, edad y urbanización, entre las más bajas de la UE. **No se sostiene para lo que no cubre o cubre tarde**: dentista, salud mental y la cita de primaria en las grandes ciudades.

**Propuesta:** un diagrama de pesas ordenado en una sola escala (% de personas, de 0 a 70), con una fila por servicio y dos extremos por fila (Q1 frente a Q5, joven frente a mayor, pueblo frente a gran ciudad):

- médico por coste, distancia o espera, Q1 / Q5: `1,6 / 1,3`;
- dentista por coste, Q1 / Q5: `8,6 / 0,9`, con el pico de 45–64 marcado (`11,1`);
- salud mental atendida en la privada, 18–24 / 65–74: `64 / 20`;
- especialista solo en la privada, clase alta / clase baja: `33 / 8`;
- cita con el médico de familia en el día o al siguiente, municipio ≤2.000 / ciudad de más de un millón: `57 / 12`.

La primera fila es la «fortaleza» (pesa casi un punto) y las demás son las grietas. Así no hay dos escalas arbitrarias.

**Copia:** zanja «la sanidad pública trata igual a todos» (sí en el médico, no en el dentista ni en el psicólogo) y «el campo está abandonado» (en primaria, al revés). Queda ambiguo el sesgo de las encuestas y que la clase es autodeclarada.

**Datos:** ampliar la ingesta de `hlth_silc_09` (bandas de edad) y leer las hojas de cruce del Barómetro que ya están en caché. Sin descargas nuevas grandes.

### 2. Reescribir el resumen y las cifras destacadas con el salto de grupo y corregir el titular de años saludables

- **«Se vive mucho y con salud»**: añadir «a los 30 años, un hombre con estudios primarios vive 8 años menos que una mujer universitaria (`50,2` frente a `58,2`)».
- **Años saludables**: el `68,6` de 2024 está en una **ruptura de serie**. Hasta 2023, España estaba por debajo de la UE (`62,1` frente a `63,1`). El titular de §1 y el punto 1 del resumen no pueden compararlo sin avisarlo. Es una corrección de rigor, independiente de los segmentos.
- **Cifra destacada nueva** en lugar de una de las dos de esperas (que se solapan): «Cita con el médico de familia en el día o al siguiente: `57 %` en pueblos de ≤2.000 habitantes, `12 %` en ciudades de más de un millón (media `22 %`)».
- **Gasto de bolsillo**: decir que el Q1 gasta menos proporción (`2,7 %` frente a `4,4 %`) porque renuncia, no porque esté mejor cubierto.

### Sobre el bloque por comunidades

Ya existe y está bien para listas, gasto y esperanza de vida. **No basta para la atención primaria**: hay que añadir la cita con el médico de familia por comunidad (Barómetro, con el margen de error visible) y, sobre todo, el corte por tamaño de municipio. La diferencia **dentro** de cada comunidad, entre pueblo y gran ciudad, es mayor que la que hay **entre** comunidades. No se proponen figuras nuevas de comunidad aparte de esa.

---

## 6. Dimensiones compartidas (para armonizar con las otras verticales)

- **Edad: `16–34 / 35–64 / 65+`**, con **`75+` como subtramo opcional** en sanidad. Ahí se concentran la dependencia (limitación `50,5 %`) y el coste (`2,7×`).
  - Encaje: EU-SILC publica 16–24 + 25–34 y 35–44 + 45–64 (agregar con pesos de población; Eurostat no da 16–34 directo en estas tablas). El Barómetro empieza en 18 (18–24 + 25–34) y tiene 65–74 / 75+. El EHIS tiene 15–29, que no encaja limpio con 16–34; usar 15–24 + 25–34.
  - Sin motivo para cambiar la propuesta de partida, salvo añadir 75+.
- **Renta: quintil de renta equivalente (Q1–Q5 de EU-SILC)**, mostrando Q1 frente a Q5 y la media. Es la misma unidad que usan vivienda y fiscalidad en EU-SILC/ECV. En sanidad, la «clase subjetiva» del Barómetro solo como proxy y diciéndolo.
- **Territorio: comunidad autónoma + tamaño del municipio.** Cambio respecto a la sugerencia de partida: en sanidad no existe «Madrid y Barcelona metropolitanas» en ninguna fuente, y lo que separa realidades es el tamaño del municipio. Propuesta armonizable:
  - **comunidad autónoma** para todo lo que se gestiona por comunidad (listas, gasto);
  - **eje urbano-rural** con dos codificaciones según la fuente: grado de urbanización de Eurostat (`DEG1` ciudades / `DEG2` pueblos y periferias / `DEG3` rural), común a todas las verticales EU-SILC, y, cuando la fuente sea el CIS/Barómetro, tamaño de municipio agrupado en `≤10.000 / 10.001–400.000 / >400.000` (el tramo >1.000.000 ≈ Madrid y Barcelona ciudad, como aproximación a «grandes metrópolis»).

---

## Resumen

- **Dimensiones:** renta (quintil), edad (16–34 / 35–64 / 65+, con 75+) y territorio en dos niveles (comunidad + tamaño de municipio). Sexo × estudios, solo para la esperanza de vida.
- **Casos tipo:** Carmen (78 años, pueblo de Castilla-La Mancha), Lucía (27, renta baja, Madrid, psicólogo y dentista), Antonio (52, trabajador manual, Andalucía), Laura (45, renta alta, Barcelona, con seguro).
- **Hallazgos:**
  - la renuncia médica es plana entre grupos;
  - dentista por coste: `11,1 %` (Q1, 45–64) frente a `1,0 %` (Q5);
  - salud mental: el `64 %` de los jóvenes la paga en la privada;
  - cita en el día o al siguiente: `57 %` en pueblos frente a `12 %` en grandes ciudades;
  - `8` años de esperanza de vida a los 30 entre los extremos de sexo × estudios.
- **Cambio prioritario:** panel de brechas «¿para quién se cumple?» en la figura consolidada; reescribir el resumen y las cifras destacadas; avisar de la ruptura de serie de los años saludables de 2024.
- **Huecos:** esperas sin desglose por edad, renta ni municipio; no hay esperanza de vida oficial por renta ni seguro privado por renta; Barómetro sin cruces dobles y con muestras pequeñas por comunidad; EHIS de una sola ola (2019).
