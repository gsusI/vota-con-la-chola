import { formatHealth } from "./format.mjs";

function niceMax(value) {
  const pow = 10 ** Math.floor(Math.log10(value));
  const unit = value / pow;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
}

// Labels: highlighted points first; a label that would overlap one already placed is dropped (the table has all).
function placeLabels(points, sx, sy, priority) {
  const placed = [];
  const shown = new Set();
  const order = [...points].sort((a, b) => priority(b) - priority(a));
  for (const p of order) {
    const x = sx(p.x) + 8;
    const y = sy(p.y);
    const w = 6.2 * (p.short || p.name).length;
    if (placed.every((q) => Math.abs(q.y - y) >= 12 || x + w < q.x || q.x + q.w < x)) {
      placed.push({ x, y, w });
      shown.add(p.code);
    }
  }
  return shown;
}

/**
 * Connected scatter for «el dato mata el relato» figures: every point is a place; an optional trail goes from its
 * first-period position (hollow marker) to its last one (filled marker); an optional size encodes a third variable.
 * One x-scale and one y-scale, both from zero.
 */
export default function ConnectedScatter({
  points,
  reference,
  xLabel,
  yLabel,
  xUnit = "count",
  yUnit = "count",
  xMax: xMaxProp,
  yMax: yMaxProp,
  emphasis = [],
  highlight = [],
  sizeLabel,
  ariaLabel,
  height = 380,
}) {
  const width = 640;
  const margin = { top: 14, right: 26, bottom: 46, left: 52 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const xs = points.flatMap((p) => [p.x, p.x0 ?? 0]).concat(reference ? [reference.x, reference.x0 ?? 0] : []);
  const ys = points.flatMap((p) => [p.y, p.y0 ?? 0]).concat(reference ? [reference.y, reference.y0 ?? 0] : []);
  const xMax = xMaxProp ?? niceMax(Math.max(...xs) * 1.04);
  const yMax = yMaxProp ?? niceMax(Math.max(...ys) * 1.04);
  const sx = (v) => margin.left + (v / xMax) * innerW;
  const sy = (v) => margin.top + innerH - (v / yMax) * innerH;
  const radius = (p, key = "size") => (p[key] == null ? 4 : 2.5 + 1.6 * Math.sqrt(p[key]));
  const colour = (p) => (highlight.includes(p.code) ? "#2a78d6" : emphasis.includes(p.code) ? "#52514e" : "#b4b2a9");
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
  const shown = placeLabels(points, sx, sy, (p) => (highlight.includes(p.code) ? 2 : emphasis.includes(p.code) ? 1 : 0));
  const tick = (value, unit) => (unit === "eur" ? formatHealth(value, "eur") : formatHealth(value, "count"));
  return (
    <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {ticks(yMax).map((t) => (
        <g key={`y${t}`}>
          <line x1={margin.left} x2={margin.left + innerW} y1={sy(t)} y2={sy(t)} className={t === 0 ? "tsChart__baseline" : "tsChart__grid"} />
          <text x={margin.left - 6} y={sy(t) + 4} textAnchor="end" className="tsChart__tick">
            {tick(t, yUnit)}
          </text>
        </g>
      ))}
      {ticks(xMax).map((t) => (
        <text key={`x${t}`} x={sx(t)} y={margin.top + innerH + 16} textAnchor="middle" className="tsChart__tick">
          {tick(t, xUnit)}
        </text>
      ))}
      <line x1={margin.left} x2={margin.left} y1={margin.top} y2={margin.top + innerH} className="tsChart__baseline" />
      <text x={margin.left + innerW / 2} y={height - 6} textAnchor="middle" className="tsChart__tick">
        {xLabel}
      </text>
      <text x={13} y={margin.top + innerH / 2} textAnchor="middle" className="tsChart__tick" transform={`rotate(-90 13 ${margin.top + innerH / 2})`}>
        {yLabel}
      </text>
      {reference ? (
        <g>
          <line x1={sx(reference.x)} x2={sx(reference.x)} y1={margin.top} y2={margin.top + innerH} className="tsChart__note" />
          <text x={sx(reference.x) + 4} y={margin.top + 10} className="tsChart__noteLabel">
            {reference.label}
          </text>
          {reference.x0 != null ? (
            <line x1={sx(reference.x0)} y1={sy(reference.y0)} x2={sx(reference.x)} y2={sy(reference.y)} stroke="#52514e" strokeWidth={1.5} strokeDasharray="3 3" />
          ) : null}
          <rect x={sx(reference.x) - 4} y={sy(reference.y) - 4} width={8} height={8} fill="#52514e" />
        </g>
      ) : null}
      {points
        .filter((p) => p.x0 != null)
        .map((p) => (
          <g key={`t-${p.code}`}>
            <line x1={sx(p.x0)} y1={sy(p.y0)} x2={sx(p.x)} y2={sy(p.y)} stroke={colour(p)} strokeWidth={highlight.includes(p.code) ? 2.5 : 1.5} opacity={0.9} />
            <circle cx={sx(p.x0)} cy={sy(p.y0)} r={radius(p, "size0")} fill="none" stroke={colour(p)} strokeWidth={1.3} />
          </g>
        ))}
      {points.map((p) => (
        <g key={p.code}>
          <circle cx={sx(p.x)} cy={sy(p.y)} r={radius(p)} fill={colour(p)} opacity={p.size != null ? 0.75 : 0.95} />
          {shown.has(p.code) ? (
            <text x={sx(p.x) + radius(p) + 3} y={sy(p.y) + 4} className="tsChart__tick" style={{ fontWeight: highlight.includes(p.code) ? 700 : 400 }}>
              {p.short || p.name}
            </text>
          ) : null}
        </g>
      ))}
      {sizeLabel ? (
        <text x={margin.left + innerW} y={margin.top + innerH - 6} textAnchor="end" className="tsChart__tick">
          {sizeLabel}
        </text>
      ) : null}
    </svg>
  );
}
