import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure, { SeriesTable } from "../components/Figure";
import SqueezeRows from "./SqueezeRows";
import AgeIncome from "./AgeIncome";
import ResultsGrid from "./ResultsGrid";
import { place } from "./places.mjs";

// Line 1: the taxpayer's pocket. Taxes paid vs household income left, per person in PPS, and their real change.
const EU_LABELS = { ES: "España", DE: "Alemania", FR: "Francia", IT: "Italia", PT: "Portugal", EU27_2020: "UE-27" };
const TAX = "#eb6834";
const INCOME = "#2a78d6";
const WORKER = "#1baf7a";
const OECD_LABELS = { ESP: "España", DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal" };

const nf = (v, digits = 1) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" }).replace("-", "−");
// «ha subido un 3,1 %» / «ha bajado un 0,7 %»: the verb carries the sign.
const moved = (v) => `ha ${v < 0 ? "bajado" : "subido"} un ${nf(Math.abs(v))} %`;
const signedPct1 = (v) => `${v >= 0 ? "+" : "−"}${nf(Math.abs(v))} %`;
const signedPct = (v) => `${v >= 0 ? "+" : "−"}${nf(Math.abs(v))} %`;
const ds = (dataset) => ({ label: `Eurostat, ${dataset}`, href: `https://ec.europa.eu/eurostat/databrowser/view/${dataset}/default/table` });
const SOURCES = [ds("gov_10a_taxag"), ds("nama_10_pc"), ds("tec00113"), ds("nasa_10_ki"), ds("prc_hicp_aind")];

export function SqueezeFigure({ squeeze, distribution, territory, segments }) {
  const rows = squeeze.areas.map((row) => ({ ...row, label: EU_LABELS[row.area] })).sort((a, b) => b.income_pps - a.income_pps);
  const by = Object.fromEntries(rows.map((row) => [row.area, row]));
  const es = by.ES;
  const eu = by.EU27_2020;
  const de = by.DE;
  const countries = rows.filter((row) => row.area !== "EU27_2020");
  const effortAbove = countries.filter((row) => row.effort_index > es.effort_index).sort((a, b) => b.effort_index - a.effort_index);
  const effortBelow = countries.filter((row) => row.effort_index < es.effort_index);
  const { year, base_year: base, index_last_year: last, bases } = squeeze;
  const survey = squeeze.survey ? { es: squeeze.survey.areas.find((row) => row.area === "ES") } : null;
  const at = (row, b) => row.by_base[String(b)];
  const outgrows = bases.filter((b) => at(es, b).tax > at(es, b).income);
  const notOutgrows = bases.filter((b) => !outgrows.includes(b));
  const euIncomeAhead = bases.filter((b) => at(eu, b).income > at(eu, b).tax);
  const b0 = at(es, base);
  const eu0 = at(eu, base);
  const reverse = eu0.income > eu0.tax;
  const wedge = distribution?.tax_wedge;
  const wEs = wedge?.areas.find((row) => row.area === "ESP");
  const wFell = wedge ? wedge.areas.filter((row) => row.area !== "ESP" && row.AW100[1] < row.AW100[0]).map((row) => OECD_LABELS[row.area]) : [];
  const irpf = distribution?.irpf;
  const high = irpf ? irpf.brackets.filter((b) => (b.lower_eur || 0) >= 60000) : [];
  const highDecl = high.reduce((sum, b) => sum + b.share_declarations_pct, 0);
  const highTax = high.reduce((sum, b) => sum + b.share_tax_pct, 0);
  const topCommon = (territory?.rows || []).filter((row) => row.regime === "comun" && row.top_rate_pct != null);
  const topMin = topCommon.length ? topCommon.reduce((a, b) => (b.top_rate_pct < a.top_rate_pct ? b : a)) : null;
  const topMax = topCommon.length ? topCommon.reduce((a, b) => (b.top_rate_pct > a.top_rate_pct ? b : a)) : null;
  const ages = segments?.income_by_age;
  const ageRows = Object.fromEntries((ages?.areas?.ES || []).map((row) => [row.age, row]));
  const ageBase = ages ? String(ages.bases[0]) : null;
  const old = ageRows.Y_GE65;
  const mid = ageRows["Y25-49"];
  const allAges = ageRows.TOTAL;
  const peerGap = (geo) => {
    const rows = Object.fromEntries((ages?.areas?.[geo] || []).map((row) => [row.age, row]));
    const a = rows.Y_GE65?.change?.[ageBase];
    const b = rows["Y25-49"]?.change?.[ageBase];
    return a == null || b == null ? null : { label: EU_LABELS[geo], old: a, mid: b };
  };
  const ageGaps = ["IT", "PT"].map(peerGap).filter(Boolean);
  const housing = segments?.housing;

  return (
    <Figure
      id="bolsillo"
      title={`Desde ${base}, lo que recauda el Estado por habitante en España ha crecido un ${nf(b0.tax)} % descontada la inflación y la renta de los hogares, un ${nf(b0.income)} %${
        reverse ? `; en la UE, al revés (${nf(eu0.tax)} % y ${nf(eu0.income)} %)` : ""
      }${old && mid ? `; pero desde ${ageBase} la renta mediana real de los mayores de 65 ${moved(old.change[ageBase])} y la de 25 a 49 años ${moved(mid.change[ageBase])}` : ""}`}
      dek={`El dato mata el relato: a la izquierda, cuánto se recauda por habitante en impuestos y cotizaciones (de hogares y empresas) y cuánta renta disponible les queda a los hogares por habitante en ${year}, en la misma escala y en estándar de poder adquisitivo (euros que compran lo mismo en cada país). A la derecha, cuánto ha cambiado cada cosa descontada la inflación, también por persona ocupada; cambia el año de partida para ver que la conclusión no depende de él (salvo ${notOutgrows.join(" y ")}). Nivel, cambio, composición y vecinos en una sola figura. Debajo, la renta de los hogares de España partida por edad: la media de todos esconde que unas edades han ganado y otras no.`}
      legend={[
        { id: "tax", label: "Impuestos y cotizaciones por habitante", color: TAX },
        { id: "worker", label: "Impuestos y cotizaciones por persona ocupada (solo el cambio)", color: WORKER },
        { id: "income", label: "Renta disponible ajustada de los hogares por habitante", color: INCOME },
      ]}
      legendKind="bar"
      sources={SOURCES}
      notes={[
        "La renta disponible ajustada incluye los servicios públicos que los hogares reciben en especie (sanidad y educación, sobre todo): ya cuenta una parte de lo que pagan los impuestos. Es la medida que Eurostat recomienda para comparar el bienestar material entre países.",
        `El porcentaje de la izquierda divide los impuestos por habitante entre la renta que queda por habitante; no es un tipo impositivo (incluye lo que ingresan las empresas y la renta ya está descontada de impuestos).`,
        `Recaudación real: carga fiscal × PIB por habitante en euros, deflactada con el IPC armonizado de cada país. Renta real: índice de Eurostat deflactado con el deflactor del consumo de los hogares. Son índices de precios distintos pero ambos de consumo. Para España, con la recaudación de la OCDE en euros, la población y el IPC del Banco Mundial sale +${nf(squeeze.spain_cpi_check.real_tax_change_pct)} % (${squeeze.spain_cpi_check.from}–${squeeze.spain_cpi_check.to}).`,
        `${year}: último año con las tres medidas para los seis países. El estándar de poder adquisitivo corrige las diferencias de precios entre países de forma aproximada.`,
        ...(ages
          ? [
              `Por edad: renta disponible equivalente mediana de las personas de cada edad (Eurostat ilc_di03, bandas de Eurostat: 16–24, 25–49, 50–64 y 65 y más; la etapa común «16–29» de las otras visualizaciones no existe en esta tabla), encuesta de ${ages.first_survey} a ${ages.survey_year} (rentas de ${ages.first_survey - 1} a ${ages.income_year}), deflactada con el IPCA a euros de ${ages.price_year}. Eurostat marca ruptura de serie en España en ${ages.breaks_es.join(" y ")}: la serie empieza en ${ages.first_survey} y no se compara con años anteriores. Alemania y Francia tienen rupturas posteriores y solo se comparan desde ellas.`,
              `La renta equivalente reparte la del hogar entre sus miembros: un joven que vive con sus padres cuenta con la renta de sus padres. ${housing?.at_home_25_34 ? `El ${nf(housing.at_home_25_34.value)} % de los de 25 a 34 años vive aún en casa de sus padres (EU-SILC ${housing.at_home_25_34.year}, ver vivienda).` : ""}`,
            ]
          : []),
        `Año de partida: ${base} por defecto porque está a mitad de ciclo; 2007 fue el pico de ingresos de la burbuja inmobiliaria, 2008 el primer año de su caída, 2013 el fondo de la crisis y 2019 el último antes de la pandemia. Por ocupado: personas con empleo en el territorio (contabilidad nacional), para separar lo que sube porque trabaja más gente.`,
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
                  {bases.map((b) => (
                    <th scope="col" key={b}>
                      Desde {b}: impuestos / por ocupado / renta
                    </th>
                  ))}
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
                    {bases.map((b) => (
                      <td key={b}>
                        {nf(at(row, b).tax)} / {nf(at(row, b).tax_worker)} / {nf(at(row, b).income)} %
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <SqueezeRows
        rows={rows}
        year={year}
        bases={bases.map(String)}
        defaultBase={String(base)}
        lastYear={last}
        taxColor={TAX}
        workerColor={WORKER}
        incomeColor={INCOME}
        highlight="ES"
      />
      {ages ? (
        <AgeIncome data={ages} color={INCOME} peerColors={{ IT: "#7a7970", PT: "#eda100" }} peerLabels={{ IT: "Italia", PT: "Portugal" }} />
      ) : null}
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«El Estado es más rico y la gente, más pobre»</strong>
          En parte. Desde {outgrows.length > 1 ? `${outgrows.slice(0, -1).join(", ")} o ${outgrows.at(-1)}` : outgrows[0]} la recaudación real por habitante crece en España más que la renta de los hogares; solo desde{" "}
          {notOutgrows.join(" y ")} (pico de ingresos de la burbuja) no. En la UE la renta crece más que la recaudación desde {euIncomeAhead.length === bases.length ? "todos esos años" : euIncomeAhead.join(", ")}.
          Pero la renta española también sube (+{nf(b0.income)} % desde {base}): los hogares son más pobres frente a Europa (+{nf(eu0.income)} %), no
          frente a su pasado. Y una parte es composición: trabaja más gente (del {nf(b0.employment_rate[0])} % al {nf(b0.employment_rate[1])} % de la
          población) y por ocupado la recaudación sube un {nf(b0.tax_worker)} % (UE: {nf(eu0.tax_worker)} %).
        </li>
        {old && mid && allAges ? (
          <li>
            <strong>«Los hogares no han ganado nada en quince años»</strong>
            Depende de la edad. Desde las rentas de {ageBase}, la renta mediana real de todas las edades {moved(allAges.change[ageBase])}; la de los mayores de
            65 {moved(old.change[ageBase])}, y la de los de 25 a 49 años {moved(mid.change[ageBase])}. Los mayores pasan de tener el {nf(old.vs_total_first, 0)} % de la
            renta mediana de todos al {nf(old.vs_total_last, 0)} %. {ageBase} es el primer año comparable tras la ruptura de serie y el último antes de la crisis;
            con otro punto de partida la distancia cambia:{" "}
            {ages.bases
              .filter((b) => String(b) !== ageBase && old.change[String(b)] != null)
              .map((b) => `desde ${b}, ${signedPct1(old.change[String(b)])} frente a ${signedPct1(mid.change[String(b)])}`)
              .join("; ")}
            . Coincide con la subida de la pensión media real (<a href="#descomposicion">más pensión por pensionista</a>) mientras la renta de
            los adultos en edad de trabajar no ha recuperado la de antes de la crisis; coinciden en el tiempo, lo que no prueba que una cosa cause la otra.
            {ageGaps.length
              ? ` Desde ${ageBase}, en ${ageGaps
                  .map((g) => `${g.label} la distancia es ${g.old - g.mid < old.change[ageBase] - mid.change[ageBase] ? "menor" : "mayor"} (${signedPct1(g.old)} frente a ${signedPct1(g.mid)})`)
                  .join(" y en ")}.`
              : ""}
            {housing ? ` Y la renta disponible no cuenta la vivienda: el ${nf(housing.old_own_nl)} % de los hogares de 65 o más tiene la casa pagada; de los de 16 a 29 que se han ido de casa, el ${nf(housing.young_rent_mkt)} % alquila a precio de mercado (` : ""}
            {housing ? <a href="#cinco-hogares">cinco hogares</a> : null}
            {housing ? ")." : ""}
          </li>
        ) : null}
        <li>
          <strong>«En España se pagan más impuestos que en Alemania»</strong>
          No por habitante: en {year} se recaudan {nf(es.tax_pps, 0)} PPS por habitante (de hogares, empresas y no residentes) frente a {nf(de.tax_pps, 0)} en
          Alemania, y eso equivale al{" "}
          {nf(es.tax_to_income_pct)} % de la renta que les queda a los hogares, casi lo mismo que en Alemania ({nf(de.tax_to_income_pct)} %) y menos que en
          la UE ({nf(eu.tax_to_income_pct)} %). El índice de «esfuerzo fiscal» de Frank, que divide la presión fiscal por el PIB por habitante, deja a
          España en {nf(es.effort_index)} (UE = 100): por encima de {effortBelow.map((row) => `${row.label} (${nf(row.effort_index)})`).join(", ")} y por
          debajo de {effortAbove.map((row) => `${row.label} (${nf(row.effort_index)})`).join(", ")}. Es un índice discutido: supone que la capacidad de
          pagar crece en proporción a la renta y mezcla lo que pagan empresas y hogares.
        </li>
        {wEs && irpf ? (
          <li>
            <strong>«El contribuyente está asfixiado»</strong>
            Depende de quién y de dónde. El IRPF es progresivo: las declaraciones de más de 60.000 € (el {nf(highDecl)} %) pagan el {nf(highTax)} % de la
            cuota. Pero la cuña fiscal sobre un salario medio (IRPF y cotizaciones) ha subido en España del {nf(wEs.AW100[0])} % en {wedge.first_year} al {nf(wEs.AW100[1])} %
            en {wedge.year}{wFell.length ? `, mientras bajaba en ${wFell.join(", ")}` : ""} (<a href="#quien-carga">quién lo carga</a>).
            {topMin && topMax
              ? ` Y el tipo máximo del IRPF va del ${nf(topMin.top_rate_pct)} % de ${place(topMin)} al ${nf(topMax.top_rate_pct)} % de ${place(topMax)}, aunque en ${place(topMin)} se paga de media más IRPF (${nf(topMin.irpf_rate_pct)} % de la base)`
              : ""}
            {topMin ? (
              <>
                {" "}
                (<a href="#territorio">por comunidad</a>).
              </>
            ) : null}
          </li>
        ) : null}
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          Quién soporta de verdad cada impuesto y qué servicios recibe cada país a cambio (<a href="#destino">más abajo</a>). Son medias de contabilidad
          nacional: en la encuesta a los hogares, el hogar mediano español
          {survey ? ` (${nf(survey.es.median_income_pps, 0)} PPS por adulto equivalente)` : ""} está mucho más cerca de la mediana europea (
          <a href="#mediana-vivienda">figura siguiente</a>).
        </li>
      </ul>
    </Figure>
  );
}

export function SqueezeIndexFigure({ squeeze }) {
  const { index_first_year: first, index_last_year: last, bases } = squeeze;
  const rows = squeeze.areas.map((row) => ({ ...row, label: EU_LABELS[row.area] }));
  const es = rows.find((row) => row.area === "ES");
  const eu = rows.find((row) => row.area === "EU27_2020");
  const gap = (row, b) => row.by_base[String(b)].tax - row.by_base[String(b)].income;
  const wider = bases.filter((b) => gap(es, b) > gap(eu, b));
  const yMax =
    Math.ceil(Math.max(...rows.flatMap((row) => [...row.real_tax_index, ...row.real_tax_worker_index, ...row.real_income_index].map((p) => p.value))) / 10) * 10;
  const all = rows.flatMap((row) => [
    { id: `${row.area}-tax`, label: `${row.label}: impuestos reales por habitante`, points: row.real_tax_index },
    { id: `${row.area}-worker`, label: `${row.label}: impuestos reales por ocupado`, points: row.real_tax_worker_index },
    { id: `${row.area}-income`, label: `${row.label}: renta real de los hogares por habitante`, points: row.real_income_index },
  ]);
  return (
    <Figure
      id="indices"
      title={`${wider.length === bases.length ? "Con cualquier año de partida" : `Con ${wider.length} de los ${bases.length} años de partida (${bases.filter((b) => !wider.includes(b)).join(", ")} es la excepción)`}, la recaudación real por habitante se separa más de la renta de los hogares en España que en la UE`}
      dek={`Series completas, ${first} = 100, descontada la inflación. Distancia entre recaudación y renta en España frente a la UE, en puntos: ${bases
        .map((b) => `desde ${b}, ${nf(gap(es, b))} frente a ${nf(gap(eu, b))}`)
        .join("; ")}. La línea verde, por persona ocupada, quita lo que sube porque trabaja más gente. Todos los paneles comparten escala.`}
      legend={[
        { id: "tax", label: "Impuestos y cotizaciones por habitante (reales)", color: TAX },
        { id: "worker", label: "Impuestos y cotizaciones por ocupado (reales)", color: WORKER },
        { id: "income", label: "Renta disponible ajustada de los hogares por habitante (real)", color: INCOME },
      ]}
      sources={[...SOURCES, ds("nama_10_pe")]}
      notes={[
        "Mismos deflactores que la figura anterior. En 2020 (pandemia) la recaudación real por habitante cae más que la renta de los hogares en todos los países.",
        "España: la burbuja inflaba la recaudación hasta 2007 y la crisis la hundió hasta 2013; por eso un «desde» elegido en esos años da cifras muy distintas.",
      ]}
      table={<SeriesTable series={all} unit="count" />}
    >
      <div className="vizMultiples">
        {rows.map((row) => (
          <div key={row.area}>
            <h3 className="vizPanelTitle">
              {row.label}
              <span>
                desde {first}: impuestos {nf(row.by_base[String(first)].tax)} % · por ocupado {nf(row.by_base[String(first)].tax_worker)} % · renta{" "}
                {nf(row.by_base[String(first)].income)} %
              </span>
            </h3>
            <TimeSeriesChart
              series={[
                { id: "tax", label: "Impuestos", shortLabel: "Imp.", color: TAX, emphasis: true, points: row.real_tax_index },
                { id: "worker", label: "Por ocupado", shortLabel: "Ocup.", color: WORKER, points: row.real_tax_worker_index },
                { id: "income", label: "Renta", shortLabel: "Renta", color: INCOME, points: row.real_income_index },
              ]}
              unit="count"
              xMin={first}
              xMax={last}
              yMax={yMax}
              height={200}
              ariaLabel={`${row.label}: impuestos y renta reales, ${first} = 100`}
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

export function SurveyFigure({ squeeze, segments }) {
  const split = segments?.housing;
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
      sources={[ds("ilc_di03"), ds("ilc_mded01"), ds("ilc_mded02"), ds("ilc_lvho07c"), { label: "Visualizaciones · Vivienda (peso mediano, ilc_lvho08a)", href: "/visualizaciones/vivienda/" }]}
      notes={[
        `Encuesta frente a contabilidad nacional: aquí el hogar mediano español tiene el ${nf(pctOf(es.median_income_pps, eu.median_income_pps), 0)} % de la renta mediana de la UE; en la figura de arriba, la renta por habitante es el ${nf(pctOf(na.ES.income_pps, na.EU27_2020.income_pps), 0)} %. La encuesta no incluye los servicios públicos en especie ni el alquiler imputado de quien vive en casa propia, ajusta por tamaño del hogar y se basa en lo que declaran los hogares; las dos medidas son oficiales y miden cosas distintas.`,
        "Gastos de vivienda: alquiler o intereses de la hipoteca (no la amortización), suministros, comunidad, reparaciones, seguros e impuestos, netos de ayudas a la vivienda. Sobrecarga: más del 40 % de la renta disponible del hogar.",
        `Quien vive en casa propia sin hipoteca tiene gastos de vivienda bajos${split?.overburden?.OWN_NL != null ? ` (pasa del 40 % de su renta el ${nf(split.overburden.OWN_NL)} %)` : ""}; donde son muchos, como en España e Italia, el dato del país puede ser bajo aunque los inquilinos dediquen mucho más de su renta.`,
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
      {split ? (
        <>
          <h3 className="rgrid__title">España, {split.year}: el «{nf(split.cost_share_mean)} %» de la vivienda, desglosado (% de la renta disponible del hogar)</h3>
          <ul className="vizBars" style={{ width: "100%" }} aria-label="Peso de la vivienda en la renta, por medida y por hogar">
            {[
              ["Media de todos los hogares (la cifra habitual)", split.cost_share_mean],
              ["Hogar mediano", split.cost_share_median],
              ["Alquiler, hogares que alquilan", split.rent_share_renters],
              ["Alquiler, persona sola menor de 65 que alquila", split.rent_share_single_lt65],
            ]
              .filter(([, v]) => v != null)
              .map(([label, v]) => (
                <li key={label}>
                  <span>{label}</span>
                  <span className="vizBars__track">
                    <span className="vizBars__bar" style={{ width: `${(v / 50) * 100}%` }} />
                    <span className="vizBars__value">{nf(v)} %</span>
                  </span>
                </li>
              ))}
          </ul>
        </>
      ) : null}
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«Al español medio le queda mucho menos que al europeo»</strong>
          Depende de cómo se mida. Por habitante en contabilidad nacional, sí ({nf(pctOf(na.ES.income_pps, na.EU27_2020.income_pps), 0)} % de la UE). Para el
          hogar mediano de la encuesta, apenas: {nf(es.median_income_pps, 0)} frente a {nf(eu.median_income_pps, 0)} en la UE y {nf(de.median_income_pps, 0)} en
          Alemania ({nf(pctOf(es.median_income_pps, de.median_income_pps), 0)} %). La media española está un {nf(pctOf(es.mean_income_pps, es.median_income_pps) - 100, 0)} %
          por encima de su mediana
          {Math.abs(pctOf(es.mean_income_pps, es.median_income_pps) - pctOf(eu.mean_income_pps, eu.median_income_pps)) < 1
            ? `, lo mismo que en la UE (${nf(pctOf(eu.mean_income_pps, eu.median_income_pps) - 100, 0)} %): la distancia entre las dos medidas no va con una renta más desigual en España.`
            : `, frente al ${nf(pctOf(eu.mean_income_pps, eu.median_income_pps) - 100, 0)} % de la UE.`}
        </li>
        <li>
          <strong>«La vivienda se come lo que queda»</strong>
          No al hogar típico: los gastos de vivienda son el {nf(es.housing_cost_share)} % de la renta en España, menos que en la UE ({nf(eu.housing_cost_share)} %)
          y en Alemania ({nf(de.housing_cost_share)} %), y en España {split?.population?.OWN_NL != null ? `el ${nf(split.population.OWN_NL)} % de la población` : "mucha gente"} vive en casa pagada.
          {split
            ? ` Y ese ${nf(split.cost_share_mean)} % es una media de cocientes: el hogar mediano dedica el ${nf(split.cost_share_median)} %. Los que alquilan pagan solo de alquiler el ${nf(split.rent_share_renters)} % de su renta, y una persona sola de menos de 65 que alquila, el ${nf(split.rent_share_single_lt65)} %. Entre los propietarios sin hipoteca, solo el ${nf(split.overburden.OWN_NL)} % pasa del 40 %.`
            : ""} Sí a quien alquila: el {nf(es.overburden_renters)} % de los
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
