import { fmt } from "./formatEdu.mjs";

// Table twin for every chart (values reachable without hovering), with the units this page needs.
export default function EduTable({ series, unit = "pct", digits = 1, caption = "Ver los datos en tabla", rowLabel = "Año", rowFormat }) {
  const years = [...new Set(series.flatMap((s) => s.points.map((p) => p.year)))].sort((a, b) => b - a);
  const lookup = series.map((s) => new Map(s.points.map((p) => [p.year, p])));
  return (
    <details className="vizTable">
      <summary>{caption}</summary>
      <div className="vizTable__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">{rowLabel}</th>
              {series.map((s) => (
                <th scope="col" key={s.id}>
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td>{rowFormat ? rowFormat(year) : year}</td>
                {lookup.map((map, index) => {
                  const point = map.get(year);
                  return (
                    <td key={series[index].id}>
                      {point ? fmt(point.value, unit, digits) : ""}
                      {point?.flag ? ` (${point.flag})` : ""}
                      {point?.hollow ? " (no comparable)" : ""}
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
