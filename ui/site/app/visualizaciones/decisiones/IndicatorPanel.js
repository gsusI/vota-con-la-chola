"use client";

import { useEffect, useRef, useState } from "react";

// One domain's official indicator over time (Spain and EU-27, zero-based y axis) with every measure of the domain
// marked at its vote date by its number and verdict marker. Width-responsive so text keeps its size on a phone.
const MARGIN = { top: 34, right: 58, bottom: 26, left: 40 };

function niceMax(max) {
  const raw = max / 4;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / pow;
  const step = (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
  return { step, max: Math.ceil(max / step) * step };
}

function frac(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

export default function IndicatorPanel({ lines = [], marks = [], notes = [], xMin = 2015, xMax = 2026.9, unitSuffix = "", ariaLabel }) {
  const ref = useRef(null);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = Math.round(entries[0].contentRect.width);
      if (w > 0) setWidth(w);
    });
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const narrow = width < 520;
  const innerW0 = width - MARGIN.left - MARGIN.right;
  const x0 = (v) => MARGIN.left + ((v - xMin) / (xMax - xMin)) * innerW0;
  // Stack marks that fall close together (vertically) so their numbers never overlap or leave the chart.
  const placed = [];
  for (const m of [...marks].sort((a, b) => a.date.localeCompare(b.date))) {
    const px = x0(frac(m.date));
    let row = 0;
    while (placed.some((p) => p.row === row && Math.abs(p.px - px) < 19)) row += 1;
    placed.push({ ...m, px, row });
  }
  const rows = placed.length ? Math.max(...placed.map((p) => p.row)) + 1 : 0;
  const top = MARGIN.top + (rows - 1) * 20;
  const height = (lines.length ? (narrow ? 230 : 250) : 86) + Math.max(0, rows - 1) * 20;
  const innerW = width - MARGIN.left - MARGIN.right;
  const plotTop = top;
  const plotBottom = height - MARGIN.bottom;
  const x = (v) => MARGIN.left + ((v - xMin) / (xMax - xMin)) * innerW;
  const allValues = lines.flatMap((l) => l.points.map((p) => p.value));
  const { step, max } = niceMax(Math.max(1, ...allValues));
  const y = (v) => plotBottom - (v / max) * (plotBottom - plotTop);
  const ticks = [];
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(Math.round(v * 100) / 100);
  const years = [];
  for (let yr = xMin; yr <= xMax; yr += narrow ? 3 : 2) years.push(yr);

  return (
    <div ref={ref} className="decPanel">
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        {lines.length
          ? ticks.map((t) => (
              <g key={t}>
                <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} stroke="var(--viz-grid, #e6e4dc)" />
                <text x={MARGIN.left - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="var(--viz-axis-text, #6b6a65)">
                  {t.toLocaleString("es-ES")}
                  {unitSuffix}
                </text>
              </g>
            ))
          : null}
        {years.map((yr) => (
          <text key={yr} x={x(yr)} y={height - 8} textAnchor="middle" fontSize="11" fill="var(--viz-axis-text, #6b6a65)">
            {yr}
          </text>
        ))}
        <line x1={MARGIN.left} x2={width - MARGIN.right} y1={plotBottom} y2={plotBottom} stroke="var(--viz-axis, #8a8880)" />
        {notes.map((n) => (
          <g key={n.label}>
            <rect x={x(n.from)} width={Math.max(2, x(n.to) - x(n.from))} y={plotTop} height={plotBottom - plotTop} fill="#f1efe8" />
            <text x={x(n.from) - 4} y={plotBottom - 8} textAnchor="end" fontSize="10.5" fill="#6b6a65">
              {narrow ? n.short || n.label : n.label}
            </text>
          </g>
        ))}
        {placed.map((m) => (
          <line key={`l${m.n}`} x1={m.px} x2={m.px} y1={plotTop - 9 - m.row * 20} y2={plotBottom} stroke={m.took_effect ? "#52514e" : "#b4b2a9"} strokeDasharray="2 3" />
        ))}
        {lines.map((l) => {
          const pts = l.points.filter((p) => p.year >= xMin && p.year <= xMax);
          if (!pts.length) return null;
          const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.year + 0.5).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
          const last = pts.at(-1);
          return (
            <g key={l.id}>
              <path d={d} fill="none" stroke={l.color} strokeWidth={l.emphasis ? 2.6 : 1.6} />
              {pts.map((p) => (
                <circle key={p.year} cx={x(p.year + 0.5)} cy={y(p.value)} r={l.emphasis ? 2.6 : 1.8} fill={l.color}>
                  <title>{`${l.label}, ${p.year}: ${p.value.toLocaleString("es-ES")}${unitSuffix}`}</title>
                </circle>
              ))}
              <text x={x(last.year + 0.5) + 6} y={y(last.value) + 4} fontSize="11" fill={l.color} fontWeight={l.emphasis ? 600 : 400}>
                {l.short || l.label}
              </text>
            </g>
          );
        })}
        {placed.map((m) => {
          const cy = plotTop - 18 - m.row * 20;
          return (
            <g key={`m${m.n}`}>
              <title>{`${m.n}. ${m.name} (${m.date}): ${m.verdictLabel}`}</title>
              <circle cx={m.px} cy={cy} r="9" fill="#fff" stroke={m.took_effect ? "#1f1e1b" : "#8a8880"} strokeDasharray={m.took_effect ? undefined : "2 2"} />
              <text x={m.px} y={cy + 3.5} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="#1f1e1b">
                {m.n}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
