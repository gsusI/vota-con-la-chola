"use client";

import { useState } from "react";
import "./consolidated.css";

// Change in pension spending (points of GDP) split into "more pensioners per inhabitant" and "more per pensioner
// relative to GDP per person", per country, for a chosen starting year. One axis shared by every row and window.
const nf = (v, digits = 1) =>
  Number(Math.abs(v)).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const signed = (v, digits = 1) => `${v >= 0 ? "+" : "−"}${nf(v, digits)}`;

export default function PensionSplit({ rows, windows, year, colors, highlight }) {
  const usable = windows.filter((w) => rows.some((row) => row.windows[w]?.from_more_pensioners_pts != null));
  const [win, setWin] = useState(usable[0]);
  const all = rows.flatMap((row) =>
    Object.values(row.windows).flatMap((w) => [w.from_more_pensioners_pts || 0, w.from_more_per_pensioner_pts || 0, w.change_pts || 0]),
  );
  // Stacked parts can extend beyond the net change when they have opposite signs: bound by the sum of each sign.
  const pos = Math.max(0, ...rows.flatMap((row) => Object.values(row.windows).map((w) => Math.max(0, w.from_more_pensioners_pts || 0) + Math.max(0, w.from_more_per_pensioner_pts || 0))));
  const neg = Math.min(0, ...rows.flatMap((row) => Object.values(row.windows).map((w) => Math.min(0, w.from_more_pensioners_pts || 0) + Math.min(0, w.from_more_per_pensioner_pts || 0))), ...all);
  const min = Math.floor(neg);
  const max = Math.ceil(pos);
  const span = max - min || 1;
  const x = (v) => `${((v - min) / span) * 100}%`;
  const ticks = [];
  for (let t = min; t <= max; t += 1) ticks.push(t);

  return (
    <div className="dbars">
      <div className="dbars__toggle" role="group" aria-label="Año de partida">
        {usable.map((w) => (
          <button type="button" key={w} aria-pressed={w === win} onClick={() => setWin(w)}>
            Desde {w}
          </button>
        ))}
      </div>
      <div className="psplit" role="table" aria-label={`Cambio del gasto en pensiones ${win}–${year}, en puntos del PIB`}>
        {rows.map((row) => {
          const w = row.windows[win];
          if (!w || w.from_more_pensioners_pts == null) {
            return (
              <div className="psplit__row" role="row" key={row.area}>
                <span role="rowheader">{row.label}</span>
                <span className="psplit__na">sin dato de pensionistas en {win}</span>
                <span />
              </div>
            );
          }
          const a = w.from_more_pensioners_pts;
          const b = w.from_more_per_pensioner_pts;
          // Stack same-sign parts outward from zero.
          const segs = [];
          let upper = 0;
          let lower = 0;
          for (const [key, value] of [
            ["pensioners", a],
            ["per", b],
          ]) {
            if (value >= 0) {
              segs.push({ key, from: upper, to: upper + value });
              upper += value;
            } else {
              segs.push({ key, from: lower + value, to: lower });
              lower += value;
            }
          }
          return (
            <div className="psplit__row" role="row" key={row.area} data-highlight={row.area === highlight ? "true" : "false"}>
              <span role="rowheader" className="psplit__label">
                {row.label}
              </span>
              <span className="dbars__track" role="cell">
                {ticks.map((t) => (
                  <span key={t} className={t === 0 ? "dbars__zero" : "psplit__tick"} style={{ left: x(t) }} aria-hidden="true" />
                ))}
                {segs.map((s) => (
                  <span
                    key={s.key}
                    className="dbars__bar"
                    style={{ left: x(s.from), width: `${((s.to - s.from) / span) * 100}%`, background: colors[s.key] }}
                  />
                ))}
                <span className="psplit__net" style={{ left: x(w.change_pts) }} aria-hidden="true" />
              </span>
              <span className="psplit__values" role="cell">
                <strong>{signed(w.change_pts)}</strong> = {signed(a)} pensionistas {signed(b)} por pensionista
                <small>
                  {" "}
                  · pensionistas por 100 hab. {nf(w.pensioners_per_100[0])} → {nf(w.pensioners_per_100[1])} · pensión real por pensionista{" "}
                  {signed(w.real_per_pensioner_change_pct, 0)} % · PIB real por hab. {signed(w.real_gdp_pp_change_pct, 0)} %
                </small>
              </span>
            </div>
          );
        })}
        <div className="psplit__row psplit__axis" aria-hidden="true">
          <span />
          <span className="dbars__track">
            {ticks.map((t) => (
              <span key={t} className="sq__tickLabel" style={{ left: x(t) }}>
                {t > 0 ? `+${t}` : t < 0 ? `−${Math.abs(t)}` : "0"}
              </span>
            ))}
          </span>
          <span />
        </div>
      </div>
    </div>
  );
}
