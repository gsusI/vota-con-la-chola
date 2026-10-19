import TimeSeriesChart from "../components/TimeSeriesChart";
import Figure from "../components/Figure";
import { formatValue } from "../components/format.mjs";

const COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"];

function spreadNote(territory) {
  const common = (territory?.rows || []).filter((row) => row.regime === "comun" && row.top_rate_pct != null);
  if (!common.length) return "";
  const lo = common.reduce((a, b) => (b.top_rate_pct < a.top_rate_pct ? b : a));
  const hi = common.reduce((a, b) => (b.top_rate_pct > a.top_rate_pct ? b : a));
  const pct = (v) => formatValue(v, "pct", 1);
  return ` (en ${territory.years?.top_rate_pct}, del ${pct(lo.top_rate_pct)} de ${lo.name} al ${pct(hi.top_rate_pct)} de ${hi.name})`;
}

const RATE_GROUPS = [
  {
    id: "personas",
    title: "Personas",
    series: [
      { key: "irpf_top_marginal_rate", label: "Tipo marginal máximo sobre la renta personal", shortLabel: "Renta, tipo máximo" },
      { key: "ssc_general_rate_employee", label: "Cotización social del trabajador", shortLabel: "Cotización trabajador" },
      { key: "vat_standard_rate", label: "Tipo general sobre el consumo (IVA; antes ITE)", shortLabel: "Consumo" },
    ],
  },
  {
    id: "empresas",
    title: "Empresas",
    series: [
      { key: "cit_general_rate", label: "Tipo general del Impuesto sobre Sociedades", shortLabel: "Beneficios" },
      { key: "ssc_general_rate_employer", label: "Cotización social a cargo de la empresa", shortLabel: "Cotización empresa" },
    ],
  },
];

function stepPoints(rows, lastYear) {
  return [...rows]
    .filter((row) => Number.isFinite(Number(row.value_pct)) && row.from_year <= lastYear)
    .sort((a, b) => a.from_year - b.from_year)
    .map((row) => ({ year: row.from_year, value: Number(row.value_pct) }));
}

function rateSources(rows) {
  const seen = new Map();
  for (const row of rows) {
    if (row.source_url && !seen.has(row.source_url)) seen.set(row.source_url, row.source);
  }
  return [...seen.entries()].map(([href, label]) => ({ href, label }));
}

export function StatutoryRatesFigure({ rates, lastYear, territory }) {
  const series = rates?.series;
  if (!series) return null;
  const groups = RATE_GROUPS.map((group) => ({
    ...group,
    series: group.series
      .filter((item) => series[item.key]?.length)
      .map((item, index) => ({ ...item, id: item.key, color: COLORS[index], step: true, until: lastYear, points: stepPoints(series[item.key], lastYear) })),
  })).filter((group) => group.series.length);
  const allRows = Object.values(series).flat();
  const yMax = Math.max(...allRows.map((row) => Number(row.value_pct) || 0));
  const firstYear = Math.min(...allRows.map((row) => row.from_year));
  const lowConfidence = allRows.filter((row) => row.confidence === "low");

  return (
    <Figure
      id="tipos"
      title="Los tipos que fija la ley: lo que paga cada euro adicional"
      dek="Tipos legales vigentes cada año, según la norma que los fijó. No son tipos efectivos (deducciones y bases cambian lo que se paga), pero muestran cuánto toma el sistema del último euro ganado, gastado o pagado en salario."
      sources={[
        ...rateSources(allRows.filter((row) => !String(row.source_url || "").includes("boe.es"))),
        { href: "https://www.boe.es/", label: `BOE: la norma de cada cambio (${allRows.filter((row) => String(row.source_url || "").includes("boe.es")).length} filas, en la tabla)` },
      ]}
      notes={[
        `Renta personal: tipo máximo de la escala general. Desde 1999 suma la escala estatal y la autonómica supletoria o de referencia; desde 2011 cada comunidad fija la suya${spreadNote(territory)}, así que la serie usa la escala de referencia.`,
        "Cotizaciones: régimen general, contrato indefinido (contingencias comunes, desempleo, FOGASA, formación profesional y, desde 2023, MEI). 1978 usa las antiguas bases tarifadas y no es comparable con los años siguientes; falta 1967–1977. Sociedades antes de 1967 no está verificado.",
        ...(lowConfidence.length ? [`${lowConfidence.length} valores con confianza baja; se señalan en la tabla.`] : []),
      ]}
      table={
        <details className="vizTable">
          <summary>Ver cada cambio de tipo con su norma</summary>
          <div className="vizTable__scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Desde</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Figura</th>
                  <th scope="col">Norma o fuente</th>
                </tr>
              </thead>
              <tbody>
                {RATE_GROUPS.flatMap((group) => group.series)
                  .flatMap((item) => (series[item.key] || []).map((row) => ({ ...row, item })))
                  .sort((a, b) => a.from_year - b.from_year)
                  .map((row, index) => (
                    <tr key={`${row.item.key}-${row.from_year}-${index}`}>
                      <td>
                        {row.from_year}
                        {row.from_year > lastYear ? " (programado)" : ""}
                      </td>
                      <td>
                        {formatValue(row.value_pct, "pct", 1)}
                        {row.confidence === "low" ? " (baja)" : ""}
                      </td>
                      <td>{row.item.shortLabel}</td>
                      <td>
                        {row.source_url ? (
                          <a href={row.source_url} rel="noopener noreferrer" target="_blank">
                            {row.label || row.source}
                          </a>
                        ) : (
                          row.label || row.source
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </details>
      }
    >
      <div className="vizMultiples">
        {groups.map((group) => (
          <div key={group.id}>
            <h3>{group.title}</h3>
            <ul className="vizLegend" aria-label={`Leyenda ${group.title}`}>
              {group.series.map((item) => (
                <li key={item.id}>
                  <span className="vizLegend__key" style={{ background: item.color }} aria-hidden="true" />
                  {item.label}
                </li>
              ))}
            </ul>
            <TimeSeriesChart
              series={group.series}
              xMin={firstYear}
              xMax={lastYear}
              yMax={yMax}
              height={260}
              endLabels={false}
              ariaLabel={`Tipos legales, ${group.title}`}
            />
          </div>
        ))}
      </div>
    </Figure>
  );
}

const FEATURED_LAWS = 4;

const LAW_SHORT = {
  "BOE-A-2006-20764": "IRPF",
  "BOE-A-1992-28740": "IVA",
  "BOE-A-1992-28741": "Impuestos Especiales",
  "BOE-A-1993-25359": "Transmisiones (ITPAJD)",
  "BOE-A-2004-4214": "Haciendas Locales",
  "BOE-A-2014-12328": "Sociedades",
  "BOE-A-1991-14392": "Patrimonio",
  "BOE-A-1987-28141": "Sucesiones y Donaciones",
  "BOE-A-2007-6820": "Reglamento del IRPF",
  "BOE-A-2003-23186": "General Tributaria",
};

const STRUCTURE_LABELS = [
  ["articulos", "Artículos"],
  ["disp_adicionales", "Disp. adicionales"],
  ["disp_transitorias", "Disp. transitorias"],
  ["disp_finales", "Disp. finales"],
];

export function ComplexityFigures({ complexity }) {
  if (!complexity) return null;
  const amendments = (complexity.amendments || [])
    .filter((law) => law.total > 0)
    .map((law) => ({ ...law, short: LAW_SHORT[law.boe_id] || law.law }))
    .sort((a, b) => b.total - a.total);
  const currentYear = Math.max(...amendments.flatMap((law) => Object.keys(law.by_year || {}).map(Number)));
  const lengths = (complexity.law_length || [])
    .filter((row) => row.words_excl_preamble > 0)
    .map((row) => ({ ...row, words: row.words_excl_preamble }));
  const maxTotal = Math.max(1, ...amendments.map((law) => law.total));
  const featured = amendments.slice(0, FEATURED_LAWS).map((law, index) => {
    let running = 0;
    const startYear = Number(String(law.enacted).slice(0, 4));
    const endYear = currentYear;
    const points = [];
    for (let year = startYear; year <= endYear; year += 1) {
      running += Number(law.by_year?.[String(year)] || 0);
      points.push({ year, value: running });
    }
    return { id: law.boe_id, label: `Ley de ${law.short}`, shortLabel: law.short, color: COLORS[index], points };
  });
  const startYear = Math.min(...featured.map((s) => s.points[0]?.year ?? 9999));
  const endYear = Math.max(...featured.map((s) => s.points.at(-1)?.year ?? 0));

  const lengthGroups = ["irpf", "is"]
    .map((tax) => ({ tax, rows: lengths.filter((row) => row.tax === tax).sort((a, b) => a.year - b.year) }))
    .filter((group) => group.rows.length);
  const structure = complexity.structure || [];
  const lengthMultiple = (tax) => {
    const rows = lengths.filter((row) => row.tax === tax).sort((a, b) => a.year - b.year || (a.version === "original" ? -1 : 1));
    return rows.length > 1 ? (rows.at(-1).words / rows[0].words).toLocaleString("es-ES", { maximumFractionDigits: 1 }) : "";
  };
  const maxWords = Math.max(1, ...lengths.map((row) => row.words));
  const boe = { label: "BOE, API de legislación consolidada", href: "https://www.boe.es/datosabiertos/api/api.php" };

  return (
    <>
      {amendments.length ? (
        <Figure
          id="modificaciones"
          title={`La ley del ${amendments[0].short} ha sido modificada por ${amendments[0].total} normas desde ${String(amendments[0].enacted).slice(0, 4)}`}
          dek={`Normas distintas que han modificado cada ley tributaria vigente desde su aprobación, según las referencias posteriores que registra el BOE. En total, ${amendments.reduce((sum, law) => sum + law.total, 0)} cambios en estas ${amendments.length} leyes (una misma norma puede modificar varias); cada uno obliga a contribuyentes, asesores y Administración a reaprender las reglas.`}
          sources={[boe]}
          notes={[
            "Cuenta una norma por ley aunque cambie varios artículos. Incluye «se modifica», «se añade», «se suprime», «se deroga» (parcial), «se sustituye», «se deja sin efecto» y «se suspende»; excluye correcciones de errores, actualizaciones de importes, sentencias e interpretaciones.",
            `Año = publicación en el BOE de la norma modificadora; ${currentYear} va hasta la fecha de consulta.`,
          ]}
          table={
            <details className="vizTable">
              <summary>Ver todas las leyes y las normas que las modifican</summary>
              <div className="vizTable__scroll">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Ley</th>
                      <th scope="col">Aprobada</th>
                      <th scope="col">Normas modificadoras</th>
                    </tr>
                  </thead>
                  <tbody>
                    {amendments.map((law) => (
                      <tr key={`row-${law.boe_id}`}>
                        <td>
                          <a href={law.url} rel="noopener noreferrer" target="_blank">
                            {law.law}
                          </a>
                        </td>
                        <td>{String(law.enacted).slice(0, 4)}</td>
                        <td>{law.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          }
        >
          <ul className="vizBars" aria-label="Normas modificadoras por ley">
            {amendments.map((law) => (
              <li key={law.boe_id}>
                <span>{law.short}</span>
                <span className="vizBars__track">
                  <span className="vizBars__bar" style={{ width: `${(law.total / maxTotal) * 100}%` }} />
                  <span className="vizBars__value">{law.total}</span>
                </span>
              </li>
            ))}
          </ul>
          {featured.length ? (
            <>
              <h3 className="vizPanelTitle">
                Modificaciones acumuladas de las {featured.length} leyes más cambiadas
                <span>Cada línea empieza el año en que se aprobó la ley.</span>
              </h3>
              <ul className="vizLegend" aria-label="Leyenda de modificaciones acumuladas">
                {featured.map((item) => (
                  <li key={item.id}>
                    <span className="vizLegend__key" style={{ background: item.color }} aria-hidden="true" />
                    {item.label}
                  </li>
                ))}
              </ul>
              <TimeSeriesChart
              series={featured}
              unit="count"
              xMin={startYear}
              xMax={endYear}
              height={300}
                ariaLabel="Modificaciones acumuladas de las principales leyes tributarias"
              />
            </>
          ) : null}
        </Figure>
      ) : null}

      {lengthGroups.length ? (
        <Figure
          id="extension"
          title={`El texto vigente de la ley del IRPF multiplica por ${lengthMultiple("irpf")} las palabras de la de 1978`}
          dek="Palabras de la parte dispositiva (sin preámbulo) de cada ley del impuesto sobre la renta y del de sociedades tal como se publicó, y del texto consolidado vigente hoy. No incluye reglamentos, órdenes ni normativa autonómica, que añaden mucho más."
          sources={[boe]}
          notes={[
            "Las leyes de 2006 y 2014 se cuentan tal como se publicaron, incluidas sus disposiciones finales que modifican otras leyes. La Contribución General sobre la Renta de 1932 solo está en PDF en la Gaceta y no se ha contado.",
          ]}
          table={
            structure.length ? (
              <details className="vizTable" open>
                <summary>Estructura de los textos vigentes</summary>
                <div className="vizTable__scroll">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Ley</th>
                        {STRUCTURE_LABELS.map(([key, label]) => (
                          <th scope="col" key={key}>
                            {label}
                          </th>
                        ))}
                        <th scope="col">Palabras</th>
                      </tr>
                    </thead>
                    <tbody>
                      {structure.map((row) => (
                        <tr key={row.boe_id}>
                          <td>
                            <a href={row.url} rel="noopener noreferrer" target="_blank">
                              {LAW_SHORT[row.boe_id] || row.law}
                            </a>
                          </td>
                          {STRUCTURE_LABELS.map(([key]) => (
                            <td key={key}>{row.counts?.[key] ?? ""}</td>
                          ))}
                          <td>{formatValue(row.words_excl_preamble, "count")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            ) : null
          }
        >
          <div className="vizStack">
            {lengthGroups.map((group) => (
              <div key={group.tax}>
                <h3>{group.tax === "irpf" ? "Impuesto sobre la renta (IRPF)" : "Impuesto sobre Sociedades"}</h3>
                <ul className="vizBars">
                  {group.rows.map((row) => (
                    <li key={`${row.boe_id}-${row.version}`}>
                      <span>
                        <a href={`https://www.boe.es/buscar/act.php?id=${row.boe_id}`} rel="noopener noreferrer" target="_blank">
                          {row.law}
                        </a>{" "}
                        · {row.version === "original" ? `${row.year}, original` : `consolidada ${String(row.version).replace("consolidated-", "")}`}
                      </span>
                      <span className="vizBars__track">
                        <span className="vizBars__bar" style={{ width: `${(row.words / maxWords) * 100}%` }} />
                        <span className="vizBars__value">{formatValue(row.words, "count")} palabras</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Figure>
      ) : null}
    </>
  );
}
