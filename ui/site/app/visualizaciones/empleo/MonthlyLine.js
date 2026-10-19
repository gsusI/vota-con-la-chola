// Static monthly line (x = fractional year), axis from zero; the values are in the table twin.
export default function MonthlyLine({ points, color, height = 260, unitLabel = "mil" }) {
  const W = 600;
  const H = height;
  const m = { top: 14, right: 12, bottom: 28, left: 46 };
  const x0 = Math.floor(Math.min(...points.map((p) => p.year)));
  const x1 = Math.ceil(Math.max(...points.map((p) => p.year)));
  const max = Math.max(...points.map((p) => p.value));
  const step = max > 800 ? 250 : max > 400 ? 100 : 50;
  const y1 = Math.ceil(max / step) * step;
  const sx = (x) => m.left + ((x - x0) / (x1 - x0)) * (W - m.left - m.right);
  const sy = (v) => m.top + (1 - v / y1) * (H - m.top - m.bottom);
  const ticks = [];
  for (let v = 0; v <= y1; v += step) ticks.push(v);
  const years = [];
  for (let y = x0; y <= x1; y += 1) years.push(y);
  const d = points.map((p, i) => `${i ? "L" : "M"}${sx(p.year).toFixed(1)},${sy(p.value).toFixed(1)}`).join("");
  return (
    <div className="tsChart">
      <svg role="img" aria-label="Afiliados fijos discontinuos cada mes" viewBox={`0 0 ${W} ${H}`} width="100%" style={{ height: "auto" }}>
        {ticks.map((t) => (
          <g key={t}>
            <line className={t === 0 ? "tsChart__baseline" : "tsChart__grid"} x1={m.left} x2={W - m.right} y1={sy(t)} y2={sy(t)} />
            <text className="tsChart__tick" x={m.left - 6} y={sy(t) + 4} textAnchor="end">
              {t.toLocaleString("es-ES")} {t ? unitLabel : ""}
            </text>
          </g>
        ))}
        {years.map((y) => (
          <text key={y} className="tsChart__tick" x={sx(y)} y={H - 8} textAnchor="middle">
            {y}
          </text>
        ))}
        <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
      </svg>
    </div>
  );
}
