"use client";

import { fmt } from "./FanChart";

// Who gains and who loses by income quintile: euros a month per household, one diverging bar per instrument,
// with the net total and the share of disposable income. Zero is always on the axis.
export const PART_LABELS = {
  irpf: "IRPF",
  iva: "IVA",
  cotizaciones: "Cotizaciones",
  sociedades: "Sociedades",
  pensiones: "Pensiones",
};
export const PART_COLORS = {
  irpf: "#2a78d6",
  iva: "#eb6834",
  cotizaciones: "#eda100",
  sociedades: "#7a5af5",
  pensiones: "#1baf7a",
};

const signed = (v, unit, d = 0) => {
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return (r > 0 ? "+" : r < 0 ? "−" : "") + fmt(Math.abs(r), unit, d);
};

export default function QuintileFigure({ rows, cuts }) {
  const parts = Object.keys(PART_LABELS).filter((p) => rows.some((r) => Math.abs(r.byPart[p]) >= 0.5));
  const extent = Math.max(
    1,
    ...rows.map((r) => Object.values(r.byPart).filter((v) => v > 0).reduce((a, b) => a + b, 0)),
    ...rows.map((r) => -Object.values(r.byPart).filter((v) => v < 0).reduce((a, b) => a + b, 0)),
  );
  const pct = (v) => `${(Math.abs(v) / extent) * 50}%`;
  const labels = ["1.º (20 % con menos renta)", "2.º", "3.º", "4.º", "5.º (20 % con más renta)"];
  return (
    <div className="qfig">
      {parts.length ? (
        <ul className="vizLegend" aria-label="Leyenda">
          {parts.map((p) => (
            <li key={p}>
              <span className="vizLegend__key" style={{ background: PART_COLORS[p], width: 10, height: 10 }} aria-hidden="true" />
              {PART_LABELS[p]}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="qfig__rows" role="table" aria-label="Cambio de renta por quintil, euros al mes por hogar">
        {rows.map((r, i) => {
          let pos = 0;
          let neg = 0;
          return (
            <div className="qfig__row" role="row" key={r.q}>
              <span className="qfig__label" role="rowheader">
                Quintil {labels[i]}
                {cuts && i < 4 ? <small>hasta {fmt(cuts[i], "eur")} por unidad de consumo</small> : null}
              </span>
              <span className="qfig__track" aria-hidden="true">
                <span className="qfig__zero" />
                {parts.map((p) => {
                  const v = r.byPart[p];
                  if (Math.abs(v) < 0.5) return null;
                  const style =
                    v > 0
                      ? { left: `calc(50% + ${pct(pos)})`, width: pct(v), background: PART_COLORS[p] }
                      : { right: `calc(50% + ${pct(neg)})`, width: pct(v), background: PART_COLORS[p] };
                  if (v > 0) pos += v;
                  else neg -= v;
                  return <span key={p} className="qfig__seg" style={style} title={`${PART_LABELS[p]}: ${signed(v, "eur")} al mes`} />;
                })}
              </span>
              <span className="qfig__value" role="cell">
                {Math.abs(r.total) < 0.5 ? "Sin cambio" : `${signed(r.total, "eur")} al mes`}
                <small>{Math.abs(r.total) < 0.5 ? "" : `${signed(r.pctDisposable, "pct", 2)} de su renta`}</small>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
