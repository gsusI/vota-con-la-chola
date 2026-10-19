import { formatHousing } from "./format.mjs";

// Same table twin as ../components/Figure.js SeriesTable, with this page's units per column.
export default function HousingTable({ series, unit = "pct", digits = 1, caption = "Ver los datos en tabla" }) {
  const years = [...new Set(series.flatMap((s) => s.points.map((p) => p.year)))].sort((a, b) => b - a);
  const lookup = series.map((s) => new Map(s.points.map((p) => [p.year, p.value])));
  return (
    <details className="vizTable">
      <summary>{caption}</summary>
      <div className="vizTable__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Año</th>
              {series.map((s) => (
                <th scope="col" key={s.id}>
                  {s.tableLabel || s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td>{year}</td>
                {lookup.map((map, index) => (
                  <td key={series[index].id}>
                    {map.has(year) ? formatHousing(map.get(year), series[index].unit || unit, series[index].digits ?? digits) : ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
