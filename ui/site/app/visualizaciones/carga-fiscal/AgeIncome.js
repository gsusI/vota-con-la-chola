"use client";

import { useState } from "react";
import "./consolidated.css";

// «Bolsillo», income half split by age (EU-SILC median equivalised income, the source's own bands). Left panel: level
// in the base year (hollow dot) and in the last year (filled), real euros, one axis from zero. Right panel: real change
// since the chosen base for Spain (bar) and for Italy and Portugal (markers), one axis for every base.
const nf = (v, digits = 0) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const signed = (v) => (v == null ? "—" : `${v >= 0 ? "+" : "−"}${nf(Math.abs(v), 1)} %`);

function ticks(min, max, step) {
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}

export default function AgeIncome({ data, color, peerColors, peerLabels }) {
  const { bases, areas, price_year: priceYear } = data;
  const [base, setBase] = useState(String(bases[0]));
  const es = areas.ES || [];
  const peers = Object.keys(peerColors).filter((geo) => (areas[geo] || []).length);
  const peerRow = (geo, age) => (areas[geo] || []).find((row) => row.age === age);
  const levelMax = Math.ceil(Math.max(...es.flatMap((row) => Object.values(row.real))) / 5000) * 5000;
  const changes = [...es, ...peers.flatMap((geo) => areas[geo])].flatMap((row) => Object.values(row.change)).filter((v) => v != null);
  const chMin = Math.min(0, Math.floor(Math.min(...changes) / 10) * 10);
  const chMax = Math.max(10, Math.ceil(Math.max(...changes) / 10) * 10);
  const lv = (v) => `${(v / levelMax) * 100}%`;
  const ch = (v) => `${((v - chMin) / (chMax - chMin)) * 100}%`;
  const levelTicks = ticks(0, levelMax, 5000);
  const changeTicks = ticks(chMin, chMax, 10);

  return (
    <>
      <h3 className="rgrid__title">España por edad: renta mediana real de cada edad (encuesta de condiciones de vida, bandas de Eurostat)</h3>
      <div className="dbars__toggle" role="group" aria-label="Año de partida del cambio real por edad">
        {bases.map((b) => (
          <button type="button" key={b} aria-pressed={String(b) === base} onClick={() => setBase(String(b))}>
            Rentas de {b}
          </button>
        ))}
      </div>
      <ul className="vizLegend" aria-label="Leyenda de la renta por edad">
        <li>
          <span className="age__dot age__dot--base" aria-hidden="true" /> Renta en {base}
        </li>
        <li>
          <span className="age__dot" style={{ background: color }} aria-hidden="true" /> Renta en {priceYear}
        </li>
        {peers.map((geo) => (
          <li key={geo}>
            <span className="age__marker age__marker--key" style={{ background: peerColors[geo] }} aria-hidden="true" /> Cambio en {peerLabels[geo]}
          </li>
        ))}
      </ul>
      <div className="sq age" role="table" aria-label={`Renta mediana real por edad en España, rentas de ${base} y de ${priceYear}, y su cambio`}>
        <div className="sq__row sq__head" role="row">
          <span role="columnheader">Edad</span>
          <span role="columnheader">
            Renta mediana por unidad de consumo <em>(euros de {priceYear})</em>
          </span>
          <span role="columnheader">
            Cambio real {base}–{priceYear} <em>(%)</em>
          </span>
        </div>
        {es.map((row) => {
          const from = row.real[base];
          const to = row.real[String(priceYear)];
          const change = row.change[base];
          return (
            <div className="sq__row" role="row" key={row.age} data-highlight={row.age === "TOTAL" ? "true" : "false"}>
              <span className="sq__label" role="rowheader">
                {row.label}
              </span>
              <div className="sq__panel" role="cell">
                <div className="sq__track">
                  {levelTicks.map((t) => (
                    <span className="sq__tick" key={t} style={{ left: lv(t) }} aria-hidden="true" />
                  ))}
                  {from != null ? (
                    <>
                      <span
                        className="age__link"
                        style={{ left: lv(Math.min(from, to)), width: `${(Math.abs(to - from) / levelMax) * 100}%`, background: color }}
                        aria-hidden="true"
                      />
                      <span className="age__dot age__dot--base age__dot--on" style={{ left: lv(from) }} aria-hidden="true" />
                    </>
                  ) : null}
                  <span className="age__dot age__dot--on" style={{ left: lv(to), background: color }} aria-hidden="true" />
                </div>
                <span className="sq__values">
                  {from != null ? `${nf(from)} → ` : ""}
                  <strong>{nf(to)} €</strong>
                </span>
              </div>
              <div className="sq__panel" role="cell">
                <div className="sq__track">
                  {changeTicks.map((t) => (
                    <span className={`sq__tick${t === 0 ? " sq__tick--zero" : ""}`} key={t} style={{ left: ch(t) }} aria-hidden="true" />
                  ))}
                  {change != null ? (
                    <span
                      className="sq__bar age__bar"
                      style={{ left: ch(Math.min(0, change)), width: `${(Math.abs(change) / (chMax - chMin)) * 100}%`, background: color }}
                    />
                  ) : null}
                  {peers.map((geo) => {
                    const v = peerRow(geo, row.age)?.change?.[base];
                    return v == null ? null : (
                      <span className="age__marker" key={geo} style={{ left: ch(v), background: peerColors[geo] }} aria-hidden="true" />
                    );
                  })}
                </div>
                <span className="sq__values">
                  <strong>España {signed(change)}</strong>
                  {peers.map((geo) => ` · ${peerLabels[geo]} ${signed(peerRow(geo, row.age)?.change?.[base])}`).join("")}
                </span>
              </div>
            </div>
          );
        })}
        <div className="sq__row sq__axis" aria-hidden="true">
          <span />
          <div className="sq__track sq__track--axis">
            {levelTicks.filter((t) => t % 10000 === 0).map((t) => (
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
