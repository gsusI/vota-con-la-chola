import Figure from "../components/Figure";
import { fmt, num } from "./format.mjs";

// Page-local building blocks for /visualizaciones/empleo/ (inline styles: the section CSS is shared).

const explainStyle = {
  display: "grid",
  gap: 6,
  margin: "4px 0 0",
  padding: "12px 14px",
  borderRadius: 10,
  background: "var(--viz-band)",
  fontSize: "0.9rem",
  lineHeight: 1.45,
};

// «Qué muestra / Cómo leerlo / Qué no dice» under every chart.
export function Explain({ what, read, not }) {
  return (
    <div style={explainStyle} className="vizExplain">
      {what ? (
        <p style={{ margin: 0 }}>
          <strong>Qué muestra.</strong> {what}
        </p>
      ) : null}
      {read ? (
        <p style={{ margin: 0 }}>
          <strong>Cómo leerlo.</strong> {read}
        </p>
      ) : null}
      {not ? (
        <p style={{ margin: 0 }}>
          <strong>Qué no dice.</strong> {not}
        </p>
      ) : null}
    </div>
  );
}

export function Fig({ explain, children, ...props }) {
  return (
    <Figure {...props}>
      {children}
      {explain ? <Explain {...explain} /> : null}
    </Figure>
  );
}

// Horizontal bars for one value per category (latest-year comparisons). Values must be >= 0.
export function CategoryBars({ rows, unit = "pct", digits = 1, highlight = [], max, label }) {
  const top = max ?? Math.max(...rows.map((row) => row.value));
  return (
    <ul className="vizBars" aria-label={label}>
      {rows.map((row) => (
        <li key={row.id}>
          <span>{row.label}</span>
          <span className="vizBars__track">
            <span
              className="vizBars__bar"
              style={{
                width: `${Math.max(0, (row.value / top) * 100)}%`,
                background: row.color || (highlight.includes(row.id) ? "var(--viz-s1)" : "var(--viz-peer)"),
              }}
            />
            <span className="vizBars__value">{fmt(row.value, unit, digits)}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// Paired bars around a zero line: e.g. GDP change vs employment change per country in a recession.
export function PairedBars({ rows, measures, unit = "growth", label }) {
  const extent = Math.max(1, ...rows.flatMap((row) => measures.map((m) => Math.abs(row[m.key] ?? 0))));
  const width = (value) => `${(Math.abs(value) / extent) * 36}%`; // leaves room for the value labels
  return (
    <div role="table" aria-label={label} style={{ display: "grid", gap: 10 }}>
      {measures.length > 1 ? (
      <ul className="vizLegend" aria-label="Leyenda">
        {measures.map((m) => (
          <li key={m.key}>
            <span className="vizLegend__key" style={{ background: m.color, height: 10, width: 10 }} aria-hidden="true" />
            {m.label}
          </li>
        ))}
      </ul>
      ) : null}
      {rows.map((row) => (
        <div role="row" key={row.id} style={{ display: "grid", gridTemplateColumns: "minmax(90px, 140px) 1fr", gap: 10, alignItems: "center" }}>
          <span role="rowheader" style={{ fontSize: "0.84rem", fontWeight: row.emphasis ? 700 : 400 }}>
            {row.label}
          </span>
          <div style={{ display: "grid", gap: 3 }}>
            {measures.map((m) => {
              const value = row[m.key];
              if (value == null) return null;
              const negative = value < 0;
              return (
                <div role="cell" key={m.key} style={{ position: "relative", height: 16, fontSize: "0.78rem" }}>
                  <span aria-hidden="true" style={{ position: "absolute", left: "50%", top: -2, bottom: -2, borderLeft: "1px solid var(--viz-axis)" }} />
                  <span
                    aria-hidden="true"
                    style={{
                      position: "absolute",
                      top: 2,
                      height: 12,
                      background: row.color || m.color,
                      opacity: row.emphasis ? 1 : 0.7,
                      left: negative ? `calc(50% - ${width(value)})` : "50%",
                      width: width(value),
                      borderRadius: negative ? "3px 0 0 3px" : "0 3px 3px 0",
                    }}
                  />
                  <span
                    style={{
                      position: "absolute",
                      top: 0,
                      whiteSpace: "nowrap",
                      fontWeight: 600,
                      ...(negative ? { right: `calc(50% + ${width(value)} + 4px)` } : { left: `calc(50% + ${width(value)} + 4px)` }),
                    }}
                  >
                    {fmt(value, unit)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// Plain table twin for categorical figures.
export function DataTable({ caption = "Ver los datos en tabla", columns, rows, open = false }) {
  return (
    <details className="vizTable" open={open} style={{ minWidth: 0 }}>
      <summary>{caption}</summary>
      <div className="vizTable__scroll">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th scope="col" key={col.key}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id ?? index}>
                {columns.map((col) => (
                  <td key={col.key}>{col.format ? col.format(row[col.key], row) : row[col.key] ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function Chapter({ id, kicker, title, children }) {
  return (
    <section className="card vizProse" id={id} aria-labelledby={`${id}-title`}>
      <p style={{ margin: 0, fontSize: "0.78rem", letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--viz-muted)" }}>{kicker}</p>
      <h2 id={`${id}-title`}>{title}</h2>
      {children}
    </section>
  );
}

export { num };
