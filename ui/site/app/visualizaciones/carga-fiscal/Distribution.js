import Figure from "../components/Figure";
import ResultsGrid from "./ResultsGrid";

// Who carries it: IRPF by income bracket (AEAT), redistribution by stage (OECD IDD) and tax wedge by wage level
// (OECD Taxing Wages), Spain against peers.
const OECD_LABELS = { ESP: "España", DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal" };
const nf = (v, digits = 1) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const dbn = (label, code) => ({ label, href: `https://db.nomics.world/OECD/${code}` });

function bracketLabel(b) {
  if (b.upper_eur === 0 && b.lower_eur == null) return "Negativa o cero";
  const k = (v) => `${nf(v / 1000, v % 1000 ? 1 : 0)} mil`;
  if (b.upper_eur == null) return `Más de ${k(b.lower_eur)} €`;
  if (!b.lower_eur) return `Hasta ${k(b.upper_eur)} €`;
  return `${k(b.lower_eur)}–${k(b.upper_eur)} €`;
}

export default function DistributionFigure({ distribution, irpfSource }) {
  const irpf = distribution.irpf;
  const red = distribution.redistribution._T;
  const redW = distribution.redistribution.Y18T65;
  const wedge = distribution.tax_wedge;
  const brackets = irpf.brackets.map((b, i) => ({ ...b, area: `b${i}`, label: bracketLabel(b) }));
  const sum = (list, key) => list.reduce((acc, b) => acc + b[key], 0);
  const high = brackets.filter((b) => (b.lower_eur || 0) >= 60000);
  const middle = brackets.filter((b) => (b.lower_eur || 0) >= 21000 && (b.upper_eur || Infinity) <= 60000);
  const low = brackets.filter((b) => b.upper_eur != null && b.upper_eur <= 12000);
  const top = brackets.at(-1);
  const shareMax = Math.ceil(Math.max(...brackets.flatMap((b) => [b.share_declarations_pct, b.share_tax_pct])) / 10) * 10;
  const rateMax = Math.ceil(Math.max(...brackets.map((b) => b.effective_rate_pct || 0)) / 10) * 10;
  const bracketIndicators = [
    { key: "decl", short: "Declaraciones (% del total)", note: "misma escala que la columna siguiente", digits: 1, max: shareMax, color: "#b4b2a9",
      values: Object.fromEntries(brackets.map((b) => [b.area, { value: b.share_declarations_pct }])) },
    { key: "tax", short: "Cuota del IRPF (% del total)", note: "quién paga el impuesto", digits: 1, max: shareMax, color: "#eb6834",
      values: Object.fromEntries(brackets.map((b) => [b.area, { value: b.share_tax_pct }])) },
    { key: "rate", short: "Tipo efectivo (cuota / base)", note: "% de su base imponible", digits: 1, max: rateMax, color: "#2a78d6",
      values: Object.fromEntries(brackets.map((b) => [b.area, { value: b.effective_rate_pct }])) },
  ];
  const rows = (list) => list.map((row) => ({ ...row, label: OECD_LABELS[row.area] }));
  const giniMax = Math.ceil(Math.max(...red.map((row) => row.market)) / 10) * 10;
  const redMax = Math.ceil(Math.max(...red.flatMap((row) => [row.by_transfers, row.by_taxes])) / 5) * 5;
  const redIndicators = (list) => [
    { key: "market", short: "Gini antes de impuestos y transferencias", note: "renta de mercado", digits: 1, max: giniMax, values: Object.fromEntries(list.map((row) => [row.area, { value: row.market, year: row.year }])) },
    { key: "disposable", short: "Gini final", note: "renta disponible", digits: 1, max: giniMax, values: Object.fromEntries(list.map((row) => [row.area, { value: row.disposable, year: row.year }])) },
    { key: "transfers", short: "Lo reducen las transferencias", note: "puntos de Gini (pensiones incluidas)", digits: 1, max: redMax, color: "#1baf7a", values: Object.fromEntries(list.map((row) => [row.area, { value: row.by_transfers, year: row.year }])) },
    { key: "taxes", short: "Lo reducen los impuestos directos", note: "puntos de Gini", digits: 1, max: redMax, color: "#eb6834", values: Object.fromEntries(list.map((row) => [row.area, { value: row.by_taxes, year: row.year }])) },
  ];
  const wedgeMax = Math.ceil(Math.max(...wedge.areas.flatMap((row) => [row.AW67[1], row.AW100[1], row.AW167[1]])) / 10) * 10;
  const wedgeIndicators = [
    ["AW67", "Gana el 67 % del salario medio"],
    ["AW100", "Gana el salario medio"],
    ["AW167", "Gana el 167 % del salario medio"],
  ].map(([lvl, label]) => ({
    key: lvl, short: label, note: `cuña ${wedge.year} (cambio desde ${wedge.first_year})`, digits: 1, max: wedgeMax,
    values: Object.fromEntries(wedge.areas.map((row) => [row.area, { value: row[lvl][1], delta: row[lvl][1] - row[lvl][0] }])),
  }));
  const es = red.find((row) => row.area === "ESP");
  const moreRedistributive = red.filter((row) => row.area !== "ESP" && row.by_taxes > es.by_taxes).map((row) => OECD_LABELS[row.area]);
  const wEs = wedge.areas.find((row) => row.area === "ESP");
  const fell = wedge.areas.filter((row) => row.area !== "ESP" && row.AW100[1] < row.AW100[0]).map((row) => OECD_LABELS[row.area]);
  const join = (items) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} ${/^h?i(?![aeou])/i.test(items.at(-1)) ? "e" : "y"} ${items.at(-1)}` : items[0] || "");

  return (
    <Figure
      id="quien-carga"
      title={`El IRPF es progresivo: las declaraciones de más de 60.000 € (el ${nf(sum(high, "share_declarations_pct"))} %) pagan el ${nf(sum(high, "share_tax_pct"))} % de la cuota; pero la cuña fiscal sobre un salario medio ha subido en España ${nf(wEs.AW100[1] - wEs.AW100[0])} puntos desde ${wedge.first_year}${fell.length ? ` mientras bajaba en ${join(fell)}` : ""}`}
      dek={`Quién carga con los impuestos directos, en tres capas. Arriba, el IRPF de ${irpf.tax_year} por tramos de rendimientos: qué parte de las declaraciones y de la cuota corresponde a cada tramo y su tipo efectivo. En medio, cuánto reducen la desigualdad las transferencias y los impuestos directos en España y en sus vecinos. Abajo, la cuña fiscal (IRPF y cotizaciones del trabajador y la empresa sobre el coste laboral) a tres niveles de salario.`}
      sources={[irpfSource, dbn("OCDE, Income Distribution Database", "DSD_WISE_IDD@DF_IDD"), dbn("OCDE, Taxing Wages", "DSD_TAX_WAGES_COMP@DF_TW_COMP")]}
      notes={[
        `IRPF: declaraciones de régimen común (sin País Vasco ni Navarra, que tienen su propio IRPF); una declaración conjunta cuenta una vez. Tramos por rendimientos e imputaciones (variable de la AEAT); tipo efectivo = cuota resultante de la autoliquidación / base imponible general y del ahorro. Quien no declara (por debajo del umbral obligatorio) no aparece.`,
        "Gini de la OCDE (0–100): renta de mercado (trabajo y capital), después de transferencias públicas (pensiones incluidas) y después de impuestos directos y cotizaciones del hogar. Último año de cada país. Con toda la población, las pensiones pesan mucho en «transferencias»; la tabla de 18 a 65 años lo aísla.",
        "No incluye el IVA ni los impuestos especiales, que pesan proporcionalmente más en los hogares de renta baja, ni las cotizaciones empresariales como carga del trabajador (sí en la cuña).",
      ]}
    >
      <h3 className="rgrid__title">IRPF {irpf.tax_year} por tramos de rendimientos</h3>
      <ResultsGrid rows={brackets} indicators={bracketIndicators} highlight={null} color="#2a78d6" peerColor="#b4b2a9" ariaLabel="IRPF por tramos de rendimientos" rowHeader="Rendimientos" />
      <h3 className="rgrid__title">Cuánto reducen la desigualdad (toda la población)</h3>
      <ResultsGrid rows={rows(red)} indicators={redIndicators(red)} highlight="ESP" color="#2a78d6" peerColor="#b4b2a9" ariaLabel="Redistribución por etapas" />
      <details className="vizTable">
        <summary>Lo mismo para la población de 18 a 65 años (sin el peso de las pensiones)</summary>
        <ResultsGrid rows={rows(redW)} indicators={redIndicators(redW)} highlight="ESP" color="#2a78d6" peerColor="#b4b2a9" ariaLabel="Redistribución, 18 a 65 años" />
      </details>
      <h3 className="rgrid__title">Cuña fiscal sobre el coste laboral, soltero sin hijos</h3>
      <ResultsGrid rows={rows(wedge.areas)} indicators={wedgeIndicators} highlight="ESP" color="#2a78d6" peerColor="#b4b2a9" ariaLabel="Cuña fiscal por nivel de salario" />
      <ul className="vizRelatos" aria-label="Qué relatos zanja y qué queda abierto">
        <li>
          <strong>«La clase media lo paga todo»</strong>
          Paga la mayor parte: los tramos de 21.000 a 60.000 € son el {nf(sum(middle, "share_declarations_pct"))} % de las declaraciones y pagan el{" "}
          {nf(sum(middle, "share_tax_pct"))} % del IRPF, con tipos efectivos de entre el {nf(middle[0].effective_rate_pct)} % y el{" "}
          {nf(middle.at(-1).effective_rate_pct)} %. Por debajo de 12.000 € (el {nf(sum(low, "share_declarations_pct"))} %) apenas se paga IRPF (
          {nf(sum(low, "share_tax_pct"))} % de la cuota).
        </li>
        <li>
          <strong>«Los ricos no pagan»</strong>
          Pagan más en proporción: más de 601.000 € tributan de media al {nf(top.effective_rate_pct)} % de su base, por debajo del tipo marginal máximo
          porque el tipo efectivo promedia todos los tramos y deducciones y las rentas del ahorro tienen una escala propia más baja. Y los impuestos
          directos reducen la desigualdad menos en España
          ({nf(es.by_taxes)} puntos de Gini) que en {join(moreRedistributive) || "ningún vecino"}.
        </li>
        <li>
          <strong>Lo que esta figura no resuelve</strong>
          Los impuestos indirectos por nivel de renta, quién soporta de verdad las cotizaciones de la empresa, la renta que no se declara y cómo cambia el
          reparto por edad.
        </li>
      </ul>
    </Figure>
  );
}
