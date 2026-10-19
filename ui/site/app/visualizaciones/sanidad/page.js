import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Figure from "../components/Figure";
import HealthChart from "./HealthChart";
import HealthTable, { Bars } from "./HealthTable";
import { formatHealth } from "./format.mjs";

export const metadata = {
  title: "Sanidad en España: esperanza de vida, gasto y listas de espera | Vota Con La Chola",
  description:
    "Esperanza de vida desde 1925, gasto sanitario público frente a Europa, listas de espera del SNS con sus rupturas de serie y médicos por habitante, con fuentes oficiales y datos descargables.",
};

const C = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  ref: "#52514e",
  peer: "#b4b2a9",
};
const NAMES = {
  ESP: "España", DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal",
  ES: "España", DE: "Alemania", FR: "Francia", IT: "Italia", PT: "Portugal", EU27_2020: "Media UE-27",
};
const MONTHS = { "06": "jun", "12": "dic" };

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const pctChange = (from, to) => ((to - from) / from) * 100;
const cutLabel = (date) => `${MONTHS[date.slice(5, 7)]} ${date.slice(0, 4)}`;
const at = (rows, year) => rows.find((p) => p.year === year)?.value;

// Source-flagged series breaks (Eurostat «b», OECD «B»): the line restarts at the break instead of joining it.
function splitAtBreaks(list) {
  return list.flatMap((item) => {
    const parts = [];
    for (const point of item.points) {
      if (!parts.length || /b/i.test(point.status || "")) parts.push([]);
      parts.at(-1).push(point);
    }
    return parts.map((points, index) => ({ ...item, id: index ? `${item.id}-b${index}` : item.id, points, noEndLabel: item.noEndLabel || index < parts.length - 1 }));
  });
}

// December cuts only (same season every year); a new segment starts at each declared series break.
function decemberSegments(rows, breakYears, base) {
  const dec = rows.filter((p) => p.date.endsWith("-12-31")).map((p) => ({ year: Number(p.date.slice(0, 4)), value: p.value }));
  const edges = [-Infinity, ...breakYears, Infinity];
  const segments = [];
  for (let i = 0; i < edges.length - 1; i += 1) {
    const points = dec.filter((p) => p.year >= edges[i] && p.year < edges[i + 1]);
    if (points.length) segments.push(points);
  }
  return segments.map((points, index) => ({
    ...base,
    id: `${base.id}-${index}`,
    points,
    noEndLabel: index < segments.length - 1,
  }));
}

function semesterTable(seriesList) {
  return (
    <HealthTable
      series={seriesList.map((s) => ({ ...s, points: s.points.map((p) => ({ ...p, key: p.date })) }))}
      keyOf={(p) => p.key}
      labelOf={cutLabel}
      periodLabel="Corte"
      caption="Ver todos los cortes semestrales en tabla"
    />
  );
}

export default function SanidadPage() {
  const data = readPublicJson("visualizaciones/data/sanidad.json", null);
  if (!data) throw new Error("Missing visualizaciones/data/sanidad.json");
  const h = data.headline;
  const src = data.sources;
  const le = data.life_expectancy;
  const sp = data.spending;
  const wait = data.waiting;
  const docs = data.doctors;
  const downloads = "/visualizaciones/data/sanidad.csv";
  const retrieved = (id) => (src[id]?.retrieved_at ? `, consultado ${String(src[id].retrieved_at).slice(0, 10)}` : "");
  const S = {
    eurostat: { label: `Eurostat${retrieved("eurostat_sdmx")}`, href: src.eurostat_sdmx.page },
    ine: { label: `INE, tabla 1414${retrieved("ine_wstempus")}`, href: src.ine_wstempus.page },
    owid: { label: `Our World in Data (HMD y otros)${retrieved("owid_grapher")}`, href: src.owid_grapher.page },
    wb: { label: `Banco Mundial${retrieved("worldbank_wdi")}`, href: src.worldbank_wdi.page },
    oecd: { label: `OCDE, Health Statistics vía DBnomics${retrieved("oecd_health_statistics")}`, href: src.oecd_health_statistics.page },
    sisle: { label: `Ministerio de Sanidad, SISLE-SNS${retrieved("minsan_sisle_sns")}`, href: src.minsan_sisle_sns.page },
    egsp: { label: `Ministerio de Sanidad, EGSP${retrieved("minsan_egsp")}`, href: src.minsan_egsp.page },
  };

  // 1. Life expectancy
  const leH = h.life_expectancy;
  const longOrder = ["DEU", "FRA", "ITA", "PRT", "ESP"];
  const longRun = longOrder.map((code) => ({
    id: code, label: NAMES[code], color: code === "ESP" ? C.blue : C.peer, emphasis: code === "ESP", noEndLabel: code !== "ESP",
    points: le.long_run[code],
  }));
  const es1925 = le.long_run.ESP[0];
  const esLongLast = le.long_run.ESP.at(-1);
  const official = [
    ...["DE", "FR", "IT", "PT"].map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, noEndLabel: true, points: le.eurostat[geo] })),
    { id: "EU27_2020", label: "Media UE-27 (Eurostat)", shortLabel: "UE-27", color: C.ref, points: le.eurostat.EU27_2020 },
    { id: "ESP", label: "España (INE)", shortLabel: "España", color: C.blue, emphasis: true, points: le.ine.total.map((p) => ({ ...p, value: Math.round(p.value * 10) / 10 })) },
  ];
  const covidDrop = at(le.ine.total, 2019) - at(le.ine.total, 2020);
  const deu = new Map(le.long_run.DEU.map((p) => [p.year, p.value]));
  const aheadOfGermany = le.long_run.ESP.find((p, i, rows) => rows.slice(i).every((q) => !deu.has(q.year) || q.value >= deu.get(q.year)))?.year;
  const worldTop = le.world.top.map((row) => ({ ...row, color: row.oecd ? C.peer : "#d9d7cf" }));
  const worldMin = Math.min(...worldTop.map((row) => row.value));

  // 2. Spending
  const spH = h.spending;
  const ppsRatio = (spH.pps_es / spH.pps_eu27) * 100;
  const peerOrder = ["DEU", "FRA", "ITA", "PRT"];
  const gdpMax = Math.max(...[...peerOrder, "ESP"].flatMap((a) => sp.pct_gdp_public[a].map((p) => p.value)));
  const oecdGdp = sp.pct_gdp_public_oecd_mean;
  const oecdBreaks = sp.pct_gdp_public.ESP.filter((p) => p.status === "B").map((p) => p.year);
  const esEur = sp.per_person_eur2020_public_esp;
  const peak2009 = at(esEur, 2009);
  const low2013 = at(esEur, 2013);
  const lastEur = esEur.at(-1);
  const recoveredYear = esEur.find((p) => p.year > 2013 && p.value >= peak2009)?.year;
  const ppp = [
    ...peerOrder.map((a) => ({ id: a, label: NAMES[a], color: C.peer, points: sp.per_person_ppp_public[a] })),
    { id: "OECD", label: "Media OCDE (simple)", shortLabel: "Media OCDE", color: C.ref, points: sp.per_person_ppp_public_oecd_mean },
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: sp.per_person_ppp_public.ESP },
  ];
  const euGdp = [
    { id: "EU27", label: "Media UE-27", color: C.ref, points: sp.eurostat_pct_gdp_public.EU27_2020 },
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: sp.eurostat_pct_gdp_public.ES.filter((p) => p.year >= 2014) },
  ];
  const regionsSpend = sp.regions_per_person;

  // 3. Waiting lists
  const wH = h.waiting;
  const breakYears = [...new Set(wait.breaks.surgery.map((b) => Number(b.date.slice(0, 4))))];
  const breakNotes = [
    { year: 2012, label: "ruptura", row: 0, keepOnMobile: true },
    { year: 2016, label: "ruptura", row: 1, keepOnMobile: true },
    { year: 2018, label: "ruptura", row: 0, keepOnMobile: true },
  ].filter((note) => breakYears.includes(note.year));
  const covidBand = [{ from: 2020, to: 2021, label: "Covid" }];
  const surgeryDays = decemberSegments(wait.surgery.mean_days, breakYears, { id: "sd", label: "Tiempo medio de espera para cirugía", shortLabel: "Días", color: C.blue, emphasis: true });
  const surgeryRate = decemberSegments(wait.surgery.rate_per_1000, breakYears, { id: "sr", label: "Pacientes en espera quirúrgica por 1.000 habitantes", shortLabel: "Por mil", color: C.orange, emphasis: true });
  const consultDays = decemberSegments(wait.consultations.mean_days, breakYears, { id: "cd", label: "Tiempo medio hasta la primera consulta de especialista", shortLabel: "Días", color: C.blue, emphasis: true });
  const consultRate = decemberSegments(wait.consultations.rate_per_1000, breakYears, { id: "cr", label: "Pacientes esperando primera consulta por 1.000 habitantes", shortLabel: "Por mil", color: C.orange, emphasis: true });
  const daysMax = Math.max(...wait.surgery.mean_days.map((p) => p.value), ...wait.consultations.mean_days.map((p) => p.value));
  const surgeryRateChange = pctChange(wH.surgery_rate[0], wH.surgery_rate[1]);
  const consultRateChange = pctChange(wH.consult_rate[0], wH.consult_rate[1]);
  const sinceLabel = cutLabel(wH.comparable_since);
  const lastLabel = cutLabel(wH.last_cut);
  const covidPeak = wait.surgery.mean_days.find((p) => p.date === "2020-06-30");
  const rectified = wait.surgery.mean_days.find((p) => p.rectified);
  const pct6 = wait.surgery.pct_over_6_months;
  const pct6From = pct6.find((p) => p.date === wH.comparable_since)?.value;
  const pct6To = pct6.at(-1).value;

  // Regions: selected procedures (RD 605/2003), the regional table kept comparable since 2017.
  const lastRegionCut = wait.regions_selected[0].days.at(-1).date;
  const regionDays = wait.regions_selected
    .map((row) => ({ code: row.code, name: row.name, value: row.days.find((p) => p.date === lastRegionCut)?.value }))
    .filter((row) => row.value != null)
    .sort((a, b) => b.value - a.value);
  const nationalSelected = wait.national_selected_days.find((p) => p.date === lastRegionCut)?.value;
  const slowest = regionDays[0];
  const fastest = regionDays.at(-1);
  const spendByCode = new Map(regionsSpend.rows.map((row) => [row.code, row.value]));
  const bigSpendShortWait = regionDays.filter((row) => spendByCode.has(row.code));
  const ranks = (values) => values.map((v) => [...values].sort((a, b) => a - b).indexOf(v));
  const spearman = (xs, ys) => {
    const rx = ranks(xs);
    const ry = ranks(ys);
    const mean = (v) => v.reduce((a, b) => a + b, 0) / v.length;
    const [mx, my] = [mean(rx), mean(ry)];
    const cov = rx.reduce((acc, x, i) => acc + (x - mx) * (ry[i] - my), 0);
    const sd = (v, m) => Math.sqrt(v.reduce((acc, x) => acc + (x - m) ** 2, 0));
    return cov / (sd(rx, mx) * sd(ry, my));
  };
  const spendWaitRho = spearman(bigSpendShortWait.map((row) => row.value), bigSpendShortWait.map((row) => spendByCode.get(row.code)));
  const regionTable = wait.regions_selected.map((row) => ({
    id: row.code, label: row.name, unit: "days",
    points: row.days.filter((p) => p.date.endsWith("-12-31")).map((p) => ({ year: Number(p.date.slice(0, 4)), value: p.value })),
  }));

  // 4. Doctors
  const docYear = docs.practising.ES.at(-1).year;
  const docRows = ["ES", "DE", "FR", "IT", "PT"]
    .map((geo) => ({ code: geo, name: NAMES[geo], value: at(docs.practising[geo], docYear) }))
    .filter((row) => row.value != null)
    .sort((a, b) => b.value - a.value);
  const gpRows = ["ES", "DE", "FR", "IT", "PT"]
    .map((geo) => ({ code: geo, name: NAMES[geo], value: at(docs.gp[geo], docYear) }))
    .filter((row) => row.value != null)
    .sort((a, b) => b.value - a.value);
  const esDoc = at(docs.practising.ES, docYear);
  const deDoc = at(docs.practising.DE, docYear);
  const frDoc = at(docs.practising.FR, docYear);
  const esGp = at(docs.gp.ES, docYear);
  const esGpBreak = docs.gp.ES.findLast((p) => /b/.test(p.status || "")) || docs.gp.ES[0];
  const practisingSeries = [
    ...["DE", "FR", "IT"].map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, points: docs.practising[geo] })),
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: docs.practising.ES },
  ];
  const gpSeries = [
    ...["DE", "FR", "IT"].map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, points: docs.gp[geo] })),
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: docs.gp.ES },
  ];

  // 5. Out of pocket
  const oop = sp.eurostat_oop_share;
  const oopYear = oop.ES.at(-1).year;
  const oopSeries = [
    ...["DE", "FR", "IT", "PT"].map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, points: oop[geo] })),
    { id: "EU27", label: "Media UE-27", color: C.ref, points: oop.EU27_2020 },
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: oop.ES },
  ];
  const oopEs = at(oop.ES, oopYear);
  const oopEu = at(oop.EU27_2020, oopYear);

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="Sanidad en España: vivir más, gastar menos y más gente esperando"
        summary="Esperanza de vida desde 1925, gasto sanitario público frente a Europa, listas de espera del SNS y médicos por habitante. Cada gráfico enlaza su fuente oficial, marca las rupturas de serie y trae sus datos en tabla."
        actions={[
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/sanidad.json", label: "JSON con procedencia" },
          { href: "#hipotesis", label: "¿Se cumple la hipótesis?" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Esperanza de vida al nacer ({leH.year})</span>
          <span className="vizStat__value">{num(leH.es)} años</span>
          <span className="vizStat__note">
            UE-27: {num(leH.eu27)}. Puesto {leH.world_rank.position} de {leH.world_rank.of} países y territorios ({leH.world_year}); {leH.oecd_rank.position}.º de la OCDE
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Gasto sanitario público por habitante ({spH.year})</span>
          <span className="vizStat__value">{num(ppsRatio, 0)} %</span>
          <span className="vizStat__note">
            de la media de la UE en poder de compra ({formatHealth(spH.pps_es, "count")} frente a {formatHealth(spH.pps_eu27, "count")} PPS); {num(spH.pct_gdp_es)} % del PIB frente a {num(spH.pct_gdp_eu27)} %
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Pacientes esperando una operación, por 1.000 habitantes</span>
          <span className="vizStat__value">+{num(surgeryRateChange, 0)} %</span>
          <span className="vizStat__note">
            {num(wH.surgery_rate[0])} en {sinceLabel} → {num(wH.surgery_rate[1])} en {lastLabel} ({formatHealth(wH.surgery_patients[1], "count")} personas)
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Espera media para operarse</span>
          <span className="vizStat__value">{num(wH.surgery_days[1], 0)} días</span>
          <span className="vizStat__note">
            {num(wH.surgery_days[0], 0)} en {sinceLabel}: no ha subido en la serie comparable (consultas: {num(wH.consult_days[0], 0)} → {num(wH.consult_days[1], 0)} días)
          </span>
        </div>
      </section>

      <Figure
        id="esperanza-de-vida"
        title={`La esperanza de vida en España es de ${num(leH.es)} años: ${num(leH.es - es1925.value, 0)} más que en ${es1925.year} y ${num(leH.es - leH.eu27)} más que la media de la UE`}
        dek={`En ${es1925.year} era de ${num(es1925.value)} años, por debajo de Alemania, Francia e Italia. España supera a Alemania desde ${aheadOfGermany} y hoy está a la par de Italia y Francia. La Covid la bajó ${num(covidDrop)} años en 2020; en ${leH.year} ya supera el nivel de 2019.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "peer", label: "Alemania, Francia, Italia y Portugal", color: C.peer },
          { id: "eu", label: "Media UE-27", color: C.ref },
        ]}
        sources={[S.owid, S.ine, S.eurostat]}
        notes={[
          "Serie larga (1925–" + esLongLast.year + "): compilación de Our World in Data, que para estos países toma la Human Mortality Database (HMD). La HMD exige registro para descargar sus ficheros, por eso se lee de esa réplica pública.",
          "Serie oficial (desde 1975): INE para España y Eurostat para los demás y la UE. No se empalman: van en paneles separados con la misma escala.",
          "Es esperanza de vida del periodo: resume la mortalidad de ese año, no cuánto vivirá de verdad quien nace.",
        ]}
        table={
          <HealthTable
            unit="years"
            series={[
              { id: "owid-esp", label: "España (serie larga)", points: le.long_run.ESP },
              { id: "ine", label: "España (INE)", points: le.ine.total, digits: 2 },
              { id: "eu", label: "UE-27 (Eurostat)", points: le.eurostat.EU27_2020 },
              ...["DEU", "FRA", "ITA", "PRT"].map((code) => ({ id: code, label: `${NAMES[code]} (serie larga)`, points: le.long_run[code] })),
            ]}
          />
        }
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Serie larga, {es1925.year}–{esLongLast.year}
              <span>Años de vida al nacer</span>
            </h3>
            <HealthChart
              series={longRun}
              unit="years"
              xMin={1925}
              xMax={esLongLast.year}
              yMax={90}
              height={260}
              bands={[{ from: 1936, to: 1939, label: "Guerra" }]}
              ariaLabel="Esperanza de vida al nacer en España y países comparables desde 1925"
            />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Serie oficial, 1975–{leH.year}
              <span>INE (España) y Eurostat (resto)</span>
            </h3>
            <HealthChart
              series={splitAtBreaks(official)}
              unit="years"
              xMin={1975}
              xMax={leH.year}
              yMax={90}
              height={260}
              ariaLabel="Esperanza de vida al nacer: España según el INE frente a la UE y países comparables según Eurostat"
            />
          </div>
        </div>
        <h3 className="vizPanelTitle">
          Los {worldTop.length} países y territorios con mayor esperanza de vida en {le.world.year}
          <span>Banco Mundial; en gris oscuro, miembros de la OCDE. La escala empieza en cero.</span>
        </h3>
        <Bars rows={worldTop} unit="years" digits={1} highlight="ESP" label="Ranking mundial de esperanza de vida" />
        <p className="vizFigure__dek">
          Las diferencias en la cabeza son de décimas: entre el primero ({num(worldTop[0].value)}) y el {worldTop.length}.º ({num(worldMin)}) hay {num(worldTop[0].value - worldMin)} años. Varios son microestados o territorios.
        </p>
      </Figure>

      <Figure
        id="gasto-pib"
        title={`España dedica a la sanidad pública el ${num(spH.pct_gdp_es)} % del PIB: menos que la media de la UE (${num(spH.pct_gdp_eu27)} %) y que la media de la OCDE (${num(oecdGdp.at(-1).value)} %)`}
        dek={`Gasto de las administraciones y seguros obligatorios. España ocupa el puesto ${sp.oecd_rank_pct_gdp.position} de ${sp.oecd_rank_pct_gdp.of} en la OCDE (${sp.oecd_rank_pct_gdp.year}). Alemania (${num(at(sp.pct_gdp_public.DEU, sp.pct_gdp_public.ESP.at(-1).year))} %) y Francia (${num(at(sp.pct_gdp_public.FRA, sp.pct_gdp_public.ESP.at(-1).year))} %) dedican entre 3 y 4 puntos más; Italia y Portugal, algo menos que España. Cada panel compara España con un país, con la misma escala.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "other", label: "País de comparación", color: C.ref },
          { id: "oecd", label: "Media OCDE (simple, años con al menos 34 de 38 miembros)", color: C.peer },
        ]}
        sources={[S.oecd, S.eurostat]}
        notes={[
          `La OCDE marca rupturas de serie para España en ${oecdBreaks.join(" y ")} (cambios de método de las cuentas de salud); el último año es una estimación.`,
          `Eurostat (base SHA 2011) da para España ${num(at(sp.eurostat_pct_gdp_public.ES, spH.year))} % en ${spH.year} frente a ${num(at(sp.eurostat_pct_gdp_public.EU27_2020, spH.year))} % de la UE-27; la media UE solo existe desde 2014.`,
        ]}
        table={
          <HealthTable
            series={[
              { id: "ESP", label: "España", points: sp.pct_gdp_public.ESP },
              ...peerOrder.map((a) => ({ id: a, label: NAMES[a], points: sp.pct_gdp_public[a] })),
              { id: "OECD", label: "Media OCDE", points: oecdGdp },
              ...euGdp.map((s) => ({ ...s, id: `eu-${s.id}`, label: `${s.label} (Eurostat)` })),
            ]}
          />
        }
      >
        <div className="vizMultiples">
          {peerOrder.map((area) => (
            <div key={area}>
              <h3 className="vizPanelTitle">
                España frente a {NAMES[area]}
                <span>
                  {NAMES[area]}: {num(sp.pct_gdp_public[area].at(-1).value)} % en {sp.pct_gdp_public[area].at(-1).year}
                </span>
              </h3>
              <HealthChart
                series={splitAtBreaks([
                  { id: "oecd", label: "Media OCDE", color: C.peer, points: oecdGdp, noEndLabel: true },
                  { id: area, label: NAMES[area], color: C.ref, points: sp.pct_gdp_public[area] },
                  { id: "ESP", label: "España", color: C.blue, emphasis: true, points: sp.pct_gdp_public.ESP },
                ])}
                xMin={1970}
                xMax={sp.pct_gdp_public.ESP.at(-1).year}
                yMax={gdpMax}
                height={210}
                annotations={oecdBreaks.map((year, index) => ({ year, label: String(year), row: index, keepOnMobile: true }))}
                ariaLabel={`Gasto sanitario público en porcentaje del PIB: España frente a ${NAMES[area]}`}
              />
            </div>
          ))}
        </div>
      </Figure>

      <Figure
        id="gasto-por-habitante"
        title={`Por habitante y a precios constantes, el gasto sanitario público de España es un ${num(ppsRatio, 0)} % de la media de la UE`}
        dek={`En euros de 2020 y paridad de poder de compra (para comparar países), España gasta ${formatHealth(sp.per_person_ppp_public.ESP.at(-1).value, "eur")} por habitante frente a ${formatHealth(sp.per_person_ppp_public_oecd_mean.at(-1).value, "eur")} de media en la OCDE (puesto ${sp.oecd_rank_per_person.position} de ${sp.oecd_rank_per_person.of}). Dentro de España, el gasto real por habitante cayó de ${formatHealth(peak2009, "eur")} en 2009 a ${formatHealth(low2013, "eur")} en 2013 (${num(pctChange(peak2009, low2013), 0)} %) y no recuperó el nivel de 2009 hasta ${recoveredYear ?? "después"}.`}
        legend={ppp}
        sources={[S.oecd, S.eurostat]}
        notes={[
          `Ratio UE: Eurostat, estándar de poder de compra (PPS) por habitante, ${spH.year}: ${formatHealth(spH.pps_es, "count")} en España frente a ${formatHealth(spH.pps_eu27, "count")} en la UE-27.`,
          "Precios constantes de 2020 y paridad de poder adquisitivo en euros, tal como los publica la OCDE. La media OCDE es simple, de los miembros con dato cada año (al menos 34 de 38).",
        ]}
        table={
          <HealthTable
            unit="eur"
            series={[
              { id: "eur", label: "España, euros de 2020", points: esEur },
              ...ppp.map((s) => ({ ...s, label: `${s.label}, euros PPA de 2020` })),
            ]}
          />
        }
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              España frente a sus pares y la OCDE
              <span>Euros por habitante en paridad de poder de compra, precios de 2020</span>
            </h3>
            <HealthChart series={splitAtBreaks(ppp)} unit="eur" xMin={1970} xMax={sp.per_person_ppp_public.ESP.at(-1).year} height={260} ariaLabel="Gasto sanitario público por habitante a precios constantes, España y comparables" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              España: gasto público real por habitante
              <span>
                Euros de 2020: {formatHealth(esEur[0].value, "eur")} en {esEur[0].year} → {formatHealth(lastEur.value, "eur")} en {lastEur.year}
              </span>
            </h3>
            <HealthChart
              series={splitAtBreaks([{ id: "eur", label: "Euros de 2020 por habitante", shortLabel: String(lastEur.year), color: C.blue, emphasis: true, points: esEur }])}
              unit="eur"
              xMin={1970}
              xMax={lastEur.year}
              height={260}
              bands={[{ from: 2010, to: 2013, label: "Recortes" }]}
              ariaLabel="Gasto sanitario público real por habitante en España"
            />
          </div>
        </div>
      </Figure>

      <Figure
        id="listas-quirurgicas"
        title={`Desde ${sinceLabel} hay un ${num(surgeryRateChange, 0)} % más de pacientes por habitante esperando una operación, pero la espera media no ha subido: ${num(wH.surgery_days[1], 0)} días`}
        dek={`Corte de diciembre de cada año, para comparar la misma época (en junio las listas suelen ser más cortas). La serie tiene tres rupturas declaradas por el Ministerio: cada tramo se dibuja por separado y no deben compararse cifras de tramos distintos. En el tramo comparable (${sinceLabel}–${lastLabel}) la tasa pasa de ${num(wH.surgery_rate[0])} a ${num(wH.surgery_rate[1])} por 1.000 habitantes y los pacientes con más de seis meses de espera de ${num(pct6From)} % a ${num(pct6To)} %; la espera media baja de ${num(wH.surgery_days[0], 0)} a ${num(wH.surgery_days[1], 0)} días. El máximo fue en ${cutLabel(covidPeak.date)}: ${num(covidPeak.value, 0)} días.`}
        legend={[
          { id: "d", label: "Tiempo medio de espera (días)", color: C.blue },
          { id: "r", label: "Pacientes en espera por 1.000 habitantes", color: C.orange },
        ]}
        sources={[S.sisle]}
        notes={[
          ...wait.breaks.surgery.map((b) => `Ruptura ${cutLabel(b.date)}: ${b.label}`),
          rectified ? `${cutLabel(rectified.date)}: ${rectified.rectified.label}` : null,
          "Lista de espera estructural (pacientes que pueden operarse y esperan por organización del sistema, RD 605/2003). Población de referencia: tarjeta sanitaria. Cada valor sale de la fila TOTAL del informe semestral; su página y fila están citadas en el fichero curado etl/data/manual/health/sisle_sns.json del repositorio.",
        ].filter(Boolean)}
        table={semesterTable([
          { id: "days", label: "Días de espera media", unit: "days", points: wait.surgery.mean_days },
          { id: "rate", label: "Pacientes por 1.000 hab.", unit: "per1000", points: wait.surgery.rate_per_1000 },
          { id: "pct", label: "% con más de 6 meses", points: wait.surgery.pct_over_6_months },
          { id: "patients", label: "Pacientes", unit: "count", points: wait.surgery.patients },
        ])}
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Tiempo medio de espera para cirugía
              <span>Días, diciembre de cada año</span>
            </h3>
            <HealthChart series={surgeryDays} unit="days" xMin={2003} xMax={Number(wH.last_cut.slice(0, 4))} yMax={daysMax} height={240} annotations={breakNotes} bands={covidBand} ariaLabel="Tiempo medio de espera quirúrgica en el SNS por tramos comparables" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Pacientes en espera por 1.000 habitantes
              <span>Diciembre de cada año</span>
            </h3>
            <HealthChart series={surgeryRate} unit="per1000" xMin={2003} xMax={Number(wH.last_cut.slice(0, 4))} height={240} annotations={breakNotes} bands={covidBand} ariaLabel="Pacientes en lista de espera quirúrgica por 1.000 habitantes por tramos comparables" />
          </div>
        </div>
      </Figure>

      <Figure
        id="consultas"
        title={`Para ver al especialista esperan ${num(wH.consult_rate[1], 0)} de cada 1.000 habitantes (${num(consultRateChange, 0)} % más que en ${sinceLabel}) y la espera media es de ${num(wH.consult_days[1], 0)} días`}
        dek={`Primera consulta de atención especializada, corte de diciembre. En el tramo comparable la espera media sube de ${num(wH.consult_days[0], 0)} a ${num(wH.consult_days[1], 0)} días; lo que más crece es el número de personas esperando. Mismas rupturas que la lista quirúrgica, y una más en junio de 2025 solo para el porcentaje de citas a más de 60 días.`}
        legend={[
          { id: "d", label: "Tiempo medio de espera (días)", color: C.blue },
          { id: "r", label: "Pacientes en espera por 1.000 habitantes", color: C.orange },
        ]}
        sources={[S.sisle]}
        notes={[
          ...wait.breaks.consultations.filter((b) => !wait.breaks.surgery.some((s) => s.date === b.date && s.label === b.label)).map((b) => `Ruptura ${cutLabel(b.date)}: ${b.label}`),
          "En 2025 el informe deja de publicar la tabla nacional por especialidades; el total sale de la fila TOTAL de la tabla por comunidades, que coincide con la nacional en los años en que existen ambas.",
        ]}
        table={semesterTable([
          { id: "days", label: "Días de espera media", unit: "days", points: wait.consultations.mean_days },
          { id: "rate", label: "Pacientes por 1.000 hab.", unit: "per1000", points: wait.consultations.rate_per_1000 },
          { id: "pct", label: "% con cita a más de 60 días", points: wait.consultations.pct_over_60_days },
        ])}
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Tiempo medio hasta la primera consulta
              <span>Días, diciembre de cada año</span>
            </h3>
            <HealthChart series={consultDays} unit="days" xMin={2006} xMax={Number(wH.last_cut.slice(0, 4))} yMax={daysMax} height={240} annotations={breakNotes} bands={covidBand} ariaLabel="Tiempo medio de espera para primera consulta de especialista por tramos comparables" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Pacientes en espera de consulta por 1.000 habitantes
              <span>Diciembre de cada año</span>
            </h3>
            <HealthChart series={consultRate} unit="per1000" xMin={2006} xMax={Number(wH.last_cut.slice(0, 4))} height={240} annotations={breakNotes} bands={covidBand} ariaLabel="Pacientes esperando primera consulta por 1.000 habitantes por tramos comparables" />
          </div>
        </div>
      </Figure>

      <Figure
        id="comunidades"
        title={`La espera media para las operaciones más comunes va de ${num(fastest.value, 0)} días en ${fastest.name} a ${num(slowest.value, 0)} en ${slowest.name}`}
        dek={`Procesos quirúrgicos seleccionados (cataratas, prótesis de cadera, hernia, varices y otros del RD 605/2003), ${cutLabel(lastRegionCut)}; media del SNS: ${num(nationalSelected, 0)} días. Al lado, el gasto sanitario público por habitante de cada comunidad en ${regionsSpend.year}: en estos datos no hay relación entre gastar más por habitante y esperar menos (correlación de rangos: ${num(spendWaitRho, 2)}).`}
        sources={[S.sisle, S.egsp]}
        notes={[
          "Se usa la lista de procesos seleccionados porque es la que los informes resumen publican por comunidad, con el mismo formato desde 2017.",
          `Gasto: sector Comunidades Autónomas, euros corrientes por habitante${regionsSpend.provisional ? `; ${regionsSpend.year} es provisional` : ""}. No incluye mutualidades de funcionarios ni gasto de la Administración central; Ceuta y Melilla dependen del INGESA y no figuran.`,
          "Las comunidades difieren en edad, dispersión y precios: una correlación entre dos barras no prueba causa.",
        ]}
        table={
          <HealthTable unit="days" caption="Ver la espera media por comunidad, diciembre de cada año" series={regionTable} />
        }
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Espera media, procesos seleccionados
              <span>Días, {cutLabel(lastRegionCut)}</span>
            </h3>
            <Bars rows={regionDays} unit="days" label="Espera media por comunidad" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Gasto sanitario público por habitante
              <span>Euros, {regionsSpend.year}; mismo orden que la espera</span>
            </h3>
            <Bars
              rows={regionDays.map((row) => ({ code: row.code, name: row.name, value: spendByCode.get(row.code) ?? null }))}
              unit="eur"
              label="Gasto sanitario público por habitante y comunidad"
            />
          </div>
        </div>
      </Figure>

      <Figure
        id="medicos"
        title={`España tiene ${num(esDoc, 0)} médicos en ejercicio por 100.000 habitantes, casi como Alemania (${num(deDoc, 0)}) y más que Francia (${num(frDoc, 0)})`}
        dek={`En el total, España no está por debajo de sus pares. En medicina de familia España notifica ${num(esGp)} por 100.000 habitantes en ${docYear}, por encima de Alemania e Italia; desde la última ruptura de su serie (${esGpBreak.year}, ${num(esGpBreak.value)}) apenas cambia. Estas cifras no dicen dónde trabajan (centro de salud, urgencias, hospital) ni cuántos pacientes atiende cada uno.`}
        legend={practisingSeries}
        sources={[S.eurostat]}
        notes={[
          "Eurostat marca la serie de España por categorías con «d» (definición distinta de la estándar; ver sus metadatos). Portugal solo publica médicos en ejercicio desde 2021 y por eso no aparece en la serie larga.",
          `España (médicos en ejercicio ${docs.practising.ES.find((p) => /b/.test(p.status || ""))?.year}, medicina de familia ${esGpBreak.year}), Italia (${docs.practising.IT.find((p) => /b/.test(p.status || ""))?.year ?? "2021"}) y Portugal (2021) tienen rupturas de serie: el salto de Italia en médicos en ejercicio y la caída de Portugal en medicina de familia son cambios de clasificación, no de plantilla. Las líneas se cortan en cada ruptura; Portugal solo aparece en las barras.`,
          "Falta el dato de médicos de familia por paciente asignado del Sistema de Información de Atención Primaria (SIAP) del Ministerio: no se ha incorporado todavía.",
        ]}
        table={
          <HealthTable
            unit="per100k"
            series={[
              ...practisingSeries.map((s) => ({ ...s, id: `p-${s.id}`, label: `${s.label}: en ejercicio` })),
              ...gpSeries.map((s) => ({ ...s, id: `g-${s.id}`, label: `${s.label}: medicina de familia`, digits: 1 })),
            ]}
          />
        }
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Médicos en ejercicio por 100.000 habitantes
              <span>{docYear}</span>
            </h3>
            <Bars rows={docRows} unit="per100k" highlight="ES" label="Médicos en ejercicio por 100.000 habitantes" />
            <HealthChart series={splitAtBreaks(practisingSeries)} unit="per100k" xMin={1980} xMax={docYear} height={220} ariaLabel="Médicos en ejercicio por 100.000 habitantes desde 1980" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Médicos de familia por 100.000 habitantes
              <span>{docYear}</span>
            </h3>
            <Bars rows={gpRows} unit="per100k" highlight="ES" label="Médicos de familia por 100.000 habitantes" />
            <HealthChart series={splitAtBreaks(gpSeries)} unit="per100k" xMin={1990} xMax={docYear} height={220} ariaLabel="Médicos de familia por 100.000 habitantes" />
          </div>
        </div>
      </Figure>

      <Figure
        id="pago-directo"
        title={`Los hogares pagan de su bolsillo el ${num(oopEs)} % del gasto sanitario en España, frente al ${num(oopEu)} % en la UE`}
        dek="Pagos directos: dentista, gafas, copagos de farmacia y consultas privadas sin seguro. Es una parte del gasto que el sistema público no cubre; no incluye las primas de seguros privados, que van aparte."
        legend={oopSeries}
        sources={[S.eurostat, S.oecd]}
        notes={["Porcentaje del gasto sanitario corriente total (SHA 2011, régimen HF3). Eurostat marca «b» (ruptura) en algunos años de Portugal."]}
        table={<HealthTable series={[...oopSeries, { id: "oecd-es", label: "España (OCDE, serie larga)", points: sp.oop_share_esp_long }]} />}
      >
        <HealthChart series={splitAtBreaks(oopSeries)} xMin={2003} xMax={oopYear} height={260} ariaLabel="Pago directo de los hogares en porcentaje del gasto sanitario" />
      </Figure>

      <section className="card vizProse" id="hipotesis" aria-labelledby="hipotesis-title">
        <h2 id="hipotesis-title">¿Se cumple la hipótesis?</h2>
        <p>
          La hipótesis de partida era: <em>España logra una de las esperanzas de vida más altas del mundo con un gasto sanitario medio, pero el acceso empeora: las esperas para operarse y para el especialista llevan años subiendo.</em>
        </p>
        <ul>
          <li>
            <strong>Esperanza de vida: se cumple.</strong> {num(leH.es)} años en {leH.year}, puesto {leH.world_rank.position} de {leH.world_rank.of} en el mundo y {leH.oecd_rank.position}.º de {leH.oecd_rank.of} en la OCDE.
          </li>
          <li>
            <strong>Gasto «medio»: no se cumple, es menor.</strong> El gasto público por habitante es un {num(ppsRatio, 0)} % del de la UE y España está en el puesto {sp.oecd_rank_per_person.position} de {sp.oecd_rank_per_person.of} en la OCDE. A cambio, los hogares pagan de su bolsillo más que la media europea ({num(oopEs)} % frente a {num(oopEu)} %).
          </li>
          <li>
            <strong>Acceso: se cumple a medias.</strong> En la serie comparable ({sinceLabel}–{lastLabel}) crece mucho el número de personas esperando (+{num(surgeryRateChange, 0)} % en cirugía, +{num(consultRateChange, 0)} % en consultas, por habitante) y la espera media para el especialista sube algo ({num(wH.consult_days[0], 0)} → {num(wH.consult_days[1], 0)} días). Pero la espera media para operarse no sube: {num(wH.surgery_days[0], 0)} → {num(wH.surgery_days[1], 0)} días. La impresión de que «todo sube» desde 2003 mezcla tres rupturas de serie.
          </li>
        </ul>
      </section>

      <section className="card vizProse" id="limites" aria-labelledby="limites-title">
        <h2 id="limites-title">Lo que estos datos no pueden decir</h2>
        <ul>
          <li>
            <strong>Causa.</strong> La esperanza de vida depende de la dieta, el tabaco, la renta o el clima tanto como del sistema sanitario. Que España viva mucho gastando menos no prueba que su sanidad sea más eficiente.
          </li>
          <li>
            <strong>Espera media no es espera real.</strong> El tiempo medio de la lista es el de quienes siguen esperando el día del corte, no el que tardó en operarse quien ya salió. Tampoco cuenta la espera previa para entrar en la lista (pruebas diagnósticas) ni la atención primaria.
          </li>
          <li>
            <strong>Cada comunidad cuenta a su manera.</strong> El Ministerio agrega lo que notifica cada comunidad; Andalucía cambió su cómputo en 2018 y Castilla-La Mancha rectificó el dato de diciembre de 2025. No hay auditoría externa de las cifras.
          </li>
          <li>
            <strong>Sin comparación internacional de esperas.</strong> La OCDE publica esperas para algunas operaciones, pero solo de una parte de los países y con definiciones distintas; no se incluyen aquí.
          </li>
          <li>
            <strong>Huecos.</strong> Faltan los cortes de junio de 2004 y 2005 (no publicados en el archivo del Ministerio), los datos de médicos de familia por paciente asignado (SIAP) y la cobertura de seguros privados.
          </li>
        </ul>
      </section>

      <section className="card vizProse" id="metodo" aria-labelledby="metodo-title">
        <h2 id="metodo-title">Método y fuentes</h2>
        <ul>
          <li>
            <strong>Denominador.</strong> Gasto en % del PIB y por habitante a precios constantes de 2020 y en paridad de poder de compra; esperas por 1.000 habitantes; médicos por 100.000. Las cifras absolutas van en las tablas.
          </li>
          <li>
            <strong>Rupturas de serie.</strong> Las listas de espera se dibujan por tramos entre las rupturas que declara el propio Ministerio (2012, 2016, 2018); el gasto de la OCDE marca las suyas (1999, 2003). La serie larga de esperanza de vida y la oficial van en paneles separados.
          </li>
          <li>
            <strong>Ejes.</strong> Todos los ejes empiezan en cero y no hay doble eje; los paneles de un mismo gráfico comparten escala.
          </li>
          <li>
            <strong>Reproducible.</strong> <code>just health-refresh</code> descarga cada API (Eurostat, INE, OCDE vía DBnomics porque sdmx.oecd.org bloquea el acceso por script, Banco Mundial, Our World in Data) y guarda el original. Los informes en PDF del Ministerio (listas de espera desde 2003 y gasto por comunidad) se descargan, se leen con <code>scripts/extract_health_pdfs_es.py</code> citando página y fila de cada valor, y se cargan en SQLite con el contrato de indicadores del proyecto: versión por publicación, comparación con la anterior, SHA-256 del fichero original y marcas de ruptura o rectificación. Desde ahí se generan los <a href={downloads}>datos publicados</a>.
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
