import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure from "../components/Figure";
import SparseLineChart from "./SparseLineChart";
import EduTable from "./EduTable";
import { StoryFigure } from "./StoryScatter";
import { fmt } from "./formatEdu.mjs";
import { AdultSkillsFigure, AttainmentFigure, C, EquityFigure, Explain, FamiliesFigure, Glossary, LabourReturnFigure, NAMES, RegionsFigure, TeachersFigure, VocationalFigure, num } from "./sections";

export const metadata = {
  title: "Gasto, resultados y abandono: la educación en España | Vota Con La Chola",
  description:
    "Gasto público real por alumno, PISA, abandono escolar, repetición, sobrecualificación y un siglo de alfabetización en España, frente a la OCDE, la UE y países similares, con fuentes oficiales y datos descargables.",
};

function retrieved(source) {
  return source?.retrieved_at ? ` (consultado ${String(source.retrieved_at).slice(0, 10)})` : "";
}

// Spain first and emphasised, the reference average in dark gray, peers in light gray.
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

export default function EducacionPage() {
  const data = readPublicJson("visualizaciones/data/educacion.json", null);
  if (!data) throw new Error("Missing visualizaciones/data/educacion.json");
  const h = data.headline;
  const src = data.sources;
  const downloads = "/visualizaciones/data/educacion.csv";
  const S = {
    oecd: { label: `OCDE, Education at a Glance (réplica DBnomics)${retrieved(src.oecd_eag_finance)}`, href: src.oecd_eag_finance.page },
    mefp: { label: `Ministerio de Educación, Estadística del Gasto Público en Educación y de Alumnado${retrieved(src.mefp_educabase)}`, href: src.mefp_educabase.page },
    eurostat: (dataset) => ({
      label: `Eurostat, ${dataset}${retrieved(src.eurostat_sdmx)}`,
      href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table`,
    }),
    wb: { label: `Banco Mundial, EdStats (PISA 2000-2018)${retrieved(src.worldbank_edstats)}`, href: src.worldbank_edstats.page },
    pisa2022: { label: "INEE, PISA 2022. Informe español (2023)", href: src.vclc_education_curated.documents.inee_pisa2022_informe_espanol.landing_page },
    pisaReports: { label: "INEE, informes españoles de PISA 2003-2018", href: "https://www.educacionfpydeportes.gob.es/inee/evaluaciones-internacionales/pisa.html" },
    pisaNote: { label: "OCDE, PISA 2022, nota de país: España (copia del INEE)", href: src.vclc_education_curated.documents.oecd_pisa2022_country_note_es.url },
    oecdSal: { label: `OCDE, Education at a Glance, salarios del profesorado (réplica DBnomics)${retrieved(src.oecd_eag_finance)}`, href: "https://db.nomics.world/OECD/DSD_EAG_SAL_TREND@DF_TCH_STA" },
    mefpEpa: { label: `Ministerio de Educación, explotación de la EPA (abandono por estudios de la madre)${retrieved(src.mefp_educabase)}`, href: "https://www.educacionfpydeportes.gob.es/servicios-al-ciudadano/estadisticas/laborales/epa.html" },
    epf: { label: `INE, Encuesta de Presupuestos Familiares${retrieved(src.ine_epf)}`, href: "https://www.ine.es/jaxiT3/Tabla.htm?t=73828" },
    piaac: { label: "INEE, PIAAC 2023. Informe español (2024)", href: src.vclc_education_curated.documents.inee_piaac2023_informe_espanol.landing_page },
    oecdEarn: { label: `OCDE, Education at a Glance, ingresos por nivel de estudios (réplica DBnomics)${retrieved(src.oecd_eag_finance)}`, href: "https://db.nomics.world/OECD/DSD_EAG_LSO_EA@DF_LSO_EARN_REL_UPPER" },
    owid: { label: `Our World in Data${retrieved(src.owid_grapher)}`, href: src.owid_grapher.page },
  };

  // 1. Spending ----------------------------------------------------------------------------------
  const sp = data.spending;
  const realPerStudent = [
    {
      id: "real",
      label: `Gasto público por alumno no universitario (euros de ${h.real_per_student_base_year})`,
      shortLabel: String(h.real_per_student_last.year),
      color: C.blue,
      points: sp.real_per_nonuni_student_eur,
    },
  ];
  const eagSpain = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: sp.eag_school_usd_ppp_2020.ESP },
    { id: "OECD", label: "Media OCDE", color: C.ref, points: sp.eag_school_usd_ppp_2020.OECD },
  ];
  const eagMax = Math.max(...Object.values(sp.eag_school_usd_ppp_2020).flat().map((p) => p.value));
  const eagPanels = ["OECD", "EU25", "DEU", "FRA", "ITA", "PRT"];
  const cofog = comparison(sp.cofog_pct_gdp, ["ES", "EU27_2020", "DE", "FR", "IT", "PT"], ["EU27_2020"]);
  const pps = comparison(sp.pps_per_student, ["ES", "EU27_2020", "DE", "FR", "IT", "PT"], ["EU27_2020"]);
  const cofogLast = sp.cofog_pct_gdp.ES.at(-1);
  const cofogEuLast = sp.cofog_pct_gdp.EU27_2020.at(-1);
  const realChange = (h.real_per_student_last.value / h.real_per_student_2000.value - 1) * 100;

  // 2. PISA --------------------------------------------------------------------------------------
  const pisaDomains = [
    { key: "math", label: "Matemáticas", first: data.pisa.first_comparable.math },
    { key: "reading", label: "Lectura", first: data.pisa.first_comparable.reading },
    { key: "science", label: "Ciencias", first: data.pisa.first_comparable.science },
  ];
  const pisaSeries = (domain) =>
    ["PRT", "ITA", "FRA", "DEU", "OECD", "ESP"]
      .filter((area) => data.pisa[domain][area]?.length)
      .map((area) => ({
        id: area,
        label: NAMES[area],
        color: area === "ESP" ? C.blue : area === "OECD" ? C.ref : C.peer,
        emphasis: area === "ESP",
        noEndLabel: !["ESP", "OECD"].includes(area),
        points: data.pisa[domain][area].map((p) => ({ ...p, hollow: !p.comparable })),
      }));
  const mathDrops = ["ESP", "DEU", "FRA", "ITA", "PRT"].map((area) => {
    const rows = Object.fromEntries(data.pisa.math[area].map((p) => [p.year, p.value]));
    return { area, from: rows[2003], to: rows[2022], delta: rows[2022] - rows[2003] };
  });
  const esMath = mathDrops.find((row) => row.area === "ESP");
  const biggerDrops = mathDrops.filter((row) => row.area !== "ESP" && row.delta < esMath.delta).map((row) => NAMES[row.area]);
  const pisaTable = pisaDomains.flatMap((domain) =>
    ["ESP", "OECD", "DEU", "FRA", "ITA", "PRT"].map((area) => ({
      id: `${domain.key}-${area}`,
      label: `${domain.label} · ${NAMES[area]}`,
      points: data.pisa[domain.key][area].map((p) => ({ ...p, hollow: !p.comparable })),
    })),
  );

  // 3. Early leavers -----------------------------------------------------------------------------
  const el = data.early_leavers;
  const leavers = comparison(el.series, ["ES", "EU27_2020", "DE", "FR", "IT", "PT"], ["EU27_2020"]);
  // Breaks less than four years apart share one short label at the first year («b» is Eurostat's break flag); every
  // break keeps its own vertical line, so close breaks never stack overlapping labels.
  const breakRows = (years) => {
    const clusters = [];
    for (const year of years) {
      const last = clusters.at(-1);
      if (last && year - last.at(-1) < 4) last.push(year);
      else clusters.push([year]);
    }
    return clusters.flatMap((cluster) =>
      cluster.map((year, index) => ({
        year,
        row: 0,
        label: index ? "" : `b ${cluster.map((y, i) => (i ? String(y).slice(2) : y)).join("·")}`,
      })),
    );
  };
  const breakNotes = breakRows(el.breaks.filter((year) => year >= 2002));
  const regionMax = Math.max(...el.regions.map((row) => row.first || row.last));
  const motherLevels = [
    ["E. Primaria e inferior", "Madre con Primaria o menos", C.orange],
    ["1ª etapa E. Secundaria", "Madre con ESO o equivalente", C.yellow],
    ["2ª etapa E. Secundaria", "Madre con Bachillerato o FP", C.aqua],
    ["E. Superior", "Madre con estudios superiores", C.blue],
  ];
  const mother = data.distribution.leavers_by_mother;
  const motherSeries = motherLevels.filter(([key]) => mother[key]).map(([key, label, color]) => ({ id: key, label, color, points: mother[key] }));
  const motherYear = mother["E. Superior"]?.at(-1)?.year;
  const motherLast = (key) => num(mother[key]?.at(-1)?.value ?? 0);

  // 4. Repetition ----------------------------------------------------------------------------------
  const behind = [
    {
      id: "behind",
      label: "Alumnado de 15 años que no está en 4.º de ESO (retrasado al menos un curso)",
      shortLabel: "España",
      color: C.blue,
      points: data.repetition.behind_at_15,
    },
  ];
  const rep = data.repetition.pisa_2022;
  const repSeries = data.repetition.pisa_series;

  // 5. Over-qualification -------------------------------------------------------------------------
  const overq = comparison(data.overqualification, ["ES", "EU27_2020", "DE", "FR", "IT", "PT"], ["EU27_2020"]);

  // 6. Long run ------------------------------------------------------------------------------------
  const literacy = ["DEU", "FRA", "ITA", "PRT", "ESP"]
    .filter((area) => data.long_run.literacy[area]?.length)
    .map((area) => {
      let broke = false;
      return {
        id: area,
        label: NAMES[area],
        color: area === "ESP" ? C.blue : C.peer,
        emphasis: area === "ESP",
        points: data.long_run.literacy[area].map((p) => {
          // UNESCO census compilations end in 1950; later values come from the UNESCO Institute for Statistics (15+).
          const breakBefore = !broke && p.year > 1960;
          if (breakBefore) broke = true;
          return { ...p, breakBefore };
        }),
      };
    });
  const schooling = ["DEU", "FRA", "ITA", "PRT", "ESP"].map((area) => ({
    id: area,
    label: NAMES[area],
    color: area === "ESP" ? C.blue : C.peer,
    emphasis: area === "ESP",
    points: data.long_run.schooling[area].filter((p) => p.year >= 1870),
  }));

  const sch = (area, year) => data.long_run.schooling[area].find((p) => p.year === year)?.value;
  const behindIn1900 = ["FRA", "ITA", "PRT"].filter((area) => sch(area, 1900) < sch("ESP", 1900)).map((area) => NAMES[area]);
  const aheadIn1950 = ["DEU", "FRA", "ITA"].filter((area) => sch(area, 1950) > sch("ESP", 1950)).map((area) => NAMES[area]);
  const list = (items) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} y ${items.at(-1)}` : items[0] || "");
  const mathRisers = mathDrops.filter((row) => row.delta > 0).map((row) => NAMES[row.area]);
  const firstChange = (domain, area) => data.base_year.pisa[domain][area]?.[0]?.change;
  const baseRows = ["math", "reading", "science"].flatMap((domain) =>
    data.base_year.pisa[domain].ESP.map((row) => ({
      domain,
      from: row.from,
      es: row.change,
      oecd: data.base_year.pisa[domain].OECD.find((o) => o.from === row.from)?.change,
    })),
  );
  const domainName = { math: "Matemáticas", reading: "Lectura", science: "Ciencias" };
  const regionScores = data.regions_pisa.rows.filter((row) => row.math != null).map((row) => row.math);
  const regionSpread = Math.max(...regionScores) - Math.min(...regionScores);
  const attain = (level) => data.attainment_25_34[level].ES.at(-1).value;

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="Educación en España: más gasto, resultados estancados y mucho menos abandono"
        summary="Cuánto gasta el Estado por alumno y en qué, qué dicen PISA, las comunidades y el origen social, cómo han cambiado el abandono y la repetición, qué pasa con la FP y los titulados, y el siglo que llevó a casi toda la población a leer. Cada gráfico explica qué muestra y qué no, enlaza su fuente oficial, compara con la OCDE, la UE y países similares, y trae sus datos en tabla."
        actions={[
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/educacion.json", label: "JSON con procedencia" },
          { href: "#dato-relato", label: "Todo en una imagen" },
          { href: "#conclusion", label: "Conclusión" },
          { href: "#glosario", label: "Glosario" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Gasto público real por alumno (Primaria a Bachillerato y FP, OCDE)</span>
          <span className="vizStat__value">+{num(h.spending_school_change_2000_pct, 0)} %</span>
          <span className="vizStat__note">
            {fmt(h.spending_school_2000, "usd")} en 2000 → {fmt(h.spending_school_last, "usd")} en {h.spending_school_last_year} (dólares PPA de 2020);
            máximo en {h.spending_school_peak.year}
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">PISA matemáticas</span>
          <span className="vizStat__value">{h.math_2022}</span>
          <span className="vizStat__note">
            {h.math_2003} en 2003; media OCDE en 2022: {data.pisa.math.OECD.at(-1).value}
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Abandono temprano (18-24 años)</span>
          <span className="vizStat__value">{num(h.leavers_last)} %</span>
          <span className="vizStat__note">
            {num(h.leavers_2008)} % en 2008; UE-27: {num(h.leavers_eu_last)} % en {h.leavers_last_year}
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Titulados superiores en empleos que no lo requieren</span>
          <span className="vizStat__value">{num(h.overq_es)} %</span>
          <span className="vizStat__note">
            UE-27: {num(h.overq_eu)} % ({h.overq_year})
          </span>
        </div>
      </section>

      <section className="card vizProse" id="esencial" aria-labelledby="esencial-title">
        <h2 id="esencial-title">Lo esencial</h2>
        <ol>
          <li>
            <strong>Más gasto, pero no desde 2009.</strong> El gasto público real por alumno es un {num(h.spending_school_change_2000_pct, 0)} % mayor que en
            2000, pero alcanzó su máximo en {h.spending_school_peak.year}, cayó un{" "}
            {num((1 - h.spending_school_trough.value / h.spending_school_peak.value) * 100, 0)} % hasta {h.spending_school_trough.year} y España gasta hoy
            el {h.spending_school_vs_oecd_pct} % de la media OCDE por alumno. <a href="#gasto">Ver gasto</a>
          </li>
          <li>
            <strong>Resultados estancados, como en casi toda la OCDE.</strong> PISA matemáticas: {h.math_2003} en 2003 y {h.math_2022} en 2022; la media
            OCDE cayó más, de {h.oecd_math_2003} a {data.pisa.math.OECD.at(-1).value}. <a href="#pisa">Ver PISA</a>
          </li>
          <li>
            <strong>Mucho menos abandono y repetición.</strong> El abandono temprano bajó del {num(h.leavers_2000)} % de 2000 (y del{" "}
            {num(h.leavers_2008)} % del pico de 2008) al {num(h.leavers_last)} % y el
            alumnado de 15 años retrasado de curso, del {num(h.behind_peak.value)} % al {num(h.behind_last.value)} %. <a href="#abandono">Ver abandono</a>
          </li>
          <li>
            <strong>Las diferencias están dentro.</strong> Entre comunidades hay {regionSpread} puntos de PISA, más que entre España y los países
            comparados, y apenas se relacionan con lo que gasta cada una (correlación {num(data.regions_pisa.pearson, 2)}). <a href="#regiones">Ver comunidades</a>
          </li>
          <li>
            <strong>Un reloj de arena.</strong> El {num(attain("ED5-8"), 0)} % de los jóvenes de 25 a 34 años tiene estudios superiores y el{" "}
            {num(attain("ED0-2"), 0)} % no pasó de la ESO; faltan técnicos intermedios y sobran universitarios en puestos que no lo piden (
            {num(h.overq_es)} %). <a href="#titulacion">Ver titulación</a>
          </li>
          <li>
            <strong>Ni gratis ni solo escuela.</strong> Las familias pagan el {num(data.capacity.private_share_all.ES.at(-1).value, 0)} % del gasto educativo,
            más que en los países comparados, y los adultos sacan {data.outcomes.piaac.piaac_literacy_mean.ESP} en PIAAC frente a{" "}
            {data.outcomes.piaac.piaac_literacy_mean.OECD} de la OCDE, con más distancia entre los jóvenes ({Math.abs(data.outcomes.piaac_gap_young)} puntos) que entre los
            mayores ({Math.abs(data.outcomes.piaac_gap_old)}). <a href="#familias">Ver familias</a> · <a href="#adultos">Ver adultos</a>
          </li>
        </ol>
      </section>

      <StoryFigure
        story={data.story}
        sources={[S.oecd, S.wb, S.pisaReports, S.pisa2022, S.mefp, S.piaac, S.eurostat("educ_uoe_fine01")]}
        h={{
          compositionPoints: data.equity.composition.effect_raw_points,
          compositionDrop: Math.abs(data.equity.composition.math_change_2012_2022),
          familyShare: data.capacity.private_share_all.ES.at(-1).value,
          piaacYoung: data.outcomes.piaac.piaac_literacy_by_age.ESP.find((row) => row.age === "16-24").value,
          piaacOld: data.outcomes.piaac.piaac_literacy_by_age.ESP.find((row) => row.age === "55-65").value,
          gapYoung: data.outcomes.piaac_gap_young,
          gapOld: data.outcomes.piaac_gap_old,
        }}
      />

      <Figure
        id="gasto"
        title={`El gasto público real por alumno es un ${num(h.spending_school_change_2000_pct, 0)} % mayor que en 2000, pero todo el aumento llegó antes de ${h.spending_school_peak.year}`}
        dek={`OCDE: ${fmt(h.spending_school_peak.value, "usd")} por alumno en ${h.spending_school_peak.year}, ${fmt(h.spending_school_trough.value, "usd")} en ${h.spending_school_trough.year} tras los recortes y ${fmt(h.spending_school_last, "usd")} en ${h.spending_school_last_year} (dólares PPA constantes de 2020). La serie anual del Ministerio, hasta ${h.real_per_student_last.year}, muestra el mismo perfil y recupera el máximo de ${h.real_per_student_peak.year} solo en ${h.real_per_student_last.year}.`}
        legend={eagSpain}
        sources={[S.oecd, S.mefp, S.eurostat("nama_10_gdp")]}
        notes={[
          "OCDE: gasto con origen público en centros educativos, de Primaria a postsecundaria no terciaria (las etapas que mide PISA), por alumno equivalente a tiempo completo; precios constantes (deflactor del PIB) y PPA de 2020. La OCDE publica años sueltos antes de 2008 y la serie pasó de la clasificación ISCED 1997 a ISCED 2011 en 2012; la OCDE la presenta como continua.",
          `Ministerio: ${sp.formula_real_per_student}. Incluye Infantil, FP y Educación Especial; excluye becas y universidad.`,
        ]}
        table={
          <EduTable
            unit="usd"
            series={[
              ...eagSpain.map((s) => ({ ...s, label: `${s.label} (OCDE, $ PPA 2020)` })),
              { id: "real", label: `España, Ministerio (€ de ${h.real_per_student_base_year})`, points: sp.real_per_nonuni_student_eur },
            ]}
          />
        }
      >
        <Explain
          shows="Cuánto gastan las administraciones por cada alumno de colegio e instituto, descontada la inflación, con dos fuentes: la OCDE (comparable entre países, con años sueltos antes de 2008) y el Ministerio (cada año, hasta 2024)."
          read="Si la línea sube, cada alumno recibe más recursos reales. Lo decisivo es la forma: sube hasta 2009, cae con los recortes hasta 2014 y tarda una década en recuperarse."
          notSay="No dice en qué se gasta (profesorado, edificios, becas) ni si se gasta bien, y no incluye lo que pagan las familias."
        />
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              OCDE · dólares PPA constantes de 2020 por alumno
              <span>
                España: {fmt(h.spending_school_2000, "usd")} (2000) → {fmt(h.spending_school_last, "usd")} ({h.spending_school_last_year})
              </span>
            </h3>
            <SparseLineChart series={eagSpain} unit="usd" yMax={eagMax} height={260} xMin={1995} ariaLabel="Gasto público real por alumno, España y media OCDE" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Ministerio · euros de {h.real_per_student_base_year} por alumno no universitario
              <span>
                {fmt(h.real_per_student_2000.value, "eur")} (2000) → {fmt(h.real_per_student_last.value, "eur")} ({h.real_per_student_last.year})
              </span>
            </h3>
            <TimeSeriesChart
              series={realPerStudent}
              unit="eur"
              height={260}
              bands={[{ from: 2010, to: 2014, label: "Recortes" }]}
              ariaLabel="Gasto público real por alumno no universitario según el Ministerio"
            />
          </div>
        </div>
      </Figure>

      <Figure
        id="gasto-comparado"
        title={`España gasta por alumno el ${h.spending_school_vs_oecd_pct} % de la media OCDE; en 2005 gastaba el ${h.spending_school_vs_oecd_2005_pct} %`}
        dek={`Con Eurostat, en ${h.pps_last_year} el gasto público por alumno fue de ${fmt(h.pps_es, "count")} PPS en España frente a ${fmt(h.pps_eu, "count")} en la UE-27 (${num((h.pps_es / h.pps_eu) * 100, 0)} %). En proporción a la economía, las administraciones gastaron en educación el ${num(cofogLast.value)} % del PIB en ${cofogLast.year}, frente al ${num(cofogEuLast.value)} % de la UE.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "ref", label: "Media de comparación", color: C.ref },
          { id: "peer", label: "Alemania, Francia, Italia, Portugal", color: C.peer },
        ]}
        sources={[S.oecd, S.eurostat("educ_uoe_fine09"), S.eurostat("gov_10a_exp")]}
        notes={[
          "Los paneles de la OCDE comparten escala. PPS: estándar de poder adquisitivo de Eurostat (euros corregidos por precios relativos), de Infantil 2.º ciclo a universidad. % del PIB: clasificación COFOG 09 de contabilidad nacional, que incluye también gasto no imputable a alumnos.",
        ]}
        table={
          <>
            <EduTable unit="usd" caption="Ver gasto por alumno de la OCDE en tabla" series={comparison(sp.eag_school_usd_ppp_2020, ["ESP", ...eagPanels], ["OECD", "EU25"]).reverse()} />
            <EduTable unit="count" digits={0} caption="Ver gasto por alumno en PPS (Eurostat) en tabla" series={[...pps].reverse()} />
            <EduTable caption="Ver gasto en educación en % del PIB en tabla" series={[...cofog].reverse()} />
          </>
        }
      >
        <Explain
          shows="El mismo gasto por alumno para España y para cada país o media de comparación, en la misma escala, y el esfuerzo total en % del PIB."
          read="Cada panel enfrenta España (azul) con una referencia (gris oscuro). Si la azul queda por debajo, España gasta menos por alumno, ya corregido por precios."
          notSay="Gastar menos no es necesariamente peor: depende de los salarios, del número de alumnos por clase y de la riqueza de cada país."
        />
        <div className="vizMultiples">
          {eagPanels.map((area) => (
            <div key={area}>
              <h3 className="vizPanelTitle">
                España frente a {NAMES[area]}
                <span>
                  {NAMES[area]} en {sp.eag_school_usd_ppp_2020[area].at(-1).year}: {fmt(sp.eag_school_usd_ppp_2020[area].at(-1).value, "usd")}
                </span>
              </h3>
              <SparseLineChart
                series={[
                  { id: area, label: NAMES[area], shortLabel: area === "EU25" ? "UE" : NAMES[area], color: C.ref, points: sp.eag_school_usd_ppp_2020[area] },
                  { id: "ESP", label: "España", color: C.blue, emphasis: true, points: sp.eag_school_usd_ppp_2020.ESP },
                ]}
                unit="usd"
                xMin={1995}
                xMax={h.spending_school_last_year}
                yMax={eagMax}
                height={200}
                ariaLabel={`Gasto real por alumno, España frente a ${NAMES[area]}`}
              />
            </div>
          ))}
          <div>
            <h3 className="vizPanelTitle">
              Gasto público por alumno, PPS (Eurostat)
              <span>Infantil 2.º ciclo a universidad</span>
            </h3>
            <TimeSeriesChart series={pps} unit="count" height={220} ariaLabel="Gasto público por alumno en PPS, España y UE" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Gasto de las administraciones en educación, % del PIB
              <span>COFOG 09 (Eurostat)</span>
            </h3>
            <TimeSeriesChart series={cofog} height={220} ariaLabel="Gasto público en educación en porcentaje del PIB" />
          </div>
        </div>
      </Figure>

      <FamiliesFigure data={data} sources={[S.eurostat("educ_uoe_fine01"), S.eurostat("nama_10_co3_p3"), S.epf]} />
      <TeachersFigure data={data} sources={[S.oecdSal, S.eurostat("educ_uoe_perp04")]} />

      <Figure
        id="pisa"
        title={`Desde su primer año comparable, España pierde ${Math.abs(firstChange("math", "ESP"))} puntos en matemáticas (2003), ${Math.abs(firstChange("reading", "ESP"))} en lectura (2000) y ${Math.abs(firstChange("science", "ESP"))} en ciencias (2006); la media OCDE pierde ${Math.abs(firstChange("math", "OECD"))} en matemáticas y ${Math.abs(firstChange("science", "OECD"))} en ciencias`}
        dek={`La media OCDE de matemáticas bajó de ${h.oecd_math_2003} a ${data.pisa.math.OECD.at(-1).value} en el mismo periodo. ${mathRisers.length ? `${list(mathRisers)}, que partían por debajo, subieron y hoy están a la par. ` : ""}En 2022 España obtuvo ${h.math_2022} en matemáticas (media OCDE ${data.pisa.math.OECD.at(-1).value}), ${h.reading_2022} en lectura (${data.pisa.reading.OECD.at(-1).value}) y ${h.science_2022} en ciencias (${data.pisa.science.OECD.at(-1).value}): en las tres, sin diferencia significativa con la media. El eje empieza en cero; las caídas son de pocas decenas de puntos en una escala centrada en 500.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "OECD", label: "Media OCDE publicada en cada ciclo", color: C.ref },
          { id: "peer", label: "Alemania, Francia, Italia, Portugal", color: C.peer },
        ]}
        sources={[S.wb, S.pisaReports, S.pisa2022]}
        notes={[
          "Puntos huecos: ciclos no comparables con los siguientes. La OCDE solo considera comparables las tendencias de lectura desde 2000, matemáticas desde 2003 y ciencias desde 2006.",
          "2022: primer ciclo tras la COVID-19 (cierres de centros en 2020) y aplazado un año; la OCDE advierte de que parte de la caída general puede deberse a la pandemia. España no tiene dato de lectura en 2018: la OCDE no lo publicó por respuestas anómalas.",
          "Media OCDE: la de cada ciclo según los informes españoles del INEE (2003-2015 y 2022) y el Banco Mundial (2018), con cita literal de documento y página. Cambia de países: 30 miembros en 2003, 34 en 2012, 37 en 2022, así que difiere unos puntos de la media de tendencia de la OCDE (solo países presentes en todos los ciclos).",
          "Sin dato con fuente verificable: media OCDE de 2000, de 2009 y de matemáticas en 2006 (en los informes solo aparecen en gráficos), y lectura y ciencias de 2022 de Alemania, Francia, Italia y Portugal. oecd.org bloquea la descarga por script.",
        ]}
        table={
          <>
            <details className="vizTable" open>
              <summary>El mismo cambio desde cada año de partida (hasta 2022)</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Materia</th>
                      <th scope="col">Desde</th>
                      <th scope="col">España</th>
                      <th scope="col">Media OCDE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {baseRows.map((row) => (
                      <tr key={`${row.domain}-${row.from}`}>
                        <td>{domainName[row.domain]}</td>
                        <td>{row.from}</td>
                        <td>{row.es > 0 ? `+${row.es}` : row.es}</td>
                        <td>{row.oecd == null ? "—" : row.oecd > 0 ? `+${row.oecd}` : row.oecd}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
            <EduTable unit="score" caption="Ver todas las puntuaciones en tabla" series={pisaTable} />
          </>
        }
      >
        <Explain
          shows="Puntuación media de los alumnos de 15 años en cada ciclo de PISA, por materia, frente a la media OCDE y a cuatro países parecidos."
          read="El eje empieza en cero, por eso las líneas parecen planas: las diferencias son de pocas decenas de puntos sobre una media de 500 (ver «qué son 10 puntos» en el glosario). Los puntos huecos no son comparables con los siguientes."
          notSay="PISA no sigue a los mismos alumnos: cada ciclo es una muestra nueva. Tampoco mide todo lo que enseña la escuela."
        />
        <div className="vizMultiples">
          {pisaDomains.map((domain) => {
            const es = data.pisa[domain.key].ESP;
            return (
              <div key={domain.key}>
                <h3 className="vizPanelTitle">
                  {domain.label}
                  <span>
                    España: {es.find((p) => p.year === domain.first)?.value} ({domain.first}) → {es.at(-1).value} ({es.at(-1).year})
                  </span>
                </h3>
                <SparseLineChart
                  series={pisaSeries(domain.key)}
                  unit="score"
                  xMin={2000}
                  xMax={2022}
                  yMax={600}
                  height={240}
                  ariaLabel={`PISA ${domain.label}, España, media OCDE y países comparables`}
                />
              </div>
            );
          })}
        </div>
      </Figure>

      <RegionsFigure data={data} sources={[S.pisa2022, S.mefp]} />
      <EquityFigure data={data} sources={[S.pisaNote, S.pisaReports]} />

      <Figure
        id="abandono"
        title={`El abandono escolar temprano bajó del ${num(h.leavers_first.value)} % en ${h.leavers_first.year} y del ${num(h.leavers_2000)} % en 2000 al ${num(h.leavers_last)} % en ${h.leavers_last_year}; el máximo reciente fue el ${num(h.leavers_2008)} % de 2008`}
        dek={`Jóvenes de 18 a 24 años que como mucho terminaron la ESO y no siguen estudiando. La distancia con la UE-27 pasó de ${num(h.leavers_2008 - h.leavers_eu_2008)} puntos a ${num(h.leavers_last - h.leavers_eu_last)}; España sigue por encima de la media europea (${num(h.leavers_eu_last)} %) y de Alemania, Francia, Italia y Portugal.`}
        legend={leavers.slice().reverse()}
        sources={[S.eurostat("edat_lfse_14"), S.eurostat("edat_lfse_16"), S.mefpEpa]}
        notes={[
          `Líneas verticales «b»: rupturas de serie que Eurostat marca con «b» en España o la UE (${el.breaks.join(", ")}), por cambios en la Encuesta de Población Activa; desde 2021 los datos de España llevan además la marca «d» (definición distinta). No se ajustan: la serie se muestra tal cual con sus marcas.`,
          "Es una encuesta: las cifras regionales tienen más error muestral, sobre todo en Ceuta, Melilla y La Rioja.",
          "Estudios de la madre: explotación de la EPA del Ministerio de Educación (tabla aban_1_08), jóvenes de 18 a 24 años; el grupo «no consta» se omite en el gráfico y está en los datos descargables.",
        ]}
        table={<EduTable caption="Ver los datos en tabla (con marcas de Eurostat)" series={leavers.slice().reverse()} />}
      >
        <Explain
          shows="Qué parte de los jóvenes de 18 a 24 años dejó de estudiar sin pasar de la ESO, en España, la UE y países comparables, y por comunidad."
          read="Una línea que baja es una buena noticia. Las líneas verticales marcan cambios de método de la encuesta: los saltos en esos años pueden ser de medida."
          notSay="No dice por qué bajó (la crisis de 2008 quitó empleo a los jóvenes sin título, hubo cambios de ley y más FP) ni qué hacen hoy quienes abandonaron."
        />
        <TimeSeriesChart
          series={leavers}
          xMin={1992}
          xMax={h.leavers_last_year}
          annotations={breakNotes}
          ariaLabel="Abandono temprano de la educación, España, UE y países comparables"
        />
        <h3 className="vizPanelTitle">
          Abandono temprano según los estudios de la madre (%)
          <span>
            {motherLast("E. Primaria e inferior")} % si la madre tiene como mucho Primaria; {motherLast("E. Superior")} % si tiene estudios superiores (
            {motherYear})
          </span>
        </h3>
        <TimeSeriesChart series={motherSeries} height={240} ariaLabel="Abandono temprano según el nivel de estudios de la madre" />
        <h3 className="vizPanelTitle">
          Por comunidad autónoma: {el.regions_first_year} → {el.regions_last_year}
          <span>
            De {num(el.regions[0].last)} % ({el.regions[0].name}) a {num(el.regions.at(-1).last)} % ({el.regions.at(-1).name}) en {el.regions_last_year}
          </span>
        </h3>
        <ul className="vizBars" aria-label={`Abandono temprano por comunidad autónoma en ${el.regions_last_year}`}>
          {el.regions.map((row) => (
            <li key={row.geo}>
              <span>{row.name}</span>
              <span className="vizBars__track">
                <span className="vizBars__bar" style={{ width: `${(row.last / regionMax) * 100}%` }} />
                <span className="vizBars__value">
                  {num(row.last)} %{row.first != null ? <span style={{ color: "var(--viz-muted)", fontWeight: 400 }}> ({el.regions_first_year}: {num(row.first)} %)</span> : null}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Figure>

      <Figure
        id="repeticion"
        title={`A los 15 años, el ${num(h.behind_last.value)} % del alumnado va retrasado de curso, frente al ${num(h.behind_first.value)} % de ${h.behind_first.course} y el ${num(h.behind_peak.value)} % del máximo de ${h.behind_peak.course}`}
        dek={`PISA cuenta lo mismo con otra medida: el alumnado de 15 años que dice haber repetido al menos una vez pasó del ${repSeries.ESP[0].value} % en ${repSeries.ESP[0].year} al ${rep.ESP} % en 2022, y sigue más del doble que la media OCDE (${rep.OECD} %).`}
        sources={[S.mefp, S.pisaReports, S.pisaNote]}
        notes={[
          "Serie anual: 100 menos la tasa de idoneidad a los 15 años del Ministerio (alumnado matriculado en el curso que le corresponde por edad). Se dibuja en el año en que termina cada curso.",
          `La caída de ${num(h.behind_2020)} % (curso 2019-20) a ${num(h.behind_2021)} % (2020-21) refleja la promoción de final del curso 2019-20, flexibilizada por la COVID-19 (Orden EFP/365/2020); después, la LOMLOE (Ley Orgánica 3/2020) y el Real Decreto 984/2021 restringieron la repetición.`,
          "PISA: respuesta del propio alumno, según los informes españoles del INEE (2012-2018) y la nota de país de la OCDE (2022). La media OCDE solo tiene cita literal para 2018 y 2022.",
        ]}
        table={
          <>
            <EduTable caption="Ver los datos en tabla" series={behind} rowLabel="Año (fin de curso)" />
            <EduTable
              digits={0}
              caption="Ver la repetición declarada en PISA en tabla"
              series={[
                { id: "ESP", label: "España", points: repSeries.ESP },
                { id: "OECD", label: "Media OCDE", points: repSeries.OECD },
              ]}
            />
          </>
        }
      >
        <Explain
          shows="Cuántos alumnos de 15 años van retrasados de curso (Ministerio, cada año) y cuántos dicen haber repetido alguna vez (PISA, cada tres años)."
          read="Son dos medidas distintas de lo mismo: el Ministerio cuenta matrículas y PISA pregunta a los alumnos. Las dos bajan, y PISA permite comparar con la OCDE."
          notSay="Repetir menos no implica aprender más: puede reflejar normas de promoción más flexibles, como en 2020."
        />
        <TimeSeriesChart
          series={behind}
          yMax={50}
          annotations={[{ year: 2021, label: "COVID-19: promoción flexible", keepOnMobile: true }]}
          ariaLabel="Alumnado de 15 años retrasado de curso en España"
        />
        <h3 className="vizPanelTitle">
          Alumnado de 15 años que dice haber repetido al menos una vez (PISA)
          <span>
            España: {repSeries.ESP[0].value} % ({repSeries.ESP[0].year}) → {rep.ESP} % (2022); media OCDE: {rep.OECD} %
          </span>
        </h3>
        <SparseLineChart
          series={[
            { id: "OECD", label: "Media OCDE", color: C.ref, points: repSeries.OECD },
            { id: "ESP", label: "España", color: C.blue, emphasis: true, points: repSeries.ESP },
          ]}
          unit="pct"
          xMin={2010}
          xMax={2022}
          yMax={50}
          height={220}
          ariaLabel="Repetición declarada en PISA, España y media OCDE"
        />
      </Figure>

      <VocationalFigure data={data} sources={[S.eurostat("educ_uoe_enrs04"), S.eurostat("edat_lfse_24")]} />
      <AttainmentFigure data={data} sources={[S.eurostat("edat_lfse_03"), S.eurostat("lfsa_eoqgan")]} overq={{ es: h.overq_es, eu: h.overq_eu }} />

      <Figure
        id="sobrecualificacion"
        title={`El ${num(h.overq_es)} % de los titulados superiores con empleo trabaja en un puesto que no exige su título; en la UE, el ${num(h.overq_eu)} %`}
        dek="Tasa de sobrecualificación: ocupados de 20 a 64 años con estudios superiores que trabajan en ocupaciones de cualificación media o baja. España tiene la más alta de los países comparados en toda la serie."
        legend={overq.slice().reverse()}
        sources={[S.eurostat("lfsa_eoqgan")]}
        notes={[
          "Mide el encaje entre título y ocupación según la clasificación ISCO, no la calidad del título ni el salario. Puede reflejar tanto exceso de titulados como un tejido productivo con pocos puestos cualificados.",
          ...(data.overqualification_breaks_es?.length
            ? [`Líneas verticales «b»: rupturas de serie de la Encuesta de Población Activa que Eurostat marca con «b» para España (${data.overqualification_breaks_es.join(", ")}); no se ajustan.`]
            : []),
        ]}
        table={<EduTable caption="Ver los datos en tabla" series={overq.slice().reverse()} />}
      >
        <Explain
          shows="Qué parte de los ocupados con estudios superiores trabaja en un puesto que no pide ese nivel."
          read="Cuanto más alta la línea, mayor el desajuste entre títulos y empleos. España está por encima de todos los países comparados en toda la serie."
          notSay="No distingue si sobran titulados o faltan empleos cualificados, ni cuánto cobran esas personas."
        />
        <TimeSeriesChart
          series={overq}
          annotations={breakRows(data.overqualification_breaks_es || [])}
          ariaLabel="Tasa de sobrecualificación, España, UE y países comparables"
        />
      </Figure>

      <AdultSkillsFigure data={data} sources={[S.piaac]} />
      <LabourReturnFigure data={data} sources={[S.oecdEarn, S.eurostat("lfsa_ergaed"), S.eurostat("edat_lfse_20")]} />

      <Figure
        id="largo-plazo"
        title={`En 1900 sabía leer el ${num(h.literacy_1900, 0)} % de la población; en ${h.literacy_last.year}, el ${num(h.literacy_last.value)} %`}
        dek={`Los años medios de escolarización de la población de 15 a 64 años pasaron de ${num(h.schooling_first.value)} en ${h.schooling_first.year} a ${num(h.schooling_last.value)} en ${h.schooling_last.year}. En 1900 España iba por delante de ${list(behindIn1900)}; se estancó hasta 1950, cuando ${list(aheadIn1950)} ya la habían adelantado, y el gran salto llegó a partir de los años 60.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "peer", label: "Alemania, Francia, Italia, Portugal", color: C.peer },
        ]}
        sources={[S.owid]}
        notes={[
          "Alfabetización: hasta 1950, censos recopilados por la UNESCO (1953, 1957), en general población de 10 o más años; después, Instituto de Estadística de la UNESCO, 15 o más años. Hay una ruptura entre 1950 y la siguiente observación: las líneas se cortan y no se empalman.",
          "Años de escolarización: Lee y Lee (2016) hasta 2010; 2015 y 2020 son proyecciones de Barro y Lee (2015). Son estimaciones reconstruidas a partir de censos, con más incertidumbre cuanto más atrás.",
        ]}
        table={
          <>
            <EduTable caption="Ver alfabetización en tabla" series={literacy.slice().reverse()} />
            <EduTable unit="years" caption="Ver años de escolarización en tabla" series={schooling.slice().reverse()} />
          </>
        }
      >
        <Explain
          shows="Un siglo de progreso educativo: qué parte de la población sabía leer y cuántos años estudiaba de media."
          read="Los puntos son observaciones (censos y estimaciones) y las líneas solo los unen. La alfabetización se corta tras 1950 porque cambia la fuente."
          notSay="Las cifras antiguas son reconstrucciones con más incertidumbre y con definiciones distintas de «saber leer»."
        />
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Población alfabetizada (%)
              <span>España: {num(h.literacy_1900)} % (1900) → {num(h.literacy_last.value)} % ({h.literacy_last.year})</span>
            </h3>
            <SparseLineChart series={literacy} unit="pct" digits={1} xMin={1895} yMax={100} height={260} ariaLabel="Tasa de alfabetización desde 1900" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Años medios de escolarización (15-64 años)
              <span>
                España: {num(h.schooling_first.value)} ({h.schooling_first.year}) → {num(h.schooling_last.value)} ({h.schooling_last.year})
              </span>
            </h3>
            <SparseLineChart series={schooling} unit="years" xMin={1870} height={260} ariaLabel="Años medios de escolarización desde 1870" />
          </div>
        </div>
      </Figure>

      <section className="card vizProse" id="conclusion" aria-labelledby="conclusion-title">
        <h2 id="conclusion-title">Conclusión: la hipótesis, contrastada</h2>
        <p>
          <strong>Hipótesis:</strong> desde 2000 el gasto público real por alumno ha subido mucho y los resultados de PISA se han quedado igual o han
          bajado. <strong>Resultado: se cumple a medias, y la parte que se cumple no basta para concluir que gastar más no sirve.</strong>
        </p>
        <ul>
          <li>
            <strong>Dónde se cumple.</strong> El gasto real por alumno es un {num(h.spending_school_change_2000_pct, 0)} % mayor que en 2000 (OCDE) y un{" "}
            {num(realChange, 0)} % mayor según el Ministerio, mientras PISA matemáticas pasa de {h.math_2003} (2003) a {h.math_2022} (2022), lectura de{" "}
            {h.reading_2000} (2000) a {h.reading_2022} y ciencias de {h.science_2006} (2006) a {h.science_2022}.
          </li>
          <li>
            <strong>Dónde falla.</strong> Todo el aumento llegó antes de {h.spending_school_peak.year}; después hubo un recorte del{" "}
            {num((1 - h.spending_school_trough.value / h.spending_school_peak.value) * 100, 0)} % y el sueldo real del profesorado sigue un{" "}
            {Math.abs(data.teachers.headline.salary_change_from_peak_pct)} % por debajo de entonces. España gasta por alumno el {h.spending_school_vs_oecd_pct} % de
            la media OCDE (el {h.spending_school_vs_oecd_2005_pct} % en 2005). Y la OCDE, que subió su gasto un {h.oecd_school_change_2005_pct} % desde 2005,
            también bajó en PISA: su media de matemáticas pasó de {h.oecd_math_2003} a {data.pisa.math.OECD.at(-1).value}; {list(biggerDrops)} perdieron más
            puntos que España.
          </li>
          <li>
            <strong>Lo que sí mejoró.</strong> El abandono temprano cayó del {num(h.leavers_2000)} % de 2000 al {num(h.leavers_last)} % y la repetición a los 15
            años, del {num(h.behind_first.value)} % de {h.behind_first.course} (máximo: {num(h.behind_peak.value)} %) al {num(h.behind_last.value)} %. Como la escolarización es obligatoria hasta los 16 años, esa mejora
            apenas cambia quién hace PISA a los 15: cambia en qué curso están (menos repetidores) y cuántos siguen estudiando después.
          </li>
          <li>
            <strong>Sistema frente a mezcla de alumnos.</strong> El aumento del alumnado inmigrante explicaría unos{" "}
            {num(data.equity.composition.effect_raw_points)} de los {Math.abs(data.equity.composition.math_change_2012_2022)} puntos perdidos en matemáticas
            desde 2012, y menos de medio punto a igual nivel socioeconómico: la composición explica poco de la caída. El origen social pesa algo menos que en
            la OCDE ({data.equity.escs_gap.ESP[2022]} frente a {data.equity.escs_gap.OECD[2022]} puntos de brecha).
          </li>
          <li>
            <strong>Más allá del gasto público y de PISA.</strong> El gasto público no es todo el gasto: las familias pagan el{" "}
            {num(data.capacity.private_share_all.ES.at(-1).value, 0)} % (el {num(data.capacity.private_share_tertiary.ES.at(-1).value, 0)} % en la
            universidad). Y el sistema entrega adultos con menos competencias que la media OCDE ({data.outcomes.piaac.piaac_literacy_mean.ESP} frente a{" "}
            {data.outcomes.piaac.piaac_literacy_mean.OECD}), con una brecha que no se cierra en las generaciones jóvenes, aunque estudiar siga
            compensando: un titulado superior cobra un {data.outcomes.earnings.ISCED11A_5T8.ESP.at(-1).value - 100} % más que uno de Bachillerato o FP.
          </li>
          <li>
            <strong>Lo que estos datos no pueden decir.</strong> Ninguna de estas series mide causalidad. Para saber si un euro más mejora resultados
            haría falta comparar alumnos parecidos con distinto gasto (evaluaciones de programas concretos), no medias nacionales. Entre comunidades, la
            relación entre gasto y PISA es débil, pero 17 casos con renta, población y salarios distintos no bastan para descartarla.
          </li>
        </ul>
      </section>

      <Glossary />

      <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método y fuentes</h2>
        <ul>
          <li>
            <strong>Denominador.</strong> El gasto se mide por alumno y a precios constantes (deflactor del PIB), y se contrasta en paridad de poder
            adquisitivo y en % del PIB. Los totales nominales solo están en los datos descargables.
          </li>
          <li>
            <strong>Comparación.</strong> Cada cifra de España se compara con la media de la OCDE o de la UE y con Alemania, Francia, Italia y Portugal antes
            de calificarla de alta o baja.
          </li>
          <li>
            <strong>Ejes y rupturas.</strong> Todos los ejes empiezan en cero, no hay ejes dobles y los paneles de un mismo gráfico comparten escala. Las
            rupturas de serie se marcan (Eurostat), los ciclos PISA no comparables se dibujan huecos y las fuentes de alfabetización no se empalman.
          </li>
          <li>
            <strong>Hipótesis.</strong> La página parte de una hipótesis (más gasto, mismos resultados) y publica también lo que la contradice: la caída
            del gasto tras 2009, el menor gasto relativo a la OCDE, la caída aún mayor de PISA en países que gastan más y la mejora del abandono escolar.
          </li>
          <li>
            <strong>Lo que no se puede concluir.</strong> Correlación no es causalidad. PISA mide a los alumnos de 15 años escolarizados, casi todos
            por ser obligatoria la escolarización hasta los 16; la caída del abandono (18-24 años) apenas cambia quién se examina, pero sí la
            proporción de repetidores. El gasto público no incluye lo que pagan las familias.
          </li>
          <li>
            <strong>Reproducible y reutilizable.</strong> <code>just education-refresh</code> descarga cada fuente, guarda el original y lo carga en SQLite
            con el contrato de indicadores del proyecto: cada publicación oficial es una versión nueva, cada valor se compara con la anterior y apunta a
            su celda en el fichero original con su SHA-256. Los valores de PISA 2022 sin API llevan documento, página PDF y cita literal, comprobada contra
            el PDF guardado. Desde ahí se generan los <a href={downloads}>datos publicados</a>.
          </li>
          <li>
            <strong>Bloqueos.</strong> oecd.org responde con un desafío de Cloudflare a la descarga por script; se usa la réplica DBnomics de la OCDE y la
            copia del INEE de la nota de país.
          </li>
        </ul>
        <p>
          Fuentes:{" "}
          {Object.values(src).map((s, index) => (
            <span key={s.page}>
              {index ? "; " : ""}
              <a href={s.page} rel="noopener noreferrer" target="_blank">
                {s.label}
              </a>
              {s.retrieved_at ? ` (consultado ${String(s.retrieved_at).slice(0, 10)})` : ""}
            </span>
          ))}
          .
        </p>
      </section>
    </main>
  );
}
