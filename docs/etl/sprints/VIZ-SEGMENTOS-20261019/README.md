# Casos tipo en `/visualizaciones/`: síntesis y armonización

Fecha: 2026-10-19. Cinco auditorías, una por vertical: [empleo](empleo.md), [educación](educacion.md),
[vivienda](vivienda.md), [sanidad](sanidad.md) y [fiscalidad](fiscalidad.md). Solo análisis: no se ha tocado código ni datos.

- **Dónde estamos.** Las cinco páginas ya tienen cortes sueltos (quintil, comunidad, tenencia), pero las cifras destacadas,
  los titulares y las figuras consolidadas siguen hablando de «España» o del «hogar medio» como si fueran una persona.
- **A dónde vamos.** Pocas dimensiones por vertical, las que de verdad parten la realidad, y unos casos tipo **compartidos**
  entre verticales, cada uno con su cifra al lado de la media.
- **Qué sigue.** El cambio prioritario de cada vertical (§4), en una sesión de implementación por vertical, más las
  correcciones de rigor de §5, que no esperan.

## 1. Lo que encontraron: la media engaña, y en cada vertical por un motivo distinto

| Vertical | Media que engaña | Lo que esconde |
|---|---|---|
| Vivienda | «El hogar dedica el 16 % de su renta a la vivienda» | Es la media de los cocientes (la mediana es el 10,4 %). Sobrecarga: 1,9 % de los propietarios sin hipoteca frente al 26,8 % de los inquilinos de mercado (×14). El 82 % de los hogares de 65+ tiene la casa pagada; de los de 16–29 que se han ido de casa, el 50 % alquila a precio de mercado, y la mitad de los de 25–34 no se ha ido. |
| Empleo | Paro del 10,5 % | Va del 2,7 % (universitario de 45–54, País Vasco) al 41,6 % (15–24 sin bachillerato, Andalucía). La bajada de la temporalidad es casi toda privada: en el sector público sigue en el 27,4 %, y en el 66 % entre los asalariados públicos de 25–29. |
| Educación | PISA 473; abandono del 12,8 % | El origen familiar separa 86 puntos de PISA (lo que se perdió desde 2003 son 12). Abandono: 2,4 % con madre universitaria frente a 32,9 % con madre de Primaria. Gran parte de la caída del abandono es efecto composición (dentro de cada grupo bajó de 2 a 7 puntos; en el total, 18). |
| Sanidad | «Buenos resultados gastando poco» | Se cumple en lo que cubre lo público (la renuncia al médico no depende de la renta: 1,6 % frente a 1,3 %). No se cumple en lo que no cubre: dentista 8,6 % frente a 0,9 % por renta, y el 64 % de los jóvenes que recibieron atención de salud mental la pagó en la privada. Cita con el médico de familia en el día o al siguiente: 57 % en pueblos y 12 % en las ciudades de más de un millón. |
| Fiscalidad | Renta de los hogares +20 % desde 2000; la cuña del soltero con salario medio | Renta mediana real 2008→2025: +29 % para los mayores de 65 y ≈0 entre los 25 y los 64. El «salario medio» de la OCDE está un 33 % por encima de la mediana. Con la misma renta bruta, al joven inquilino de Madrid le queda la mitad que al pensionista propietario. |

Tienen en común que **la tenencia de la vivienda y la edad hacen la mayor parte del trabajo** en vivienda y en fiscalidad,
**el origen social** en educación (y, a través de la formación, en empleo), y **el territorio** en todas, pero a una
escala distinta en cada vertical.

## 2. Dimensiones armonizadas

### Edad: etapas de vida comunes, banda oficial a la vista

Las fuentes no admiten una sola partición: la ECV del INE da 16–29 / 30–44 / 45–64 / 65+, la EPA y la EU-SILC por edad dan
15–24 / 25–34 / …, y educación tiene edades fijadas por definición (15 años en PISA, 18–24 en abandono). Regla común:

| Etapa | Banda preferida | Alternativa según la fuente |
|---|---|---|
| Joven | **16–29** (ECV: tenencia, renta) | 25–34 (EPA, Eurostat SILC), 15–24 para el paro juvenil, 18–24 para el abandono |
| Adulto joven, crianza o compra | **30–44** | 35–44 |
| Adulto maduro | **45–64** | 45–54 / 55–64 cuando la generación importe (empleo, educación adulta) |
| Mayor | **65+** (fijo en todas las verticales) | 75+ como subtramo en sanidad |

- El corte de los 65 años no se mueve en ninguna vertical (pensión, casa pagada, uso de la sanidad).
- Cada figura **rotula la banda real de su fuente**. Nunca se empalma una banda con otra ni se promedian tasas para fabricar
  una banda: si hace falta, se suman efectivos.
- Edad de la persona de referencia para las variables del hogar (tenencia, gasto); edad propia para las de la persona
  (paro, renta equivalente, emancipación).
- Las cifras de jóvenes de la EU-SILC dejan fuera a quienes viven con sus padres (el 50 % de los de 25–34): cada figura de
  jóvenes que use la encuesta pone al lado la tasa de emancipación (`ilc_lvps08`).

### Territorio: comunidad siempre, y un segundo nivel según lo que separe

- **Base común: comunidad autónoma (NUTS 2)**, con régimen **foral o común** marcado en fiscalidad.
- **Segundo nivel, distinto en cada vertical**, porque lo que separa no es lo mismo en cada una:
  - *Coste de vida* (vivienda y fiscalidad): **municipios de Madrid, Barcelona y Palma frente al resto de su provincia y
    al resto de España** (SERPAVI y ADRH por municipio). No hay paridades de poder adquisitivo regionales oficiales: el
    alquiler hace de aproximación, y hay que decirlo.
  - *Acceso* (sanidad): **tamaño del municipio** (Barómetro Sanitario), donde lo rural está *mejor* en atención primaria.
  - *Mercado de trabajo* (empleo): la comunidad basta; ser área metropolitana no cambia el paro (Cádiz 22 %, Vitoria 7 %).
    Empleo agrupa las comunidades en tres mercados (paro bajo y salario alto; paro bajo y salario medio; paro alto) más
    Ceuta y Melilla aparte.
  - *Tablas de la EU-SILC que no bajan de comunidad*: el **grado de urbanización** (DEGURBA) como sustituto, diciendo que
    Madrid y Valladolid cuentan las dos como «ciudad».

### Dimensiones compartidas además de edad y territorio

- **Tenencia en 4 grupos**: propietario sin hipoteca / con hipoteca / alquiler de mercado / alquiler reducido o cedido.
  Es el primer eje en vivienda y el segundo en fiscalidad; empleo la usa en su lente de capacidad.
- **Renta: quintil de renta equivalente** (EU-SILC/ECV), Q1 frente a Q5 y la media. En sanidad, la «clase» del Barómetro
  es autodeclarada: se usa como aproximación, y se dice.
- **Origen social** (estudios de la madre o de los padres; ISEC en PISA): primer eje en educación. Se puede reutilizar en
  empleo cuando una fuente lo cruce.
- Descartadas como eje en todas las verticales (se usan dentro de los casos o en una frase): sexo (salvo la esperanza de
  vida por sexo y estudios), nacionalidad (se nota sobre todo a través de la tenencia, la renta y la formación),
  titularidad del centro (a igual ISEC la brecha es de 5 puntos), tamaño de empresa y sector.

| Vertical | Dimensiones elegidas (por orden) |
|---|---|
| Vivienda | tenencia · edad/cohorte · territorio tensionado frente al resto |
| Empleo | edad · formación · comunidad · relación laboral (contrato, jornada, sector público) como atributo |
| Educación | origen social · comunidad (siempre junto al ISEC) · generación (adultos) · origen migratorio después de la ESO |
| Sanidad | renta · edad (con 75+) · comunidad + tamaño del municipio · sexo × estudios solo para la esperanza de vida |
| Fiscalidad | edad · tenencia · quintil de renta · tipo de hogar (hijos) como modificador |

## 3. Casos tipo compartidos

Cinco personas que aparecen en todas las verticales donde tienen algo que decir, para que el lector pueda seguirlas de una
página a otra. Las cifras están en cada informe; esta tabla dice en qué caso de cada informe se apoyan.

| Persona | Vivienda | Empleo | Educación | Sanidad | Fiscalidad |
|---|---|---|---|---|---|
| **1. Joven (25–34, el tramo del sueldo neto joven del INE), asalariada, vive sola de alquiler en la ciudad de Madrid** | B | B | 5 (si es extranjera) | Lucía | A |
| **2. Pareja de 30–44 con hijos, hipoteca o alquiler en un área metropolitana** | C / D | — | 1 / 2 (sus hijos) | — | B |
| **3. Adulto de 45–64 con poca formación, en el sur** | — | A / F | 3 (sus hijos), 6 | Antonio | — |
| **4. Pensionista de 65 años o más, propietario sin hipoteca, en una provincia del interior** | A | — | 6 (generación) | Carmen | D |
| **5. Profesional de 45–54, universitario, en el norte o en Madrid** | — | D | 4 (sus hijos) | Laura | E |

Casos propios de una vertical que se mantienen: el joven que vive con sus padres (vivienda E: no aparece en ninguna
estadística de gasto), la monoparental (fiscalidad C), la jornada parcial que no se eligió (empleo E) y el interino del
sector público (empleo C).

Reglas para los casos:
- Una persona tiene la **misma definición en todas las páginas** (edad, tenencia, territorio). Ejemplo: la persona 1 usa el
  alquiler mediano SERPAVI de la **ciudad** de Madrid (869 €) tanto en vivienda como en fiscalidad. Hoy fiscalidad usa los
  800 € de la comunidad.
- Cuando no hay un cruce oficial, la cifra viene del **corte marginal** que define al caso y se dice así («personas de su
  edad…, de su municipio…»), nunca se presenta como una celda observada.
- Las cifras calculadas (fiscalidad, vivienda) llevan su fórmula y sus supuestos, y se marcan como ilustrativas.
- La media nacional va siempre al lado, para que se vea el salto.

## 4. Prioridades: un cambio principal por vertical

| Vertical | Cambio principal | Datos | Coste |
|---|---|---|---|
| Empleo | Figura «estructural, ¿de quién?»: paro por edad × formación × comunidad frente a la media española y a la de la UE del mismo grupo | Eurostat `lfst_r_lfu3rt`, tabla que el pipeline ya usa | Bajo |
| Vivienda | Mosaico tenencia × edad (con los no emancipados y los casos marcados) en lugar del titular de `#sobrecarga`; el 16 % de carga fiscal, con su desglose | INE ECV t=9994, `ilc_lvho07c`, `ilc_lvps08` | Medio |
| Sanidad | Panel de brechas «¿para quién se cumple?» en la figura consolidada | `hlth_silc_09` por edad; hojas de cruce del Barómetro ya en la caché | Bajo |
| Educación | Figura «¿dónde está la diferencia?»: brechas de PISA bruta y ajustada por ISEC (origen social, comunidad, titularidad, origen migratorio, sexo, caída desde 2003, distancia con la OCDE) | Citas del INEE y la OCDE ya descargadas | Bajo |
| Fiscalidad | La mitad «renta» de `#bolsillo` partida por edad; luego, la figura «Cinco hogares» en cascada con las personas de §3 | `ilc_di03` por edad + IPCA, INE ECV t=9994; OCDE Taxing Wages por tipo de hogar | Medio, y depende de la ruptura de 2013 |

Orden propuesto: empleo, sanidad y educación primero (datos ya disponibles o en caché); después vivienda; fiscalidad la
última, porque su figura de casos se alimenta de los alquileres de vivienda y de los salarios de empleo.

## 5. Correcciones de rigor que no esperan a la segmentación

- **Sanidad**: el titular y el resumen comparan los años de vida saludable de 2024 (68,6) con la UE (65,2) sin avisar de
  que 2024 es una ruptura de serie (`b` en `hlth_hlye`). Hasta 2023, España estaba por **debajo** de la UE (62,1 frente a
  63,1).
- **Empleo**: el bloque «Lo que estos datos no pueden decir» sigue diciendo que no se ven las comunidades, pero los
  capítulos 4 y 7 ya las muestran. Junto al paro juvenil del 24,9 % falta la proporción sobre toda la población (8,4 %).
- **Vivienda y fiscalidad**: el «16 %» es una media de cocientes; hay que dar también la mediana (10,4 %).
- **Educación**: «mucho menos abandono» se tiene que presentar con su efecto composición, como hipótesis hasta tener los
  pesos.

## 6. Pendiente de verificar antes de publicar

- Fiscalidad: el saldo fiscal neto por edad (EsadeEcPol) sale de un resumen de buscador; la página da `403` a scripts.
  Hay que verificarlo en el PDF o dejarlo fuera.
- Fiscalidad: posible ruptura de `ilc_di03` en 2013 (el INE pasó a usar rentas de registros); leer las marcas de Eurostat.
- Vivienda: el 98,7 % del Consejo de la Juventud es una fuente secundaria (vía prensa); se cita como tal o no se cita.
- Sanidad: rareza en `hlth_silc_11` (enfermedad crónica del 29,2 % entre los de 16–24, por encima del 18,9 % de los de
  25–34).
- Empleo: la temporalidad privada sale por diferencia; falta localizar la tabla gemela del INE.
- Educación: las puntuaciones de PISA por cuartil ISEC solo están en figura o en oecd.org (bloqueado por Cloudflare); la
  figura propuesta no las necesita.

## 7. Huecos de datos comunes (para decirlos en las páginas)

- No hay cruce oficial edad × tenencia × comunidad (hacen falta microdatos de la ECV, con intervalos de confianza).
- No hay precio oficial de los contratos de alquiler nuevos: el SERPAVI recoge los contratos vigentes declarados.
- No hay paridades de poder adquisitivo regionales oficiales.
- Las esperas sanitarias no se publican por edad, renta ni municipio.
- No hay ingresos de los autónomos comparables en la EPA.
- No hay incidencia oficial del IVA por renta (solo las tablas experimentales de Eurostat, `icw_tax_*`, de 2010, 2015 y 2020).
