import { formatHealth } from "./format.mjs";

// Table twin of every chart (copy of ../components/Figure.js SeriesTable with this page's units and period labels).
export default function HealthTable({ series, unit = "pct", digits = 1, caption = "Ver los datos en tabla", periodLabel = "Año", keyOf = (p) => p.year, labelOf = (k) => k }) {
  const keys = [...new Set(series.flatMap((s) => s.points.map(keyOf)))].sort((a, b) => (a < b ? 1 : a > b ? -1 : 0));
  const lookup = series.map((s) => new Map(s.points.map((p) => [keyOf(p), p])));
  return (
    <details className="vizTable">
      <summary>{caption}</summary>
      <div className="vizTable__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">{periodLabel}</th>
              {series.map((s) => (
                <th scope="col" key={s.id}>
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {keys.map((key) => (
              <tr key={key}>
                <td>{labelOf(key)}</td>
                {lookup.map((map, index) => {
                  const point = map.get(key);
                  return (
                    <td key={series[index].id}>
                      {point ? formatHealth(point.value, series[index].unit || unit, series[index].digits ?? digits) : ""}
                      {point?.status ? <sup title={`Marca de la fuente: ${point.status}`}> {point.status}</sup> : null}
                      {point?.breaks ? <sup title={point.breaks.join(" ")}> ruptura</sup> : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function Bars({ rows, unit, digits = 0, highlight, label = "Valores", max }) {
  const top = max ?? Math.max(...rows.filter((row) => row.value != null).map((row) => row.value));
  const base = highlight ? "#b4b2a9" : "#2a78d6";
  return (
    <ul className="vizBars" aria-label={label}>
      {rows.map((row) => (
        <li key={row.code}>
          <span style={row.code === highlight ? { fontWeight: 700 } : undefined}>{row.name}</span>
          <span className="vizBars__track">
            {row.value == null ? (
              <span className="vizBars__value" style={{ fontWeight: 400, color: "var(--ink-muted)" }}>sin dato</span>
            ) : (
              <>
                <span
                  className="vizBars__bar"
                  style={{ width: `${(row.value / top) * 100}%`, background: row.code === highlight ? "#2a78d6" : row.color || base }}
                />
                <span className="vizBars__value">{formatHealth(row.value, unit, digits)}</span>
              </>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}
