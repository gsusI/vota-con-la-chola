"use client";

import { useState } from "react";
import "./consolidated.css";

// Stacked bar per country (latest common year) + a ring at the country's total in the base year: level,
// composition, change and peers in one figure. Optional diamond marker (e.g. revenue against spending).
export default function ConsolidatedBars({ rows, parts, axisMax, year, baseYear, highlight, marker, ariaLabel }) {
  const [active, setActive] = useState(null);
  const ticks = [];
  for (let t = 0; t <= axisMax; t += 10) ticks.push(t);
  const pct = (v) => `${(v / axisMax) * 100}%`;
  const fmt = (v) => `${Number(v).toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
  const signed = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;

  return (
    <div className="cbars">
      <div className="cbars__grid" role="list" aria-label={ariaLabel || `Recaudación por quién la ingresa, ${year}, y total en ${baseYear}`}>
        {rows.map((row) => {
          let offset = 0;
          return (
            <div className="cbars__row" role="listitem" key={row.area} data-highlight={row.area === highlight ? "true" : "false"}>
              <span className="cbars__label">{row.label}</span>
              <div className="cbars__track">
                {ticks.map((t) => (
                  <span className="cbars__tick" key={t} style={{ left: pct(t) }} aria-hidden="true" />
                ))}
                <span className="cbars__stack">
                  {parts.map((part) => {
                    const value = row[part.key] || 0;
                    const left = offset;
                    offset += value;
                    if (value <= 0.05) return null;
                    const isActive = active && active.area === row.area && active.key === part.key;
                    return (
                      <button
                        type="button"
                        className="cbars__seg"
                        key={part.key}
                        data-active={isActive ? "true" : "false"}
                        style={{ left: pct(left), width: pct(value), background: part.color }}
                        aria-label={`${row.label}, ${part.label}: ${fmt(value)} del PIB`}
                        onPointerEnter={() => setActive({ area: row.area, key: part.key })}
                        onPointerLeave={() => setActive(null)}
                        onFocus={() => setActive({ area: row.area, key: part.key })}
                        onBlur={() => setActive(null)}
                      />
                    );
                  })}
                </span>
                {row.base_total != null ? (
                  <span
                    className="cbars__base"
                    style={{ left: pct(row.base_total) }}
                    title={`${row.label}: ${fmt(row.base_total)} del PIB en ${row.base_year ?? baseYear}`}
                    aria-hidden="true"
                  />
                ) : null}
                {marker && row[marker.key] != null ? (
                  <span
                    className="cbars__marker"
                    style={{ left: pct(row[marker.key]) }}
                    title={`${row.label}: ${marker.label} ${fmt(row[marker.key])} del PIB en ${year}`}
                    aria-hidden="true"
                  />
                ) : null}
              </div>
              <span className="cbars__value">
                <strong>{fmt(row.total)}</strong>
                {row.base_total != null ? (
                  <span>
                    {" "}
                    {signed(row.total - row.base_total)} desde {row.base_year ?? baseYear}
                  </span>
                ) : null}
              </span>
            </div>
          );
        })}
        <div className="cbars__row cbars__axis" aria-hidden="true">
          <span />
          <div className="cbars__track">
            {ticks.map((t) => (
              <span className="cbars__tickLabel" key={t} style={{ left: pct(t) }}>
                {t}%
              </span>
            ))}
          </div>
          <span />
        </div>
      </div>
      <p className="cbars__readout" role="status">
        {active
          ? (() => {
              const row = rows.find((item) => item.area === active.area);
              const part = parts.find((item) => item.key === active.key);
              const ranked = [...rows].sort((a, b) => (b[part.key] || 0) - (a[part.key] || 0));
              const rank = ranked.findIndex((item) => item.area === row.area) + 1;
              return `${row.label} · ${part.label}: ${fmt(row[part.key])} del PIB en ${year} (${rank}.º de ${rows.length})`;
            })()
          : "Pasa el cursor o el foco por un tramo para ver su valor y su puesto en el grupo."}
      </p>
    </div>
  );
}
