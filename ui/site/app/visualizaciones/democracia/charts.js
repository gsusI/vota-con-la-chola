// Static SVG charts for /visualizaciones/democracia/ (server-rendered; every chart has a table twin on the page).
// All value axes start at zero; panels of one figure share their scale.

export const PARTY_COLORS = { UCD: "#7a6fd0", PSOE: "#eb6834", PP: "#2a78d6" };
export const CLASS_COLORS = { tercero_a_tiempo: "#2f7d55", tercero_tarde: "#c08a00", buena_voluntad: "#b23a48", no_aplica: "#b4b2a9" };
export const CLASS_LABELS = {
  tercero_a_tiempo: "Un tercero la hace cumplir a tiempo",
  tercero_tarde: "Se hace cumplir tarde",
  buena_voluntad: "Depende de la buena voluntad",
  no_aplica: "No aplica",
};
export const CLASS_SHORT = { tercero_a_tiempo: "A tiempo", tercero_tarde: "Tarde", buena_voluntad: "Buena voluntad", no_aplica: "No aplica" };
export const COUNTRY = { ESP: "España", DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal", POL: "Polonia", HUN: "Hungría" };

export const num = (value, digits = 0) =>
  value == null
    ? "—"
    : Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });

function niceMax(max) {
  if (max <= 0) return 1;
  const pow = 10 ** Math.floor(Math.log10(max));
  const unit = max / pow;
  const step = unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10;
  return step * pow;
}

function ticks(max, n = 4) {
  return Array.from({ length: n + 1 }, (_, i) => (max / n) * i);
}

// Lines over years on one zero-based axis. series: [{id,label,color,width,dash,points:[{year,value}]}]
export function LineChart({ series, xMin, xMax, yMax, height = 300, width = 760, rightMargin = 110, bands = [], unitLabel, digits = 0, ariaLabel, markers = [] }) {
  const W = width;
  const M = { top: 16, right: rightMargin, bottom: 28, left: 40 };
  const all = series.flatMap((s) => s.points.map((p) => p.value));
  const top = yMax ?? niceMax(Math.max(...all));
  const x0 = xMin ?? Math.min(...series.flatMap((s) => s.points.map((p) => p.year)));
  const x1 = xMax ?? Math.max(...series.flatMap((s) => s.points.map((p) => p.year)));
  const sx = (year) => M.left + ((year - x0) / (x1 - x0)) * (W - M.left - M.right);
  const sy = (v) => height - M.bottom - (v / top) * (height - M.top - M.bottom);
  const yearTicks = [];
  for (let y = Math.ceil(x0 / 10) * 10; y <= x1; y += 10) yearTicks.push(y);
  const labels = series
    .filter((s) => s.points.length && !s.noEndLabel)
    .map((s) => ({ id: s.id, text: s.shortLabel || s.label, color: s.color, y: sy(s.points.at(-1).value) }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i += 1) if (labels[i].y - labels[i - 1].y < 13) labels[i].y = labels[i - 1].y + 13;
  return (
    <svg viewBox={`0 0 ${W} ${height}`} className="demoChart" role="img" aria-label={ariaLabel}>
      {bands.map((b) => (
        <g key={`${b.from}-${b.label}`}>
          <rect x={sx(b.from)} y={M.top} width={Math.max(1, sx(b.to) - sx(b.from))} height={height - M.top - M.bottom} fill={b.color} opacity={b.opacity ?? 0.1} />
          {b.label ? (
            <text x={sx(b.from) + 3} y={M.top + 10} className="demoChart__band">
              {b.label}
            </text>
          ) : null}
        </g>
      ))}
      {ticks(top).map((t) => (
        <g key={t}>
          <line x1={M.left} x2={W - M.right} y1={sy(t)} y2={sy(t)} className="demoChart__grid" />
          <text x={M.left - 6} y={sy(t) + 4} textAnchor="end" className="demoChart__tick">
            {num(t, digits)}
          </text>
        </g>
      ))}
      {yearTicks.map((y) => (
        <text key={y} x={sx(y)} y={height - 8} textAnchor="middle" className="demoChart__tick">
          {y}
        </text>
      ))}
      {unitLabel ? (
        <text x={M.left} y={10} className="demoChart__tick">
          {unitLabel}
        </text>
      ) : null}
      {series.map((s) => (
        <polyline
          key={s.id}
          fill="none"
          stroke={s.color}
          strokeWidth={s.width ?? 2}
          strokeDasharray={s.dash}
          strokeLinejoin="round"
          points={s.points.map((p) => `${sx(p.year).toFixed(1)},${sy(p.value).toFixed(1)}`).join(" ")}
        />
      ))}
      {markers.map((m) => (
        <g key={m.label}>
          <line x1={sx(m.year)} x2={sx(m.year)} y1={M.top} y2={height - M.bottom} stroke="#52514e" strokeDasharray="2 3" />
          <text x={sx(m.year) - 3} y={height - M.bottom - 4} textAnchor="end" className="demoChart__band">
            {m.label}
          </text>
        </g>
      ))}
      {labels.map((l) => (
        <text key={l.id} x={W - M.right + 6} y={l.y + 4} className="demoChart__label" fill={l.color}>
          {l.text}
        </text>
      ))}
    </svg>
  );
}

// Paired horizontal bars on one shared zero-based scale. rows: [{id,label,a,b,color}]; keys: [{key,label,color}]
export function PairedBars({ rows, keys, digits = 2, ariaLabel, max }) {
  const top = max ?? niceMax(Math.max(...rows.flatMap((r) => keys.map((k) => r[k.key] ?? 0))));
  return (
    <div className="demoPaired" role="img" aria-label={ariaLabel}>
      {rows.map((row) => (
        <div className="demoPaired__row" key={row.id}>
          <span className="demoPaired__label">
            {row.swatch ? <span className="demoSwatch" style={{ background: row.swatch }} aria-hidden="true" /> : null}
            {row.label}
          </span>
          <span className="demoPaired__bars">
            {keys.map((k) => (
              <span className="demoPaired__track" key={k.key}>
                <span className="demoPaired__bar" style={{ width: `${((row[k.key] ?? 0) / top) * 100}%`, background: k.color }} />
                <span className="demoPaired__value">{num(row[k.key], digits)}</span>
              </span>
            ))}
          </span>
        </div>
      ))}
    </div>
  );
}

// Simple zero-based horizontal bars. rows: [{id,label,value,color,note}]
export function HBars({ rows, digits = 0, unit = "", ariaLabel, max }) {
  const top = max ?? niceMax(Math.max(...rows.map((r) => r.value ?? 0)));
  return (
    <ul className="demoHBars" aria-label={ariaLabel}>
      {rows.map((row) => (
        <li key={row.id}>
          <span className="demoHBars__label">{row.label}</span>
          <span className="demoHBars__track">
            <span className="demoHBars__bar" style={{ width: `${((row.value ?? 0) / top) * 100}%`, background: row.color || "#52514e" }} />
            <span className="demoHBars__value">
              {num(row.value, digits)}
              {unit}
              {row.note ? <span className="demoHBars__note"> {row.note}</span> : null}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// One square per year, coloured by status; a thin line under it with the party governing on 1 January.
export function YearStrip({ years, statusColors, statusLabels, partyOf }) {
  return (
    <div className="demoStrip">
      <ol className="demoStrip__years" aria-label="Estado del presupuesto de cada año" style={{ gridTemplateColumns: `repeat(${years.length}, minmax(0, 1fr))` }}>
        {years.map((y) => (
          <li key={y.year} title={`${y.year}: ${statusLabels[y.status]}`}>
            <span className="demoStrip__cell" style={{ background: statusColors[y.status] }} aria-hidden="true" />
            <span className="demoStrip__party" style={{ background: PARTY_COLORS[partyOf(y)] || "#b4b2a9" }} aria-hidden="true" />
            <span className="demoStrip__year">{y.year % 10 === 0 ? y.year : ""}</span>
            <span className="srOnly">
              {y.year}: {statusLabels[y.status]}, gobierno de {partyOf(y)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
