import "./consolidated.css";

// Service results next to the spending bars: one column per indicator, rows in the same country order as the bars.
// Each column has its own axis starting at zero, shared by every country in that column.
const nf = (v, digits) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export default function ResultsGrid({ rows, indicators, highlight, color, peerColor }) {
  return (
    <div className="rgrid__scroll">
      <table className="rgrid" aria-label="Resultados de los servicios públicos por país">
        <thead>
          <tr>
            <th scope="col">País</th>
            {indicators.map((ind) => (
              <th scope="col" key={ind.key}>
                {ind.short}
                <span>{ind.better === "lower" ? "menos es mejor" : "más es mejor"}</span>
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
                const max = Math.max(...Object.values(ind.values).map((v) => v.value));
                return (
                  <td key={ind.key}>
                    {cell ? (
                      <>
                        <span className="rgrid__track" aria-hidden="true">
                          <span
                            className="rgrid__bar"
                            style={{ width: `${(cell.value / max) * 100}%`, background: row.area === highlight ? color : peerColor }}
                          />
                        </span>
                        <span className="rgrid__value">
                          {nf(cell.value, ind.digits)}
                          {cell.year !== ind.year ? <small> ({cell.year})</small> : null}
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
