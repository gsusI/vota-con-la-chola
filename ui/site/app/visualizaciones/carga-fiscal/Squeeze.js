import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure, { SeriesTable } from "../components/Figure";
import SqueezeRows from "./SqueezeRows";
import ResultsGrid from "./ResultsGrid";

// Line 1: the taxpayer's pocket. Taxes paid vs household income left, per person in PPS, and their real change.
const EU_LABELS = { ES: "España", DE: "Alemania", FR: "Francia", IT: "Italia", PT: "Portugal", EU27_2020: "UE-27" };
const TAX = "#eb6834";
const INCOME = "#2a78d6";

const nf = (v, digits = 1) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const ds = (dataset) => ({ label: `Eurostat, ${dataset}`, href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table` });
const SOURCES = [ds("gov_10a_taxag"), ds("nama_10_pc"), ds("tec00113"), ds("nasa_10_ki"), ds("prc_hicp_aind")];

export function SqueezeFigure({ squeeze }) {
  const rows = squeeze.areas.map((row) => ({ ...row, label: EU_LABELS[row.area] })).sort((a, b) => b.income_pps - a.income_pps);
  const by = Object.fromEntries(rows.map((row) => [row.area, row]));
  const es = by.ES;
  const eu = by.EU27_2020;
  const de = by.DE;
  const countries = rows.filter((row) => row.area !== "EU27_2020");
  const incomeRank = [...countries].sort((a, b) => b.real_income_change_pct - a.real_income_change_pct);
  const slower = incomeRank.slice(incomeRank.indexOf(es) + 1).map((row) => row.label);
  const faster = incomeRank.slice(0, incomeRank.indexOf(es));
  const effortAbove = countries.filter((row) => row.effort_index > es.effort_index).sort((a, b) => b.effort_index - a.effort_index);
  const effortBelow = countries.filter((row) => row.effort_index < es.effort_index);
  const ratio = es.real_tax_change_pct / es.real_income_change_pct;
  const { year, base_year: base, index_last_year: last } = squeeze;
  const survey = squeeze.survey ? { es: squeeze.survey.areas.find((row) => row.area === "ES") } : null;

  return (
    <Figure
      id="bolsillo"
      title={`Desde ${base}, lo que recauda el Estado por habitante ha crecido un ${nf(es.real_tax_change_pct)} % descontada la inflación; la renta que les queda a los hogares, un ${nf(es.real_income_change_pct)} %`}
      dek={`El dato mata el relato: a la izquierda, cuánto se paga por habitante en impuestos y cotizaciones y cuánta renta disponible les queda a los hogares por habitante en ${year}, en la misma escala y en estándar de poder adquisitivo (euros que compran lo mismo en cada país). A la derecha, cuánto ha cambiado cada cosa desde ${base}, descontada la inflación. Nivel, cambio y comparación con los vecinos en una sola figura.`}
      legend={[
        { id: "tax", label: "Impuestos y cotizaciones por habitante", color: TAX },
        { id: "income", label: "Renta disponible ajustada de los hogares por habitante", color: INCOME },
      ]}
      legendKind="bar"
      sources={SOURCES}
      notes={[
        "La renta disponible ajustada incluye los servicios públicos que los hogares reciben en especie (sanidad y educación, sobre todo): ya cuenta una parte de lo que pagan los impuestos. Es la medida que Eurostat recomienda para comparar el bienestar material entre países.",
        `El porcentaje de la izquierda divide los impuestos por habitante entre la renta que queda por habitante; no es un tipo impositivo (incluye lo que ingresan las empresas y la renta ya está descontada de impuestos).`,
        `Recaudación real: carga fiscal × PIB por habitante en euros, deflactada con el IPC armonizado de cada país. Renta real: índice de Eurostat deflactado con el deflactor del consumo de los hogares. Son índices de precios distintos pero ambos de consumo. Para España, con la recaudación de la OCDE en euros, la población y el IPC del Banco Mundial sale +${nf(squeeze.spain_cpi_check.real_tax_change_pct)} % (${squeeze.spain_cpi_check.from}–${squeeze.spain_cpi_check.to}).`,
        `${year}: último año con las tres medidas para los seis países. El estándar de poder adquisitivo corrige las diferencias de precios entre países de forma aproximada.`,
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">País</th>
                  <th scope="col">Carga fiscal {year} (% PIB)</th>
                  <th scope="col">PIB por habitante (EPA)</th>
                  <th scope="col">Impuestos por habitante (EPA)</th>
                  <th scope="col">Renta que queda por habitante (EPA)</th>
                  <th scope="col">Impuestos / renta</th>
                  <th scope="col">Índice de esfuerzo fiscal (UE = 100)</th>
                  <th scope="col">Impuestos reales {base}–{last}</th>
                  <th scope="col">Renta real {base}–{last}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.area}>
                    <td>{row.label}</td>
                    <td>{nf(row.tax_pct_gdp)} %</td>
                    <td>{nf(row.gdp_pps, 0)}</td>
                    <td>{nf(row.tax_pps, 0)}</td>
                    <td>{nf(row.income_pps, 0)}</td>
                    <td>{nf(row.tax_to_income_pct)} %</td>
                    <td>{nf(row.effort_index)}</td>
                    <td>{nf(row.real_tax_change_pct)} %</td>
                    <td>{nf(row.real_income_change_pct)} %</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <SqueezeRows rows={rows} year={year} baseYear={base} lastYear={last} taxColor={TAX} incomeColor={INCOME} highlight="ES" />
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«El Estado es más rico y la gente, más pobre»</strong>
          Medio cierto. Desde {base} la recaudación real por habitante ha crecido {nf(ratio)} veces más deprisa que la renta de los hogares (+
          {nf(es.real_tax_change_pct)} % frente a +{nf(es.real_income_change_pct)} %). Pero los hogares no son más pobres que en {base}: lo son frente a
          Europa. Su renta real creció un {nf(eu.real_income_change_pct)} % en la UE
          {faster.length ? `, ${faster.map((row) => `${nf(row.real_income_change_pct)} % en ${row.label}`).join(", ")}` : ""}
          {slower.length ? `; solo ${slower.join(" y ")} creció menos` : ""}.
        </li>
        <li>
          <strong>«En España se pagan más impuestos que en Alemania»</strong>
          No por persona: en {year} cada habitante paga {nf(es.tax_pps, 0)} frente a {nf(de.tax_pps, 0)} en Alemania, y lo que paga equivale al{" "}
          {nf(es.tax_to_income_pct)} % de la renta que les queda a los hogares, casi lo mismo que en Alemania ({nf(de.tax_to_income_pct)} %) y menos que en
          la UE ({nf(eu.tax_to_income_pct)} %). El índice de «esfuerzo fiscal» de Frank, que divide la presión fiscal por el PIB por habitante, deja a
          España en {nf(es.effort_index)} (UE = 100): por encima de {effortBelow.map((row) => `${row.label} (${nf(row.effort_index)})`).join(", ")} y por
          debajo de {effortAbove.map((row) => `${row.label} (${nf(row.effort_index)})`).join(", ")}. Es un índice discutido: supone que la capacidad de
          pagar crece en proporción a la renta y mezcla lo que pagan empresas y hogares.
        </li>
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          Quién soporta de verdad cada impuesto y qué servicios recibe cada país a cambio (<a href="#destino">más abajo</a>). Son medias de contabilidad
          nacional: en la encuesta a los hogares, el hogar mediano español
          {survey ? ` (${nf(survey.es.median_income_pps, 0)} por adulto equivalente)` : ""} está mucho más cerca de la mediana europea (
          <a href="#mediana-vivienda">figura siguiente</a>).
        </li>
      </ul>
    </Figure>
  );
}

export function SqueezeIndexFigure({ squeeze }) {
  const { base_year: base, index_last_year: last } = squeeze;
  const rows = squeeze.areas.map((row) => ({ ...row, label: EU_LABELS[row.area], gap: row.real_tax_change_pct - row.real_income_change_pct }));
  const ranked = [...rows].filter((row) => row.area !== "EU27_2020").sort((a, b) => b.gap - a.gap);
  const es = rows.find((row) => row.area === "ES");
  const esRank = ranked.indexOf(es) + 1;
  const ahead = ranked.slice(0, esRank - 1).map((row) => row.label);
  const yMax = Math.ceil(Math.max(...rows.flatMap((row) => [...row.real_tax_index, ...row.real_income_index].map((p) => p.value))) / 10) * 10;
  const all = rows.flatMap((row) => [
    { id: `${row.area}-tax`, label: `${row.label}: impuestos reales por habitante`, points: row.real_tax_index },
    { id: `${row.area}-income`, label: `${row.label}: renta real de los hogares por habitante`, points: row.real_income_index },
  ]);
  return (
    <Figure
      id="indices"
      title={`La recaudación real por habitante ha crecido ${nf(es.gap)} puntos más que la renta de los hogares en España desde ${base}${
        esRank === 1 ? ", la mayor distancia del grupo" : `, solo por detrás de ${ahead.join(" y ")}`
      }`}
      dek={`Índices ${base} = 100, descontada la inflación. Cuando la línea naranja va por encima de la azul, lo que ingresa el sector público por habitante crece más deprisa que la renta disponible de los hogares. Todos los paneles comparten escala.`}
      legend={[
        { id: "tax", label: "Impuestos y cotizaciones por habitante (reales)", color: TAX },
        { id: "income", label: "Renta disponible ajustada de los hogares por habitante (real)", color: INCOME },
      ]}
      sources={SOURCES}
      notes={["Mismos deflactores que la figura anterior. En 2020 (pandemia) la recaudación real por habitante cae más que la renta de los hogares en todos los países."]}
      table={<SeriesTable series={all} unit="count" />}
    >
      <div className="vizMultiples">
        {rows.map((row) => (
          <div key={row.area}>
            <h3 className="vizPanelTitle">
              {row.label}
              <span>
                impuestos {row.real_tax_change_pct >= 0 ? "+" : "−"}
                {nf(Math.abs(row.real_tax_change_pct))} % · renta {row.real_income_change_pct >= 0 ? "+" : "−"}
                {nf(Math.abs(row.real_income_change_pct))} %
              </span>
            </h3>
            <TimeSeriesChart
              series={[
                { id: "tax", label: "Impuestos", shortLabel: "Imp.", color: TAX, emphasis: true, points: row.real_tax_index },
                { id: "income", label: "Renta", shortLabel: "Renta", color: INCOME, points: row.real_income_index },
              ]}
              unit="count"
              xMin={base}
              xMax={last}
              yMax={yMax}
              height={200}
              ariaLabel={`${row.label}: impuestos y renta reales por habitante, ${base} = 100`}
            />
          </div>
        ))}
      </div>
    </Figure>
  );
}

const SURVEY_META = [
  { key: "median_income_pps", short: "Renta mediana (PPS por adulto equivalente)", better: "higher", digits: 0 },
  { key: "mean_income_pps", short: "Renta media (PPS por adulto equivalente)", better: "higher", digits: 0 },
  { key: "housing_cost_share", short: "Gastos de vivienda (% de la renta)", better: "lower", digits: 1 },
  { key: "housing_cost_share_poor", short: "Ídem, hogares en riesgo de pobreza", better: "lower", digits: 1 },
  { key: "overburden_renters", short: "Inquilinos a precio de mercado con sobrecarga (%)", better: "lower", digits: 1 },
  { key: "overburden_mortgage", short: "Propietarios con hipoteca con sobrecarga (%)", better: "lower", digits: 1 },
  { key: "overburden", short: "Toda la población con sobrecarga (%)", better: "lower", digits: 1 },
];

export function SurveyFigure({ squeeze }) {
  const survey = squeeze.survey;
  const { survey_year: wave, income_year: incomeYear } = survey;
  const areas = survey.areas.map((row) => ({ ...row, label: EU_LABELS[row.area] }));
  const by = Object.fromEntries(areas.map((row) => [row.area, row]));
  const es = by.ES;
  const eu = by.EU27_2020;
  const de = by.DE;
  const na = Object.fromEntries(squeeze.areas.map((row) => [row.area, row]));
  // Same row order as the «bolsillo» figure.
  const rows = [...areas].sort((a, b) => na[b.area].income_pps - na[a.area].income_pps);
  const indicators = SURVEY_META.map((meta) => ({
    ...meta,
    year: wave,
    values: Object.fromEntries(areas.map((row) => [row.area, { year: wave, value: row[meta.key] }])),
  }));
  const pctOf = (a, b) => (a / b) * 100;
  const renterRank = [...areas].filter((row) => row.area !== "EU27_2020").sort((a, b) => b.overburden_renters - a.overburden_renters);
  const renterAbove = renterRank.slice(0, renterRank.indexOf(es)).map((row) => `${row.label} (${nf(row.overburden_renters)} %)`);
  const vs = (a, b) => (Math.abs(a - b) / b < 0.03 ? "casi en" : a > b ? "por encima de" : "por debajo de");
  return (
    <Figure
      id="mediana-vivienda"
      title={`El hogar mediano español está ${vs(es.median_income_pps, eu.median_income_pps)} la mediana de la UE; los inquilinos, no: el ${nf(es.overburden_renters)} % de los que pagan alquiler de mercado dedica más del 40 % de su renta a la vivienda (UE: ${nf(eu.overburden_renters)} %)`}
      dek={`Encuesta de condiciones de vida (EU-SILC ${wave}, rentas de ${incomeYear}). La renta es la disponible en dinero de cada hogar, dividida por sus unidades de consumo para comparar hogares de distinto tamaño, en estándar de poder adquisitivo. Debajo, cuánto se lleva la vivienda. Mismo orden de países que la figura de lo que se paga y lo que queda; cada columna, con su escala desde cero.`}
      sources={[ds("ilc_di03"), ds("ilc_mded01"), ds("ilc_lvho07c")]}
      notes={[
        `Encuesta frente a contabilidad nacional: aquí el hogar mediano español tiene el ${nf(pctOf(es.median_income_pps, eu.median_income_pps), 0)} % de la renta mediana de la UE; en la figura de arriba, la renta por habitante es el ${nf(pctOf(na.ES.income_pps, na.EU27_2020.income_pps), 0)} %. La encuesta no incluye los servicios públicos en especie ni el alquiler imputado de quien vive en casa propia, ajusta por tamaño del hogar y se basa en lo que declaran los hogares; las dos medidas son oficiales y miden cosas distintas.`,
        "Gastos de vivienda: alquiler o intereses de la hipoteca (no la amortización), suministros, comunidad, reparaciones, seguros e impuestos, netos de ayudas a la vivienda. Sobrecarga: más del 40 % de la renta disponible del hogar.",
        "Quien vive en casa propia sin hipoteca apenas tiene gastos de vivienda; donde son muchos, como en España e Italia, el dato del país puede ser bajo aunque los inquilinos estén ahogados.",
      ]}
      table={
        <details className="vizTable">
          <summary>Ver los datos en tabla</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">País</th>
                  {SURVEY_META.map((meta) => (
                    <th scope="col" key={meta.key}>
                      {meta.short}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.area}>
                    <td>{row.label}</td>
                    {SURVEY_META.map((meta) => (
                      <td key={meta.key}>{nf(row[meta.key], meta.digits)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <ResultsGrid rows={rows} indicators={indicators} highlight="ES" color={INCOME} peerColor="#b4b2a9" />
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«Al español medio le queda mucho menos que al europeo»</strong>
          Depende de cómo se mida. Por habitante en contabilidad nacional, sí ({nf(pctOf(na.ES.income_pps, na.EU27_2020.income_pps), 0)} % de la UE). Para el
          hogar mediano de la encuesta, apenas: {nf(es.median_income_pps, 0)} frente a {nf(eu.median_income_pps, 0)} en la UE y {nf(de.median_income_pps, 0)} en
          Alemania ({nf(pctOf(es.median_income_pps, de.median_income_pps), 0)} %). La media española está un {nf(pctOf(es.mean_income_pps, es.median_income_pps) - 100, 0)} %
          por encima de su mediana
          {Math.abs(pctOf(es.mean_income_pps, es.median_income_pps) - pctOf(eu.mean_income_pps, eu.median_income_pps)) < 1
            ? `, lo mismo que en la UE (${nf(pctOf(eu.mean_income_pps, eu.median_income_pps) - 100, 0)} %): la desigualdad no explica la distancia entre las dos medidas.`
            : `, frente al ${nf(pctOf(eu.mean_income_pps, eu.median_income_pps) - 100, 0)} % de la UE.`}
        </li>
        <li>
          <strong>«La vivienda se come lo que queda»</strong>
          No al hogar típico: los gastos de vivienda son el {nf(es.housing_cost_share)} % de la renta en España, menos que en la UE ({nf(eu.housing_cost_share)} %)
          y en Alemania ({nf(de.housing_cost_share)} %), porque muchos viven en casa pagada. Sí a quien alquila: el {nf(es.overburden_renters)} % de los
          inquilinos a precio de mercado pasa del 40 %, frente al {nf(eu.overburden_renters)} % de la UE y el {nf(de.overburden_renters)} % de Alemania
          {renterAbove.length ? `; solo ${renterAbove.join(" y ")} está peor` : "; el peor dato del grupo"}. Y a los hogares en riesgo de pobreza, que dedican a la
          vivienda el {nf(es.housing_cost_share_poor)} % de su renta.
        </li>
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          Cómo ha cambiado desde 2008 (la encuesta tiene rupturas de serie en varios países), las diferencias entre ciudades y comunidades, y la calidad y el
          tamaño de la vivienda. Más en <a href="/visualizaciones/vivienda/">vivienda</a>.
        </li>
      </ul>
    </Figure>
  );
}
