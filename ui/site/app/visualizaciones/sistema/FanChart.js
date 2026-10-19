"use client";

import { useEffect, useRef, useState } from "react";
import { svgPointerX } from "../components/pointer";

// Line chart for model paths: baseline, scenario and its 5-95 % band. The y axis always includes zero.
const M = { top: 14, right: 16, bottom: 26, left: 48 };

export const fmt = (v, unit, digits = 1) => {
  if (v == null || !Number.isFinite(v)) return "—";
  const n = Number(v);
  const s = (d) => n.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
  if (unit === "eur") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} €`;
  if (unit === "k") return `${Math.round(n).toLocaleString("es-ES", { useGrouping: "always" })} mil`;
  if (unit === "pp") return `${s(digits)} pp`;
  return `${s(digits)} %`;
};

function niceTicks(lo, hi, target = 4) {
  const span = hi - lo || 1;
  const raw = span / target;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / pow;
  const step = (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
  const out = [];
  for (let t = Math.floor(lo / step) * step; t <= hi + step * 1e-9; t += step) out.push(Number(t.toFixed(10)));
  return out;
}

export default function FanChart({ years, series, unit = "pct", height = 240, ariaLabel, digits = 1 }) {
  const wrap = useRef(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState(null);
  useEffect(() => {
    const node = wrap.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = Math.round(entries[0].contentRect.width);
      if (w > 0) setWidth(w);
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const all = series.flatMap((s) => [...s.values, ...(s.lo || []), ...(s.hi || [])]).filter(Number.isFinite);
  let lo = Math.min(0, ...all);
  let hi = Math.max(0, ...all);
  if (hi - lo < 1e-9) hi = lo + 1;
  const ticks = niceTicks(lo, hi);
  lo = Math.min(lo, ticks[0]);
  hi = Math.max(hi, ticks.at(-1));
  const innerW = Math.max(120, width - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const x0 = years[0];
  const x1 = years.at(-1);
  const sx = (y) => M.left + ((y - x0) / (x1 - x0)) * innerW;
  const sy = (v) => M.top + (1 - (v - lo) / (hi - lo)) * innerH;
  const path = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${sx(years[i]).toFixed(1)},${sy(v).toFixed(1)}`).join("");
  const area = (a, b) =>
    `${a.map((v, i) => `${i ? "L" : "M"}${sx(years[i]).toFixed(1)},${sy(v).toFixed(1)}`).join("")}` +
    `${b
      .map((v, i) => [years[i], v])
      .reverse()
      .map(([y, v]) => `L${sx(y).toFixed(1)},${sy(v).toFixed(1)}`)
      .join("")}Z`;
  const xTicks = years.filter((y) => y % 5 === 0 || y === x0);
  const hoverIdx = hover == null ? null : years.indexOf(hover);

  return (
    <div className="fanChart" ref={wrap}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label={ariaLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={M.left + innerW} y1={sy(t)} y2={sy(t)} className={t === 0 ? "fanChart__zero" : "fanChart__grid"} />
            <text x={M.left - 6} y={sy(t) + 4} className="fanChart__tick" textAnchor="end">
              {unit === "eur" ? `${t.toLocaleString("es-ES")} €` : unit === "k" ? t.toLocaleString("es-ES") : `${t.toLocaleString("es-ES")}`}
            </text>
          </g>
        ))}
        {xTicks.map((y) => (
          <text key={y} x={sx(y)} y={height - 8} className="fanChart__tick" textAnchor="middle">
            {y}
          </text>
        ))}
        {series.map((s) =>
          s.lo && s.hi ? <path key={`b-${s.id}`} d={area(s.lo, s.hi)} fill={s.color} opacity={0.16} /> : null,
        )}
        {series.map((s) => (
          <path
            key={s.id}
            d={path(s.values)}
            fill="none"
            stroke={s.color}
            strokeWidth={s.emphasis ? 2.5 : 1.75}
            strokeDasharray={s.dash ? "5 4" : undefined}
          />
        ))}
        {hoverIdx != null && hoverIdx >= 0 ? (
          <line x1={sx(hover)} x2={sx(hover)} y1={M.top} y2={M.top + innerH} className="fanChart__hover" />
        ) : null}
        <rect
          x={M.left}
          y={M.top}
          width={innerW}
          height={innerH}
          fill="transparent"
          onPointerMove={(e) => {
            const px = svgPointerX(e);
            const y = Math.round(x0 + ((px - M.left) / innerW) * (x1 - x0));
            setHover(Math.min(x1, Math.max(x0, y)));
          }}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      <p className="fanChart__readout" aria-live="polite">
        {hoverIdx != null && hoverIdx >= 0 ? (
          <>
            <strong>{hover}</strong>
            {series.map((s) => (
              <span key={s.id} style={{ "--key": s.color }}>
                {s.label}: {fmt(s.values[hoverIdx], unit, digits)}
                {s.lo ? ` (${fmt(s.lo[hoverIdx], unit, digits)} a ${fmt(s.hi[hoverIdx], unit, digits)})` : ""}
              </span>
            ))}
          </>
        ) : (
          <span className="fanChart__hint">Pasa el dedo o el ratón por el gráfico para ver cada año.</span>
        )}
      </p>
    </div>
  );
}
