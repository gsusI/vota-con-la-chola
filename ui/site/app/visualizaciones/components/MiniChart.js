// Static preview chart for the hub cards: no client JS. Lines are drawn in a stretched SVG
// (non-scaling strokes) and every label is HTML placed in % of the plot, so text never distorts.
import { formatValue } from "./format.mjs";

const defaultTick = (value) => `${value.toLocaleString("es-ES")}%`;

const VIEW = 1000;

function niceMax(max) {
  const pow = 10 ** Math.floor(Math.log10(max));
  const unit = max / pow;
  const step = (unit <= 2 ? 0.5 : unit <= 5 ? 1 : 2) * pow;
  return Math.ceil(max / step) * step;
}

export default function MiniChart({ series, unit = "pct", digits = 1, format, tick = defaultTick, yMax, xMin, xMax, breaks = [], ariaLabel }) {
  const clean = series.map((s) => ({ ...s, points: s.points.filter((p) => p.value != null).sort((a, b) => a.year - b.year) }));
  const years = clean.flatMap((s) => s.points.map((p) => p.year));
  const x0 = xMin ?? Math.min(...years);
  const x1 = xMax ?? Math.max(...years);
  const values = clean.flatMap((s) => s.points.map((p) => p.value));
  const y1 = yMax ?? niceMax(Math.max(...values));
  // Axes start at zero; only a series that goes negative extends the axis below it.
  const dataMin = Math.min(...values);
  const yMin = dataMin < 0 ? -niceMax(-dataMin) : 0;
  const fmt = format ?? ((value) => formatValue(value, unit, digits));
  const px = (year) => ((year - x0) / Math.max(1, x1 - x0)) * 100;
  const py = (value) => 100 - ((value - yMin) / (y1 - yMin)) * 100;

  // Separate paths across gaps of more than one year: series breaks are shown, never spliced.
  function pathFor(points) {
    let d = "";
    let prev = null;
    for (const p of points) {
      if (p.year < x0 || p.year > x1) continue;
      const cmd = !prev || p.year - prev.year > 1 ? "M" : "L";
      d += `${cmd}${((px(p.year) * VIEW) / 100).toFixed(1)},${((py(p.value) * VIEW) / 100).toFixed(1)}`;
      prev = p;
    }
    return d;
  }

  // End labels for labelled series, nudged apart so they never overlap.
  const labels = clean
    .filter((s) => s.endLabel && s.points.length)
    .map((s) => {
      const last = s.points.at(-1);
      return { id: s.id, color: s.color, text: s.endLabel, value: last.value, x: px(last.year), y: py(last.value), strong: s.emphasis };
    })
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i += 1) {
    if (labels[i].y - labels[i - 1].y < 22) labels[i].y = labels[i - 1].y + 22;
  }

  return (
    <div className="vizMini" role="img" aria-label={ariaLabel}>
      {/* Left gutter sized to the widest y tick (~7 px per character at 0.72rem). */}
      <div className="vizMini__plot" style={{ left: `${10 + 7 * Math.max(String(tick(y1)).length, String(tick(y1 / 2)).length)}px` }}>
        <span className="vizMini__tick vizMini__tick--y" style={{ top: "0%" }}>
          {tick(y1)}
        </span>
        <span className="vizMini__tick vizMini__tick--y" style={{ top: `${py(y1 / 2)}%` }}>
          {tick(y1 / 2)}
        </span>
        <span className="vizMini__tick vizMini__tick--y" style={{ top: `${py(0)}%` }}>
          0
        </span>
        <svg viewBox={`0 0 ${VIEW} ${VIEW}`} preserveAspectRatio="none" aria-hidden="true">
          <line className="vizMini__grid" x1={0} x2={VIEW} y1={0} y2={0} />
          <line className="vizMini__grid" x1={0} x2={VIEW} y1={(py(y1 / 2) * VIEW) / 100} y2={(py(y1 / 2) * VIEW) / 100} />
          {breaks
            .filter((year) => year > x0 && year < x1)
            .map((year) => (
              <line key={`b-${year}`} className="vizMini__break" x1={(px(year) * VIEW) / 100} x2={(px(year) * VIEW) / 100} y1={0} y2={VIEW} />
            ))}
          <line className="vizMini__base" x1={0} x2={VIEW} y1={(py(0) * VIEW) / 100} y2={(py(0) * VIEW) / 100} />
          {clean.map((s) => (
            <path key={s.id} d={pathFor(s.points)} fill="none" stroke={s.color} strokeWidth={s.emphasis ? 3 : 1.75} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
        {labels.map((label) => (
          <span key={`d-${label.id}`} className="vizMini__dot" style={{ left: `${label.x}%`, top: `${py(label.value)}%`, background: label.color }} />
        ))}
        {labels.map((label) => (
          <span
            key={`l-${label.id}`}
            className={`vizMini__label${label.strong ? " is-strong" : ""}`}
            // A series that ends early is labelled at its own end, not at the right edge.
            style={{ top: `${label.y}%`, left: label.x < 92 ? `calc(${label.x}% + 10px)` : undefined, color: label.color }}
          >
            <span>{label.text}</span> <b>{fmt(label.value)}</b>
          </span>
        ))}
        <span className="vizMini__tick vizMini__tick--x" style={{ left: "0%" }}>
          {x0}
        </span>
        <span className="vizMini__tick vizMini__tick--x vizMini__tick--end" style={{ left: "100%" }}>
          {x1}
        </span>
      </div>
    </div>
  );
}
