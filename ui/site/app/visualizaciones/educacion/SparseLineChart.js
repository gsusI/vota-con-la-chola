"use client";

// Line chart for series observed at irregular years (PISA cycles, censuses, OECD finance years).
// Unlike the shared TimeSeriesChart, consecutive observations are joined whatever the gap; a point with
// `breakBefore` starts a new segment (series break: shown, never spliced) and `hollow` points mark values that are
// not comparable with the rest. Every observation gets a marker so readers see where data actually exists.
import { useEffect, useMemo, useRef, useState } from "react";
import { svgPointerX } from "../components/pointer";
import { fmt } from "./formatEdu.mjs";

const MARGIN = { top: 16, right: 64, bottom: 30, left: 44 };

function niceStep(max, targetTicks) {
  const raw = max / targetTicks;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / pow;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
}

function tickLabel(value, unit) {
  if (unit === "pct") return `${value}%`;
  if ((unit === "count" || unit === "usd") && value >= 1000) return `${(value / 1000).toLocaleString("es-ES")} mil`;
  return value.toLocaleString("es-ES");
}


export default function SparseLineChart({
  series,
  unit = "count",
  xMin,
  xMax,
  yMax,
  height = 300,
  digits = 0,
  endLabels = true,
  bands = [],
  ariaLabel,
}) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(720);
  const [hoverYear, setHoverYear] = useState(null);

  useEffect(() => {
    const node = wrapRef.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const next = Math.round(entries[0].contentRect.width);
      if (next > 0) setWidth(next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const prepared = useMemo(
    () =>
      series.map((item) => {
        const pts = item.points.filter((p) => p.value != null).sort((a, b) => a.year - b.year);
        return { ...item, points: pts, byYear: new Map(pts.map((p) => [p.year, p])) };
      }),
    [series],
  );
  const years = [...new Set(prepared.flatMap((s) => s.points.map((p) => p.year)))].sort((a, b) => a - b);
  const x0 = xMin ?? years[0];
  const x1 = xMax ?? years.at(-1);
  const dataMax = Math.max(...prepared.flatMap((s) => s.points.map((p) => p.value)));
  const step = niceStep(yMax ?? dataMax, height < 220 ? 4 : 5);
  const y1 = Math.ceil((yMax ?? dataMax) / step) * step;

  const compact = width < 520;
  const longest = Math.max(...series.map((s) => (s.shortLabel || s.label).length));
  const margin = {
    ...MARGIN,
    right: endLabels && !compact ? Math.min(220, 24 + 6.6 * (8 + longest)) : 16,
    left: unit === "pct" ? 40 : 48,
  };
  const innerW = Math.max(120, width - margin.left - margin.right);
  const innerH = height - margin.top - margin.bottom;
  const sx = (year) => margin.left + ((year - x0) / Math.max(1, x1 - x0)) * innerW;
  const sy = (value) => margin.top + innerH - (value / y1) * innerH;

  const yTicks = [];
  for (let v = 0; v <= y1 + 1e-9; v += step) yTicks.push(Math.round(v * 100) / 100);
  const span = x1 - x0;
  const xStep = span > 80 ? (compact ? 40 : 20) : span > 40 ? (compact ? 20 : 10) : span > 15 ? (compact ? 6 : 3) : compact ? 4 : 2;
  const xTicks = [];
  for (let y = Math.ceil(x0 / xStep) * xStep; y <= x1; y += xStep) xTicks.push(y);

  function pathFor(item) {
    let d = "";
    let open = false;
    for (const point of item.points) {
      if (point.year < x0 || point.year > x1) continue;
      const cmd = !open || point.breakBefore ? "M" : "L";
      d += `${cmd}${sx(point.year).toFixed(1)},${sy(point.value).toFixed(1)}`;
      open = true;
    }
    return d;
  }

  const labels = [];
  if (endLabels && !compact) {
    const candidates = prepared
      .filter((s) => s.points.length && !s.noEndLabel)
      .map((s) => {
        const last = s.points.filter((p) => p.year <= x1).at(-1);
        return { id: s.id, text: s.shortLabel || s.label, value: last.value, x: sx(last.year), y: sy(last.value), priority: s.emphasis ? 0 : 1 };
      })
      .sort((a, b) => a.priority - b.priority);
    for (const c of candidates) {
      if (labels.every((l) => Math.abs(l.y - c.y) >= 14)) labels.push(c);
    }
  }

  function nearestYear(event) {
    const px = svgPointerX(event);
    const target = x0 + ((px - margin.left) / innerW) * (x1 - x0);
    return years.reduce((best, y) => (Math.abs(y - target) < Math.abs(best - target) ? y : best), years[0]);
  }

  function onKeyDown(event) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const index = hoverYear == null ? years.length - 1 : years.indexOf(hoverYear);
    const next = Math.min(years.length - 1, Math.max(0, index + (event.key === "ArrowLeft" ? -1 : 1)));
    setHoverYear(years[next]);
  }

  const rows =
    hoverYear == null
      ? []
      : prepared
          .map((s) => ({ id: s.id, label: s.label, color: s.color, point: s.byYear.get(hoverYear) }))
          .filter((row) => row.point);
  const tooltipLeft = hoverYear == null ? 0 : sx(hoverYear);
  const flip = tooltipLeft > width * 0.62;

  return (
    <div className="tsChart" ref={wrapRef}>
      <svg
        role="img"
        aria-label={ariaLabel}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onBlur={() => setHoverYear(null)}
      >
        {bands.map((band) => (
          <g key={`band-${band.from}`}>
            <rect
              className="tsChart__band"
              x={sx(Math.max(band.from, x0))}
              y={margin.top}
              width={Math.max(1, sx(Math.min(band.to, x1)) - sx(Math.max(band.from, x0)))}
              height={innerH}
            />
            {!compact ? (
              <text className="tsChart__bandLabel" x={sx(Math.max(band.from, x0)) + 4} y={margin.top + 12}>
                {band.label}
              </text>
            ) : null}
          </g>
        ))}
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line className={tick === 0 ? "tsChart__baseline" : "tsChart__grid"} x1={margin.left} x2={margin.left + innerW} y1={sy(tick)} y2={sy(tick)} />
            <text className="tsChart__tick" x={margin.left - 6} y={sy(tick) + 4} textAnchor="end">
              {tickLabel(tick, unit)}
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <text className="tsChart__tick" key={`x-${tick}`} x={sx(tick)} y={height - 8} textAnchor="middle">
            {tick}
          </text>
        ))}
        {prepared.map((s) => (
          <g key={s.id}>
            <path d={pathFor(s)} fill="none" stroke={s.color} strokeWidth={s.emphasis ? 2.5 : 2} strokeLinejoin="round" strokeLinecap="round" />
            {s.points
              .filter((p) => p.year >= x0 && p.year <= x1)
              .map((p) => (
                <circle
                  key={`${s.id}-${p.year}`}
                  cx={sx(p.year)}
                  cy={sy(p.value)}
                  r={s.emphasis ? 3.5 : 2.5}
                  fill={p.hollow ? "var(--viz-surface, #fff)" : s.color}
                  stroke={s.color}
                  strokeWidth={p.hollow ? 1.5 : 0}
                />
              ))}
          </g>
        ))}
        {labels.map((label) => {
          const s = prepared.find((item) => item.id === label.id);
          return (
            <text key={`label-${label.id}`} className="tsChart__endLabel" x={label.x + 8} y={label.y + 4} fill={s.color}>
              {label.text} · {fmt(label.value, unit, digits)}
            </text>
          );
        })}
        {hoverYear != null ? (
          <line className="tsChart__crosshair" x1={sx(hoverYear)} x2={sx(hoverYear)} y1={margin.top} y2={margin.top + innerH} />
        ) : null}
        <rect
          x={margin.left - 8}
          y={0}
          width={innerW + 16}
          height={height}
          fill="transparent"
          onPointerMove={(event) => setHoverYear(nearestYear(event))}
          onPointerLeave={() => setHoverYear(null)}
        />
      </svg>
      {hoverYear != null && rows.length ? (
        <div
          className="tsChart__tooltip"
          style={{ left: flip ? undefined : tooltipLeft + 12, right: flip ? width - tooltipLeft + 12 : undefined, top: margin.top }}
          role="status"
        >
          <span className="tsChart__tooltipYear">{hoverYear}</span>
          {rows.map((row) => (
            <span className="tsChart__tooltipRow" key={`t-${row.id}`}>
              <span className="tsChart__key" style={{ background: row.color }} aria-hidden="true" />
              <strong>{fmt(row.point.value, unit, digits)}</strong>
              <span className="tsChart__tooltipLabel">
                {row.label}
                {row.point.hollow ? " (no comparable)" : ""}
              </span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
