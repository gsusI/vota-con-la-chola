import { formatValue } from "./format.mjs";

export function Legend({ items, kind = "line" }) {
  if (!items || items.length < 2) return null;
  return (
    <ul className="vizLegend" aria-label="Leyenda">
      {items.map((item) => (
        <li key={item.id}>
          <span
            className="vizLegend__key"
            style={{ background: item.color, height: kind === "bar" ? 10 : 3, width: kind === "bar" ? 10 : 16 }}
            aria-hidden="true"
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

// Every chart has a table twin: values stay reachable without hovering.
export function SeriesTable({ series, unit = "pct", digits = 1, caption = "Ver los datos en tabla" }) {
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
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td>{year}</td>
                {lookup.map((map, index) => (
                  <td key={series[index].id}>{map.has(year) ? formatValue(map.get(year), unit, digits) : ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function Sources({ items, notes = [] }) {
  return (
    <figcaption className="vizFigure__caption">
      <span>
        Fuente:{" "}
        {items.map((item, index) => (
          <span key={item.href}>
            {index ? "; " : ""}
            <a href={item.href} rel="noopener noreferrer" target="_blank">
              {item.label}
            </a>
          </span>
        ))}
        .
      </span>
      {notes.map((note) => (
        <span key={note}>{note}</span>
      ))}
    </figcaption>
  );
}

export default function Figure({ id, title, dek, legend, legendKind, children, sources, notes, table }) {
  return (
    <figure className="card vizFigure" id={id} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{title}</h2>
      {dek ? <p className="vizFigure__dek">{dek}</p> : null}
      <Legend items={legend} kind={legendKind} />
      {children}
      {sources ? <Sources items={sources} notes={notes} /> : null}
      {table}
    </figure>
  );
}
