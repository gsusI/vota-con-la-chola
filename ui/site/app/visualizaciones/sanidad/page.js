import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import Figure from "../components/Figure";
import HealthChart from "./HealthChart";
import HealthTable, { Bars } from "./HealthTable";
import { formatHealth } from "./format.mjs";
import Explain from "./Explain";
import Scatter from "./Scatter";
import ConnectedScatter from "./ConnectedScatter";

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

  // 6. Outcomes beyond life expectancy
  const out = data.outcomes;
  const hlyYear = out.hly.ES.at(-1).year;
  const peerRows = (byGeo, year, digits = 1) =>
    ["ES", "EU27_2020", "DE", "FR", "IT", "PT"]
      .map((geo) => ({ code: geo, name: NAMES[geo], value: at(byGeo[geo] || [], year), color: geo === "EU27_2020" ? C.ref : undefined }))
      .filter((row) => row.value != null)
      .sort((a, b) => b.value - a.value);
  const hlyRows = peerRows(out.hly, hlyYear);
  const hlyEs = at(out.hly.ES, hlyYear);
  const hlyEu = at(out.hly.EU27_2020, hlyYear);
  const leForHly = at(out.hly_le.ES, hlyYear);
  const trtYear = out.treatable.ES.at(-1).year;
  const trtEs = at(out.treatable.ES, trtYear);
  const trtEu = at(out.treatable.EU27_2020, trtYear);
  const prvEs = at(out.preventable.ES, trtYear);
  const prvEu = at(out.preventable.EU27_2020, trtYear);
  const trtSeries = [
    ...["DE", "FR", "IT", "PT"].map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, points: out.treatable[geo] })),
    { id: "EU27", label: "Media UE-27", color: C.ref, points: out.treatable.EU27_2020 },
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: out.treatable.ES },
  ];
  const trtRows = peerRows(out.treatable, trtYear);
  const cancerLabels = { breast: "Mama (mujeres)", colon: "Colon", lung: "Pulmón" };
  const cancerRows = (key) =>
    ["ESP", "DEU", "FRA", "ITA", "PRT"]
      .map((code) => ({ code, name: NAMES[code], value: out.cancer_survival[key][code]?.at(-1)?.value }))
      .filter((row) => row.value != null)
      .sort((a, b) => b.value - a.value);

  // 7. Ageing
  const ages = data.ageing;
  const over65Series = [
    ...["DE", "FR", "IT", "PT"].map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, points: ages.over65[geo] })),
    { id: "EU27", label: "Media UE-27", color: C.ref, points: ages.over65.EU27_2020 },
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: ages.over65.ES },
  ];
  const o65Last = ages.over65.ES.at(-1);
  const o65Eu = at(ages.over65.EU27_2020, o65Last.year);
  const o65_2000 = at(ages.over65.ES, 2000);
  const o80Last = ages.over80.ES.at(-1);

  // 8. Workforce beyond doctors
  const staff = data.workforce;
  const ratioRows = Object.entries(staff.nurses_per_doctor)
    .map(([geo, v]) => ({ code: geo, name: `${NAMES[geo]} (${v.year})`, value: v.value }))
    .sort((a, b) => b.value - a.value);
  const nurseRows = Object.entries(staff.nurses_per_doctor)
    .map(([geo, v]) => ({ code: geo, name: `${NAMES[geo]} (${v.year})`, value: v.nurses }))
    .sort((a, b) => b.value - a.value);
  const esRatio = staff.nurses_per_doctor.ES;
  const deRatio = staff.nurses_per_doctor.DE;
  const age55 = staff.doctors_55plus_share;
  const age55Es = age55.ES.at(-1);
  const age55Peak = age55.ES.reduce((best, p) => (p.value > best.value ? p : best), age55.ES[0]);
  const age55Series = [
    ...["DE", "FR", "IT"].filter((geo) => age55[geo]).map((geo) => ({ id: geo, label: NAMES[geo], color: C.peer, points: age55[geo] })),
    { id: "ES", label: "España", color: C.blue, emphasis: true, points: age55.ES },
  ];
  const siap = staff.siap;

  // 9. Private insurance
  const ins = data.insurance;
  const vhiEs = ins.voluntary.ESP;
  const vhiSeries = [
    { id: "PRT", label: "Portugal", color: C.peer, points: ins.voluntary.PRT || [] },
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: vhiEs },
  ];

  // 10. Primary care (Barómetro Sanitario) and perception
  const pc = data.primary_care;
  const pcLast = pc.mean_days.at(-1);
  const quick = pc.same_day.map((p) => ({ year: p.year, value: Math.round((p.value + at(pc.next_day, p.year)) * 10) / 10 }));
  const quickLast = quick.at(-1);
  const noSlotLast = pc.no_slot.at(-1);
  const perc = data.perception;
  const worseLast = perc.worse.at(-1);
  const betterLast = perc.better.at(-1);
  const worseFirst = perc.worse[0];
  const betterFirst = perc.better[0];
  const percSeries = [
    { id: "better", label: "Creen que las listas han mejorado", shortLabel: "Mejoran", color: C.aqua, points: perc.better },
    { id: "worse", label: "Creen que las listas han empeorado", shortLabel: "Empeoran", color: C.orange, emphasis: true, points: perc.worse },
  ];

  // 11. Waits for specific operations (OCDE)
  const intl = data.waits_international;
  const kneeIntl = intl.procedures.CM8154;
  const hipIntl = intl.procedures.CM8151_8153;
  const catIntl = intl.procedures.CM131_138;
  const procColors = { CM8154: C.blue, CM8151_8153: C.orange, CM131_138: C.aqua, CM683_687_689: C.yellow };
  const procSeries = Object.entries(intl.spain_mean_on_list).map(([code, item]) => ({
    id: code, label: item.label, color: procColors[code],
    // The OECD series for Spain come from SISLE and inherit its declared breaks: the line restarts there.
    points: item.points.map((p) => ([2012, 2016, 2018].includes(p.year) ? { ...p, status: "b" } : p)),
  }));
  const procChange = Object.entries(intl.spain_mean_on_list).map(([code, item]) => ({
    code, label: item.label, from: at(item.points, 2018), to: item.points.at(-1),
  }));
  const selected = wait.national_selected_days.filter((p) => p.date.endsWith("-12-31")).map((p) => ({ year: Number(p.date.slice(0, 4)), value: p.value }));
  const selectedChange = pctChange(wH.selected_days[0], wH.selected_days[1]);

  // 13. «El dato mata el relato»
  const story = data.data_vs_story;

  // 12. Regions side by side
  const reg = data.regions;
  const regComplete = reg.rows.filter((row) => row.spend != null);
  const short = (name) => name.replace("Comunidad de ", "").replace("Región de ", "").replace("Comunitat ", "C. ").replace("Castilla-La Mancha", "C.-La Mancha").replace("Castilla y León", "C. y León");
  const regionsUp = reg.rows.filter((row) => row.days_2018 != null && row.days > row.days_2018).length;
  const regionsWith2018 = reg.rows.filter((row) => row.days_2018 != null).length;
  const madrid = reg.rows.find((row) => row.code === "13");
  const leTop = [...reg.rows].sort((a, b) => b.life_expectancy - a.life_expectancy)[0];
  const spendTop = [...regComplete].sort((a, b) => b.spend - a.spend)[0];

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="Sanidad en España: vivir más, gastar menos y más gente esperando"
        summary="Cuánto vivimos y con qué salud, cuánto gastamos frente a Europa, cuánto se espera para operarse, ver al especialista o al médico de familia, y quién atiende. Cada gráfico enlaza su fuente oficial, explica cómo leerlo y qué no dice, marca las rupturas de serie y trae sus datos en tabla."
        actions={[
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/sanidad.json", label: "JSON con procedencia" },
          { href: "#conclusion", label: "¿Se cumple la hipótesis?" },
          { href: "#glosario", label: "Glosario" },
        ]}
      />

      <section className="card vizProse" id="resumen" aria-labelledby="resumen-title">
        <h2 id="resumen-title">Lo esencial, con sus cifras</h2>
        <ol>
          <li>
            <strong>Se vive mucho y con salud.</strong> {num(leH.es)} años de esperanza de vida en {leH.year} ({num(leH.eu27)} en la UE), puesto {leH.world_rank.position} de {leH.world_rank.of} en el mundo, y {num(hlyEs)} años de vida saludable frente a {num(hlyEu)} en la UE. La mortalidad que una buena atención sanitaria puede evitar es de {num(trtEs, 0)} muertes por 100.000 habitantes frente a {num(trtEu, 0)} en la UE.
          </li>
          <li>
            <strong>Con menos gasto público que la media, no con un gasto medio.</strong> {num(spH.pct_gdp_es)} % del PIB frente a {num(spH.pct_gdp_eu27)} % en la UE; por habitante, un {num(ppsRatio, 0)} % de la media europea. Los hogares pagan de su bolsillo el {num(oopEs)} % del gasto ({num(oopEu)} % en la UE).
          </li>
          <li>
            <strong>Cada vez más gente espera.</strong> Desde {sinceLabel}, los pacientes en lista para operarse por 1.000 habitantes suben un {num(surgeryRateChange, 0)} % y los que esperan al especialista un {num(consultRateChange, 0)} %. Siete de cada diez pacientes no consiguen cita con su médico de familia para el mismo día o el siguiente ({num(noSlotLast.value, 0)} % por falta de hueco, {pcLast.year}).
          </li>
          <li>
            <strong>La espera media general para operarse no sube, pero la de las operaciones más comunes sí.</strong> La media de toda la lista pasa de {num(wH.surgery_days[0], 0)} a {num(wH.surgery_days[1], 0)} días; la de los procesos más frecuentes (cataratas, prótesis, hernias…) de {num(wH.selected_days[0], 0)} a {num(wH.selected_days[1], 0)} días (+{num(selectedChange, 0)} %).
          </li>
          <li>
            <strong>Faltan enfermeras más que médicos.</strong> {num(esDoc, 0)} médicos en ejercicio por 100.000 habitantes, como Alemania; pero {num(esRatio.value, 2)} enfermeras por médico frente a {num(deRatio.value, 2)} en Alemania.
          </li>
        </ol>
        <p>
          Índice: <a href="#el-dato-mata-el-relato">el dato frente al relato</a> · <a href="#esperanza-de-vida">esperanza de vida</a> · <a href="#salud-y-mortalidad">vida saludable y mortalidad evitable</a> · <a href="#envejecimiento">envejecimiento</a> · <a href="#gasto-pib">gasto</a> · <a href="#pago-directo">bolsillo y seguros</a> · <a href="#listas-quirurgicas">listas de espera</a> · <a href="#operaciones">operaciones concretas</a> · <a href="#consultas">especialista</a> · <a href="#atencion-primaria">médico de familia</a> · <a href="#percepcion">opinión</a> · <a href="#medicos">médicos</a> · <a href="#enfermeras">enfermeras</a> · <a href="#comunidades">comunidades</a> · <a href="#conclusion">conclusión</a> · <a href="#glosario">glosario</a>
        </p>
      </section>

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
          <span className="vizStat__label">Espera media en las operaciones más comunes</span>
          <span className="vizStat__value">{num(wH.selected_days[1], 0)} días</span>
          <span className="vizStat__note">
            {num(wH.selected_days[0], 0)} en {sinceLabel} (+{num(selectedChange, 0)} %); la media de toda la lista baja de {num(wH.surgery_days[0], 0)} a {num(wH.surgery_days[1], 0)}
          </span>
        </div>
      </section>

      <Figure
        id="el-dato-mata-el-relato"
        title={`España logra la mortalidad tratable de los países que más gastan (${num(story.countries.spain.y, 0)} muertes por 100.000) con un ${num(100 - story.countries.spain.x, 0)} % menos de gasto público por habitante que la media de la UE; dentro de España, el gasto real subió en las ${story.regions.n} comunidades entre ${story.regions.from} y ${story.regions.to} y aun así la espera para las operaciones más comunes creció en ${story.regions.days_up}`}
        dek={`Dos gráficos que se leen juntos. Arriba, los ${story.countries.rows.length} países de la UE: cuanto más gasta un país, menos muertes evitables por atención sanitaria tiene (correlación de rangos ${num(story.countries.rho, 2)}), y España queda muy por debajo de esa pauta: ningún país que gaste menos tiene menos mortalidad tratable, y solo ${story.countries.lower_mortality.length} la tienen menor, todos gastando por encima de la media. Abajo, las comunidades: el gasto real por habitante pasó de ${formatHealth(story.regions.total.x0, "eur")} a ${formatHealth(story.regions.total.x, "eur")} (euros de 2020), y la espera de los procesos seleccionados subió en ${story.regions.days_up} de ${story.regions.n} y los pacientes en lista por habitante en ${story.regions.rate_up}.`}
        sources={[S.eurostat, S.egsp, S.sisle, S.oecd]}
        notes={[
          `Países: gasto público y obligatorio (HF1) en estándar de poder de compra por habitante, como índice UE-27 = 100 en cada año para que la inflación no desplace los puntos; mortalidad tratable estandarizada por edad. Trayectorias ${story.countries.first} → ${story.countries.last} para España, Alemania, Francia, Italia, Portugal y la media UE (cuadrado).`,
          `Comunidades: gasto sanitario público consolidado del sector CCAA (EGSP), deflactado a euros de 2020 con el índice de precios que la OCDE aplica al gasto sanitario español (${story.regions.from}: ${num(story.regions.deflator[story.regions.from], 3)}; ${story.regions.to}: ${num(story.regions.deflator[story.regions.to], 3)}). Espera media de los procesos seleccionados del SISLE en diciembre de cada año; tamaño del círculo = pacientes en esa lista por 1.000 habitantes. Ceuta y Melilla no tienen gasto en la EGSP. ${story.regions.from} es el primer año comparable tras la ruptura de Andalucía.`,
          `Correlación de rangos entre gasto y espera en ${story.regions.to}: ${num(story.regions.rho_level, 2)}; entre la subida del gasto y la subida de la espera: ${num(story.regions.rho_change, 2)} (las comunidades que más subieron el gasto no redujeron más la espera).`,
        ]}
        table={
          <HealthTable
            periodLabel="Lugar"
            keyOf={(p) => p.key}
            labelOf={(k) => k}
            caption="Ver los datos de los dos gráficos en tabla"
            series={[
              { id: "cx", label: `Gasto público por habitante, UE = 100 (${story.countries.last})`, unit: "count", points: story.countries.rows.map((c) => ({ key: c.name, value: c.x })) },
              { id: "cy", label: `Mortalidad tratable por 100.000 (${story.countries.last})`, unit: "count", points: story.countries.rows.map((c) => ({ key: c.name, value: c.y })) },
              { id: "rx0", label: `Gasto CCAA ${story.regions.from}, € de 2020`, unit: "eur", points: story.regions.rows.map((c) => ({ key: c.name, value: c.x0 })) },
              { id: "rx", label: `Gasto CCAA ${story.regions.to}, € de 2020`, unit: "eur", points: story.regions.rows.map((c) => ({ key: c.name, value: c.x })) },
              { id: "ry0", label: `Días dic ${story.regions.from}`, unit: "count", points: story.regions.rows.map((c) => ({ key: c.name, value: c.y0 })) },
              { id: "ry", label: `Días dic ${story.regions.to}`, unit: "count", points: story.regions.rows.map((c) => ({ key: c.name, value: c.y })) },
              { id: "rs", label: `Pacientes por 1.000 dic ${story.regions.to}`, unit: "ratio", digits: 2, points: story.regions.rows.map((c) => ({ key: c.name, value: c.size })) },
            ]}
          />
        }
      >
        <Explain
          shows="Los dos relatos más repetidos puestos a prueba a la vez: si España tiene «la mejor sanidad del mundo» (resultados frente a gasto, entre países) y si «la sanidad se hunde por los recortes» (gasto real frente a esperas, entre comunidades y en el tiempo)."
          read="Cada punto es un lugar; la línea va de su posición inicial (círculo hueco) a la final (círculo lleno). Arriba, más a la izquierda es gastar menos y más abajo, morir menos de causas tratables: la esquina inferior izquierda es la de hacer mucho con poco. Abajo, más a la derecha es más gasto real por habitante y más arriba, más días de espera; un círculo más grande indica más pacientes en lista por habitante."
          not="No prueba causas: la baja mortalidad puede deberse a la dieta, el tabaco o la estructura familiar tanto como al sistema sanitario, y la espera depende de cómo organiza y cuenta cada comunidad su lista. No dice si gastar más acortaría las esperas: dice que gastar más de 2018 a 2024 no lo hizo."
        />
        <ul className="vizLegend" aria-label="Leyenda de color">
          <li><span className="vizLegend__key" style={{ background: "#2a78d6", width: 10, height: 10, borderRadius: 5 }} aria-hidden="true" />España (arriba); Madrid y Cataluña, citadas en el texto (abajo)</li>
          <li><span className="vizLegend__key" style={{ background: "#52514e", width: 10, height: 10, borderRadius: 5 }} aria-hidden="true" />Alemania, Francia, Italia y Portugal (y la media UE, cuadrado)</li>
          <li><span className="vizLegend__key" style={{ background: "#b4b2a9", width: 10, height: 10, borderRadius: 5 }} aria-hidden="true" />Resto de la UE / comunidades</li>
        </ul>
        <ul className="vizLegend" aria-label="Leyenda de marcadores">
          <li><span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, border: "1.5px solid #52514e" }} />Posición inicial</li>
          <li><span aria-hidden="true" style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: "#52514e" }} />Posición final</li>
          <li><span aria-hidden="true" style={{ display: "inline-block", width: 16, height: 16, borderRadius: 8, background: "#b4b2a9" }} />Abajo: más grande = más pacientes en lista por 1.000 habitantes</li>
        </ul>
        <h3 className="vizPanelTitle">
          1. Países de la UE: gasto público por habitante frente a mortalidad tratable, {story.countries.first} → {story.countries.last}
          <span>Gasto en índice UE-27 = 100 (poder de compra); muertes por 100.000, estandarizadas por edad</span>
        </h3>
        <ConnectedScatter
          points={story.countries.rows}
          reference={{ ...story.countries.eu, label: "Media UE = 100" }}
          xLabel="Gasto sanitario público por habitante (UE-27 = 100)"
          yLabel="Mortalidad tratable por 100.000"
          emphasis={["DE", "FR", "IT", "PT"]}
          highlight={["ES"]}
          ariaLabel="Países de la UE: gasto sanitario público por habitante frente a mortalidad tratable, con la trayectoria de España y sus vecinos"
        />
        <h3 className="vizPanelTitle">
          2. Comunidades autónomas: gasto real por habitante frente a días de espera, {story.regions.from} → {story.regions.to}
          <span>Euros de 2020; días de espera media de los procesos quirúrgicos seleccionados en diciembre</span>
        </h3>
        <ConnectedScatter
          points={story.regions.rows.map((row) => ({ ...row, short: short(row.name) }))}
          xLabel="Gasto sanitario público por habitante, euros de 2020"
          yLabel="Días de espera, procesos seleccionados"
          xUnit="eur"
          highlight={["13", "09"]}
          sizeLabel="Tamaño: pacientes por 1.000 habitantes"
          ariaLabel="Comunidades autónomas: gasto real por habitante frente a días de espera, de 2018 a 2024"
        />
        <section aria-label="Qué relatos zanja este gráfico" style={{ display: "grid", gap: 6, marginTop: 8 }}>
          <p style={{ margin: 0 }}>
            <strong>«Tenemos la mejor sanidad del mundo».</strong> En resultados, casi: pocas muertes evitables con poco dinero. En acceso, no: las esperas crecen en casi todas las comunidades.
          </p>
          <p style={{ margin: 0 }}>
            <strong>«La sanidad se hunde por los recortes».</strong> Los recortes fueron reales en 2010–2013 (ver el gasto por habitante), pero entre {story.regions.from} y {story.regions.to} el gasto real subió en las {story.regions.spend_up} comunidades y la espera subió en {story.regions.days_up} de ellas: el problema de acceso de estos años no se explica por menos dinero.
          </p>
          <p style={{ margin: 0 }}>
            <strong>«Basta con gastar más».</strong> Entre países, gastar más va con menos mortalidad tratable; entre comunidades, gastar más no va con esperar menos ({num(story.regions.rho_level, 2)}).
          </p>
          <p style={{ margin: 0 }}>
            <strong>Lo que sigue siendo ambiguo.</strong> Por qué España saca tanto con tan poco (¿sistema, hábitos, salarios sanitarios bajos?), si la demanda creció más deprisa que el gasto (envejecimiento, pacientes que antes no se apuntaban) y si las listas de cada comunidad miden lo mismo. Ningún gráfico con estos datos puede separar esas causas.
          </p>
        </section>
      </Figure>

      <h2 style={{ margin: "26px 4px 0", fontSize: "1.3rem" }}>1. Resultados de salud</h2>
      <p style={{ margin: "0 4px", color: "var(--ink-soft)" }}>¿Vivimos mucho y bien, y cuánto tiene que ver la sanidad?</p>

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
        <Explain
          shows="Cuántos años vive de media quien nace en cada año, en España y en cuatro países vecinos, desde 1925."
          read="La línea azul es España. A la izquierda, la serie larga de investigación; a la derecha, la oficial. Las barras ordenan a los países con mayor esperanza de vida del mundo."
          not="No es cuánto vivirá un bebé de hoy (resume la mortalidad de ese año) ni dice por qué se vive más: el sistema sanitario es solo una de las causas."
        />
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
        id="salud-y-mortalidad"
        title={`Además de vivir más, en España se vive más años con buena salud (${num(hlyEs)} frente a ${num(hlyEu)} en la UE) y mueren menos personas por causas que la atención sanitaria puede evitar (${num(trtEs, 0)} por 100.000 frente a ${num(trtEu, 0)})`}
        dek={`La mortalidad «tratable» cuenta las muertes antes de los 75 años que una atención sanitaria eficaz y a tiempo debería evitar (infartos, algunos cánceres, diabetes…); la «prevenible», las que evitarían la salud pública y los hábitos (tabaco, alcohol, accidentes). España está entre los mejores en ambas: ${num(prvEs, 0)} muertes prevenibles por 100.000 frente a ${num(prvEu, 0)} en la UE.`}
        legend={trtSeries}
        sources={[S.eurostat, S.oecd]}
        notes={[
          "Años de vida saludable: Eurostat, a partir de la pregunta de la encuesta SILC sobre limitación de la actividad por problemas de salud. Es autopercepción: Italia y Alemania difieren mucho más en lo que se declara que en su salud real, así que el ranking entre países es orientativo.",
          "Mortalidad evitable: tasas estandarizadas por edad (población europea de 2013), lista común OCDE/Eurostat.",
          "Supervivencia a cinco años: OCDE con datos del programa CONCORD, pacientes diagnosticados en 2010–2014 (el último periodo comparable publicado). Los intervalos de confianza se solapan entre varios países.",
        ]}
        table={
          <HealthTable
            series={[
              { id: "hly-es", label: "Años saludables, España", unit: "years", points: out.hly.ES },
              { id: "hly-eu", label: "Años saludables, UE-27", unit: "years", points: out.hly.EU27_2020 },
              ...trtSeries.map((s) => ({ ...s, id: `trt-${s.id}`, label: `${s.label}: mortalidad tratable`, unit: "count" })),
            ]}
          />
        }
      >
        <Explain
          shows="Tres medidas de resultado de salud que van más allá de cuántos años se vive: cuántos de ellos sin limitaciones, cuántas muertes evitables hay y cuántos pacientes de cáncer siguen vivos a los cinco años."
          read="Más años saludables y más supervivencia es mejor; menos mortalidad evitable es mejor. España (azul) frente a sus vecinos (gris) y la media de la UE (gris oscuro)."
          not="No separa cuánto se debe al sistema sanitario y cuánto a la dieta, el clima o la renta. Los años saludables dependen de cómo responde cada población a una encuesta."
        />
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Años de vida saludable al nacer
              <span>{hlyYear}; esperanza de vida total en España: {num(leForHly)} años</span>
            </h3>
            <Bars rows={hlyRows} unit="years" digits={1} highlight="ES" label="Años de vida saludable al nacer" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Mortalidad tratable por 100.000 habitantes
              <span>Menos es mejor; tasa estandarizada, {trtYear}</span>
            </h3>
            <Bars rows={trtRows} unit="count" highlight="ES" label="Mortalidad tratable por 100.000 habitantes" />
            <HealthChart series={splitAtBreaks(trtSeries)} unit="count" xMin={out.treatable.ES[0].year} xMax={trtYear} height={200} ariaLabel="Mortalidad tratable por 100.000 habitantes, España y comparables" />
          </div>
        </div>
        <h3 className="vizPanelTitle">
          Supervivencia neta a cinco años del diagnóstico de cáncer, 2010–2014
          <span>% de pacientes; España en azul</span>
        </h3>
        <div>
          {Object.keys(cancerLabels).map((key) => (
            <div key={key} style={{ marginBottom: 10 }}>
              <h3 className="vizPanelTitle" style={{ fontSize: "0.9rem" }}>{cancerLabels[key]}</h3>
              <Bars rows={cancerRows(key)} unit="pct" digits={1} highlight="ESP" max={100} label={`Supervivencia a cinco años, cáncer de ${cancerLabels[key]}`} />
            </div>
          ))}
        </div>
      </Figure>

      <Figure
        id="envejecimiento"
        title={`España envejece, pero aún menos que sus vecinos: el ${num(o65Last.value)} % de la población tiene 65 años o más, frente al ${num(o65Eu)} % en la UE`}
        dek={`En 2000 eran el ${num(o65_2000)} %. Los mayores usan mucho más la sanidad (consultas, ingresos, prótesis, cataratas), así que el envejecimiento empuja la demanda y el gasto aunque no cambie nada más. El ${num(o80Last.value)} % tiene ya 80 años o más (${o80Last.year}). Italia y Portugal, con poblaciones más viejas, gastan por habitante parecido a España.`}
        legend={over65Series}
        sources={[S.eurostat]}
        notes={["Eurostat demo_pjanind, población a 1 de enero. La UE-27 empieza en 2001. Una proyección del gasto por edad (Informe de Envejecimiento de la Comisión Europea) no está aún en la base de datos."]}
        table={<HealthTable series={[...over65Series, { id: "o80", label: "España, 80 años o más", points: ages.over80.ES }]} />}
      >
        <Explain
          shows="Qué parte de la población tiene 65 años o más, desde 1960."
          read="Cuanto más alta la línea, más demanda sanitaria por persona cabe esperar. España (azul) sube, pero por debajo de Italia, Portugal y Alemania."
          not="No dice cuánto más gasta una persona mayor ni si esa demanda está cubierta; tampoco cuánto pesa la inmigración joven, que frena el envejecimiento en España."
        />
        <HealthChart series={splitAtBreaks(over65Series)} xMin={1960} xMax={o65Last.year} height={260} ariaLabel="Población de 65 años o más, porcentaje del total" />
      </Figure>

      <h2 style={{ margin: "26px 4px 0", fontSize: "1.3rem" }}>2. Gasto</h2>
      <p style={{ margin: "0 4px", color: "var(--ink-soft)" }}>¿Cuánto dinero ponemos, entre todos y de nuestro bolsillo?</p>

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
        <Explain
          shows="Qué parte de la riqueza que produce cada país (PIB) se dedica a sanidad pública, desde 1970."
          read="Cada panel compara España (azul) con un país (gris oscuro) y la media OCDE (gris claro), con la misma escala. Las líneas verticales marcan rupturas de serie."
          not="No dice si el dinero se gasta bien ni cuánto pagan los hogares de su bolsillo (eso está más abajo). Un PIB que cae puede subir el porcentaje sin gastar más."
        />
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
        <Explain
          shows="Cuántos euros de gasto sanitario público hay por persona, quitando la inflación y las diferencias de precios entre países."
          read="Izquierda: España frente a vecinos y media OCDE. Derecha: solo España, para ver el recorte de 2010–2013 y la recuperación."
          not="No incluye el gasto privado ni separa sueldos, fármacos o inversión."
        />
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
        id="pago-directo"
        title={`Los hogares pagan de su bolsillo el ${num(oopEs)} % del gasto sanitario en España, frente al ${num(oopEu)} % en la UE, y un ${num(vhiEs.at(-1).value, 0)} % de la población pagaba además un seguro privado en ${vhiEs.at(-1).year}`}
        dek="Pagos directos: dentista, gafas, copagos de farmacia y consultas privadas sin seguro. Es una parte del gasto que el sistema público no cubre; no incluye las primas de seguros privados, que van aparte."
        legend={oopSeries}
        sources={[S.eurostat, S.oecd]}
        notes={["Porcentaje del gasto sanitario corriente total (SHA 2011, régimen HF3). Eurostat marca «b» (ruptura) en algunos años de Portugal."]}
        table={<HealthTable series={[...oopSeries, { id: "oecd-es", label: "España (OCDE, serie larga)", points: sp.oop_share_esp_long }]} />}
      >
        <Explain
          shows="Qué parte del gasto sanitario pagan los hogares directamente de su bolsillo y qué parte de la población tiene seguro privado."
          read="Más alto significa que el sistema público cubre menos o que la gente compra más servicios privados."
          not="No dice si ese gasto es por necesidad (dentista, gafas) o por preferencia (evitar la espera)."
        />
        <HealthChart series={splitAtBreaks(oopSeries)} xMin={2003} xMax={oopYear} height={260} ariaLabel="Pago directo de los hogares en porcentaje del gasto sanitario" />
        <h3 className="vizPanelTitle">
          Población con seguro sanitario privado voluntario
          <span>% de la población (OCDE); España {num(vhiEs.at(-1).value)} % en {vhiEs.at(-1).year}</span>
        </h3>
        <HealthChart series={vhiSeries} xMin={1995} xMax={Math.max(vhiEs.at(-1).year, (ins.voluntary.PRT || [{ year: 0 }]).at(-1).year)} height={200} ariaLabel="Población con seguro sanitario voluntario" />
        <p className="vizFigure__dek">
          En España casi todo el seguro privado es «duplicado»: se paga además de la cobertura pública, sobre todo para esperar menos y elegir médico ({num(ins.duplicate_esp.at(-1)?.value)} % de la población en {ins.duplicate_esp.at(-1)?.year}). La OCDE solo publica este dato para España cada tres años y hasta {vhiEs.at(-1).year}. Alemania y Francia no se comparan aquí porque allí el seguro privado cumple otra función (sustituye o completa al público) y sus series tienen rupturas.
        </p>
      </Figure>

      <h2 style={{ margin: "26px 4px 0", fontSize: "1.3rem" }}>3. Acceso</h2>
      <p style={{ margin: "0 4px", color: "var(--ink-soft)" }}>¿Cuánto hay que esperar para operarse, para el especialista y para el médico de familia?</p>

      <Figure
        id="listas-quirurgicas"
        title={`Desde ${sinceLabel} hay un ${num(surgeryRateChange, 0)} % más de pacientes por habitante esperando una operación; la espera media de toda la lista no sube (${num(wH.surgery_days[1], 0)} días), la de las operaciones más comunes sí (${num(wH.selected_days[0], 0)} → ${num(wH.selected_days[1], 0)})`}
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
        <Explain
          shows="Cuántas personas esperan una operación por cada 1.000 habitantes y cuántos días llevan esperando de media, cada diciembre desde 2003."
          read="Cada tramo de línea es un periodo comparable; entre tramos hubo un cambio de método y no se deben comparar. Solo desde diciembre de 2018 la serie es homogénea."
          not="No es lo que tardó en operarse quien ya salió de la lista; no incluye la espera previa para pruebas ni para el especialista."
        />
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
        id="operaciones"
        title={`En las operaciones más comunes la espera sí ha subido: prótesis de rodilla ${num(procChange.find((p) => p.code === "CM8154").from, 0)} → ${num(procChange.find((p) => p.code === "CM8154").to.value, 0)} días de media entre 2018 y ${procChange[0].to.year}`}
        dek={`Media de días que llevan esperando los pacientes que están en lista, por operación (datos que España envía a la OCDE desde el SISLE). Desde 2018: ${procChange.map((p) => `${p.label.toLowerCase()} ${num(p.from, 0)} → ${num(p.to.value, 0)}`).join("; ")}. Comparada con los ${kneeIntl.rows.length} países que publican esperas, la mediana española desde que el especialista indica la operación está en mitad de la tabla: puesto ${kneeIntl.position} de ${kneeIntl.of} en rodilla (1 = espera más corta), ${hipIntl.position} de ${hipIntl.of} en cadera y ${catIntl.position} de ${catIntl.of} en cataratas.`}
        legend={procSeries}
        sources={[S.oecd, S.sisle]}
        notes={[
          "Alemania y Francia no publican esperas para cirugía programada porque no gestionan listas de espera centralizadas; por eso no aparecen. Cada país mide a su manera (por ejemplo, desde la indicación del especialista o desde la inscripción en la lista).",
          "Las series españolas heredan las rupturas del SISLE (2012, 2016, 2018); solo se comparan valores desde 2018. El pico de 2020 es la Covid.",
          `Procesos seleccionados del SISLE (corte de diciembre): ${num(wH.selected_days[0], 0)} días en ${sinceLabel} y ${num(wH.selected_days[1], 0)} en ${lastLabel}.`,
        ]}
        table={
          <HealthTable
            unit="days"
            series={[
              ...procSeries,
              { id: "sel", label: "Procesos seleccionados SISLE (diciembre)", points: selected },
              ...[kneeIntl, hipIntl, catIntl].map((item, i) => ({ id: `intl-${i}`, label: `${item.label}: mediana España (OCDE)`, points: item.spain })),
            ]}
          />
        }
      >
        <Explain
          shows="Cuántos días llevan esperando de media quienes están en lista para cuatro operaciones frecuentes, y cómo se compara la espera española con otros países."
          read="Una línea que sube significa esperas más largas. En las barras, más larga es peor; España en azul."
          not="La media de quienes esperan no es lo que tardó quien ya se operó; tampoco cuenta la espera para el especialista ni para las pruebas previas."
        />
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              España: días de espera de los pacientes en lista
              <span>Media anual por operación (OCDE/SISLE)</span>
            </h3>
            <HealthChart series={splitAtBreaks(procSeries)} unit="days" xMin={2003} xMax={procChange[0].to.year} height={260} annotations={breakNotes} bands={covidBand} ariaLabel="Días de espera de los pacientes en lista por operación en España" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Procesos seleccionados del SISLE
              <span>Días, diciembre de cada año (serie comparable desde 2018)</span>
            </h3>
            <HealthChart
              series={splitAtBreaks([{ id: "sel", label: "Procesos seleccionados", shortLabel: "Días", color: C.blue, emphasis: true, points: selected.map((p) => (p.year === 2018 ? { ...p, status: "b" } : p)) }])}
              unit="days" xMin={2017} xMax={Number(wH.last_cut.slice(0, 4))} height={260} bands={covidBand}
              ariaLabel="Días de espera media de los procesos quirúrgicos seleccionados"
            />
          </div>
        </div>
        <div>
          {[kneeIntl, hipIntl, catIntl].map((item) => (
            <div key={item.label} style={{ marginBottom: 12 }}>
              <h3 className="vizPanelTitle" style={{ fontSize: "0.9rem" }}>
                {item.label}: mediana de días desde la indicación
                <span>{item.year}; más larga es peor</span>
              </h3>
              <Bars rows={item.rows} unit="days" highlight="ESP" label={`Mediana de días de espera, ${item.label}`} />
            </div>
          ))}
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
        <Explain
          shows="Cuántas personas esperan su primera consulta con un especialista del hospital y cuántos días llevan esperando."
          read="Igual que la lista quirúrgica: tramos separados por rupturas, corte de diciembre."
          not="No mide la espera para pruebas diagnósticas ni las revisiones sucesivas; solo la primera consulta."
        />
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
        id="atencion-primaria"
        title={`Solo el ${num(quickLast.value, 0)} % consigue cita con su médico de familia el mismo día o al siguiente; quienes esperan, esperan ${num(pcLast.value)} días de media`}
        dek={`Encuesta del Barómetro Sanitario a quienes fueron a su médico de familia de la sanidad pública en el último año. El ${num(noSlotLast.value, 0)} % dice que pasó más de un día «porque no había cita antes» (${pc.no_slot[0].value.toLocaleString("es-ES")} % en ${pc.no_slot[0].year}). Cada médico de familia tiene asignadas de media ${formatHealth(siap.poblacion_por_medico_familia.value, "count")} personas y un ${num(siap.pct_medicos_familia_mas_1500.value, 0)} % pasa de 1.500, el umbral que usa el propio SIAP (SIAP, ${siap.poblacion_por_medico_familia.year}).`}
        legend={[
          { id: "q", label: "Atendidos el mismo día o al siguiente (%)", color: C.aqua },
          { id: "n", label: "Esperaron porque no había cita antes (%)", color: C.orange },
        ]}
        sources={[
          { label: `Ministerio de Sanidad y CIS, Barómetro Sanitario${retrieved("minsan_barometro")}`, href: src.minsan_barometro.page },
          { label: "Ministerio de Sanidad, SIAP 2023", href: src.minsan_siap.page },
        ]}
        notes={[
          "La pregunta existe desde 2022; antes el Barómetro no medía la espera para el médico de familia. Es una encuesta (varios miles de entrevistas al año en tres oleadas), con su margen de error.",
          `SIAP: valores impresos en el resumen gráfico de 2023 (página ${siap.poblacion_por_medico_familia.page}: «${siap.poblacion_por_medico_familia.quote}»; página ${siap.pct_medicos_familia_mas_1500.page}: «${siap.pct_medicos_familia_mas_1500.quote}»). El portal interactivo del SIAP no permite una descarga reproducible por script y no hay serie histórica en texto.`,
        ]}
        table={
          <HealthTable
            series={[
              { id: "same", label: "Mismo día (%)", points: pc.same_day },
              { id: "next", label: "Día siguiente (%)", points: pc.next_day },
              { id: "noslot", label: "Sin cita antes (%)", points: pc.no_slot },
              { id: "days", label: "Días de espera de quienes esperaron", unit: "count", digits: 1, points: pc.mean_days.map((p) => ({ ...p })) },
            ]}
          />
        }
      >
        <Explain
          shows="Qué pasa cuando alguien pide cita con su médico de familia: si le atienden enseguida o tiene que esperar, y por qué."
          read="La línea verde (atención inmediata) es baja y no mejora; la naranja (falta de cita) ronda el 70 %."
          not="Son respuestas de los pacientes, no registros de los centros de salud; solo hay cuatro años y no se puede comparar con antes de 2022 ni con otros países."
        />
        <HealthChart
          series={[
            { id: "q", label: "Mismo día o al siguiente", shortLabel: "Al momento", color: C.aqua, points: quick },
            { id: "n", label: "Sin cita antes", shortLabel: "Sin hueco", color: C.orange, emphasis: true, points: pc.no_slot },
          ]}
          xMin={2022} xMax={pcLast.year} yMax={100} height={240}
          ariaLabel="Acceso a cita con el médico de familia según el Barómetro Sanitario"
        />
      </Figure>

      <Figure
        id="percepcion"
        title={`El ${num(worseLast.value, 0)} % cree que las listas de espera empeoraron en el último año; en ${worseFirst.year} lo creía el ${num(worseFirst.value, 0)} %`}
        dek={`Opinión, no medida. Los que creen que mejoraron pasan del ${num(betterFirst.value, 0)} % al ${num(betterLast.value, 0)} %. El pesimismo se dispara con los recortes de 2012–2014 y tras la Covid, y no ha vuelto a los niveles de los 2000, aunque la espera media de toda la lista quirúrgica no haya subido en la serie comparable: lo que la gente percibe se parece más al número de personas esperando y a la espera para el especialista y el médico de familia.`}
        legend={percSeries}
        sources={[{ label: `Ministerio de Sanidad y CIS, Barómetro Sanitario, serie 1998–2025${retrieved("minsan_barometro")}`, href: src.minsan_barometro.page }]}
        notes={["Pregunta 16: «En general, ¿cree Ud. que, durante los últimos doce meses, el problema de las listas de espera ha mejorado, ha empeorado o sigue igual?». No hubo Barómetro en 2001, 2020 y 2021. El resto responde «sigue igual» o no sabe."]}
        table={<HealthTable series={percSeries} />}
      >
        <Explain
          shows="Qué porcentaje de la gente cree que las listas de espera mejoraron o empeoraron en el último año, desde 2000."
          read="Cuando la línea naranja está por encima de la verde, predominan los que ven empeoramiento."
          not="No mide esperas reales y puede reflejar el debate público; tampoco distingue entre cirugía, especialista o atención primaria."
        />
        <HealthChart series={percSeries} xMin={2000} xMax={worseLast.year} height={260} bands={[{ from: 2012, to: 2014, label: "Recortes" }]} ariaLabel="Opinión sobre la evolución de las listas de espera" />
      </Figure>

      <h2 style={{ margin: "26px 4px 0", fontSize: "1.3rem" }}>4. Quién atiende</h2>
      <p style={{ margin: "0 4px", color: "var(--ink-soft)" }}>Médicos, enfermeras y relevo generacional.</p>

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
        <Explain
          shows="Cuántos médicos en ejercicio y cuántos médicos de familia hay por cada 100.000 habitantes, frente a países vecinos."
          read="Más arriba es más médicos por persona. Las líneas se cortan donde un país cambió de definición."
          not="No dice dónde trabajan, con qué carga ni cuántos pacientes ve cada uno (eso lo intenta la sección de atención primaria)."
        />
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
        id="enfermeras"
        title={`España tiene ${num(esRatio.nurses, 0)} enfermeras en ejercicio por 100.000 habitantes, menos de la mitad que Alemania (${num(deRatio.nurses, 0)}): ${num(esRatio.value, 2)} por cada médico`}
        dek={`La escasez de personal sanitario se ve mejor en enfermería que en medicina. Además, el ${num(age55Es.value, 0)} % de los médicos tiene 55 años o más (${age55Es.year}; máximo del ${num(age55Peak.value, 0)} % en ${age55Peak.year}): se jubilarán en la próxima década, una proporción parecida a la de Alemania y Francia y menor que la de Italia.`}
        legend={[
          { id: "ES", label: "España", color: C.blue },
          { id: "peer", label: "Países de comparación", color: C.peer },
        ]}
        sources={[S.eurostat, { label: "Ministerio de Sanidad, SIAP 2023", href: src.minsan_siap.page }]}
        notes={[
          `En atención primaria hay de media ${formatHealth(siap.poblacion_por_enfermera_ap.value, "count")} personas asignadas por enfermera (SIAP ${siap.poblacion_por_enfermera_ap.year}).`,
          "Médicos por edad: Eurostat hlth_rs_phys; cada país notifica su categoría habitual (en ejercicio o profesionalmente activos). Portugal solo tiene datos comparables desde 2021 y no se incluye en la línea.",
          "Las plazas MIR anuales (formación de especialistas) no están todavía en la base de datos: se publican en órdenes del BOE sin serie descargable.",
        ]}
        table={
          <HealthTable
            series={[
              ...Object.entries(staff.nurses).map(([geo, pts]) => ({ id: `n-${geo}`, label: `${NAMES[geo]}: enfermeras por 100.000`, unit: "per100k", points: pts })),
              ...age55Series.map((s) => ({ ...s, id: `a-${s.id}`, label: `${s.label}: % de médicos con 55 años o más` })),
            ]}
          />
        }
      >
        <Explain
          shows="Cuántas enfermeras hay por habitante y por médico, y qué parte de los médicos está cerca de jubilarse."
          read="Barras más largas: más enfermeras. En la línea, cuanto más alta, más médicos cerca de la jubilación."
          not="No dice dónde trabajan ni con qué carga; las definiciones de «en ejercicio» varían algo entre países."
        />
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Enfermeras en ejercicio por 100.000 habitantes
              <span>Último año disponible</span>
            </h3>
            <Bars rows={nurseRows} unit="per100k" highlight="ES" label="Enfermeras por 100.000 habitantes" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Enfermeras por cada médico
              <span>Último año disponible</span>
            </h3>
            <Bars rows={ratioRows} unit="ratio" digits={2} highlight="ES" label="Enfermeras por médico" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Médicos con 55 años o más
              <span>% del total</span>
            </h3>
            <HealthChart series={splitAtBreaks(age55Series)} xMin={2000} xMax={age55Es.year} yMax={50} height={200} ariaLabel="Porcentaje de médicos con 55 años o más" />
          </div>
        </div>
      </Figure>

      <h2 style={{ margin: "26px 4px 0", fontSize: "1.3rem" }}>5. Comunidades autónomas</h2>
      <p style={{ margin: "0 4px", color: "var(--ink-soft)" }}>Gasto, esperas y resultados lado a lado.</p>

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
        <Explain
          shows="La espera para las operaciones más comunes en cada comunidad, al lado de cuánto gasta cada una por habitante y de su esperanza de vida."
          read="Barras: misma ordenación en las dos columnas. Nubes de puntos: si gastar más acortara la espera, los puntos bajarían hacia la derecha; no lo hacen."
          not="Una comparación entre comunidades no prueba causas: difieren en edad, dispersión, precios y en cómo cuentan sus listas."
        />
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
        <h3 className="vizPanelTitle">
          Gastar más no acorta la espera ni alarga la vida: cada punto es una comunidad
          <span>Correlación de rangos entre gasto por habitante y espera: {num(reg.rho_spend_days, 2)}; entre gasto y esperanza de vida: {num(reg.rho_spend_le, 2)} (0 = ninguna relación, 1 = relación perfecta)</span>
        </h3>
        <div className="vizMultiples">
          <div>
            <Scatter
              points={regComplete.map((row) => ({ code: row.code, name: row.name, short: short(row.name), x: row.spend, y: row.days }))}
              xLabel={`Gasto sanitario público por habitante, ${reg.spend_year} (€)`}
              yLabel="Días de espera, procesos seleccionados"
              xUnit="eur"
              yUnit="days"
              highlight={["13", "09"]}
              ariaLabel="Gasto por habitante frente a días de espera por comunidad autónoma"
            />
          </div>
          <div>
            <h3 className="vizPanelTitle" style={{ fontSize: "0.9rem" }}>
              Esperanza de vida por comunidad, {reg.le_year}
              <span>INE; las diferencias son de un par de años</span>
            </h3>
            <Bars
              rows={[...reg.rows].filter((row) => row.life_expectancy != null).sort((a, b) => b.life_expectancy - a.life_expectancy).map((row) => ({ code: row.code, name: row.name, value: row.life_expectancy }))}
              unit="years"
              digits={1}
              highlight="13"
              label="Esperanza de vida por comunidad autónoma"
            />
          </div>
        </div>
        <p className="vizFigure__dek">
          Por qué no hay relación: {madrid ? `${madrid.name} gasta ${formatHealth(madrid.spend, "eur")} por habitante, de los más bajos, y tiene la espera más corta (${num(madrid.days, 0)} días) y la mayor esperanza de vida (${num(madrid.life_expectancy)} años)` : ""}; {spendTop.name}, la que más gasta ({formatHealth(spendTop.spend, "eur")}), espera {num(spendTop.days, 0)} días. El gasto por habitante depende de la dispersión de la población (más centros por persona en zonas rurales), los salarios, la edad y cuánto gasto privado hay; la espera, de cómo se organiza cada servicio (quirófanos de tarde, conciertos con la privada, gestión de la lista) y de cómo cuenta cada comunidad. En {regionsUp} de {regionsWith2018} comunidades la espera de los procesos seleccionados es hoy mayor que en diciembre de 2018.
        </p>
        <details className="vizTable">
          <summary>Ver las comunidades lado a lado</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Comunidad</th>
                  <th scope="col">Gasto por habitante {reg.spend_year}</th>
                  <th scope="col">Días de espera {cutLabel(reg.cut)}</th>
                  <th scope="col">Días dic 2018</th>
                  <th scope="col">Pacientes por 1.000 hab.</th>
                  <th scope="col">Esperanza de vida {reg.le_year}</th>
                  <th scope="col">% que cree que las listas empeoran</th>
                </tr>
              </thead>
              <tbody>
                {[...reg.rows].sort((a, b) => a.name.localeCompare(b.name, "es")).map((row) => (
                  <tr key={row.code}>
                    <td>{row.name}</td>
                    <td>{row.spend != null ? formatHealth(row.spend, "eur") : "sin dato"}</td>
                    <td>{formatHealth(row.days, "count")}</td>
                    <td>{row.days_2018 != null ? formatHealth(row.days_2018, "count") : ""}</td>
                    <td>{num(row.rate, 2)}</td>
                    <td>{row.life_expectancy != null ? num(row.life_expectancy, 2) : ""}</td>
                    <td>{row.worse_pct != null ? num(row.worse_pct) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </Figure>

      <section className="card vizProse" id="conclusion" aria-labelledby="conclusion-title">
        <h2 id="conclusion-title">Conclusión: dónde acierta y dónde falla la hipótesis</h2>
        <p>
          La hipótesis de partida era: <em>España logra una de las esperanzas de vida más altas del mundo con un gasto sanitario medio, pero el acceso empeora: las esperas para operarse y para el especialista llevan años subiendo.</em>
        </p>
        <ul>
          <li>
            <strong>Resultados de salud: se cumple, y más allá de la esperanza de vida.</strong> {num(leH.es)} años ({leH.world_rank.position}.º de {leH.world_rank.of} en el mundo, {leH.oecd_rank.position}.º de {leH.oecd_rank.of} en la OCDE), {num(hlyEs)} años saludables frente a {num(hlyEu)} en la UE y una mortalidad tratable de {num(trtEs, 0)} por 100.000 frente a {num(trtEu, 0)}. La supervivencia al cáncer no destaca: en mama y pulmón queda algo por debajo de los vecinos.
          </li>
          <li>
            <strong>Gasto «medio»: falla. Es bajo.</strong> {num(spH.pct_gdp_es)} % del PIB frente a {num(spH.pct_gdp_eu27)} % en la UE; un {num(ppsRatio, 0)} % del gasto público por habitante europeo; puesto {sp.oecd_rank_per_person.position} de {sp.oecd_rank_per_person.of} en la OCDE. Parte de la diferencia la pagan los hogares de su bolsillo ({num(oopEs)} % frente a {num(oopEu)} %) o con seguros privados duplicados.
          </li>
          <li>
            <strong>Acceso: se cumple en lo esencial, con un matiz.</strong> Crece mucho el número de personas esperando (+{num(surgeryRateChange, 0)} % en cirugía y +{num(consultRateChange, 0)} % en consultas por habitante desde {sinceLabel}), sube la espera para el especialista ({num(wH.consult_days[0], 0)} → {num(wH.consult_days[1], 0)} días) y la de las operaciones más comunes ({num(wH.selected_days[0], 0)} → {num(wH.selected_days[1], 0)} días), y siete de cada diez pacientes no encuentran cita inmediata con su médico de familia. El matiz: la espera media de <em>toda</em> la lista quirúrgica no sube ({num(wH.surgery_days[0], 0)} → {num(wH.surgery_days[1], 0)} días), porque la componen especialidades que se mueven en sentidos distintos.
          </li>
          <li>
            <strong>Lo que no se puede afirmar.</strong> Que las esperas «llevan subiendo desde 2003»: la serie del Ministerio tiene tres rupturas (2012, 2016, 2018) y antes de 2018 no se pueden comparar cifras. Que gastar más acortaría las esperas: entre comunidades no hay relación entre gasto por habitante y espera (correlación {num(reg.rho_spend_days, 2)}).
          </li>
        </ul>
        <p>
          Respecto a la primera versión de esta página: la conclusión sobre el acceso se endurece. La media general de la lista quirúrgica no sube, pero las esperas de las operaciones más frecuentes, del especialista y del médico de familia sí empeoran o siguen siendo largas.
        </p>
      </section>

      <section className="card vizProse" id="glosario" aria-labelledby="glosario-title">
        <h2 id="glosario-title">Glosario</h2>
        <dl style={{ display: "grid", gap: "10px", margin: 0 }}>
          {[
            ["SISLE-SNS", "Sistema de Información sobre Listas de Espera del Sistema Nacional de Salud. Desde 2003 cada comunidad envía al Ministerio sus listas a 30 de junio y 31 de diciembre (Real Decreto 605/2003) y el Ministerio publica un informe semestral."],
            ["Lista de espera estructural", "Pacientes que pueden operarse o ser atendidos y esperan por la organización del sistema. Excluye a quienes aplazan por voluntad propia o por motivos clínicos."],
            ["Procesos seleccionados", "Las operaciones más frecuentes que todas las comunidades notifican por igual: cataratas, prótesis de cadera y rodilla, hernia inguinal, varices, colecistectomía, artroscopia, hallux valgus, amigdalectomía, próstata, túnel carpiano, quiste pilonidal y otras."],
            ["Ruptura de serie", "Cambio de método, cobertura o definición que hace que las cifras de antes y de después no sean comparables. Aquí se dibujan como líneas cortadas o tramos separados, nunca empalmadas."],
            ["Pacientes por 1.000 habitantes", "Personas en lista divididas por la población con tarjeta sanitaria, por mil. Permite comparar años y comunidades con poblaciones distintas."],
            ["Media y mediana de espera", "La media suma todos los días y divide por los pacientes: unos pocos casos muy largos la suben. La mediana es el valor del paciente del medio: la mitad espera menos y la otra mitad más."],
            ["PPS y PPA", "Estándar de poder de compra (Eurostat) y paridad de poder adquisitivo (OCDE): convierten euros de distintos países a una unidad que compra lo mismo en todos, para comparar gasto real."],
            ["Precios constantes", "Cifras corregidas por la inflación: un euro de 1990 y uno de 2024 valen lo mismo en la gráfica (aquí, euros de 2020)."],
            ["Gasto público y obligatorio (HF1)", "Gasto sanitario que pagan las administraciones y los seguros obligatorios, incluidas las mutualidades de funcionarios."],
            ["Gasto de bolsillo (HF3)", "Lo que pagan directamente los hogares sin reembolso: dentista, gafas, copagos de farmacia, consultas privadas sin seguro. No incluye las primas de seguros."],
            ["Seguro duplicado", "Seguro privado que se paga además de tener derecho a la sanidad pública, para usar médicos y hospitales privados."],
            ["Mortalidad tratable y prevenible", "Muertes antes de los 75 años que una atención sanitaria eficaz (tratable) o la prevención y la salud pública (prevenible) deberían evitar, según una lista común de la OCDE y Eurostat."],
            ["Años de vida saludable", "Años que se espera vivir sin limitaciones por problemas de salud, según lo que declara la población en una encuesta europea."],
            ["Tarjeta sanitaria (TSI)", "Tarjeta individual del sistema público; el número de tarjetas asignadas a un médico de familia es su «cupo»."],
            ["Correlación de rangos", "Mide si dos variables suben juntas al ordenar las comunidades de mayor a menor: 1 es relación perfecta, 0 ninguna y −1 relación inversa."],
          ].map(([term, text]) => (
            <div key={term}>
              <dt style={{ fontWeight: 700 }}>{term}</dt>
              <dd style={{ margin: 0 }}>{text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="card vizProse" id="limites" aria-labelledby="limites-title">
        <h2 id="limites-title">Lo que estos datos no pueden decir</h2>
        <ul>
          <li>
            <strong>Causa.</strong> La esperanza de vida depende de la dieta, el tabaco, la renta o el clima tanto como del sistema sanitario. Que España viva mucho gastando menos no prueba que su sanidad sea más eficiente.
          </li>
          <li>
            <strong>Espera media no es espera real.</strong> El tiempo medio de la lista es el de quienes siguen esperando el día del corte, no el que tardó en operarse quien ya salió. Tampoco cuenta la espera previa para entrar en la lista (pruebas diagnósticas).
          </li>
          <li>
            <strong>Cada comunidad cuenta a su manera.</strong> El Ministerio agrega lo que notifica cada comunidad; Andalucía cambió su cómputo en 2018 y Castilla-La Mancha rectificó el dato de diciembre de 2025. No hay auditoría externa de las cifras.
          </li>
          <li>
            <strong>Comparación internacional parcial.</strong> Solo una docena de países publica esperas en la OCDE, cada uno con su método; Alemania y Francia no.
          </li>
          <li>
            <strong>Huecos.</strong> No existen informes del SISLE de junio de 2004 y de junio de 2005: el Ministerio no los publicó por separado (el informe de diciembre de 2005 solo da esas cifras en un gráfico y sobre una serie revisada, así que no se incluyen). La serie del SIAP (médicos de familia por paciente) solo se puede consultar en un visor interactivo; aquí van los valores de 2023 impresos en su resumen. Faltan las plazas MIR por año y el gasto sanitario por edad.
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
            <strong>Reproducible.</strong> <code>just health-refresh</code> descarga cada API (Eurostat, INE, OCDE vía DBnomics porque sdmx.oecd.org bloquea el acceso por script, Banco Mundial, Our World in Data) y las hojas del Barómetro Sanitario, y guarda el original; cada valor del Barómetro apunta a su celda. Los informes en PDF del Ministerio (listas de espera desde 2003 y gasto por comunidad) se descargan, se leen con <code>scripts/extract_health_pdfs_es.py</code> citando página y fila de cada valor, y se cargan en SQLite con el contrato de indicadores del proyecto: versión por publicación, comparación con la anterior, SHA-256 del fichero original y marcas de ruptura o rectificación. Desde ahí se generan los <a href={downloads}>datos publicados</a>.
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
