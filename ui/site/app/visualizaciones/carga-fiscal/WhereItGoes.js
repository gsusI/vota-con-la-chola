import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure, { SeriesTable } from "../components/Figure";
import ConsolidatedBars from "./ConsolidatedBars";
import ResultsGrid from "./ResultsGrid";
import DeltaBars from "./DeltaBars";

// Line 2: where the money goes (COFOG by function), against the results of public services, with peers.
const EU_LABELS = { ES: "España", DE: "Alemania", FR: "Francia", IT: "Italia", PT: "Portugal", EU27_2020: "UE-27" };
const COLORS = {
  pensions: "#2a78d6",
  social: "#8db6e8",
  health: "#1baf7a",
  education: "#eda100",
  interest: "#eb6834",
  rest: "#b4b2a9",
  revenue: "#52514e",
  spending: "#52514e",
};
const SHORT = {
  pensions: "Pensiones",
  social: "Resto de protección social",
  health: "Sanidad",
  education: "Educación",
  interest: "Intereses",
  rest: "Resto",
};
const RESULT_META = {
  life_expectancy: { short: "Esperanza de vida (años)", digits: 1 },
  treatable: { short: "Mortalidad tratable (por 100.000)", digits: 1 },
  pisa_math: { short: "PISA matemáticas", digits: 0 },
  early_leavers: { short: "Abandono escolar (%)", digits: 1 },
  social_rental: { short: "Vivienda social (% del parque)", digits: 1 },
};

const nf = (v, digits = 1) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const ds = (dataset) => ({ label: `Eurostat, ${dataset}`, href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table` });
const signedPts = (v) => `${v >= 0 ? "+" : "−"}${nf(Math.abs(v))}`;
const cmp = (a, b) => (Math.abs(a - b) < 0.3 ? "lo mismo que" : a > b ? "más que" : "menos que");

export function SpendingSectionIntro() {
  return (
    <section className="card vizProse" id="a-donde-va" aria-labelledby="a-donde-va-title">
      <h2 id="a-donde-va-title">¿A dónde va lo recaudado?</h2>
      <p>
        Si la recaudación se ha multiplicado, la pregunta obvia es en qué se gasta y si los servicios han mejorado al mismo ritmo. Estas figuras cruzan el
        gasto público por función (clasificación COFOG de Eurostat, desde 1995) con los resultados de los servicios que publican las páginas de{" "}
        <a href="/visualizaciones/sanidad/">sanidad</a>, <a href="/visualizaciones/educacion/">educación</a> y{" "}
        <a href="/visualizaciones/vivienda/">vivienda</a>.
      </p>
    </section>
  );
}

export function WhereItGoesFigure({ spending, results }) {
  const { year } = spending;
  const rows = spending.areas.map((row) => ({ ...row, label: EU_LABELS[row.area] })).sort((a, b) => b.total - a.total);
  const es = rows.find((row) => row.area === "ES");
  const eu = rows.find((row) => row.area === "EU27_2020");
  const parts = spending.functions.map((f) => ({ key: f.key, label: f.label, short: SHORT[f.key], color: COLORS[f.key] }));
  const axisMax = Math.ceil(Math.max(...rows.map((row) => Math.max(row.total, row.base_total || 0, row.revenue))) / 10) * 10;
  const w95 = spending.spain_windows[0];
  const d = (key) => {
    const f = w95.functions.find((item) => item.key === key);
    return f.pct[1] - f.pct[0];
  };
  const indicators = (results?.indicators || []).map((ind) => {
    const years = Object.values(ind.values).map((v) => v.year);
    return { ...ind, ...RESULT_META[ind.key], year: Math.max(...years) };
  });
  const value = (key, area) => indicators.find((ind) => ind.key === key)?.values[area]?.value;
  const over = Object.fromEntries((results?.spain_over_time || []).map((item) => [item.key, item]));
  const byPensions = [...rows].filter((row) => row.area !== "EU27_2020").sort((a, b) => b.pensions - a.pensions);
  const pensionsRank = byPensions.indexOf(es) + 1;
  const pensionsAbove = byPensions.slice(0, pensionsRank - 1).map((row) => row.label);
  const pisa = indicators.find((ind) => ind.key === "pisa_math");
  const pisaPeers = pisa ? Object.entries(pisa.values).filter(([area]) => area !== "ES").map(([, v]) => v.value) : [];
  const lifeRank =
    [...rows].sort((a, b) => (value("life_expectancy", b.area) || 0) - (value("life_expectancy", a.area) || 0)).indexOf(es) + 1;
  const siblingSources = Object.values(results?.provenance || {}).map((p) => ({ label: p.label, href: p.page }));

  return (
    <Figure
      id="destino"
      title={`España dedica a pensiones el ${nf(es.pensions)} % del PIB, ${cmp(es.pensions, eu.pensions)} la UE (${nf(eu.pensions)} %); a sanidad y educación, ${cmp(es.health + es.education, eu.health + eu.education)} la UE (${nf(es.health)} % y ${nf(es.education)} % frente a ${nf(eu.health)} % y ${nf(eu.education)} %)`}
      dek={`El dato mata el relato: cada barra es el gasto público de cada país en ${year} (% del PIB) repartido por función; el círculo marca su gasto total en ${es.base_year} (${eu.base_year} para la UE) y el rombo, sus ingresos públicos en ${year}: lo que la barra sobrepasa al rombo es déficit. Debajo, en el mismo orden, los resultados de sus servicios públicos, cada columna con su escala desde cero. Composición, cambio, financiación, resultados y vecinos en una sola figura.`}
      legend={parts.map((part) => ({ id: part.key, label: part.label, color: part.color }))}
      legendKind="bar"
      sources={[ds("gov_10a_exp"), ds("gov_10a_main"), ...siblingSources]}
      notes={[
        "Pensiones: funciones COFOG de vejez y supervivencia (GF1002 y GF1003), que incluyen las pensiones públicas contributivas y no contributivas y los servicios a mayores. Intereses: transacciones de la deuda pública (GF0107).",
        "Los resultados vienen, sin recalcular, de los datos publicados en las páginas de sanidad, educación y vivienda (cada una cita su fuente oficial: Eurostat, OCDE PISA, OCDE Affordable Housing Database). PISA no publica media de la UE-27; la vivienda social es el último año disponible de cada país.",
        "Gasto y resultados no son causa y efecto: la esperanza de vida o PISA dependen también de la edad, la dieta, la renta y el origen social de cada país.",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla (cambio de cada función desde el primer año disponible)</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">País</th>
                  <th scope="col">Gasto {year}</th>
                  <th scope="col">Ingresos {year}</th>
                  <th scope="col">Saldo {year}</th>
                  {parts.map((part) => (
                    <th scope="col" key={part.key}>
                      {part.short}
                    </th>
                  ))}
                  <th scope="col">Sueldos públicos (todas las funciones)</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.area}>
                    <td>{row.label}</td>
                    <td>
                      {nf(row.total)} % ({signedPts(row.total - row.base_total)} desde {row.base_year})
                    </td>
                    <td>{nf(row.revenue)} %</td>
                    <td>{nf(row.balance)} %</td>
                    {parts.map((part) => (
                      <td key={part.key}>
                        {nf(row[part.key])} %
                        {row.parts_change ? ` (${signedPts(row.parts_change[part.key])} desde ${row.parts_base_year})` : ""}
                      </td>
                    ))}
                    <td>{nf(row.pay)} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <p className="cbars__legendNote">
        <span className="cbars__key" aria-hidden="true" /> Gasto total en {es.base_year} <span className="cbars__key cbars__key--marker" aria-hidden="true" />{" "}
        Ingresos públicos en {year}
      </p>
      <ConsolidatedBars
        rows={rows}
        parts={parts}
        axisMax={axisMax}
        year={year}
        baseYear={es.base_year}
        highlight="ES"
        marker={{ key: "revenue", label: "ingresos públicos" }}
        ariaLabel={`Gasto público por función, ${year}, gasto total en el primer año e ingresos públicos`}
      />
      {indicators.length ? (
        <>
          <h3 className="rgrid__title">Resultados de los servicios públicos (mismo orden de países)</h3>
          <ResultsGrid rows={rows} indicators={indicators} highlight="ES" color="#2a78d6" peerColor="#b4b2a9" />
        </>
      ) : null}
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«Lo que se recauda de más se va en pensiones»</strong>
          En gran parte, sí. Desde {w95.from} los ingresos públicos de España han subido {nf(w95.revenue_pct[1] - w95.revenue_pct[0])} puntos del PIB:{" "}
          {nf(w95.balance_pct[1] - w95.balance_pct[0])} fueron a reducir el déficit y el gasto subió {nf(w95.spending_pct[1] - w95.spending_pct[0])}. Dentro del
          gasto: pensiones {signedPts(d("pensions"))}, sanidad {signedPts(d("health"))}, educación {signedPts(d("education"))}, intereses{" "}
          {signedPts(d("interest"))}, resto de protección social {signedPts(d("social"))} y todo lo demás {signedPts(d("rest"))}. Aun así, España es el{" "}
          {pensionsRank}.º de {rows.length - 1} países en gasto en pensiones{pensionsAbove.length ? `, por debajo de ${pensionsAbove.join(" y ")}` : ""}.
        </li>
        <li>
          <strong>«Pagamos más y los servicios están peor»</strong>
          Depende del servicio. Gastando en sanidad {cmp(es.health, eu.health)} la UE, España tiene la {lifeRank === 1 ? "mayor" : `${lifeRank}.ª mayor`} esperanza de vida del
          grupo ({nf(value("life_expectancy", "ES"))} años) y menos mortalidad tratable que la media ({nf(value("treatable", "ES"))} frente a{" "}
          {nf(value("treatable", "EU27_2020"))} por 100.000). Pero la espera media para operarse pasó de {nf(over.surgery_wait_days?.from.value, 0)} días en{" "}
          {String(over.surgery_wait_days?.from.date).slice(0, 4)} a {nf(over.surgery_wait_days?.to.value, 0)} en {String(over.surgery_wait_days?.to.date).slice(0, 4)}{" "}
          (con cambios de método), el abandono escolar ({nf(value("early_leavers", "ES"))} %) sigue por encima de la UE ({nf(value("early_leavers", "EU27_2020"))} %)
          aunque venía del {nf(over.early_leavers?.from.value)} % en {over.early_leavers?.from.year}, en PISA saca {nf(value("pisa_math", "ES"), 0)} puntos, como
          sus vecinos ({nf(Math.min(...pisaPeers), 0)}–{nf(Math.max(...pisaPeers), 0)}), y la vivienda social es el{" "}
          {nf(value("social_rental", "ES"))} % del parque frente al {nf(value("social_rental", "FR"))} % de Francia.
        </li>
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          La eficiencia de cada euro, el reparto entre comunidades autónomas, qué parte de los resultados se debe al gasto y qué parte a la demografía, y si las
          pensiones de hoy están financiadas para mañana. Las pensiones son renta de los pensionistas, no un servicio: comparan mal con sanidad o educación.
        </li>
      </ul>
    </Figure>
  );
}

export function DecompositionFigure({ spending }) {
  const [w95, w07] = spending.spain_windows;
  const share = (w, key) => {
    const f = w.functions.find((item) => item.key === key);
    return { pct: f.pct[1] - f.pct[0], eur: f.eur[1] - f.eur[0] };
  };
  const spend07 = w07.spending_pct[1] - w07.spending_pct[0];
  const pens07 = share(w07, "pensions").pct;
  const spendEur95 = w95.spending_eur[1] - w95.spending_eur[0];
  const pensEur95 = share(w95, "pensions").eur;
  const labels = Object.fromEntries(spending.functions.map((f) => [f.key, SHORT[f.key]]));
  const series = spending.functions.map((f) => ({
    id: f.key,
    label: f.label,
    points: spending.spain_series[`${f.key}_pct_gdp`],
  }));
  const pay = spending.spain_series.pay_pct_gdp;
  return (
    <Figure
      id="descomposicion"
      title={`Desde ${w07.from} el gasto público ha subido ${nf(spend07)} puntos del PIB; ${nf(pens07)} fueron a pensiones`}
      dek={`En euros constantes por habitante, desde ${w95.from} el gasto ha crecido ${nf(spendEur95, 0)} €, de los que ${nf(pensEur95, 0)} € (${nf((pensEur95 / spendEur95) * 100, 0)} %) fueron a pensiones, ${nf(share(w95, "health").eur, 0)} € a sanidad y ${nf(share(w95, "education").eur, 0)} € a educación; los intereses bajaron ${nf(-share(w95, "interest").eur, 0)} €. Cambia el año de partida: ${w07.from} es el último año antes de la crisis financiera, con ingresos inflados por la burbuja.`}
      sources={[ds("gov_10a_exp"), ds("gov_10a_main"), ds("nama_10_pc")]}
      notes={[
        "Euros de 2010 por habitante: % del PIB de cada función × PIB real por habitante (volumen encadenado, deflactor del PIB).",
        `Los sueldos públicos no son una función sino un tipo de gasto repartido entre todas: ${nf(pay[0].value)} % del PIB en ${pay[0].year} y ${nf(pay.at(-1).value)} % en ${pay.at(-1).year}.`,
      ]}
      table={<SeriesTable series={series} />}
    >
      <DeltaBars windows={[w95, w07]} labels={{ ...labels, revenue: "Ingresos", spending: "Gasto" }} colors={COLORS} />
    </Figure>
  );
}

export function LongRunSpendingFigure({ spending, imfSource }) {
  const lr = spending.long_run;
  const s = spending.spain_series;
  const until = (rows, y) => rows.filter((p) => p.year <= y);
  const series = [
    { id: "tr", label: "Ingresos, todas las AAPP (Eurostat)", shortLabel: "Ingresos", color: "#2a78d6", emphasis: true, points: s.revenue_pct_gdp },
    { id: "te", label: "Gasto, todas las AAPP (Eurostat)", shortLabel: "Gasto", color: "#eb6834", emphasis: true, points: s.spending_pct_gdp },
    { id: "ie", label: "Intereses de la deuda, todas las AAPP (Eurostat)", shortLabel: "Intereses", color: "#eda100", points: s.interest_pct_gdp },
    { id: "rev", label: "Ingresos del Estado central (FMI)", shortLabel: "FMI ingr.", color: "#8db6e8", points: until(lr.imf_revenue_pct_gdp, 1980) },
    { id: "exp", label: "Gasto del Estado central (FMI)", shortLabel: "FMI gasto", color: "#f3a988", points: until(lr.imf_spending_pct_gdp, 1980) },
    { id: "imf_ie", label: "Intereses del Estado central (FMI)", shortLabel: "", color: "#f4cf7a", points: until(lr.imf_interest_pct_gdp, 1980) },
  ];
  const debt = [{ id: "d", label: "Deuda pública bruta (FMI)", shortLabel: String(lr.imf_debt_pct_gdp.at(-1).year), color: "#52514e", emphasis: true, points: lr.imf_debt_pct_gdp }];
  const low = lr.imf_debt_pct_gdp.filter((p) => p.year >= 1950 && p.year <= 2000).reduce((a, b) => (b.value < a.value ? b : a));
  const lastDebt = lr.imf_debt_pct_gdp.at(-1);
  const first = lr.imf_spending_pct_gdp[0];
  const lastTe = s.spending_pct_gdp.at(-1);
  return (
    <>
      <Figure
        id="gasto-largo-plazo"
        title={`El gasto público pasó del ${nf(first.value, 0)} % del PIB en ${first.year} al ${nf(lastTe.value, 0)} % en ${lastTe.year}`}
        dek="Hasta 1980, solo el Estado central (FMI); desde 1995, todas las administraciones (Eurostat). Entre 1981 y 1994 no hay una serie abierta homogénea de todas las administraciones: el hueco se deja visible y no se empalma."
        legend={series}
        sources={[imfSource, ds("gov_10a_main")]}
        notes={[
          "El FMI amplía la cobertura de España a lo largo de los años 80 (Seguridad Social, comunidades autónomas): por eso solo se muestra hasta 1980, como en la figura de ingresos.",
        ]}
        table={<SeriesTable series={series} />}
      >
        <TimeSeriesChart series={series} xMin={1925} xMax={lastTe.year} bands={[{ from: 1936, to: 1939, label: "Guerra" }]} ariaLabel="Ingresos, gasto e intereses públicos en España, % del PIB" />
      </Figure>
      <Figure
        id="deuda"
        title={`La deuda pública pasó del ${nf(low.value, 0)} % del PIB en ${low.year} al ${nf(lastDebt.value, 0)} % en ${lastDebt.year}`}
        dek={`Deuda bruta de las administraciones públicas. Los intereses que genera cuestan hoy el ${nf(s.interest_pct_gdp.at(-1).value)} % del PIB, menos que en ${s.interest_pct_gdp[0].year} (${nf(s.interest_pct_gdp[0].value)} %) gracias a los tipos bajos.`}
        sources={[imfSource]}
        notes={["Serie histórica de deuda del FMI (Historical Public Debt Database); en los años antiguos cubre sobre todo al Estado central."]}
        table={<SeriesTable series={debt} />}
      >
        <TimeSeriesChart series={debt} xMin={1925} xMax={lastDebt.year} bands={[{ from: 1936, to: 1939, label: "Guerra" }]} ariaLabel="Deuda pública de España, % del PIB" />
      </Figure>
    </>
  );
}
