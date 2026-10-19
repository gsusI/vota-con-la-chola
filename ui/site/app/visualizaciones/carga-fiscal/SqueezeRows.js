"use client";

import { useState } from "react";
import "./consolidated.css";

// «El dato mata el relato» for the taxpayer's pocket: per country, two panels on one row, each with its own single
// axis shared by every row. Left: taxes paid and household income left per person (PPS, same scale for both).
// Right: real change of each since the chosen base year (%, one scale for every country and every base, so switching
// the base never rescales). Colour = taxes per person, taxes per employed person, income.
const nf = (v, digits = 0) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const signed = (v) => `${v >= 0 ? "+" : "−"}${nf(Math.abs(v), 1)} %`;

function ticks(min, max, step) {
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}

export default function SqueezeRows({ rows, year, bases, defaultBase, lastYear, taxColor, workerColor, incomeColor, highlight }) {
  const [baseYear, setBaseYear] = useState(defaultBase);
  const levelMax = Math.ceil(Math.max(...rows.map((row) => row.income_pps)) / 10000) * 10000;
  const changes = rows.flatMap((row) => Object.values(row.by_base).flatMap((b) => [b.tax, b.tax_worker, b.income]));
  const chMin = Math.min(0, Math.floor(Math.min(...changes) / 10) * 10);
  const chMax = Math.max(10, Math.ceil(Math.max(...changes) / 10) * 10);
  const lv = (v) => `${(v / levelMax) * 100}%`;
  const ch = (v) => `${((v - chMin) / (chMax - chMin)) * 100}%`;
  const bar = (from, to) => ({ left: ch(Math.min(from, to)), width: `${(Math.abs(to - from) / (chMax - chMin)) * 100}%` });
  const levelTicks = ticks(0, levelMax, 10000);
  const changeTicks = ticks(chMin, chMax, 10);

  return (
    <>
    <div className="dbars__toggle" role="group" aria-label="Año de partida del cambio real">
      {bases.map((b) => (
        <button type="button" key={b} aria-pressed={b === baseYear} onClick={() => setBaseYear(b)}>
          Desde {b}
        </button>
      ))}
    </div>
    <div className="sq" role="table" aria-label={`Impuestos y renta que queda por habitante en ${year}, y su cambio real desde ${baseYear}`}>
      <div className="sq__row sq__head" role="row">
        <span role="columnheader">País</span>
        <span role="columnheader">
          Por habitante en {year} <em>(estándar de poder adquisitivo)</em>
        </span>
        <span role="columnheader">
          Cambio real {baseYear}–{lastYear} <em>(%)</em>
        </span>
      </div>
      {rows.map((row) => (
        <div className="sq__row" role="row" key={row.area} data-highlight={row.area === highlight ? "true" : "false"}>
          <span className="sq__label" role="rowheader">
            {row.label}
          </span>
          <div className="sq__panel" role="cell">
            <div className="sq__track">
              {levelTicks.map((t) => (
                <span className="sq__tick" key={t} style={{ left: lv(t) }} aria-hidden="true" />
              ))}
              <span className="sq__bar sq__bar--top" style={{ left: 0, width: lv(row.tax_pps), background: taxColor }} />
              <span className="sq__bar sq__bar--bottom" style={{ left: 0, width: lv(row.income_pps), background: incomeColor }} />
            </div>
            <span className="sq__values">
              <span style={{ color: taxColor }}>paga {nf(row.tax_pps)}</span> ·{" "}
              <span style={{ color: incomeColor }}>le quedan {nf(row.income_pps)}</span> · {nf(row.tax_to_income_pct, 1)} %
            </span>
          </div>
          <div className="sq__panel" role="cell">
            <div className="sq__track sq__track--three">
              {changeTicks.map((t) => (
                <span className={`sq__tick${t === 0 ? " sq__tick--zero" : ""}`} key={t} style={{ left: ch(t) }} aria-hidden="true" />
              ))}
              <span className="sq__bar sq__bar--a" style={{ ...bar(0, row.by_base[baseYear].tax), background: taxColor }} />
              <span className="sq__bar sq__bar--b" style={{ ...bar(0, row.by_base[baseYear].tax_worker), background: workerColor }} />
              <span className="sq__bar sq__bar--c" style={{ ...bar(0, row.by_base[baseYear].income), background: incomeColor }} />
            </div>
            <span className="sq__values">
              <span style={{ color: taxColor }}>impuestos {signed(row.by_base[baseYear].tax)}</span> ·{" "}
              <span style={{ color: workerColor }}>por ocupado {signed(row.by_base[baseYear].tax_worker)}</span> ·{" "}
              <span style={{ color: incomeColor }}>renta {signed(row.by_base[baseYear].income)}</span>
            </span>
          </div>
        </div>
      ))}
      <div className="sq__row sq__axis" aria-hidden="true">
        <span />
        <div className="sq__track sq__track--axis">
          {levelTicks.map((t) => (
            <span className="sq__tickLabel" key={t} style={{ left: lv(t) }}>
              {t ? `${nf(t / 1000)} mil` : "0"}
            </span>
          ))}
        </div>
        <div className="sq__track sq__track--axis">
          {changeTicks.filter((t) => t % 20 === 0).map((t) => (
            <span className="sq__tickLabel" key={t} style={{ left: ch(t) }}>
              {t > 0 ? `+${t}` : t < 0 ? `−${Math.abs(t)}` : "0"}
            </span>
          ))}
        </div>
      </div>
    </div>
    </>
  );
}
