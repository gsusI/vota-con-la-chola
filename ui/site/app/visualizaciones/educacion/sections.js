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
        "No hay una estadística oficial comparable del sueldo del profesorado por comunidad (cada una fija sus complementos y el Ministerio solo publica el gasto de personal para toda España); queda pendiente.",
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
                  <th scope="col">Abandono temprano {data.territory.leavers_year}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.region}>
                    <td>{name(row.region)}</td>
                    <td>{row.math}</td>
                    <td>{fmt(row.spending_per_student, "eur")}</td>
                    <td>{row.early_leavers != null ? `${num(row.early_leavers)} %` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Explain
        shows="Cada fila es una comunidad autónoma, ordenada por su puntuación en matemáticas en PISA 2022: la puntuación, lo que gastó su consejería de educación por alumno ese año y su tasa de abandono temprano más reciente."
        read={`Si más gasto significara mejores resultados, las barras verdes se acortarían de arriba abajo igual que las azules. Apenas ocurre: ${name(priciest.region)}, la que más gasta, queda en el puesto ${rank(priciest.region)} de ${rows.length} en PISA; ${name(cheapest.region)}, la que menos, en el ${rank(cheapest.region)}.`}
        notSay="No mide eficiencia ni causalidad: las comunidades difieren en renta, origen del alumnado, dispersión rural, salarios docentes y precios. Una correlación débil con 17 comunidades no prueba que el gasto no importe."
      />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(110px, 160px) 1fr 1fr 1fr", gap: "4px 12px", fontSize: "0.84rem", alignItems: "center" }}>
        <span />
        <strong>PISA matemáticas (eje 0–600)</strong>
        <strong>Gasto por alumno (eje desde 0)</strong>
        <strong>Abandono temprano {data.territory.leavers_year} (eje 0–30 %)</strong>
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
      <span style={track}>
        {row.early_leavers != null ? <span style={bar((row.early_leavers / 30) * 75, C.orange)} /> : null}
        <span>{row.early_leavers != null ? `${num(row.early_leavers)} %` : "—"}</span>
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
        "ISEC: índice PISA de estatus económico, social y cultural (estudios y profesión de los padres, recursos en casa). Valores de la nota de país de la OCDE y de los informes españoles del INEE, con cita literal. Las barras muestran la distancia a la media OCDE (0) de cada ciclo; el valor de 2015 (−0,51) se aparta mucho del resto y, sin una serie homogénea de la OCDE (oecd.org bloquea la descarga), no lo leemos como tendencia: lo más que puede decirse es que el alumnado español se ha acercado a la media OCDE entre 2012 y 2022.",
        "Brecha por origen social a lo largo del tiempo: la nota de país de la OCDE afirma que «Entre el 2012 y el 2022, la brecha en el rendimiento matemático entre el mejor 25 % y el peor 25 % de los estudiantes según el ISEC permanecía estable en España, así como en el promedio OCDE». Las puntuaciones por cuartil de cada ciclo solo están en tablas de oecd.org.",
        "Cobertura: la escolarización es obligatoria hasta los 16 años (Ley Orgánica 1/1990, LOGSE), así que casi todos los alumnos de 15 años están escolarizados y se examinan. La caída del abandono temprano, que se mide entre los 18 y los 24 años, apenas cambia quién hace PISA; lo que sí cambia es en qué curso están (menos repetidores).",
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
        notSay="La cuenta del efecto composición es ilustrativa: supone que nada más cambió. Tampoco recoge otros cambios de la mezcla, como que hoy hay menos repetidores entre los alumnos de 15 años."
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
            Origen social medio del alumnado de España en cada ciclo (ISEC)
            <span>Media OCDE = 0 en cada ciclo; valores publicados por el INEE</span>
          </h3>
          <Bars
            label="ISEC medio de España por ciclo"
            unit="ratio"
            digits={2}
            max={0.6}
            rows={(data.composition.isec_by_cycle.ESP || []).map((p) => ({ label: `PISA ${p.year}`, value: Math.abs(p.value), color: C.blue, note: `(${num(p.value, 2)}; por debajo de la media OCDE)` }))}
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
      title={`El sueldo real del profesorado de ESO es un ${Math.abs(th.salary_change_from_2005_pct)} % menor que en ${th.salary_2005.year} y un ${Math.abs(th.salary_change_from_peak_pct)} % menor que en su máximo de ${th.salary_peak.year}; en la OCDE, un ${th.oecd_change_from_2005_pct} % mayor que en ${th.salary_2005.year}`}
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
const AGE_LABEL = { "Y25-34": "25-34 años", "Y35-44": "35-44 años", "Y45-54": "45-54 años", "Y55-64": "55-64 años" };

function StackRow({ label, bold, levels, value }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(80px, 150px) 1fr", gap: 10, alignItems: "center", fontSize: "0.84rem" }}>
      <span style={{ fontWeight: bold ? 700 : 400 }}>{label}</span>
      <span style={{ display: "flex", height: 20, borderRadius: 4, overflow: "hidden" }}>
        {levels.map(([level, levelLabel, color]) => {
          const v = value(level);
          return (
            <span
              key={level}
              title={`${levelLabel}: ${num(v)} %`}
              style={{ width: `${v}%`, background: color, color: "#fff", fontSize: "0.72rem", display: "flex", alignItems: "center", justifyContent: "center", whiteSpace: "nowrap", overflow: "hidden" }}
            >
              {v >= 8 ? `${num(v, 0)} %` : ""}
            </span>
          );
        })}
      </span>
    </div>
  );
}

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
  const gen = data.attainment_by_age;
  const genRow = (age) => gen.rows.find((row) => row.age === age);
  return (
    <Figure
      id="titulacion"
      title={`España tiene a la vez más jóvenes con estudios superiores (${num(last("ED5-8", "ES").value, 0)} %) y más sin pasar de la ESO (${num(last("ED0-2", "ES").value, 0)} %) que la UE; le falta el escalón intermedio (${num(last("ED3_4", "ES").value, 0)} % frente a ${num(last("ED3_4", "EU27_2020").value, 0)} %)`}
      dek={`Población de 25 a 34 años por nivel de estudios, ${year}. Es el «reloj de arena» de la educación española y ayuda a leer la sobrecualificación: con tantos titulados superiores y pocos técnicos intermedios, una parte de los universitarios ocupa puestos de cualificación media (${num(overq.es)} % frente a ${num(overq.eu)} % en la UE).`}
      legend={levels.map(([id, label, color]) => ({ id, label, color }))}
      legendKind="bar"
      sources={sources}
      notes={["Encuesta de Población Activa de cada país. Los tres niveles suman 100 % (con decimales de redondeo).", "Por generación: Eurostat edat_lfse_03 por grupo de edad. Cada grupo es una generación distinta en el mismo año, no la misma persona a lo largo del tiempo; los mayores estudiaron con otro sistema educativo y con otras oportunidades.", "No hemos encontrado en Eurostat la sobrecualificación por rama de estudios, solo por sector de actividad (lfsa_eoqgan2); queda pendiente."]}
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
          <StackRow key={geo} label={NAMES[geo]} bold={geo === "ES"} levels={levels} value={(level) => last(level, geo)?.value || 0} />
        ))}
      </div>
      {gen ? (
        <>
          <h3 className="vizPanelTitle">
            Por generación, {gen.year}
            <span>
              Como mucho ESO: {num(genRow("Y25-34").ES["ED0-2"])} % de 25 a 34 años y {num(genRow("Y55-64").ES["ED0-2"])} % de 55 a 64 (UE-27:{" "}
              {num(genRow("Y25-34").EU27_2020["ED0-2"])} % y {num(genRow("Y55-64").EU27_2020["ED0-2"])} %)
            </span>
          </h3>
          <div style={{ display: "grid", gap: 8 }}>
            {gen.rows.flatMap((row) =>
              ["ES", "EU27_2020"].map((geo) => (
                <StackRow
                  key={`${row.age}-${geo}`}
                  label={`${AGE_LABEL[row.age] || row.age} · ${geo === "ES" ? "España" : "UE-27"}`}
                  bold={geo === "ES"}
                  levels={levels}
                  value={(level) => row[geo][level] || 0}
                />
              )),
            )}
          </div>
        </>
      ) : null}
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

// --------------------------------------------------------------------------------------------- families
const lastOf = (rows) => (rows?.length ? rows.at(-1) : null);

export function FamiliesFigure({ data, sources }) {
  const cap = data.capacity;
  const areas = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"];
  const shareRows = (key) =>
    areas
      .map((geo) => ({ geo, row: lastOf(cap[key][geo]) }))
      .filter((item) => item.row)
      .map((item) => ({ label: NAMES[item.geo], value: item.row.value, color: item.geo === "ES" ? C.blue : item.geo === "EU27_2020" ? C.ref : C.peer }));
  const all = shareRows("private_share_all");
  const tertiary = shareRows("private_share_tertiary");
  const es = all.find((row) => row.label === "España");
  const esTertiary = tertiary.find((row) => row.label === "España");
  const peersAll = all.filter((row) => row.label !== "España");
  const highest = peersAll.every((row) => row.value < es.value);
  const year = lastOf(cap.private_share_all.ES).year;
  const consumption = comparison(cap.household_consumption_share, areas, ["EU27_2020"]);
  const cEs = lastOf(cap.household_consumption_share.ES);
  const cEu = lastOf(cap.household_consumption_share.EU27_2020);
  const q = Object.fromEntries(cap.epf_quintiles.map((row) => [row.label, row]));
  const bands = data.distribution.epf_income_bands;
  const bandMax = Math.max(...bands.map((row) => row.per_household));
  const lowBand = bands.find((row) => row.band !== "Total");
  const highBand = [...bands].reverse().find((row) => row.band !== "Total");
  return (
    <Figure
      id="familias"
      title={`La enseñanza no es gratis para las familias: pagan el ${num(es.value, 0)} % del gasto educativo en España${highest ? ", más que en Alemania, Francia, Italia y Portugal" : ""}, y el ${num(esTertiary.value, 0)} % del universitario`}
      dek={`Los hogares dedican a educación el ${num(cEs.value)} % de su consumo (UE: ${num(cEu.value)} %, ${cEs.year}). En ${q.Total.year}, el hogar medio gastó ${fmt(q.Total.per_household, "eur")} al año en enseñanza; los hogares que ingresan ${lowBand.band.toLowerCase().replace(" euros", " €")} al mes, ${fmt(lowBand.per_household, "eur")} (el ${num(lowBand.share_of_spending, 2)} % de su gasto), y los de ${highBand.band.toLowerCase().replace(" euros", " €")}, ${fmt(highBand.per_household, "eur")} (${num(highBand.share_of_spending, 2)} %): el gasto privado en educación crece mucho más deprisa que la renta.`}
      legend={[
        { id: "ES", label: "España", color: C.blue },
        { id: "ref", label: "UE-27", color: C.ref },
        { id: "peer", label: "Alemania, Francia, Italia, Portugal", color: C.peer },
      ]}
      sources={sources}
      notes={[
        `Origen privado del gasto (${year}): sector privado no educativo —sobre todo hogares— en % del gasto total en educación, de Infantil a universidad (Eurostat UOE). Recoge lo que pagan hogares y otras entidades privadas, como matrículas y cuotas de centros privados y concertados; la estadística no separa la concertada.`,
        "Encuesta de Presupuestos Familiares (INE): tramos de ingresos mensuales netos regulares del hogar (tabla 73809) y, en la tabla de datos, quintiles de gasto total (tabla 73828); euros corrientes. El porcentaje es la parte de su gasto total que cada tramo dedica a enseñanza. El tramo de menos de 500 € no tiene dato el último año.",
        "Falta: precio de la matrícula universitaria por comunidad en % de la renta del hogar. No hemos encontrado una tabla oficial descargable por script (la nota del Ministerio está en lamoncloa.gob.es, que devolvió un error de conexión TLS a la descarga automática el 19 de octubre de 2026).",
      ]}
      table={
        <>
          <EduTable caption="Ver el origen privado del gasto en tabla" series={areas.map((geo) => ({ id: geo, label: `${NAMES[geo]} · todas las etapas`, points: cap.private_share_all[geo] || [] }))} />
          <EduTable digits={2} caption="Ver el consumo de los hogares en educación en tabla" series={[...consumption].reverse()} />
          <EduTable unit="eur" caption="Ver el gasto por hogar y quintil de gasto total en tabla (EPF)" series={cap.epf_quintiles.map((row) => ({ id: row.label, label: row.label, points: row.series }))} />
        </>
      }
    >
      <Explain
        shows="Cuánto pone cada familia de su bolsillo: qué parte del gasto en educación no paga el Estado, cuánto del consumo de los hogares va a enseñanza y cuánto gasta cada tipo de hogar."
        read="Las barras comparan España (azul) con la UE y cuatro países. En la encuesta del INE, cada quintil es un 20 % de los hogares ordenados de menos a más gasto total."
        notSay="No separa la concertada de la privada ni mide la renta de los hogares (la encuesta ordena por gasto). Tampoco dice si ese gasto compra mejores resultados."
      />
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            Gasto en educación de origen privado, {year}
            <span>% del gasto total, de Infantil a universidad</span>
          </h3>
          <Bars label="Origen privado del gasto en educación" unit="pct" digits={1} max={50} rows={all} />
          <h3 className="vizPanelTitle">
            Ídem en la universidad
            <span>% del gasto en educación superior</span>
          </h3>
          <Bars label="Origen privado del gasto universitario" unit="pct" digits={1} max={50} rows={tertiary} />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Gasto de los hogares en educación
            <span>% de su consumo final (contabilidad nacional)</span>
          </h3>
          <SparseLineChart series={consumption} unit="pct" digits={1} height={200} yMax={2} ariaLabel="Gasto de los hogares en educación en porcentaje de su consumo" />
          <h3 className="vizPanelTitle">
            Gasto en enseñanza por hogar según sus ingresos, {bands[0]?.year}
            <span>Euros al año, por ingresos mensuales netos del hogar (INE, EPF)</span>
          </h3>
          <Bars
            label="Gasto en enseñanza por hogar según ingresos"
            unit="eur"
            max={bandMax}
            rows={bands.map((row) => ({
              label: row.band === "Total" ? "Media" : row.band.replace(" euros", " €"),
              value: row.per_household,
              color: row.band === "Total" ? C.ref : C.blue,
              note: `${num(row.share_of_spending, 2)} % de su gasto`,
            }))}
          />
        </div>
      </div>
    </Figure>
  );
}

// --------------------------------------------------------------------------------------------- adults
export function AdultSkillsFigure({ data, sources }) {
  const p = data.outcomes.piaac;
  const ages = p.piaac_literacy_by_age.ESP.map((row) => row.age);
  const value = (key, area, age) => p[key][area].find((row) => row.age === age)?.value;
  const gy = data.outcomes.piaac_gap_young;
  const go = data.outcomes.piaac_gap_old;
  return (
    <Figure
      id="adultos"
      title={`Los adultos españoles sacan ${p.piaac_literacy_mean.ESP} puntos en comprensión lectora (OCDE: ${p.piaac_literacy_mean.OECD}), y la distancia es mayor entre los jóvenes de 16 a 24 años (${Math.abs(gy)} puntos) que entre los de 55 a 65 (${Math.abs(go)})`}
      dek={`PIAAC 2023 mide las competencias de la población de 16 a 65 años: el resultado acumulado del sistema, no solo de la escuela de hoy. En matemáticas, ${p.piaac_numeracy_mean.ESP} frente a ${p.piaac_numeracy_mean.OECD}. Los titulados superiores españoles sacan ${p.piaac_literacy_tertiary.ESP} en lectura frente a ${p.piaac_literacy_tertiary.OECD} de la OCDE; los que no terminaron secundaria superior, ${p.piaac_literacy_below_upper_secondary.ESP} frente a ${p.piaac_literacy_below_upper_secondary.OECD}.`}
      legend={[
        { id: "ES", label: "España", color: C.blue },
        { id: "OECD", label: "Media OCDE", color: C.ref },
        { id: "EU", label: "Media UE", color: C.peer },
      ]}
      legendKind="bar"
      sources={sources}
      notes={[
        "Valores del Cuadro 2.1 y del capítulo 2 del informe español de PIAAC 2023 (INEE), con cita literal. La escala va de 0 a 500. Cada grupo de edad es una generación distinta, no la misma persona a lo largo del tiempo.",
        "Que los jóvenes saquen más que los mayores refleja sobre todo cuántos años estudió cada generación; que la distancia con la OCDE sea mayor entre los jóvenes indica que la mejora española no ha cerrado la brecha.",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Edad</th>
                  <th scope="col">Lectura España</th>
                  <th scope="col">Lectura OCDE</th>
                  <th scope="col">Lectura UE</th>
                  <th scope="col">Matemáticas España</th>
                  <th scope="col">Matemáticas OCDE</th>
                  <th scope="col">Matemáticas UE</th>
                </tr>
              </thead>
              <tbody>
                {ages.map((age) => (
                  <tr key={age}>
                    <td>{age}</td>
                    {["piaac_literacy_by_age", "piaac_numeracy_by_age"].flatMap((key) => ["ESP", "OECD", "EU"].map((area) => <td key={`${key}-${area}`}>{value(key, area, age)}</td>))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <Explain
        shows="Qué saben hacer los adultos con un texto y con números, por edad, en España frente a la media de la OCDE y la UE."
        read="Cada grupo de barras es una generación. Si la barra azul se acercara a la gris oscura en los más jóvenes, la escuela reciente estaría cerrando la brecha; ocurre lo contrario."
        notSay="No separa lo que aprendieron en la escuela de lo que aprendieron después (trabajo, formación) ni el efecto de la inmigración adulta."
      />
      <div className="vizMultiples">
        {[
          ["piaac_literacy_by_age", "Comprensión lectora"],
          ["piaac_numeracy_by_age", "Matemáticas"],
        ].map(([key, label]) => (
          <div key={key}>
            <h3 className="vizPanelTitle">
              {label} por edad
              <span>Puntos PIAAC 2023 (eje 0-300)</span>
            </h3>
            <div style={{ display: "grid", gap: 6 }}>
              {ages.map((age) => (
                <div key={age} style={{ display: "grid", gridTemplateColumns: "56px 1fr", gap: 8, alignItems: "center", fontSize: "0.82rem" }}>
                  <span>{age}</span>
                  <span style={{ display: "grid", gap: 2 }}>
                    {[
                      ["ESP", C.blue],
                      ["OECD", C.ref],
                      ["EU", C.peer],
                    ].map(([area, color]) => (
                      <span key={area} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ height: 8, width: `${(value(key, area, age) / 300) * 85}%`, background: color, borderRadius: "0 3px 3px 0" }} />
                        <span style={{ fontSize: "0.74rem" }}>{value(key, area, age)}</span>
                      </span>
                    ))}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Figure>
  );
}

// --------------------------------------------------------------------------------------------- labour return
export function LabourReturnFigure({ data, sources }) {
  const o = data.outcomes;
  const areas = ["ES", "EU27_2020", "DE", "FR", "IT", "PT"];
  const empLast = (level, geo) => lastOf(o.employment[level][geo]);
  const premium = (area) => lastOf(o.earnings.ISCED11A_5T8[area]);
  const penalty = (area) => lastOf(o.earnings.ISCED11A_0T2[area]);
  const earnAreas = ["ESP", "OECD", "EU25", "DEU", "FRA", "ITA", "PRT"].filter((area) => premium(area));
  const neet = comparison(o.neet, areas, ["EU27_2020"]);
  const neetEs = lastOf(o.neet.ES);
  const neetEu = lastOf(o.neet.EU27_2020);
  const levels = [
    ["ED0-2", "Como mucho ESO"],
    ["ED3_4", "Bachillerato o FP media"],
    ["ED5-8", "Estudios superiores"],
  ];
  const year = empLast("ED5-8", "ES").year;
  return (
    <Figure
      id="rendimiento-laboral"
      title={`Estudiar sigue compensando: un titulado superior cobra un ${premium("ESP").value - 100} % más que uno de Bachillerato o FP (OCDE: ${premium("OECD").value - 100} %) y trabaja el ${num(empLast("ED5-8", "ES").value, 0)} % frente al ${num(empLast("ED0-2", "ES").value, 0)} % de quien no pasó de la ESO`}
      dek={`Pero el escalón intermedio rinde menos que en Europa: con Bachillerato o FP trabaja el ${num(empLast("ED3_4", "ES").value)} % de los adultos de 25 a 64 años, frente al ${num(empLast("ED3_4", "EU27_2020").value)} % de la UE (${year}). Quien no terminó secundaria superior cobra el ${penalty("ESP").value} % de lo que cobra quien sí la tiene (OCDE: ${penalty("OECD").value} %). Los jóvenes de 15 a 29 años que ni estudian ni trabajan son el ${num(neetEs.value)} % (UE: ${num(neetEu.value)} %).`}
      legend={[
        { id: "ES", label: "España", color: C.blue },
        { id: "ref", label: "UE-27 / media OCDE", color: C.ref },
        { id: "peer", label: "Alemania, Francia, Italia, Portugal", color: C.peer },
      ]}
      sources={sources}
      notes={[
        "Ingresos relativos: trabajadores a tiempo completo de 25 a 64 años, secundaria superior = 100 (OCDE, Education at a Glance, vía DBnomics). Último año disponible por país.",
        "Tasa de empleo: ocupados de 25 a 64 años en % de su grupo de estudios (Eurostat lfsa_ergaed). Ninis: Eurostat edat_lfse_20.",
      ]}
      table={
        <>
          <EduTable caption="Ver el empleo por nivel de estudios en tabla" series={levels.flatMap(([level, label]) => ["ES", "EU27_2020"].map((geo) => ({ id: `${level}-${geo}`, label: `${label} · ${NAMES[geo]}`, points: o.employment[level][geo] || [] })))} />
          <EduTable unit="score" caption="Ver los ingresos relativos en tabla" series={earnAreas.flatMap((area) => [["ISCED11A_5T8", "superiores"], ["ISCED11A_0T2", "como mucho ESO"]].map(([level, label]) => ({ id: `${area}-${level}`, label: `${NAMES[area]} · ${label}`, points: o.earnings[level][area] || [] })))} />
          <EduTable caption="Ver los ninis en tabla" series={[...neet].reverse()} />
        </>
      }
    >
      <Explain
        shows="Lo que da cada nivel de estudios en el mercado de trabajo (empleo y sueldo) y cuántos jóvenes se quedan fuera de estudios y empleo."
        read="Ingresos: 100 es lo que cobra quien tiene Bachillerato o FP media; 150 significa un 50 % más. Empleo: porcentaje de cada grupo que trabaja."
        notSay="Las diferencias no son solo efecto del título: quien estudia más suele venir de familias con más recursos. Y una media nacional mezcla carreras con salidas muy distintas."
      />
      <div className="vizMultiples">
        <div>
          <h3 className="vizPanelTitle">
            Tasa de empleo por nivel de estudios, {year}
            <span>% de 25 a 64 años</span>
          </h3>
          <Bars
            label="Tasa de empleo por nivel de estudios"
            unit="pct"
            digits={1}
            max={100}
            rows={levels.flatMap(([level, label]) => [
              { label: `${label} · España`, value: empLast(level, "ES").value, color: C.blue },
              { label: `${label} · UE-27`, value: empLast(level, "EU27_2020").value, color: C.ref },
            ])}
          />
        </div>
        <div>
          <h3 className="vizPanelTitle">
            Ingresos de los titulados superiores
            <span>Secundaria superior = 100; a tiempo completo, 25-64 años</span>
          </h3>
          <Bars
            label="Ingresos relativos de los titulados superiores"
            unit="score"
            max={200}
            rows={earnAreas.map((area) => ({
              label: NAMES[area],
              value: premium(area).value,
              color: area === "ESP" ? C.blue : ["OECD", "EU25"].includes(area) ? C.ref : C.peer,
              note: `(${premium(area).year})`,
            }))}
          />
          <h3 className="vizPanelTitle">
            Jóvenes de 15 a 29 años que ni estudian ni trabajan (%)
            <span>Eurostat, edat_lfse_20</span>
          </h3>
          <TimeSeriesChart series={neet} height={200} endLabels={false} ariaLabel="Ninis de 15 a 29 años" />
        </div>
      </div>
    </Figure>
  );
}
