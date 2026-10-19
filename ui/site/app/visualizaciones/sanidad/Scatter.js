import { formatHealth } from "./format.mjs";

function niceMax(value) {
  const pow = 10 ** Math.floor(Math.log10(value));
  const unit = value / pow;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
}

// Highlighted points are labelled first; a label that would overlap one already placed is dropped (the table has all).
function labelled(points, sx, sy, highlight) {
  const placed = [];
  const order = [...points].sort((a, b) => Number(highlight.includes(b.code)) - Number(highlight.includes(a.code)));
  const shown = new Set();
  for (const p of order) {
    const x = sx(p.x);
    const y = sy(p.y);
    const w = 7.2 * (p.short || p.name).length + 4;
    if (placed.every((q) => Math.abs(q.y - y) >= 15 || x + w < q.x || q.x + q.w < x)) {
      placed.push({ x, y, w });
      shown.add(p.code);
    }
  }
  return points.map((p) => ({ ...p, showLabel: shown.has(p.code) }));
}

// Labelled scatter (server-rendered SVG). Both axes start at zero, as every chart on this site.
export default function Scatter({ points, xLabel, yLabel, xUnit = "eur", yUnit = "days", highlight = [], ariaLabel, height = 340 }) {
  const width = 640;
  const margin = { top: 16, right: 24, bottom: 46, left: 56 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xMax = niceMax(Math.max(...points.map((p) => p.x)) * 1.05);
  const yMax = niceMax(Math.max(...points.map((p) => p.y)) * 1.05);
  const sx = (v) => margin.left + (v / xMax) * innerW;
  const sy = (v) => margin.top + innerH - (v / yMax) * innerH;
  // Round tick steps (1, 2, 2.5 or 5 × 10^n) so labels read cleanly.
  const ticks = (max) => {
    const raw = max / 5;
    const pow = 10 ** Math.floor(Math.log10(raw));
    const unit = raw / pow;
    const step = (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
    const out = [];
    for (let v = 0; v <= max + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
    return out;
  };
  return (
    <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {ticks(yMax).map((t) => (
        <g key={`y${t}`}>
          <line x1={margin.left} x2={margin.left + innerW} y1={sy(t)} y2={sy(t)} className={t === 0 ? "tsChart__baseline" : "tsChart__grid"} />
          <text x={margin.left - 6} y={sy(t) + 4} textAnchor="end" className="tsChart__tick">
            {formatHealth(t, yUnit === "years" ? "count" : yUnit === "days" ? "count" : yUnit)}
          </text>
        </g>
      ))}
      {ticks(xMax).filter((t) => t > 0).map((t) => (
        <text key={`x${t}`} x={sx(t)} y={margin.top + innerH + 16} textAnchor="middle" className="tsChart__tick">
          {formatHealth(t, xUnit)}
        </text>
      ))}
      <line x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + innerH} className="tsChart__baseline" />
      <text x={margin.left + innerW / 2} y={height - 6} textAnchor="middle" className="tsChart__tick">
        {xLabel}
      </text>
      <text x={14} y={margin.top + innerH / 2} textAnchor="middle" className="tsChart__tick" transform={`rotate(-90 14 ${margin.top + innerH / 2})`}>
        {yLabel}
      </text>
      {labelled(points, sx, sy, highlight).map((p) => {
        const on = highlight.includes(p.code);
        return (
          <g key={p.code}>
            <circle cx={sx(p.x)} cy={sy(p.y)} r={on ? 5 : 4} fill={on ? "#2a78d6" : "#52514e"} opacity={on ? 1 : 0.75} />
            {p.showLabel ? (
              <text x={sx(p.x) + 7} y={sy(p.y) + 4} className="tsChart__tick" style={{ fontWeight: on ? 700 : 400 }}>
                {p.short || p.name}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
