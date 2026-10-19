import { formatHealth } from "./format.mjs";

// Ranked dumbbell: one row per place, two values on the same scale (from zero) joined by a line.
export default function Dumbbell({ rows, unit = "pct", digits = 1, leftKey, rightKey, leftLabel, rightLabel, highlight = [], ariaLabel, max }) {
  const width = 640;
  const rowH = 22;
  const margin = { top: 26, right: 70, bottom: 22, left: 150 };
  const height = margin.top + margin.bottom + rows.length * rowH;
  const innerW = width - margin.left - margin.right;
  const top = max ?? Math.max(...rows.flatMap((row) => [row[leftKey], row[rightKey]]).filter((v) => v != null));
  const sx = (v) => margin.left + (v / top) * innerW;
  const colors = { left: "#eb6834", right: "#1baf7a" };
  return (
    <svg role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <g>
        <circle cx={margin.left} cy={10} r={5} fill={colors.left} />
        <text x={margin.left + 9} y={14} className="tsChart__tick">{leftLabel}</text>
        <circle cx={margin.left + 230} cy={10} r={5} fill={colors.right} />
        <text x={margin.left + 239} y={14} className="tsChart__tick">{rightLabel}</text>
      </g>
      <line x1={sx(0)} x2={sx(0)} y1={margin.top - 4} y2={height - margin.bottom} className="tsChart__baseline" />
      {[0, 0.5, 1].map((f) => (
        <text key={f} x={sx(top * f)} y={height - 6} textAnchor="middle" className="tsChart__tick">
          {formatHealth(top * f, unit, 0)}
        </text>
      ))}
      {rows.map((row, i) => {
        const y = margin.top + i * rowH + rowH / 2;
        const on = highlight.includes(row.code);
        const a = row[leftKey];
        const b = row[rightKey];
        return (
          <g key={row.code}>
            <text x={margin.left - 8} y={y + 4} textAnchor="end" className="tsChart__tick" style={{ fontWeight: on ? 700 : 400 }}>
              {row.name}
            </text>
            {a != null && b != null ? <line x1={sx(Math.min(a, b))} x2={sx(Math.max(a, b))} y1={y} y2={y} stroke={on ? "#2a78d6" : "#b4b2a9"} strokeWidth={on ? 3 : 2} /> : null}
            {b != null ? <circle cx={sx(b)} cy={y} r={on ? 5.5 : 4.5} fill={colors.right} /> : null}
            {a != null ? <circle cx={sx(a)} cy={y} r={on ? 5.5 : 4.5} fill={colors.left} /> : null}
            {a != null ? (
              <text x={sx(Math.max(a, b ?? 0)) + 8} y={y + 4} className="tsChart__tick" style={{ fontWeight: on ? 700 : 400 }}>
                {formatHealth(a, unit, digits)}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
