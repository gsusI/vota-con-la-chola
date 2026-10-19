import { readPublicJson } from "../../static-snapshot.mjs";
import { StaticRouteHero } from "../../static-route-components";
import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure, { SeriesTable } from "../components/Figure";
import { HypothesisCard, LimitsCard, MethodCard, RatioDecadesTable, WedgeBars } from "./sections";

export const metadata = {
  title: "El paro en España: ¿estructural o cíclico? | Vota Con La Chola",
  description:
    "Paro desde 1960 frente a Europa, paro juvenil, temporalidad, productividad por hora y cuña fiscal, con fuentes oficiales, rupturas de serie y datos descargables.",
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
  ESP: "España",
  EU27: "UE-27",
  DEU: "Alemania",
  DEU_W: "Alemania Occidental (RFA)",
  FRA: "Francia",
  ITA: "Italia",
  PRT: "Portugal",
  OECD_REP: "Media OCDE",
  EU22OECD: "Media UE en la OCDE",
};
const PEERS = ["DEU", "FRA", "ITA", "PRT"];

const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const pct = (value, digits = 1) => `${num(value, digits)} %`;

function constant(value, from, to) {
  const out = [];
  for (let year = from; year <= to; year += 1) out.push({ year, value });
  return out;
}

// Peers in gray are drawn first so the highlighted series stay on top.
function back(series) {
  return [...series.filter((s) => s.color === C.peer), ...series.filter((s) => s.color !== C.peer)];
}

function eventNotes(events, ids) {
  return events.filter((e) => ids.includes(e.id));
}

export default function EmpleoPage() {
  const data = readPublicJson("visualizaciones/data/empleo.json", null);
  if (!data) throw new Error("Missing visualizaciones/data/empleo.json");
  const h = data.headline;
  const src = data.sources;
  const retrieved = (id) => String(src[id]?.retrieved_at || "").slice(0, 10);
  const S = {
    ameco: { label: `Comisión Europea, AMECO (vía DBnomics, consultado ${retrieved("ameco_dbnomics")})`, href: src.ameco_dbnomics.page },
    ine: { label: `INE, EPA (consultado ${retrieved("ine_epa_tempus")})`, href: src.ine_epa_tempus.page },
    eurostat: (dataset) => ({
      label: `Eurostat, ${dataset} (consultado ${retrieved("eurostat_sdmx")})`,
      href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table`,
    }),
    wages: { label: `OCDE, Taxing Wages (vía DBnomics, consultado ${retrieved("oecd_taxing_wages")})`, href: src.oecd_taxing_wages.page },
    pdb: { label: `OCDE, Productivity Database (vía DBnomics, consultado ${retrieved("oecd_productivity")})`, href: src.oecd_productivity.page },
  };
  const downloads = "/visualizaciones/data/empleo.csv";
  const events = data.events || [];
  const evYear = (id) => events.find((e) => e.id === id)?.year;
  const epaBreaks = events
    .filter((e) => e.kind === "series_break")
    .map((e) => ({ year: e.year, label: `EPA ${e.year}`, row: 1 }));
  const reform = (id, label, row = 0) => (evYear(id) ? [{ year: evYear(id), label, row }] : []);

  // 1. Unemployment since 1960
  const u = data.unemployment;
  const longRun = [
    { id: "ESP", label: "España (AMECO, desde la EPA)", shortLabel: "España", color: C.blue, emphasis: true, points: u.amecos.ESP },
    { id: "DU15", label: "UE-15 con la RFA (1971–1991)", shortLabel: "UE-15 (RFA)", color: C.yellow, points: u.amecos.DU15 },
    { id: "EU15", label: "UE-15 (desde 1991)", shortLabel: "UE-15", color: C.ref, points: u.amecos.EU15 },
    { id: "EU27", label: "UE-27 (desde 1997)", shortLabel: "UE-27", color: C.orange, points: u.amecos.EU27 },
  ];
  const epaRow = { id: "EPA", label: "España, EPA del INE (media de los cuatro trimestres)", points: u.epa_annual };
  const yMaxUne = Math.ceil(Math.max(...u.amecos.ESP.map((p) => p.value)) / 5) * 5;

  // 2. Ratio
  const ratioSeries = [
    { id: "r_DU15", label: "España frente a la UE-15 con la RFA", shortLabel: "vs UE-15 (RFA)", color: C.yellow, points: data.ratio_es_europe.DU15 },
    { id: "r_EU15", label: "España frente a la UE-15", shortLabel: "vs UE-15", color: C.blue, emphasis: true, points: data.ratio_es_europe.EU15 },
    { id: "r_EU27", label: "España frente a la UE-27", shortLabel: "vs UE-27", color: C.orange, points: data.ratio_es_europe.EU27 },
  ];
  const refLines = [
    { id: "eq", label: "Igual que Europa (100)", shortLabel: "Igual", color: C.peer, points: constant(100, 1971, h.last_year) },
    { id: "double", label: "El doble que Europa (200)", shortLabel: "El doble", color: C.peer, points: constant(200, 1971, h.last_year) },
  ];

  // 3. NAWRU
  const n = data.nawru;
  const nawru = [
    { id: "es_actual", label: "España, paro observado", shortLabel: "Paro", color: C.blue, emphasis: true, points: u.amecos.ESP.filter((p) => p.year >= 1965) },
    { id: "es_nawru", label: "España, paro estructural estimado (NAWRU)", shortLabel: "NAWRU España", color: C.orange, points: n.ESP },
    { id: "du15_nawru", label: "UE-15 con la RFA, NAWRU (1972–1991)", shortLabel: "NAWRU UE-15 (RFA)", color: C.yellow, points: n.DU15 },
    { id: "eu15_nawru", label: "UE-15, NAWRU (desde 1991)", shortLabel: "NAWRU UE-15", color: C.ref, points: n.EU15 },
  ];

  // 4. Peers
  const peerMax = Math.max(
    ...u.amecos.ESP.map((p) => p.value),
    ...Object.values(u.peers).flatMap((rows) => rows.map((p) => p.value)),
  );
  const m = h.mean_since_1980;

  // 5. Youth
  const y = data.youth;
  const youth = [
    { id: "es_h", label: "España (serie histórica 1993–2020)", shortLabel: "España, hist.", color: C.aqua, noEndLabel: true, points: y.historical.ESP },
    { id: "eu_h", label: "UE-27 (serie histórica)", shortLabel: "UE-27, hist.", color: C.yellow, noEndLabel: true, points: y.historical.EU27 },
    { id: "es", label: "España (serie vigente, desde 2003)", shortLabel: "España", color: C.blue, emphasis: true, points: y.current.ESP },
    { id: "eu", label: "UE-27 (serie vigente)", shortLabel: "UE-27", color: C.ref, points: y.current.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: y.current[area] })),
  ];

  // 6. Temporary employment
  const t = data.temporary;
  const tempMax = Math.ceil(Math.max(...Object.values(t.eurostat).flatMap((rows) => rows.map((p) => p.value))) / 5) * 5;
  const temp = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: t.eurostat.ESP },
    { id: "EU27", label: "UE-27", color: C.ref, points: t.eurostat.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: t.eurostat[area] })),
  ];
  const epaContracts = [
    { id: "temporal", label: "Con contrato temporal", shortLabel: "Temporales", color: C.blue, emphasis: true, points: t.epa_temporal_share },
    { id: "discontinuo", label: "Fijos discontinuos (indefinidos)", shortLabel: "Fijos discontinuos", color: C.orange, points: t.epa_discontinuo_share },
  ];
  const breakYears = Object.entries(t.eurostat_es_flags || {})
    .filter(([, flag]) => flag.includes("b"))
    .map(([year]) => year);
  const reformMarks = [...reform("reform_2012", "Reforma 2012"), ...reform("reform_2022", "Reforma 2022")];
  const tempDrop = h.temp_es_2021 - h.temp_es_last;
  const discontRise = h.discont_last - h.discont_2021;

  // 7. Productivity
  const p = data.productivity;
  const g = h.productivity_growth_pct;
  const prod = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: p.index_1995.ESP },
    { id: "EU27", label: "UE-27", color: C.ref, points: p.index_1995.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: p.index_1995[area] })),
  ];
  const level = [
    { id: "ESP", label: "España", color: C.blue, emphasis: true, points: p.level_vs_eu27.ESP },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: p.level_vs_eu27[area] })),
    { id: "eu", label: "Media de la UE-27 = 100", shortLabel: "UE-27", color: C.ref, points: constant(100, h.productivity_base, h.level_last_year) },
  ];
  const lvFirst = h.level_vs_eu_first.ESP;
  const lvLast = h.level_vs_eu_last.ESP;
  const peersSlower = Object.entries(g).filter(([area, value]) => area !== "ESP" && value < g.ESP).map(([area]) => NAMES[area]);

  // 8. Tax wedge
  const w = data.tax_wedge;
  const wedgeOrder = ["DEU", "FRA", "ITA", "PRT", "OECD_REP", "EU22OECD", "ESP"];
  const wedge = wedgeOrder.map((area) => ({
    id: area,
    label: NAMES[area],
    color: area === "ESP" ? C.blue : area === "OECD_REP" ? C.ref : area === "EU22OECD" ? C.orange : C.peer,
    emphasis: area === "ESP",
    points: w.aw100[area],
  }));
  const wl = h.wedge_last;
  const wf = h.wedge_first;

  // 9. Employment rate
  const e = data.employment_rate;
  const emp = [
    { id: "es_h", label: "España (serie histórica 1993–2020)", shortLabel: "España, hist.", color: C.aqua, noEndLabel: true, points: e.historical.ESP },
    { id: "eu_h", label: "UE-27 (serie histórica)", shortLabel: "UE-27, hist.", color: C.yellow, noEndLabel: true, points: e.historical.EU27 },
    { id: "es", label: "España (serie vigente)", shortLabel: "España", color: C.blue, emphasis: true, points: e.current.ESP },
    { id: "eu", label: "UE-27 (serie vigente)", shortLabel: "UE-27", color: C.ref, points: e.current.EU27 },
    ...PEERS.map((area) => ({ id: area, label: NAMES[area], color: C.peer, points: e.current[area] })),
  ];

  const euEmp = new Map(e.current.EU27.map((pt) => [pt.year, pt.value]));
  const empGaps = e.current.ESP.filter((pt) => euEmp.has(pt.year)).map((pt) => ({ year: pt.year, gap: euEmp.get(pt.year) - pt.value }));
  const empGapMax = empGaps.reduce((a, b) => (b.gap > a.gap ? b : a));
  const empGapLast = empGaps.at(-1);

  return (
    <main className="shell vizArticle">
      <StaticRouteHero
        eyebrow="Visualizaciones · datos públicos"
        title="El paro en España: ¿estructural o cíclico?"
        summary="Ponemos a prueba una hipótesis: que el paro español es estructural, casi el doble del europeo en cada ciclo desde 1980, y que la productividad por hora apenas ha crecido desde 1995. Publicamos también lo que la contradice."
        actions={[
          { href: downloads, label: "Descargar datos (CSV)" },
          { href: "/visualizaciones/data/empleo.json", label: "JSON con procedencia" },
          { href: "#metodo", label: "Método y fuentes" },
        ]}
      />

      <section className="vizStats" aria-label="Cifras clave">
        <div className="card vizStat">
          <span className="vizStat__label">Paro en {h.last_year}</span>
          <span className="vizStat__value">{pct(h.es_last)}</span>
          <span className="vizStat__note">
            frente al {pct(h.eu27_last)} de la UE-27: {num(h.ratio_eu27_last, 2)} veces
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Paro de España sobre el europeo desde {h.hypothesis_from}</span>
          <span className="vizStat__value">×{num(h.ratio_mean_since, 2)}</span>
          <span className="vizStat__note">
            de media; por encima de 1,5 veces en {h.years_ratio_ge_1_5} de {h.years_since} años (UE-15)
          </span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">
            Productividad por hora, {h.productivity_base}–{h.productivity_last}
          </span>
          <span className="vizStat__value">+{num(g.ESP)} %</span>
          <span className="vizStat__note">frente a +{num(g.EU27)} % en la UE-27 (en volumen)</span>
        </div>
        <div className="card vizStat">
          <span className="vizStat__label">Asalariados temporales</span>
          <span className="vizStat__value">{pct(h.temp_es_last)}</span>
          <span className="vizStat__note">
            {pct(h.temp_es_2021)} en 2021; fijos discontinuos: {num(h.discont_k_2021, 0)} mil → {num(h.discont_k_last, 0)} mil
          </span>
        </div>
      </section>

      <HypothesisCard h={data.headline} />

      <Figure
        id="paro"
        title={`Desde ${h.hypothesis_from}, el paro de España ha sido de media ${num(h.ratio_mean_since)} veces el europeo`}
        dek={`España tuvo un paro parecido al europeo hasta mediados de los setenta (${pct(h.es_mean_1960_1974)} de media en 1960–1974). Desde 1980 la distancia solo se estrechó en el auge previo a 2008: picos del ${pct(h.peaks.max_1980s.value, 1)} (${h.peaks.max_1980s.year}), ${pct(h.peaks.max_1990s.value)} (${h.peaks.max_1990s.year}) y ${pct(h.peaks.max_crisis.value)} (${h.peaks.max_crisis.year}); mínimo del ${pct(h.peaks.min_pre_crisis.value)} en ${h.peaks.min_pre_crisis.year}. La media europea cambia de cobertura dos veces: las tres series se muestran sin empalmar.`}
        legend={longRun}
        sources={[S.ameco, S.ine]}
        notes={[
          `AMECO homogeneiza la EPA a lo largo del tiempo; desde 2002 coincide con la EPA del INE (en la tabla) con una diferencia máxima de ${num(h.epa_vs_ameco_max_gap, 2)} puntos. La EPA cambió de definición o de cuestionario en 2001, 2005 y 2021 (marcadas).`,
          "Años 60 y primeros 70: la emigración a Europa y el peso del campo rebajaban el paro medido; no es comparable con una economía sin esa válvula.",
          `Último año observado: ${h.last_year}. Las previsiones de AMECO para años posteriores se descartan.`,
        ]}
        table={<SeriesTable series={[...longRun.slice(0, 1), epaRow, ...longRun.slice(1)]} />}
      >
        <TimeSeriesChart
          series={longRun}
          xMin={h.first_year}
          xMax={h.last_year}
          yMax={yMaxUne}
          annotations={[...reform("reform_1984_temporary_contracts", "Contratos temporales (1984)"), ...epaBreaks]}
          ariaLabel="Tasa de paro de España y de la media europea desde 1960"
        />
      </Figure>

      <Figure
        id="ratio"
        title={`El paro español superó 1,5 veces el europeo en ${h.years_ratio_ge_1_5} de los ${h.years_since} años desde ${h.hypothesis_from}, y el doble en ${h.years_ratio_ge_2}`}
        dek={`Paro de España con la media europea = 100. Por década: ${data.ratio_decades
          .map((d) => `${d.decade}s ×${num(d.mean_ratio, 2)}`)
          .join(", ")}. La excepción es el auge previo a 2008: en ${h.ratio_lowest_since.year} el paro español fue solo ${num(h.ratio_lowest_since.value, 2)} veces el de la UE-15. El máximo, ${num(h.ratio_highest.value, 2)} veces, llegó en ${h.ratio_highest.year}.`}
        legend={ratioSeries}
        sources={[S.ameco]}
        notes={[
          "Cociente calculado por nosotros con las tasas de AMECO del mismo año. Cada línea usa una media europea distinta; donde se solapan se ve cuánto cambia el resultado según el grupo de comparación.",
        ]}
        table={<RatioDecadesTable decades={data.ratio_decades} series={ratioSeries} />}
      >
        <TimeSeriesChart
          series={[...refLines, ...ratioSeries]}
          unit="count"
          xMin={1971}
          xMax={h.last_year}
          annotations={reform("reform_1984_temporary_contracts", "1984")}
          ariaLabel="Paro de España en relación con la media europea, Europa = 100"
        />
      </Figure>

      <Figure
        id="estructural"
        title={`La Comisión Europea estima que el paro estructural de España no ha bajado del ${pct(h.nawru_min_since.value)} desde ${h.hypothesis_from}`}
        dek={`El NAWRU es el paro que no acelera los salarios según el modelo de la Comisión: en ${h.last_year}, ${pct(h.nawru_last)} en España frente a ${pct(h.nawru_eu15_last)} en la UE-15 (${num(h.nawru_ratio_mean_since, 2)} veces de media desde ${h.hypothesis_from}). Pero la parte cíclica también es enorme: el paro observado quedó ${num(-h.gap_min.value)} puntos por debajo del estructural en ${h.gap_min.year} y ${num(h.gap_max.value)} puntos por encima en ${h.gap_max.year}.`}
        legend={nawru}
        sources={[S.ameco]}
        notes={[
          "El NAWRU es una estimación de modelo, no una observación: se revisa con cada previsión y tiende a seguir al paro observado (histéresis), por lo que puede exagerar lo «estructural» tras una crisis larga.",
        ]}
        table={<SeriesTable series={nawru} />}
      >
        <TimeSeriesChart series={nawru} xMin={1965} xMax={h.last_year} yMax={yMaxUne} ariaLabel="Paro observado y paro estructural estimado (NAWRU)" />
      </Figure>

      <Figure
        id="paises"
        title={`Desde ${h.hypothesis_from}, el paro medio de España (${pct(m.ESP)}) casi duplica el de Italia (${pct(m.ITA)}), Francia (${pct(m.FRA)}) y Portugal (${pct(m.PRT)})`}
        dek={`Alemania: ${pct(m.DEU)}. Cada país en su panel, con la misma escala vertical. Antes de 1975 España no tenía más paro que sus vecinos.`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "other", label: "País de comparación", color: C.ref },
        ]}
        sources={[S.ameco]}
        notes={["Alemania: hasta 1991, Alemania Occidental (RFA); desde 1991, Alemania unificada. Se muestran como dos tramos."]}
        table={
          <SeriesTable
            series={[
              { id: "ESP", label: "España", points: u.amecos.ESP },
              { id: "DEU_W", label: NAMES.DEU_W, points: u.peers.DEU_W },
              ...PEERS.map((area) => ({ id: area, label: NAMES[area], points: u.peers[area] })),
            ]}
          />
        }
      >
        <div className="vizMultiples">
          {PEERS.map((area) => (
            <div key={area}>
              <h3 className="vizPanelTitle">
                España frente a {NAMES[area]}
                <span>
                  Media desde {h.hypothesis_from}: {pct(m.ESP)} frente a {pct(m[area])}
                </span>
              </h3>
              <TimeSeriesChart
                series={[
                  ...(area === "DEU" ? [{ id: "DEU_W", label: "RFA", color: C.ref, points: u.peers.DEU_W }] : []),
                  { id: area, label: NAMES[area], color: C.ref, points: u.peers[area] },
                  { id: "ESP", label: "España", color: C.blue, emphasis: true, points: u.amecos.ESP },
                ]}
                xMin={h.first_year}
                xMax={h.last_year}
                yMax={peerMax}
                height={210}
                ariaLabel={`Tasa de paro de España frente a ${NAMES[area]}`}
              />
            </div>
          ))}
        </div>
      </Figure>

      <Figure
        id="jovenes"
        title={`El paro de los jóvenes activos es del ${pct(h.youth_es_last)} en España y del ${pct(h.youth_eu_last)} en la UE-27`}
        dek={`Menores de 25 años (15–24). Desde 2003 ha sido de media ${num(h.youth_ratio_mean, 2)} veces el europeo y llegó al ${pct(h.youth_es_max.value)} en ${h.youth_es_max.year}. La serie histórica de Eurostat (cerrada en 2020) y la vigente se solapan para que se vea la ruptura.`}
        legend={youth.filter((s) => s.color !== C.peer).concat([{ id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer }])}
        sources={[S.eurostat("une_rt_a"), S.eurostat("une_rt_a_h")]}
        notes={[
          "La tasa se calcula sobre los jóvenes activos (que trabajan o buscan empleo), no sobre todos los jóvenes: muchos estudian. Un 25 % de paro juvenil no significa que uno de cada cuatro jóvenes esté parado.",
        ]}
        table={<SeriesTable series={youth} />}
      >
        <TimeSeriesChart series={back(youth)} xMin={1993} xMax={h.last_year} annotations={epaBreaks.filter((b) => b.year >= 1993)} ariaLabel="Paro juvenil, España frente a la UE" />
      </Figure>

      <Figure
        id="temporalidad"
        title={`La temporalidad bajó del ${pct(h.temp_es_2021)} al ${pct(h.temp_es_last)} tras la reforma de 2022, y los fijos discontinuos casi se duplicaron`}
        dek={`Tras décadas con la temporalidad más alta de este grupo de países (máximo del ${pct(h.temp_es_max.value)} en ${h.temp_es_max.year}), España queda en ${h.temp_last_year} a ${num(h.temp_es_last - h.temp_eu_last)} puntos de la UE-27 (${pct(h.temp_eu_last)}). La caída de ${num(tempDrop)} puntos desde 2021 no se explica solo por el cambio de etiqueta: los fijos discontinuos, que cuentan como indefinidos, subieron ${num(discontRise)} puntos (de ${num(h.discont_k_2021, 0)} mil a ${num(h.discont_k_last, 0)} mil asalariados, según la EPA).`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "EU27", label: "UE-27", color: C.ref },
          { id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer },
        ]}
        sources={[S.eurostat("lfsa_etpgan"), S.ine]}
        notes={[
          "Fijos discontinuos: contrato indefinido para trabajos que se repiten de forma intermitente (campañas, temporadas). Entre llamamientos no trabajan ni cobran salario, así que un contrato indefinido puede esconder la misma intermitencia que antes tenía un temporal. La EPA no mide cuántos días al año trabaja cada uno.",
          breakYears.length ? `Eurostat marca ruptura de serie para España en ${breakYears.join(", ")}; desde 2021 la definición difiere de la anterior (reglamento IESS).` : "",
          "Eurostat: asalariados de 15 a 64 años. INE: asalariados de 16 y más años, media de los cuatro trimestres de cada año completo.",
        ].filter(Boolean)}
        table={<SeriesTable series={[...temp, ...epaContracts.map((s) => ({ ...s, label: `EPA (INE): ${s.label}` }))]} />}
      >
        <div className="vizMultiples">
          <div>
            <h3 className="vizPanelTitle">
              Asalariados con contrato temporal
              <span>% del total de asalariados, Eurostat</span>
            </h3>
            <TimeSeriesChart series={back(temp)} xMin={1995} xMax={h.last_year} yMax={tempMax} height={260} annotations={reformMarks} ariaLabel="Porcentaje de asalariados temporales, España frente a la UE" />
          </div>
          <div>
            <h3 className="vizPanelTitle">
              Temporales y fijos discontinuos en España
              <span>% del total de asalariados, EPA del INE</span>
            </h3>
            <TimeSeriesChart series={epaContracts} xMin={2002} xMax={h.last_year} yMax={tempMax} height={260} annotations={reformMarks} ariaLabel="Temporales y fijos discontinuos en España, porcentaje de asalariados" />
          </div>
        </div>
      </Figure>

      <Figure
        id="productividad"
        title={`Desde ${h.productivity_base}, la productividad por hora creció un ${num(g.ESP)} % en España y un ${num(g.EU27)} % en la UE-27`}
        dek={`PIB en volumen por hora trabajada, ${h.productivity_base} = 100. Alemania +${num(g.DEU)} %, Portugal +${num(g.PRT)} %, Francia +${num(g.FRA)} %. ${
          peersSlower.length ? `Solo ${peersSlower.join(" y ")} creció menos (+${num(g.ITA)} %).` : ""
        }`}
        legend={[
          { id: "ESP", label: "España", color: C.blue },
          { id: "EU27", label: "UE-27", color: C.ref },
          { id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer },
        ]}
        sources={[S.eurostat("nama_10_lp_ulc")]}
        notes={[
          "Índice reescalado por nosotros a 1995 = 100 desde el índice 2015 = 100 de Eurostat (productividad real por hora, RLPR_HW).",
          "La media de la UE-27 incluye a los países del Este, que crecen deprisa porque parten de niveles bajos; la comparación justa es con países de nivel parecido (Francia, Italia, Alemania).",
          "En las crisis la productividad de España sube porque se destruyen primero los empleos menos productivos (2008–2013): el índice mezcla eficiencia y composición del empleo.",
        ]}
        table={<SeriesTable series={prod} unit="count" digits={1} />}
      >
        <TimeSeriesChart series={back(prod)} unit="count" xMin={h.productivity_base} xMax={h.productivity_last} ariaLabel="Productividad por hora trabajada, índice 1995 = 100" />
      </Figure>

      <Figure
        id="nivel"
        title={`España pasó de producir por hora un ${num(lvFirst - 100, 0)} % más que la media de la UE-27 a un ${num(100 - lvLast, 0)} % menos`}
        dek={`Nivel del PIB por hora trabajada en dólares de paridad de poder de compra constantes, media de la UE-27 = 100: España ${num(lvFirst)} en ${h.productivity_base} y ${num(lvLast)} en ${h.level_last_year}. Alemania, Francia e Italia siguen muy por encima; Portugal, por debajo.`}
        legend={level.filter((s) => s.color !== C.peer).concat([{ id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer }])}
        sources={[S.pdb]}
        notes={[
          "Cociente calculado por nosotros sobre el PIB por hora en dólares PPA a precios constantes de la OCDE. Las paridades de poder de compra tienen margen de error de varios puntos en los niveles entre países.",
        ]}
        table={<SeriesTable series={level} unit="count" digits={1} />}
      >
        <TimeSeriesChart series={back(level)} unit="count" xMin={h.productivity_base} xMax={h.level_last_year} ariaLabel="PIB por hora trabajada respecto a la UE-27" />
      </Figure>

      <Figure
        id="cuna-fiscal"
        title={`La cuña fiscal sobre el salario medio es del ${pct(wl.ESP)} en España: más que la media OCDE (${pct(wl.OECD_REP)}) y en la media de la UE (${pct(wl.EU22OECD)})`}
        dek={`IRPF y cotizaciones (del trabajador y de la empresa) sobre el coste laboral de un soltero sin hijos con el salario medio. Desde ${h.wedge_first_year} subió en España (${pct(wf.ESP)} → ${pct(wl.ESP)}) mientras bajaba en Alemania, Francia e Italia, que siguen por encima. Con el 67 % del salario medio: ${pct(h.wedge_low_last.ESP)} en España frente a ${pct(h.wedge_low_last.OECD_REP)} en la OCDE.`}
        legend={wedge.filter((s) => s.color !== C.peer).concat([{ id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer }])}
        sources={[S.wages, { label: "Cien años de impuestos en España", href: "/visualizaciones/carga-fiscal/" }]}
        notes={[
          "Media UE en la OCDE: media simple de los 22 países de la UE que pertenecen a la OCDE. Una cuña alta encarece contratar, pero esta comparación no prueba que explique el paro: Alemania tiene más cuña y mucho menos paro.",
        ]}
        table={<SeriesTable series={[...wedge].reverse()} />}
      >
        <TimeSeriesChart series={back(wedge)} xMin={h.wedge_first_year} xMax={h.wedge_last_year} yMax={60} height={280} ariaLabel="Cuña fiscal sobre el salario medio" />
        <WedgeBars values={wl} names={NAMES} year={h.wedge_last_year} color={C.blue} />
      </Figure>

      <Figure
        id="tasa-empleo"
        title={`Trabaja el ${pct(h.emp_es_last)} de la población de 20 a 64 años en España, frente al ${pct(h.emp_eu_last)} en la UE-27`}
        dek={`Es la otra cara del paro: cuenta también a quienes no buscan empleo. La distancia con la UE-27 pasó de ${num(empGapMax.gap)} puntos en ${empGapMax.year} a ${num(empGapLast.gap)} en ${empGapLast.year}.`}
        legend={emp.filter((s) => s.color !== C.peer).concat([{ id: "peers", label: "Alemania, Francia, Italia y Portugal", color: C.peer }])}
        sources={[S.eurostat("lfsi_emp_a"), S.eurostat("lfsi_emp_a_h")]}
        notes={["La serie histórica (1993–2020) y la vigente (desde 2003) se solapan; no se empalman."]}
        table={<SeriesTable series={emp} />}
      >
        <TimeSeriesChart series={back(emp)} xMin={1993} xMax={h.emp_last_year} yMax={100} ariaLabel="Tasa de empleo de 20 a 64 años" />
      </Figure>

      <LimitsCard />
      <MethodCard data={data} downloads={downloads} events={eventNotes(events, events.map((ev) => ev.id))} />
    </main>
  );
}
