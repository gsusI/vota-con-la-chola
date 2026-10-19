"use client";

import { useState } from "react";
import "./consolidated.css";

// Spain: change in spending by function between two years, in % of GDP and in real euros per person, each panel
// with its own single axis (zero in the middle when needed). A toggle picks the starting year.
const nf = (v, digits = 0) =>
  Number(Math.abs(v)).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const signed = (v, digits, suffix) => `${v >= 0 ? "+" : "−"}${nf(v, digits)}${suffix}`;

function Panel({ title, rows, field, digits, suffix, colors }) {
  const values = rows.map((row) => row[field]);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = max - min || 1;
  const pos = (v) => `${((v - min) / span) * 100}%`;
  return (
    <div className="dbars__panel">
      <h3 className="rgrid__title">{title}</h3>
      {rows.map((row) => (
        <div className="dbars__row" key={row.key} data-total={row.total ? "true" : "false"}>
          <span className="dbars__label">{row.label}</span>
          <span className="dbars__track">
            <span className="dbars__zero" style={{ left: pos(0) }} aria-hidden="true" />
            <span
              className="dbars__bar"
              style={{
                left: pos(Math.min(0, row[field])),
                width: `${(Math.abs(row[field]) / span) * 100}%`,
                background: colors[row.key] || "var(--viz-ink)",
              }}
            />
          </span>
          <span className="dbars__value">{signed(row[field], digits, suffix)}</span>
        </div>
      ))}
    </div>
  );
}

export default function DeltaBars({ windows, labels, colors }) {
  const [index, setIndex] = useState(Math.max(0, windows.findIndex((w) => w.from === 2000)));
  const w = windows[index];
  const functions = w.functions.map((f) => ({
    key: f.key,
    label: labels[f.key],
    pct: f.pct[1] - f.pct[0],
    eur: f.eur[1] - f.eur[0],
  }));
  const rows = [
    { key: "revenue", label: "Ingresos públicos", pct: w.revenue_pct[1] - w.revenue_pct[0], eur: w.revenue_eur[1] - w.revenue_eur[0], total: true },
    { key: "spending", label: "Gasto público", pct: w.spending_pct[1] - w.spending_pct[0], eur: w.spending_eur[1] - w.spending_eur[0], total: true },
    ...functions,
  ];
  return (
    <div className="dbars">
      <div className="dbars__toggle" role="group" aria-label="Año de partida">
        {windows.map((item, i) => (
          <button type="button" key={item.from} aria-pressed={i === index} onClick={() => setIndex(i)}>
            Desde {item.from}
          </button>
        ))}
      </div>
      <div className="vizMultiples">
        <Panel title={`Cambio ${w.from}–${w.to}, puntos del PIB`} rows={rows} field="pct" digits={1} suffix="" colors={colors} />
        <Panel title={`Cambio ${w.from}–${w.to}, euros de 2010 por habitante`} rows={rows} field="eur" digits={0} suffix=" €" colors={colors} />
      </div>
    </div>
  );
}
