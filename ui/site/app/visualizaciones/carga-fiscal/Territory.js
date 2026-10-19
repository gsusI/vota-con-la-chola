import Figure from "../components/Figure";
import ResultsGrid from "./ResultsGrid";
import { place, placeTitle } from "./places.mjs";
import "./consolidated.css";

// Territory: the top IRPF rate in every autonomous community (common and foral regimes) on the same axis as the peer
// countries, then regional financing, spending, income and the IRPF actually paid.
const OECD_LABELS = { ESP: "España (media OCDE de las escalas)", DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal" };
const COLOR = { comun: "#2a78d6", foral: "#eda100", peer: "#b4b2a9", ref: "#52514e" };
const nf = (v, digits = 1) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });

function RankedBars({ rows, max }) {
  const ticks = [];
  for (let t = 0; t <= max; t += 10) ticks.push(t);
  const x = (v) => `${(v / max) * 100}%`;
  return (
    <div className="rbars" role="table" aria-label="Tipo marginal máximo del IRPF por comunidad y país">
      {rows.map((row) => (
        <div className="rbars__row" role="row" key={row.key} data-kind={row.kind}>
          <span role="rowheader" className="rbars__label">
            {row.label}
          </span>
          <span className="rbars__track" role="cell">
            {ticks.map((t) => (
              <span key={t} className="psplit__tick" style={{ left: x(t) }} aria-hidden="true" />
            ))}
            <span className="rbars__bar" style={{ width: x(row.value), background: COLOR[row.kind] }} />
          </span>
          <span className="rbars__value" role="cell">
            {nf(row.value)} %{row.note ? <small> {row.note}</small> : null}
          </span>
        </div>
      ))}
      <div className="rbars__row rbars__axis" aria-hidden="true">
        <span />
        <span className="rbars__track">
          {ticks.map((t) => (
            <span key={t} className="sq__tickLabel" style={{ left: x(t) }}>
              {t} %
            </span>
          ))}
        </span>
        <span />
      </div>
    </div>
  );
}

export default function TerritoryFigure({ territory, sources }) {
  const peers = territory.peers_top_rates;
  const regions = territory.rows;
  const common = regions.filter((row) => row.regime === "comun");
  const lo = common.reduce((a, b) => (b.top_rate_pct < a.top_rate_pct ? b : a));
  const hi = common.reduce((a, b) => (b.top_rate_pct > a.top_rate_pct ? b : a));
  const peerRows = peers.areas.filter((row) => row.area !== "ESP");
  const pLo = peerRows.reduce((a, b) => (b.top_rate_pct < a.top_rate_pct ? b : a));
  const pHi = peerRows.reduce((a, b) => (b.top_rate_pct > a.top_rate_pct ? b : a));
  const esOecd = peers.areas.find((row) => row.area === "ESP");
  const thousand = (v) => `${nf(v / 1000, 0)} mil €`;
  const bars = [
    ...regions.map((row) => ({
      key: row.code,
      label: row.regime === "foral" ? `${row.code === "NC" ? "Navarra" : row.name} (foral)` : row.name,
      value: row.top_rate_pct,
      kind: row.regime,
      note: row.regional_threshold_eur ? `desde ${thousand(row.regime === "foral" ? row.regional_threshold_eur : Math.max(territory.state_top_threshold_eur, row.regional_threshold_eur))}` : "",
    })),
    ...peerRows.map((row) => ({ key: row.area, label: OECD_LABELS[row.area], value: row.top_rate_pct, kind: "peer", note: `desde ${nf(row.threshold_x_avg_wage)} × salario medio` })),
    { key: "ESP", label: OECD_LABELS.ESP, value: esOecd.top_rate_pct, kind: "ref", note: `${peers.year}` },
  ].sort((a, b) => b.value - a.value);
  const y = territory.years;
  const by = (key) => Object.fromEntries(regions.filter((row) => row[key] != null).map((row) => [row.code, { value: row[key] }]));
  const indicators = [
    { key: "gdp", short: `PIB por habitante ${y.gdp_per_inhabitant_eur} (€)`, note: "INE", digits: 0, values: by("gdp_per_inhabitant_eur") },
    { key: "fin", short: `Financiación por habitante ajustado ${y.financing_per_adj_inhabitant_eur} (€)`, note: "antes de fondos de convergencia", digits: 0, values: by("financing_per_adj_inhabitant_eur") },
    { key: "fin2", short: "Ídem, con fondos de convergencia (€)", note: "cálculo propio", digits: 0, values: by("financing_after_funds_per_adj_inhabitant_eur") },
    { key: "spend", short: `Gasto de la comunidad por habitante ${y.spending_per_inhabitant_eur} (€)`, note: "no financiero, liquidado", digits: 0, values: by("spending_per_inhabitant_eur") },
    { key: "irpf", short: `IRPF pagado, % de la base ${territory.irpf_tax_year}`, note: "AEAT, régimen común", digits: 1, values: by("irpf_rate_pct") },
    { key: "irpf_ret", short: `IRPF por declaración ${territory.irpf_tax_year} (€)`, note: "media", digits: 0, values: by("irpf_tax_per_return_eur") },
  ];
  const gridRows = [...regions]
    .sort((a, b) => (b.gdp_per_inhabitant_eur || 0) - (a.gdp_per_inhabitant_eur || 0))
    .map((row) => ({ area: row.code, label: row.regime === "foral" ? `${row.code === "NC" ? "Navarra" : row.name} (foral)` : row.name }));
  const irpfTop = common.reduce((a, b) => ((b.irpf_rate_pct || 0) > (a.irpf_rate_pct || 0) ? b : a));
  const irpfLow = common.reduce((a, b) => ((b.irpf_rate_pct ?? 99) < (a.irpf_rate_pct ?? 99) ? b : a));
  const finLo = common.reduce((a, b) => (b.financing_per_adj_inhabitant_eur < a.financing_per_adj_inhabitant_eur ? b : a));
  const finHi = common.reduce((a, b) => (b.financing_per_adj_inhabitant_eur > a.financing_per_adj_inhabitant_eur ? b : a));
  const spendHiCommon = common.reduce((a, b) => (b.spending_per_inhabitant_eur > a.spending_per_inhabitant_eur ? b : a));
  const forals = regions.filter((row) => row.regime === "foral");
  const wider = hi.top_rate_pct - lo.top_rate_pct > pHi.top_rate_pct - pLo.top_rate_pct;

  return (
    <Figure
      id="territorio"
      title={`El tipo máximo del IRPF va del ${nf(lo.top_rate_pct)} % de ${place(lo)} al ${nf(hi.top_rate_pct)} % de ${place(hi)}: ${wider ? "más distancia dentro de España que" : "tanta distancia dentro de España como"} entre sus vecinos (del ${nf(pLo.top_rate_pct)} % de ${OECD_LABELS[pLo.area]} al ${nf(pHi.top_rate_pct)} % de ${OECD_LABELS[pHi.area]})`}
      dek={`Tipo marginal máximo del IRPF sobre la renta general en ${y.top_rate_pct}: el estatal (${nf(territory.state_top_rate_pct)} %) más el de cada comunidad; País Vasco y Navarra tienen su propio IRPF (foral). En el mismo eje, el de los países vecinos según la OCDE. Debajo, lo que cada comunidad recibe del sistema de financiación, lo que gasta y lo que sus contribuyentes pagan de verdad en IRPF, ordenadas por PIB por habitante.`}
      legend={[
        { id: "comun", label: "Comunidad de régimen común", color: COLOR.comun },
        { id: "foral", label: "Régimen foral", color: COLOR.foral },
        { id: "peer", label: "País vecino (OCDE)", color: COLOR.peer },
        { id: "ref", label: "España, media de la OCDE", color: COLOR.ref },
      ]}
      legendKind="bar"
      sources={sources}
      notes={[
        `En régimen común el tipo máximo combinado solo se alcanza por encima de ${nf(territory.state_top_threshold_eur, 0)} € de base liquidable (umbral del tramo estatal, Ley 35/2006, art. 63); el tramo autonómico más alto empieza antes, desde ${nf(territory.regional_threshold_range[0].threshold_eur, 0)} € (${territory.regional_threshold_range[0].name}) hasta ${nf(territory.regional_threshold_range[1].threshold_eur, 0)} € (${territory.regional_threshold_range[1].name}). Las rentas del ahorro tienen otra escala.`,
        "País Vasco: escala de Gipuzkoa de 2024 (bizkaia.eus cortó la conexión al descargar y Álava y Gipuzkoa no tenían publicado el resumen de 2025); confianza media. Navarra: texto consolidado de su ley del IRPF en el BOE.",
        "Financiación: liquidación del sistema de régimen común (Hacienda), por habitante ajustado (población ponderada por necesidades de gasto); la columna con fondos de convergencia es un cálculo propio. País Vasco y Navarra no están en el sistema común (Concierto y Convenio) y no hay una cifra oficial comparable.",
        "Gasto por habitante: presupuestos liquidados de cada comunidad, sin las transferencias a ayuntamientos ni la PAC. No es comparable uno a uno: las forales y algunas comunes (policía en Cataluña) tienen más competencias.",
        "IRPF pagado: cuota resultante de la autoliquidación sobre la base imponible (AEAT), solo régimen común.",
      ]}
    >
      <RankedBars rows={bars} max={60} />
      <h3 className="rgrid__title">Financiación, gasto y lo que se paga de verdad, por comunidad</h3>
      <ResultsGrid rows={gridRows} indicators={indicators} highlight={null} color="#2a78d6" peerColor="#8db6e8" ariaLabel="Finanzas por comunidad" rowHeader="Comunidad" />
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«{placeTitle(lo)} es un paraíso fiscal»</strong>
          Tiene el tipo máximo más bajo ({nf(lo.top_rate_pct)} %), pero sus contribuyentes pagan de media el {nf(lo.irpf_rate_pct)} % de su base, el más{" "}
          {irpfTop.code === lo.code ? "alto" : `alto tras ${place(irpfTop)}`} de las comunidades de régimen común (frente al {nf(irpfLow.irpf_rate_pct)} % de {place(irpfLow)}), porque sus rentas son más altas:{" "}
          {nf(lo.irpf_tax_per_return_eur, 0)} € por declaración. El tipo máximo afecta a muy pocos.
        </li>
        <li>
          <strong>«Unas comunidades reciben mucho más que otras»</strong>
          Sí, y no sigue a la renta: antes de los fondos de convergencia, la financiación por habitante ajustado va de {nf(finLo.financing_per_adj_inhabitant_eur, 0)} €
          en {place(finLo)} a {nf(finHi.financing_per_adj_inhabitant_eur, 0)} € en {place(finHi)}. Los fondos suben a las de abajo hasta la media. Las forales gastan
          más por habitante ({forals.map((row) => `${placeTitle(row)}: ${nf(row.spending_per_inhabitant_eur, 0)} €`).join("; ")}) que cualquier común (máximo{" "}
          {nf(spendHiCommon.spending_per_inhabitant_eur, 0)} € en {place(spendHiCommon)}), con más competencias y su propio sistema.
        </li>
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          Los tipos efectivos por tramo en cada comunidad, los impuestos cedidos (patrimonio, sucesiones), la financiación comparable del País Vasco y Navarra y
          los saldos fiscales (cuánto aporta y recibe cada territorio del Estado).
        </li>
      </ul>
    </Figure>
  );
}
