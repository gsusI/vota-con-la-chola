import "./consolidated.css";

// Service results next to the spending bars: one column per indicator, rows in the same country order as the bars.
// Each column has its own axis starting at zero, shared by every country in that column.
const nf = (v, digits) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const signed = (v, digits) => `${v >= 0 ? "+" : "−"}${nf(Math.abs(v), digits)}`;

// Optional per indicator: `max` (share one axis across several columns) and per cell `delta` (change, shown after the value).
export default function ResultsGrid({ rows, indicators, highlight, color, peerColor, ariaLabel, rowHeader = "País" }) {
  return (
    <div className="rgrid__scroll">
      <table className="rgrid" aria-label={ariaLabel || "Resultados de los servicios públicos por país"}>
        <thead>
          <tr>
            <th scope="col">{rowHeader}</th>
            {indicators.map((ind) => (
              <th scope="col" key={ind.key}>
                {ind.short}
                {ind.better ? <span>{ind.better === "lower" ? "menos es mejor" : "más es mejor"}</span> : ind.note ? <span>{ind.note}</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.area} data-highlight={row.area === highlight ? "true" : "false"}>
              <th scope="row">{row.label}</th>
              {indicators.map((ind) => {
                const cell = ind.values[row.area];
                const max = ind.max ?? Math.max(...Object.values(ind.values).map((v) => v.value));
                return (
                  <td key={ind.key}>
                    {cell ? (
                      <>
                        <span className="rgrid__track" aria-hidden="true">
                          <span
                            className="rgrid__bar"
                            style={{ width: `${(Math.max(0, cell.value || 0) / max) * 100}%`, background: row.area === highlight ? color : ind.color || peerColor }}
                          />
                        </span>
                        <span className="rgrid__value">
                          {cell.value == null ? "—" : nf(cell.value, ind.digits)}
                          {cell.delta != null ? <small> ({signed(cell.delta, ind.digits)})</small> : null}
                          {ind.year != null && cell.year !== ind.year ? <small> ({cell.year})</small> : null}
                        </span>
                      </>
                    ) : (
                      <span className="rgrid__value rgrid__na">sin dato</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
