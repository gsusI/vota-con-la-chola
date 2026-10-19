import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure from "../components/Figure";
import SparseLineChart from "./SparseLineChart";
import EduTable from "./EduTable";
import { fmt } from "./formatEdu.mjs";

export const C = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  ref: "#52514e",
  peer: "#b4b2a9",
};

export const NAMES = {
  ESP: "España",
  ES: "España",
  OECD: "Media OCDE",
  EU25: "Media UE (países de la OCDE)",
  EU27_2020: "UE-27",
  DEU: "Alemania",
  DE: "Alemania",
  FRA: "Francia",
  FR: "Francia",
  ITA: "Italia",
  IT: "Italia",
  PRT: "Portugal",
  PT: "Portugal",
};

const REGION_SHORT = {
  "Asturias, Principado de": "Asturias",
  "Balears, Illes": "Illes Balears",
  "Madrid, Comunidad de": "Madrid",
  "Murcia, Región de": "Región de Murcia",
  "Navarra, Comunidad Foral de": "Navarra",
  "Rioja, La": "La Rioja",
};

export const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const muted = { color: "var(--viz-muted)", fontWeight: 400 };

// Three short answers above each chart: what it shows, how to read it and what it cannot tell.
export function Explain({ shows, read, notSay }) {
  const items = [
    ["Qué muestra", shows],
    ["Cómo leerlo", read],
    ["Qué no dice", notSay],
  ].filter(([, text]) => text);
  return (
    <dl
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
        gap: "10px 18px",
        margin: "4px 0 14px",
        padding: "12px 14px",
        borderLeft: "3px solid var(--viz-grid)",
        background: "var(--viz-band)",
        borderRadius: 6,
        fontSize: "0.86rem",
        lineHeight: 1.45,
      }}
    >
      {items.map(([label, text]) => (
        <div key={label}>
          <dt style={{ fontWeight: 700, marginBottom: 2 }}>{label}</dt>
          <dd style={{ margin: 0, color: "var(--viz-ink-2)" }}>{text}</dd>
        </div>
      ))}
    </dl>
  );
}

function comparison(seriesByArea, areas, refs = []) {
  return areas
    .filter((area) => seriesByArea[area]?.length)
    .map((area) => {
      const isSpain = area === "ESP" || area === "ES";
      return {
        id: area,
        label: NAMES[area] || area,
        color: isSpain ? C.blue : refs.includes(area) ? C.ref : C.peer,
        emphasis: isSpain,
        points: seriesByArea[area],
      };
    })
    .reverse();
}

function Bars({ rows, max, unit = "pct", digits = 0, label }) {
  return (
    <ul className="vizBars" aria-label={label}>
      {rows.map((row) => (
        <li key={row.label}>
          <span>{row.label}</span>
          <span className="vizBars__track">
            <span className="vizBars__bar" style={{ width: `${(row.value / max) * 100}%`, background: row.color || C.blue }} />
            <span className="vizBars__value">
              {fmt(row.value, unit, digits)}
              {row.note ? <span style={muted}> {row.note}</span> : null}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------------------------- regions
export function RegionsFigure({ data, sources }) {
  const rp = data.regions_pisa;
  const rows = rp.rows.filter((row) => row.math != null);
  const best = rows[0];
  const worst = rows.at(-1);
  const maxSpend = Math.max(...rows.map((row) => row.spending_per_student));
  const countries = ["DEU", "FRA", "ITA", "PRT", "ESP", "OECD"]
    .map((area) => ({ area, value: data.pisa.math[area]?.find((p) => p.year === 2022)?.value }))
    .filter((row) => row.value != null);
  const countrySpread = Math.max(...countries.map((c) => c.value)) - Math.min(...countries.map((c) => c.value));
  const cheapest = [...rows].sort((a, b) => a.spending_per_student - b.spending_per_student)[0];
  const priciest = [...rows].sort((a, b) => b.spending_per_student - a.spending_per_student)[0];
  const name = (region) => REGION_SHORT[region] || region;
  const rank = (region) => rows.findIndex((row) => row.region === region) + 1;
  return (
    <Figure
      id="regiones"
      title={`Entre comunidades hay ${best.math - worst.math} puntos de diferencia en PISA matemáticas, más que entre España, Alemania, Francia, Italia y Portugal (${countrySpread} puntos)`}
      dek={`${name(best.region)} (${best.math}) y ${name(worst.region)} (${worst.math}) en 2022. El gasto público por alumno apenas lo explica: la correlación entre gasto y puntuación en las ${rp.n} comunidades es de ${num(rp.pearson, 2)}. ${name(priciest.region)} gasta ${fmt(priciest.spending_per_student, "eur")} por alumno y ${name(cheapest.region)} ${fmt(cheapest.spending_per_student, "eur")}.`}
      sources={sources}
      notes={[
        `Gasto por alumno: ${rp.formula}. No incluye el gasto de ayuntamientos ni del Ministerio en cada comunidad; Ceuta y Melilla (${rp.cities.Ceuta} y ${rp.cities.Melilla} puntos) las gestiona el Ministerio y no tienen consejería, por eso quedan fuera de la comparación.`,
        "El denominador es todo el alumnado de régimen general, también el de centros privados sin concierto, que no recibe gasto público: las comunidades con más enseñanza privada sin concierto salen con menos gasto por alumno del que reciben los centros sostenidos con fondos públicos.",
        "PISA por comunidad: muestras ampliadas del INEE; cada valor tiene un margen de error de varios puntos. Euros corrientes de 2022 sin corregir por diferencias de precios entre comunidades.",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Comunidad</th>
                  <th scope="col">PISA matemáticas 2022</th>
                  <th scope="col">Gasto por alumno 2022</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.region}>
                    <td>{name(row.region)}</td>
                    <td>{row.math}</td>
                    <td>{fmt(row.spending_per_student, "eur")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Explain
        shows="Cada fila es una comunidad autónoma, ordenada por su puntuación en matemáticas en PISA 2022. A la izquierda, la puntuación; a la derecha, lo que gastó su consejería de educación por alumno ese año."
        read={`Si más gasto significara mejores resultados, las barras verdes se acortarían de arriba abajo igual que las azules. Apenas ocurre: ${name(priciest.region)}, la que más gasta, queda en el puesto ${rank(priciest.region)} de ${rows.length} en PISA; ${name(cheapest.region)}, la que menos, en el ${rank(cheapest.region)}.`}
        notSay="No mide eficiencia ni causalidad: las comunidades difieren en renta, origen del alumnado, dispersión rural, salarios docentes y precios. Una correlación débil con 17 comunidades no prueba que el gasto no importe."
      />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(110px, 160px) 1fr 1fr", gap: "4px 12px", fontSize: "0.84rem", alignItems: "center" }}>
        <span />
        <strong>PISA matemáticas (eje 0–600)</strong>
        <strong>Gasto por alumno (eje desde 0)</strong>
        {rows.map((row) => (
          <RegionRow key={row.region} row={row} name={name(row.region)} maxSpend={maxSpend} />
        ))}
      </div>
    </Figure>
  );
}

function RegionRow({ row, name, maxSpend }) {
  const track = { display: "flex", alignItems: "center", gap: 6, minWidth: 0 };
  const bar = (width, color) => ({ height: 14, width: `${width}%`, background: color, borderRadius: "0 3px 3px 0", minWidth: 2 });
  return (
    <>
      <span>{name}</span>
      <span style={track}>
        <span style={bar((row.math / 600) * 85, C.blue)} />
        <span>{row.math}</span>
      </span>
      <span style={track}>
        <span style={bar((row.spending_per_student / maxSpend) * 70, C.aqua)} />
        <span>{fmt(row.spending_per_student, "eur")}</span>
      </span>
    </>
  );
}

// --------------------------------------------------------------------------------------------- equity
export function EquityFigure({ data, sources }) {
  const eq = data.equity;
  const comp = eq.composition;
  const share = eq.immigrant_share;
  return (
    <Figure
      id="equidad"
      title={`El origen social pesa en España algo menos que en la OCDE (${eq.escs_gap.ESP[2022]} frente a ${eq.escs_gap.OECD[2022]} puntos), y la llegada de alumnado inmigrante explicaría solo ${num(comp.effect_raw_points)} de los ${Math.abs(comp.math_change_2012_2022)} puntos perdidos en matemáticas desde 2012`}
      dek={`El alumnado de origen inmigrante pasó del ${num(share.ESP[0].value)} % en ${share.ESP[0].year} al ${num(comp.share_2022, 0)} % en 2022. Saca ${comp.gap_raw} puntos menos en matemáticas, pero solo ${comp.gap_adjusted} cuando se compara con alumnos de su mismo nivel socioeconómico: la diferencia es sobre todo social, no de origen.`}
      sources={sources}
      notes={[
        `Efecto composición: ${comp.formula}. ${num(comp.share_2022 - comp.share_2012)} puntos porcentuales más de alumnado inmigrante × ${comp.gap_raw} puntos de diferencia = ${num(comp.effect_raw_points)} puntos de la media; con la diferencia ajustada por nivel socioeconómico (${comp.gap_adjusted}), ${num(comp.effect_adjusted_points)}.`,
        "ISEC: índice PISA de estatus económico, social y cultural (estudios y profesión de los padres, recursos en casa). Valores de la nota de país de la OCDE y de los informes españoles del INEE, con cita literal.",
      ]}
      table={
        <EduTable
          caption="Ver el alumnado de origen inmigrante en tabla"
          series={[
            { id: "ESP", label: "España", points: share.ESP },
            { id: "OECD", label: "Media OCDE", points: share.OECD },
          ]}
        />
      }
    >
      <Explain
        shows="Cuánto pesa el origen familiar en los resultados de PISA y cuánto ha cambiado la composición del alumnado. Separa el «sistema» de la «mezcla» de alumnos."
        read={`Brecha socioeconómica: puntos de diferencia entre el 25 % de alumnos más aventajado y el 25 % menos. Cuanto menor, más equitativo. El efecto composición es una cuenta sencilla: cuánto bajaría la media solo porque cambia quién se examina.`}
        notSay="La cuenta del efecto composición es ilustrativa: supone que nada más cambió. Tampoco recoge otros cambios de la mezcla, como que hoy siguen en clase alumnos que antes abandonaban o repetían."
      />
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            Brecha entre el 25 % más y menos aventajado
            <span>Puntos de PISA matemáticas, 2022</span>
          </h3>
          <Bars
            label="Brecha socioeconómica en PISA matemáticas"
            unit="score"
            max={120}
            rows={[
              { label: "España", value: eq.escs_gap.ESP[2022], color: C.blue },
              { label: "Media OCDE", value: eq.escs_gap.OECD[2022], color: C.ref },
            ]}
          />
          <h3 className="vizPanelTitle">
            Alumnos desaventajados en el cuarto superior (resilientes)
            <span>% del alumnado desaventajado, 2022</span>
          </h3>
          <Bars
            label="Alumnado resiliente"
            max={25}
            rows={[
              { label: "España", value: eq.resilient.ESP[2022], color: C.blue },
              { label: "Media OCDE", value: eq.resilient.OECD[2022], color: C.ref },
            ]}
          />
          <h3 className="vizPanelTitle">
            Variación de resultados explicada por el origen social
            <span>% de la varianza en matemáticas, 2022</span>
          </h3>
          <Bars
            label="Varianza explicada por el ISEC"
            max={25}
            rows={[
              { label: "España", value: eq.escs_variance.ESP[2022], color: C.blue },
              { label: "Media OCDE", value: eq.escs_variance.OECD[2022], color: C.ref },
            ]}
          />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Alumnado de 15 años de origen inmigrante (%)
            <span>
              España: {num(share.ESP[0].value)} % ({share.ESP[0].year}) → {num(comp.share_2022, 0)} % (2022); el {eq.immigrant_disadvantaged_pct} % de ellos es desaventajado
            </span>
          </h3>
          <SparseLineChart
            series={[
              { id: "OECD", label: "Media OCDE", color: C.ref, points: share.OECD },
              { id: "ESP", label: "España", color: C.blue, emphasis: true, points: share.ESP },
            ]}
            unit="pct"
            digits={1}
            xMin={2000}
            xMax={2022}
            yMax={20}
            height={200}
            ariaLabel="Alumnado de origen inmigrante en PISA"
          />
          <h3 className="vizPanelTitle">
            Caída de PISA matemáticas 2012-2022 y parte atribuible al cambio de composición
            <span>Puntos</span>
          </h3>
          <Bars
            label="Efecto composición"
            unit="ratio"
            max={12}
            rows={[
              { label: "Caída total de España", value: Math.abs(comp.math_change_2012_2022), color: C.ref },
              { label: "Por más alumnado inmigrante", value: comp.effect_raw_points, color: C.orange },
              { label: "Ídem, a igual nivel social", value: comp.effect_adjusted_points, color: C.yellow },
            ]}
          />
        </div>
      </div>
    </Figure>
  );
}

// --------------------------------------------------------------------------------------------- teachers
export function TeachersFigure({ data, sources }) {
  const t = data.teachers;
  const th = t.headline;
  const salary = ["PRT", "ITA", "FRA", "DEU", "OECD", "ESP"]
    .filter((area) => t.salary_index.ISCED11_24[area]?.length)
    .map((area) => ({
      id: area,
      label: NAMES[area],
      color: area === "ESP" ? C.blue : area === "OECD" ? C.ref : C.peer,
      emphasis: area === "ESP",
      noEndLabel: !["ESP", "OECD"].includes(area),
      points: t.salary_index.ISCED11_24[area],
    }));
  const salaryMax = Math.max(...salary.flatMap((s) => s.points.map((p) => p.value)));
  const ratio = comparison(t.pupil_teacher.ED2, ["ES", "EU27_2020", "DE", "FR", "IT", "PT"], ["EU27_2020"]);
  const esRatio = t.pupil_teacher.ED2.ES.at(-1);
  const euRatio = t.pupil_teacher.ED2.EU27_2020?.at(-1);
  return (
    <Figure
      id="profesorado"
      title={`El sueldo real del profesorado de ESO sigue un ${Math.abs(th.salary_change_from_peak_pct)} % por debajo de ${th.salary_peak.year}; en la OCDE ha subido`}
      dek={`Índice de salario legal con 15 años de experiencia, descontada la inflación (2015 = 100): España ${num(th.salary_peak.value)} en ${th.salary_peak.year} y ${num(th.salary_last.value)} en ${th.salary_last.year}; media OCDE ${num(th.oecd_2009)} en 2009 y ${num(th.oecd_last.value)} en ${th.oecd_last.year}. A la vez, hay menos alumnos por profesor que en la UE: ${num(esRatio.value)} en ESO frente a ${euRatio ? num(euRatio.value) : "—"} (${esRatio.year}).`}
      legend={[
        { id: "ESP", label: "España", color: C.blue },
        { id: "ref", label: "Media OCDE / UE-27", color: C.ref },
        { id: "peer", label: "Alemania, Francia, Italia, Portugal", color: C.peer },
      ]}
      sources={sources}
      notes={[
        "Salario: profesorado de centros públicos de secundaria inferior con la titulación más habitual y 15 años de experiencia, salario legal (no el cobrado con complementos). Es un índice: compara la evolución de cada país consigo mismo, no niveles entre países.",
        "Alumnos por profesor: equivalentes a tiempo completo, ESO y equivalentes (ISCED 2). No es el tamaño de las clases.",
      ]}
      table={
        <>
          <EduTable unit="index" caption="Ver el índice de salarios en tabla" series={[...salary].reverse()} />
          <EduTable unit="ratio" caption="Ver alumnos por profesor en tabla" series={[...ratio].reverse()} />
        </>
      }
    >
      <Explain
        shows="Dos recursos que el gasto paga: lo que cobra un profesor, descontada la inflación, y cuántos alumnos hay por profesor."
        read="Índice 2015 = 100: un valor de 110 significa un 10 % más de poder adquisitivo que en 2015. Las líneas de cada país solo se comparan con su propio pasado."
        notSay="No dice si los profesores cobran mucho o poco frente a otros países ni frente a otros titulados, ni nada sobre su formación o la calidad de la enseñanza."
      />
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            Salario real del profesorado de ESO (índice 2015 = 100)
            <span>OCDE, Education at a Glance</span>
          </h3>
          <SparseLineChart series={salary} unit="index" digits={1} xMin={2000} yMax={salaryMax} height={240} ariaLabel="Salario real del profesorado de ESO" />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Alumnos por profesor en ESO
            <span>Eurostat, educ_uoe_perp04</span>
          </h3>
          <SparseLineChart series={ratio} unit="ratio" digits={1} height={240} endLabels={false} ariaLabel="Alumnos por profesor en secundaria inferior" />
        </div>
      </div>
    </Figure>
  );
}

// --------------------------------------------------------------------------------------------- vocational
export function VocationalFigure({ data, sources }) {
  const v = data.vocational;
  const share = comparison(v.share_upper_secondary, ["ES", "EU27_2020", "DE", "FR", "IT", "PT"], ["EU27_2020"]);
  const esShare = v.share_upper_secondary.ES.at(-1);
  const euShare = v.share_upper_secondary.EU27_2020.at(-1);
  const rg = v.recent_graduates_employment;
  const last = (level, geo) => rg[level][geo]?.at(-1);
  const year = last("ED35_45", "ES")?.year;
  const rows = [
    ["ED34_44", "Bachillerato (general)"],
    ["ED35_45", "FP de grado medio y equivalentes"],
    ["ED5-8", "Estudios superiores"],
  ].flatMap(([level, label]) => [
    { label: `${label} · España`, value: last(level, "ES")?.value, color: C.blue },
    { label: `${label} · UE-27`, value: last(level, "EU27_2020")?.value, color: C.ref },
  ]);
  return (
    <Figure
      id="fp"
      title={`Solo el ${num(esShare.value, 0)} % del alumnado de Bachillerato y FP de grado medio está en FP (UE: ${num(euShare.value, 0)} %), aunque sus titulados encuentran empleo antes que los de Bachillerato`}
      dek={`En ${year}, el ${num(last("ED35_45", "ES").value)} % de los titulados recientes de FP de grado medio trabajaba, frente al ${num(last("ED34_44", "ES").value)} % de los de Bachillerato que no siguieron estudiando; en la UE, ${num(last("ED35_45", "EU27_2020").value)} % y ${num(last("ED34_44", "EU27_2020").value)} %.`}
      legend={share.slice().reverse()}
      sources={sources}
      notes={[
        "Peso de la FP: alumnado en programas profesionales (ISCED 35) sobre el total de secundaria superior (ISCED 3), Eurostat UOE. Empleo: jóvenes de 20 a 34 años que terminaron hace 1-3 años y no siguen estudiando (Encuesta de Población Activa).",
        "Quien acaba Bachillerato suele seguir estudiando; los que no lo hacen son un grupo seleccionado, por eso su tasa de empleo no mide el valor del Bachillerato.",
      ]}
      table={<EduTable caption="Ver el peso de la FP en tabla" series={share.slice().reverse()} />}
    >
      <Explain
        shows="Qué parte del alumnado de 16 a 18 años elige la vía profesional y cuántos titulados recientes trabajan según lo que estudiaron."
        read="La línea azul es España; la oscura, la media de la UE. En las barras, cada par compara España y la UE para el mismo título."
        notSay="No dice la calidad del empleo (salario, temporalidad, si está relacionado con lo estudiado) ni incluye la FP de grado superior, que cuenta como estudios superiores."
      />
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            FP en % del alumnado de secundaria superior
            <span>Eurostat, educ_uoe_enrs04</span>
          </h3>
          <TimeSeriesChart series={share} yMax={60} height={240} ariaLabel="Peso de la FP en secundaria superior" />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Titulados recientes con empleo, {year}
            <span>% de 20-34 años, 1-3 años tras terminar</span>
          </h3>
          <Bars label="Empleo de titulados recientes" unit="pct" digits={1} max={100} rows={rows.filter((row) => row.value != null)} />
        </div>
      </div>
    </Figure>
  );
}

// --------------------------------------------------------------------------------------------- attainment
export function AttainmentFigure({ data, sources, overq }) {
  const a = data.attainment_25_34;
  const areas = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"];
  const last = (level, geo) => a[level][geo]?.at(-1);
  const year = last("ED5-8", "ES").year;
  const levels = [
    ["ED0-2", "Como mucho ESO", C.orange],
    ["ED3_4", "Bachillerato o FP media", C.yellow],
    ["ED5-8", "Estudios superiores", C.blue],
  ];
  return (
    <Figure
      id="titulacion"
      title={`España tiene a la vez más jóvenes con estudios superiores (${num(last("ED5-8", "ES").value, 0)} %) y más sin pasar de la ESO (${num(last("ED0-2", "ES").value, 0)} %) que la UE; le falta el escalón intermedio (${num(last("ED3_4", "ES").value, 0)} % frente a ${num(last("ED3_4", "EU27_2020").value, 0)} %)`}
      dek={`Población de 25 a 34 años por nivel de estudios, ${year}. Es el «reloj de arena» de la educación española y ayuda a leer la sobrecualificación: con tantos titulados superiores y pocos técnicos intermedios, una parte de los universitarios ocupa puestos de cualificación media (${num(overq.es)} % frente a ${num(overq.eu)} % en la UE).`}
      legend={levels.map(([id, label, color]) => ({ id, label, color }))}
      legendKind="bar"
      sources={sources}
      notes={["Encuesta de Población Activa de cada país. Los tres niveles suman 100 % (con decimales de redondeo).", "No hemos encontrado en Eurostat la sobrecualificación por rama de estudios, solo por sector de actividad (lfsa_eoqgan2); queda pendiente."]}
      table={
        <EduTable
          caption="Ver los datos en tabla"
          series={areas.flatMap((geo) => levels.map(([level, label]) => ({ id: `${geo}-${level}`, label: `${NAMES[geo]} · ${label}`, points: a[level][geo] || [] })))}
        />
      }
    >
      <Explain
        shows="Cómo se reparte cada generación joven entre tres niveles de estudios terminados."
        read="Cada barra suma 100 %. El tramo naranja son quienes no pasaron de la ESO; el amarillo, Bachillerato o FP de grado medio; el azul, estudios superiores (universidad y FP de grado superior)."
        notSay="No mide competencias: un título no garantiza lo que se sabe. Tampoco dice qué títulos tienen más salida."
      />
      <div style={{ display: "grid", gap: 8 }}>
        {areas.map((geo) => (
          <div key={geo} style={{ display: "grid", gridTemplateColumns: "minmax(80px, 120px) 1fr", gap: 10, alignItems: "center", fontSize: "0.84rem" }}>
            <span style={{ fontWeight: geo === "ES" ? 700 : 400 }}>{NAMES[geo]}</span>
            <span style={{ display: "flex", height: 20, borderRadius: 4, overflow: "hidden" }}>
              {levels.map(([level, label, color]) => {
                const value = last(level, geo)?.value || 0;
                return (
                  <span
                    key={level}
                    title={`${label}: ${num(value)} %`}
                    style={{ width: `${value}%`, background: color, color: "#fff", fontSize: "0.72rem", display: "flex", alignItems: "center", justifyContent: "center", whiteSpace: "nowrap", overflow: "hidden" }}
                  >
                    {value >= 8 ? `${num(value, 0)} %` : ""}
                  </span>
                );
              })}
            </span>
          </div>
        ))}
      </div>
    </Figure>
  );
}

// --------------------------------------------------------------------------------------------- glossary
export function Glossary() {
  const terms = [
    ["PISA", "Prueba de la OCDE a alumnos de 15 años cada tres años (2022 se aplazó un año por la pandemia). Mide si saben usar matemáticas, lectura y ciencias en situaciones prácticas, no si dominan el temario."],
    ["Escala PISA y qué son 10 puntos", "La escala se fijó con media 500 y desviación típica 100 entre los países de la OCDE. Según el informe del INEE, 10 puntos equivalen a un tamaño del efecto del 10 % de esa desviación: una diferencia apreciable pero moderada. Diferencias de 2 o 3 puntos suelen caer dentro del margen de error."],
    ["Media OCDE", "Media simple de los países de la OCDE que participan en cada ciclo; como los países cambian, se compara mejor dentro del mismo año."],
    ["PPS y dólares PPA", "Unidades que corrigen las diferencias de precios entre países (paridad de poder adquisitivo), para que un euro gastado en España y en Alemania compre lo mismo."],
    ["Precios constantes", "Cantidades corregidas por la inflación (aquí con el deflactor del PIB), para comparar años distintos."],
    ["Abandono temprano", "Jóvenes de 18 a 24 años que como mucho terminaron la ESO y no estudian ni se forman. Indicador oficial de la UE, medido con la Encuesta de Población Activa."],
    ["Tasa de idoneidad", "Porcentaje del alumnado matriculado en el curso que le corresponde por su edad. Lo que falta hasta 100 es, casi siempre, alumnado que ha repetido."],
    ["ISEC", "Índice PISA de estatus económico, social y cultural: estudios y profesión de los padres y recursos del hogar."],
    ["Sobrecualificación", "Titulados superiores ocupados en trabajos de cualificación media o baja según la clasificación de ocupaciones ISCO."],
    ["Ruptura de serie", "Cambio de método en la fuente que impide comparar directamente antes y después; se marca y no se empalma."],
  ];
  return (
    <section className="card vizProse" id="glosario" aria-labelledby="glosario-title">
      <h2 id="glosario-title">Glosario</h2>
      <dl style={{ display: "grid", gap: 10, margin: 0 }}>
        {terms.map(([term, text]) => (
          <div key={term}>
            <dt style={{ fontWeight: 700 }}>{term}</dt>
            <dd style={{ margin: 0 }}>{text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
