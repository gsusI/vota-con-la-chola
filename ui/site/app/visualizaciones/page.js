import Link from "next/link";
import { readPublicJson } from "../static-snapshot.mjs";
import { getDatasetsForSection, getSectionById, withBasePath } from "../siteCatalog.mjs";
import MiniChart from "./components/MiniChart";
import { DEFAULT_LEVERS, simulate } from "./sistema/engine.mjs";

export const metadata = {
  title: "Visualizaciones de datos públicos | Vota Con La Chola",
  description: "Gráficos sobre datos públicos con fuente oficial, rupturas de serie señaladas y datos descargables.",
};

const C = { blue: "#2a78d6", orange: "#eb6834", ref: "#52514e", peer: "#b4b2a9" };

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const years = (value) => `${num(value)} años`;
const thousands = (value) => Math.round(Number(value)).toLocaleString("es-ES", { useGrouping: "always" });
// «1,67 millones de hogares» but «957.674 viviendas», as on the housing page.
const howMany = (value, noun) =>
  Math.abs(Number(value)) >= 1e6 ? `${num(Number(value) / 1e6, 2)} millones de ${noun}` : `${thousands(value)} ${noun}`;
// Keep «37 %» and «1,67 millones» on one line.
const nbsp = (text) => text.replace(/ (%|millones)/g, "\u00a0$1");
const plainTick = (value) => value.toLocaleString("es-ES");

function load(name) {
  const data = readPublicJson(`visualizaciones/data/${name}.json`, null);
  if (!data) throw new Error(`Missing visualizaciones/data/${name}.json`);
  return data;
}

const day = (source) => (source?.retrieved_at ? String(source.retrieved_at).slice(0, 10) : null);

// One preview per page: the chart that carries its main finding, with the same title wording,
// zero-based axis and series breaks (unspliced paths) as on the page itself.
function buildStories() {
  const tax = load("carga-fiscal");
  const th = tax.headline;
  const jobs = load("empleo");
  const jh = jobs.headline;
  const u = jobs.unemployment.amecos;
  const home = load("vivienda");
  const hh = home.headline;
  const s13 = hh.since_2013;
  const sup = home.supply;
  const edu = load("educacion");
  const eh = edu.headline;
  const el = edu.early_leavers;
  const health = load("sanidad");
  const le = health.life_expectancy;
  const leH = health.headline.life_expectancy;
  const es1925 = le.long_run.ESP[0];
  const esLongLast = le.long_run.ESP.at(-1);

  return [
    {
      href: "/visualizaciones/carga-fiscal/",
      topic: "Impuestos",
      title: `De un ${num(th.first_value_imf, 0)} % a un ${num(th.last_value, 0)} % del PIB en un siglo`,
      dek: "Presión fiscal en España desde 1925. Dos series que se solapan sin empalmar: el Estado central (FMI) hasta 1980 y todas las administraciones (OCDE) desde 1965.",
      chart: {
        series: [
          { id: "imf", color: C.orange, endLabel: "Estado (FMI)", points: tax.long_run.imf_revenue_pct_gdp.filter((p) => p.year <= 1980) },
          { id: "oecd", color: C.blue, emphasis: true, endLabel: "AAPP (OCDE)", points: tax.long_run.oecd_tax_pct_gdp },
        ],
        xMin: 1925,
        xMax: th.last_year,
        yMax: 40,
        ariaLabel: "Presión fiscal en España, 1925 a hoy, en porcentaje del PIB",
      },
      unitNote: "% del PIB",
      sources: [
        { label: "FMI", href: tax.sources.imf_fpp.page, retrieved: day(tax.sources.imf_fpp) },
        { label: "OCDE", href: tax.sources.oecd_revenue_statistics.page, retrieved: day(tax.sources.oecd_revenue_statistics) },
      ],
      also: "Recaudación real por habitante, quién paga, comparación con la OCDE, tipos legales y complejidad del BOE.",
    },
    {
      href: "/visualizaciones/empleo/",
      topic: "Empleo",
      title: `Desde ${jh.hypothesis_from}, el paro de España ha sido de media ${num(jh.ratio_mean_since)} veces el europeo`,
      dek: "Tasa de paro desde 1960 frente a la media europea. La UE-15 cambia de cobertura en 1991 (reunificación alemana): se dibuja en dos tramos.",
      chart: {
        series: [
          { id: "DU15", color: C.ref, points: u.DU15 },
          { id: "EU15", color: C.ref, endLabel: "UE-15", points: u.EU15 },
          { id: "ESP", color: C.blue, emphasis: true, endLabel: "España", points: u.ESP },
        ],
        xMin: jh.first_year,
        xMax: jh.last_year,
        yMax: Math.ceil(Math.max(...u.ESP.map((p) => p.value)) / 5) * 5,
        ariaLabel: "Tasa de paro de España y de la media europea desde 1960",
      },
      unitNote: "% de la población activa",
      sources: [{ label: "Comisión Europea, AMECO", href: jobs.sources.ameco_dbnomics.page, retrieved: day(jobs.sources.ameco_dbnomics) }],
      also: "Paro estructural (NAWRU), paro juvenil, temporalidad y fijos discontinuos, productividad por hora y cuña fiscal.",
    },
    {
      href: "/visualizaciones/vivienda/",
      topic: "Vivienda",
      title: `Desde ${s13.from} se han terminado ${howMany(s13.completed, "viviendas")} y se han formado ${howMany(s13.net_households, "hogares nuevos")}`,
      dek: `${num(s13.ratio, 2)} viviendas por cada hogar nuevo. Entre 1991 y 2011 fue al revés (máximo de ${thousands(hh.completed_peak)} terminadas en ${hh.completed_peak_year}) y aun así el precio subió: la página publica también esa contraevidencia. Línea vertical: cambio de la EPA en 2021.`,
      chart: {
        series: [
          { id: "households", color: C.orange, endLabel: "Hogares nuevos", points: sup.net_households_epa },
          { id: "completed", color: C.blue, emphasis: true, endLabel: "Terminadas", points: sup.completed_total },
        ],
        breaks: [2021],
        format: (value) => `${num(value / 1000, 0)} mil`,
        tick: (value) => (value ? `${(value / 1000).toLocaleString("es-ES")} mil` : "0"),
        ariaLabel: "Viviendas terminadas y hogares nuevos netos al año en España",
      },
      unitNote: "viviendas y hogares al año",
      sources: [
        { label: "Ministerio de Vivienda", href: "https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=32000000", retrieved: day(home.sources.mivau_boletin) },
        { label: "INE (EPA) vía Banco de España", href: home.sources.bde_indicadores_vivienda.page, retrieved: day(home.sources.bde_indicadores_vivienda) },
      ],
      also: "Años de salario por piso, edad de emancipación, propiedad y alquiler, impuestos de compra y gasto público.",
    },
    {
      href: "/visualizaciones/educacion/",
      topic: "Educación",
      title: `El abandono escolar temprano bajó del ${num(eh.leavers_2008)} % en 2008 al ${num(eh.leavers_last)} % en ${eh.leavers_last_year}`,
      dek: `Jóvenes de 18 a 24 años sin estudios más allá de la ESO. España sigue por encima de la UE-27 (${num(eh.leavers_eu_last)} %). Líneas verticales: rupturas de serie de Eurostat.`,
      chart: {
        series: [
          { id: "EU27_2020", color: C.ref, endLabel: "UE-27", points: el.series.EU27_2020 },
          { id: "ES", color: C.blue, emphasis: true, endLabel: "España", points: el.series.ES },
        ],
        xMax: eh.leavers_last_year,
        breaks: el.breaks,
        ariaLabel: "Abandono temprano de la educación, España y UE-27",
      },
      unitNote: "% de 18 a 24 años",
      sources: [{ label: "Eurostat, edat_lfse_14", href: "https://ec.europa.eu/eurostat/databrowser/view/edat_lfse_14/default/table", retrieved: day(edu.sources.eurostat_sdmx) }],
      also: "Gasto real por alumno frente a la OCDE, PISA desde 2000, repetición de curso, sobrecualificación y un siglo de alfabetización.",
    },
    {
      href: "/visualizaciones/sanidad/",
      topic: "Sanidad",
      title: `La esperanza de vida pasó de ${num(es1925.value, 0)} años en ${es1925.year} a ${num(esLongLast.value)} en ${esLongLast.year}`,
      dek: `Hoy es ${num(leH.es - leH.eu27)} años mayor que la media de la UE (INE y Eurostat, ${leH.year}). En gris, Alemania, Francia, Italia y Portugal.`,
      chart: {
        series: [
          ...["DEU", "FRA", "ITA", "PRT"].map((code) => ({ id: code, color: C.peer, points: le.long_run[code] })),
          { id: "ESP", color: C.blue, emphasis: true, endLabel: "España", points: le.long_run.ESP },
        ],
        xMin: 1925,
        xMax: esLongLast.year,
        yMax: 90,
        format: years,
        tick: plainTick,
        ariaLabel: "Esperanza de vida al nacer en España y países comparables desde 1925",
      },
      unitNote: "años de vida al nacer",
      sources: [{ label: "Our World in Data (HMD)", href: health.sources.owid_grapher.page, retrieved: day(health.sources.owid_grapher) }],
      also: "Gasto sanitario público frente a Europa, listas de espera del SNS con sus rupturas, médicos por habitante y pago de bolsillo.",
    },
    simulatorStory(),
  ];
}

// The simulator's preview: official baseline against the same lever (+1 pp a year over CPI) paid with debt.
function simulatorStory() {
  const model = load("sistema");
  const run = simulate(model, { ...DEFAULT_LEVERS, reval: 1 });
  const end = model.years.length - 1;
  const pts = (values) => model.years.map((year, i) => ({ year, value: Math.round(values[i] * 100) / 100 }));
  return {
    href: "/visualizaciones/sistema/",
    topic: "Simulador",
    title: `Subir las pensiones un punto sobre el IPC suma ${num(run.debt_dev_pp[end], 0)} puntos de deuda en 2050 si se paga con deuda`,
    dek: `Gasto en pensiones con la ley actual (Ageing Report 2024) y con una revalorización de un punto más que el IPC desde ${model.policy_start}. En la página: el mismo cambio pagado con cotizaciones o con IVA, y qué les pasa a dos casos tipo.`,
    chart: {
      series: [
        { id: "base", color: C.ref, endLabel: "Ley actual", points: pts(model.baseline.pension_pct) },
        { id: "scen", color: C.blue, emphasis: true, endLabel: "+1 punto", points: pts(run.pension_pct) },
      ],
      xMin: model.years[0],
      xMax: model.years[end],
      yMax: Math.ceil(Math.max(...run.pension_pct) / 5) * 5,
      ariaLabel: "Gasto en pensiones públicas en % del PIB, ley actual y revalorización de un punto sobre el IPC",
    },
    unitNote: "% del PIB",
    sources: [{ label: "Comisión Europea, Ageing Report 2024", href: model.sources.ageing_report.page, retrieved: model.sources.ageing_report.retrieved_at }],
    also: "Mapa causal con 24 fichas de evidencia, edad de jubilación, cotizaciones, quién paga según la financiación y cómo votó cada partido.",
  };
}

const PRINCIPLES = [
  "Fuente oficial enlazada en cada gráfico",
  "Ejes desde cero",
  "Rupturas de serie a la vista, sin empalmar",
  "Comparación con la UE y la OCDE",
  "Datos en CSV y JSON",
];

export default function VisualizacionesHubPage() {
  const section = getSectionById("visualizaciones");
  const stories = buildStories();
  const datasets = getDatasetsForSection("visualizaciones");
  const downloadsByPage = stories.map((story) => ({
    ...story,
    files: datasets.filter((dataset) => dataset.path.includes(story.href.split("/").filter(Boolean).at(-1))),
  }));

  return (
    <main className="shell vizHub">
      <header className="card vizHub__hero">
        <p className="eyebrow">Visualizaciones · datos públicos</p>
        <h1>{section.title}</h1>
        <p className="vizHub__lede">
          Series oficiales de largo plazo para comprobar hipótesis sobre España. Publicamos también lo que las contradice.
        </p>
        <ul className="vizHub__principles" aria-label="Cómo están hechos">
          {PRINCIPLES.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </header>

      <section className="vizHub__grid" aria-label="Visualizaciones disponibles">
        {stories.map((story, index) => (
          <article key={story.href} className={`card vizStory${index === 0 ? " vizStory--lead" : ""}`}>
            <p className="vizStory__topic">{story.topic}</p>
            <h2 className="vizStory__title">
              <Link href={withBasePath(story.href)} className="vizStory__link">
                {nbsp(story.title)}
              </Link>
            </h2>
            <p className="vizStory__dek">{nbsp(story.dek)}</p>
            <div className="vizStory__chart">
              <span className="vizStory__unit">{story.unitNote}</span>
              <MiniChart {...story.chart} />
            </div>
            <p className="vizStory__source">
              Fuente:{" "}
              {story.sources.map((source, i) => (
                <span key={source.href}>
                  {i ? "; " : ""}
                  <a href={source.href} rel="noopener noreferrer" target="_blank">
                    {source.label}
                  </a>
                </span>
              ))}
              {story.sources[0].retrieved ? ` (consultado ${story.sources[0].retrieved})` : ""}.
            </p>
            <p className="vizStory__also">
              <strong>En la página:</strong> {story.also}
            </p>
            <span className="vizStory__cta" aria-hidden="true">
              Ver todos los gráficos →
            </span>
          </article>
        ))}
      </section>

      <section className="card vizHub__data" aria-labelledby="viz-datos">
        <h2 id="viz-datos">Datos descargables</h2>
        <p>Cada valor de los gráficos, con su fuente y fecha de consulta.</p>
        <ul>
          {downloadsByPage.map((story) => (
            <li key={story.href}>
              <span>{story.topic}</span>
              {story.files.map((file) => (
                <a key={file.id} href={withBasePath(file.path)}>
                  {file.path.endsWith(".csv") ? "CSV" : "JSON con procedencia"}
                </a>
              ))}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
