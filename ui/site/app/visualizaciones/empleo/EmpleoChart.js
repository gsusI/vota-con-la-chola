"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fmt } from "./format.mjs";

// Copy of ../components/TimeSeriesChart.js with this page's units (index, thousands of people, signed growth
// rates) and a zero line inside the plot when values go negative. Axes always include zero.
const MARGIN = { top: 40, right: 64, bottom: 30, left: 44 };

function niceStep(span, targetTicks) {
  const raw = span / targetTicks;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / pow;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * pow;
}

function tickLabel(value, unit) {
  if (unit === "thousands") return value >= 1000 ? `${(value / 1000).toLocaleString("es-ES")} M` : `${value.toLocaleString("es-ES")} mil`;
  if (unit === "index") return value.toLocaleString("es-ES");
  if (unit === "growth") return `${value > 0 ? "+" : ""}${value.toLocaleString("es-ES")}%`;
  return `${value.toLocaleString("es-ES")}%`;
}

export default function EmpleoChart({
  series,
  unit = "pct",
  xMin,
  xMax,
  yMax,
  height = 320,
  annotations = [],
  endLabels = true,
  ariaLabel,
  digits = 1,
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
        const points = item.points.filter((p) => p.value != null).sort((a, b) => a.year - b.year);
        return { ...item, points, byYear: new Map(points.map((p) => [p.year, p.value])) };
      }),
    [series],
  );

  const allYears = prepared.flatMap((s) => s.points.map((p) => p.year));
  const x0 = xMin ?? Math.min(...allYears);
  const x1 = xMax ?? Math.max(...allYears);
  const values = prepared.flatMap((s) => s.points.filter((p) => p.year >= x0 && p.year <= x1).map((p) => p.value));
  const dataMax = Math.max(0, ...values);
  const dataMin = Math.min(0, ...values);
  const top = Math.max(yMax ?? dataMax, dataMax);
  const step = niceStep(top - dataMin || 1, height < 220 ? 4 : 5);
  const y1 = Math.ceil(top / step) * step;
  const y0 = Math.floor(dataMin / step) * step;

  const compact = width < 520;
  const endLabelRoom = Math.min(230, 24 + 6.6 * (10 + Math.max(...series.map((s) => (s.shortLabel || s.label).length))));
  const margin = { ...MARGIN, top: annotations.length ? MARGIN.top : 16, right: endLabels && !compact ? endLabelRoom : 16, left: unit === "thousands" ? 58 : 46 };
  const innerW = Math.max(120, width - margin.left - margin.right);
  const innerH = height - margin.top - margin.bottom;
  const sx = (year) => margin.left + ((year - x0) / Math.max(1, x1 - x0)) * innerW;
  const sy = (value) => margin.top + innerH - ((value - y0) / (y1 - y0)) * innerH;

  const yTicks = [];
  for (let v = y0; v <= y1 + 1e-9; v += step) yTicks.push(Math.round(v * 100) / 100);
  const span = x1 - x0;
  const xStep = span > 80 ? (compact ? 25 : 10) : span > 40 ? (compact ? 20 : 10) : compact ? 10 : 5;
  const xTicks = [];
  for (let y = Math.ceil(x0 / xStep) * xStep; y <= x1; y += xStep) xTicks.push(y);

  function pathFor(item) {
    let d = "";
    let prev = null;
    for (const point of item.points) {
      if (point.year < x0 || point.year > x1) continue;
      const gap = !prev || point.year - prev.year > 1;
      d += `${gap ? "M" : "L"}${sx(point.year).toFixed(1)},${sy(point.value).toFixed(1)}`;
      prev = point;
    }
    return d;
  }

  const labels = [];
  if (endLabels && !compact) {
    const candidates = prepared
      .filter((s) => s.points.length && !s.noEndLabel)
      .map((s) => {
        const last = s.points.filter((p) => p.year <= x1).at(-1);
        return last ? { id: s.id, text: s.shortLabel || s.label, value: last.value, x: sx(last.year), y: sy(last.value), priority: s.emphasis ? 0 : 1 } : null;
      })
      .filter(Boolean)
      .sort((a, b) => a.priority - b.priority);
    for (const c of candidates) {
      if (labels.every((l) => Math.abs(l.y - c.y) >= 14)) labels.push(c);
    }
  }

  function yearFromPointer(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * width;
    const year = Math.round(x0 + ((px - margin.left) / innerW) * (x1 - x0));
    return Math.min(x1, Math.max(x0, year));
  }

  function onKeyDown(event) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.key === "ArrowLeft" ? -1 : 1;
    setHoverYear((current) => Math.min(x1, Math.max(x0, (current ?? x1) + delta)));
  }

  const rows =
    hoverYear == null
      ? []
      : prepared.map((s) => ({ id: s.id, label: s.label, color: s.color, value: s.byYear.get(hoverYear) ?? null })).filter((row) => row.value != null);
  const tooltipLeft = hoverYear == null ? 0 : sx(hoverYear);
  const flip = tooltipLeft > width * 0.62;

  return (
    <div className="tsChart" ref={wrapRef}>
      <svg role="img" aria-label={ariaLabel} width={width} height={height} viewBox={`0 0 ${width} ${height}`} tabIndex={0} onKeyDown={onKeyDown} onBlur={() => setHoverYear(null)}>
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
        {(compact ? annotations.filter((note) => note.keepOnMobile) : annotations).map((note, index) => (
          <g key={`note-${note.year}-${index}`}>
            <line className="tsChart__note" x1={sx(note.year)} x2={sx(note.year)} y1={margin.top - 4 - (note.row || 0) * 13} y2={margin.top + innerH} />
            <text className="tsChart__noteLabel" x={sx(note.year) + 3} y={margin.top - 8 - (note.row || 0) * 13} textAnchor={sx(note.year) > width - 120 ? "end" : "start"}>
              {note.label}
            </text>
          </g>
        ))}
        {prepared.map((s) => (
          <path key={s.id} d={pathFor(s)} fill="none" stroke={s.color} strokeWidth={s.emphasis ? 2.5 : 2} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {labels.map((label) => {
          const s = prepared.find((item) => item.id === label.id);
          return (
            <g key={`label-${label.id}`}>
              <circle cx={label.x} cy={label.y} r={4} fill={s.color} className="tsChart__dot" />
              <text className="tsChart__endLabel" x={label.x + 8} y={label.y + 4}>
                {label.text} · {fmt(label.value, unit, digits)}
              </text>
            </g>
          );
        })}
        {hoverYear != null ? (
          <g>
            <line className="tsChart__crosshair" x1={sx(hoverYear)} x2={sx(hoverYear)} y1={margin.top} y2={margin.top + innerH} />
            {rows.map((row) => (
              <circle key={`h-${row.id}`} cx={sx(hoverYear)} cy={sy(row.value)} r={4} fill={row.color} className="tsChart__dot" />
            ))}
          </g>
        ) : null}
        <rect
          x={margin.left - 8}
          y={0}
          width={innerW + 16}
          height={height}
          fill="transparent"
          onPointerMove={(event) => setHoverYear(yearFromPointer(event))}
          onPointerLeave={() => setHoverYear(null)}
        />
      </svg>
      {hoverYear != null && rows.length ? (
        <div className="tsChart__tooltip" style={{ left: flip ? undefined : tooltipLeft + 12, right: flip ? width - tooltipLeft + 12 : undefined, top: margin.top }} role="status">
          <span className="tsChart__tooltipYear">{hoverYear}</span>
          {rows.map((row) => (
            <span className="tsChart__tooltipRow" key={`t-${row.id}`}>
              <span className="tsChart__key" style={{ background: row.color }} aria-hidden="true" />
              <strong>{fmt(row.value, unit, digits)}</strong>
              <span className="tsChart__tooltipLabel">{row.label}</span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
