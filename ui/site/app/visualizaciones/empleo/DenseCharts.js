"use client";

import { useEffect, useRef, useState } from "react";
import { fmt, num } from "./format.mjs";

// Dense «el dato mata el relato» charts: one y-scale each, zero always included, two legends (colour + marker/pattern).

function useWidth(initial = 720) {
  const ref = useRef(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const next = Math.round(entries[0].contentRect.width);
      if (next > 0) setWidth(next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

function ticks(min, max, step) {
  const out = [];
  for (let v = Math.floor(min / step) * step; v <= max + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
  return out;
}

// Spain - Europe unemployment gap per year: structural part (bar from zero), cyclical part (segment from the top of the
// structural bar to the observed gap) and the observed gap (dot).
export function GapDecomposition({ rows, colors, height = 340, annotations = [] }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const m = { top: annotations.length ? 30 : 12, right: 12, bottom: 28, left: 46 };
  const innerW = Math.max(120, width - m.left - m.right);
  const innerH = height - m.top - m.bottom;
  const values = rows.flatMap((r) => [0, r.structural, r.gap]);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const step = hi - lo > 12 ? 4 : 2;
  const y0 = Math.floor(lo / step) * step;
  const y1 = Math.ceil(hi / step) * step;
  const x0 = rows[0].year;
  const x1 = rows.at(-1).year;
  const band = innerW / (x1 - x0 + 1);
  const bw = Math.max(2, band * 0.7);
  const sx = (year) => m.left + (year - x0) * band + band / 2;
  const sy = (v) => m.top + ((y1 - v) / (y1 - y0)) * innerH;
  const compact = width < 520;
  const xStep = compact ? 10 : 5;
  const row = hover == null ? null : rows.find((r) => r.year === hover);
  return (
    <div className="tsChart" ref={ref}>
      <svg role="img" aria-label="Brecha de paro entre España y la UE-15 descompuesta en parte estructural y parte cíclica" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {ticks(y0, y1, step).map((t) => (
          <g key={t}>
            <line className={t === 0 ? "tsChart__baseline" : "tsChart__grid"} x1={m.left} x2={m.left + innerW} y1={sy(t)} y2={sy(t)} />
            <text className="tsChart__tick" x={m.left - 6} y={sy(t) + 4} textAnchor="end">
              {t > 0 ? "+" : ""}
              {t.toLocaleString("es-ES")}
            </text>
          </g>
        ))}
        {rows
          .filter((r) => r.year % xStep === 0)
          .map((r) => (
            <text key={r.year} className="tsChart__tick" x={sx(r.year)} y={height - 8} textAnchor="middle">
              {r.year}
            </text>
          ))}
        {annotations.map((a) => (
          <g key={a.year}>
            <line className="tsChart__note" x1={sx(a.year)} x2={sx(a.year)} y1={m.top - 6} y2={m.top + innerH} />
            {!compact ? (
              <text className="tsChart__noteLabel" x={sx(a.year) + 3} y={m.top - 10} textAnchor={sx(a.year) > width - 120 ? "end" : "start"}>
                {a.label}
              </text>
            ) : null}
          </g>
        ))}
        {rows.map((r) => {
          const x = sx(r.year) - bw / 2;
          const top = Math.min(sy(r.structural), sy(0));
          const cycTop = Math.min(sy(r.structural), sy(r.gap));
          return (
            <g key={r.year} opacity={hover == null || hover === r.year ? 1 : 0.55}>
              <rect x={x} y={top} width={bw} height={Math.abs(sy(r.structural) - sy(0))} fill={colors.structural} />
              <rect
                x={x + bw * 0.2}
                y={cycTop}
                width={bw * 0.6}
                height={Math.max(1, Math.abs(sy(r.gap) - sy(r.structural)))}
                fill={r.cyclical >= 0 ? colors.cyclicalUp : colors.cyclicalDown}
              />
              <circle cx={sx(r.year)} cy={sy(r.gap)} r={Math.min(4, Math.max(2.5, bw / 3))} fill={colors.gap} stroke="var(--viz-surface)" strokeWidth={1} />
            </g>
          );
        })}
        <rect
          x={m.left}
          y={0}
          width={innerW}
          height={height}
          fill="transparent"
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - rect.left) / rect.width) * innerW;
            setHover(Math.min(x1, Math.max(x0, x0 + Math.floor(px / band))));
          }}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      {row ? (
        <div className="tsChart__tooltip" style={{ left: sx(row.year) > width * 0.6 ? undefined : sx(row.year) + 12, right: sx(row.year) > width * 0.6 ? width - sx(row.year) + 12 : undefined, top: m.top }} role="status">
          <span className="tsChart__tooltipYear">{row.year}</span>
          <span className="tsChart__tooltipRow">
            <strong>{fmt(row.gap, "pp")}</strong>
            <span className="tsChart__tooltipLabel">
              brecha observada ({num(row.es)} % frente a {num(row.eu)} % en la {row.eu_ref})
            </span>
          </span>
          <span className="tsChart__tooltipRow">
            <span className="tsChart__key" style={{ background: colors.structural }} aria-hidden="true" />
            <strong>{fmt(row.structural, "pp")}</strong>
            <span className="tsChart__tooltipLabel">estructural (NAWRU {num(row.nawru_es)} % frente a {num(row.nawru_eu)} %)</span>
          </span>
          <span className="tsChart__tooltipRow">
            <span className="tsChart__key" style={{ background: row.cyclical >= 0 ? colors.cyclicalUp : colors.cyclicalDown }} aria-hidden="true" />
            <strong>{fmt(row.cyclical, "pp")}</strong>
            <span className="tsChart__tooltipLabel">cíclica</span>
          </span>
        </div>
      ) : null}
    </div>
  );
}

// Employees by contract each quarter (stacked areas from zero, thousands) plus, as a second encoding, the annual mean
// of «fijos discontinuos» without activity registered as job seekers (hatched layer stacked on the working ones).
export function ContractStack({ quarters, seekers, colors, reformQuarter, height = 360 }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const m = { top: 26, right: 12, bottom: 28, left: 58 };
  const innerW = Math.max(120, width - m.left - m.right);
  const innerH = height - m.top - m.bottom;
  const idx = (q) => (Number(q.slice(0, 4)) - Number(quarters[0].quarter.slice(0, 4))) * 4 + Number(q.slice(5)) - 1;
  const n = quarters.length;
  const sx = (i) => m.left + (i / (n - 1)) * innerW;
  const seekerByYear = new Map(seekers.map((s) => [s.year, s.value]));
  const tops = quarters.map((q) => q.total + (seekerByYear.get(Number(q.quarter.slice(0, 4))) || 0));
  const step = 2500;
  const y1 = Math.ceil(Math.max(...tops) / step) * step;
  const sy = (v) => m.top + (1 - v / y1) * innerH;
  const withSeek = quarters.map((q) => ({ ...q, seek: seekerByYear.get(Number(q.quarter.slice(0, 4))) || 0 }));
  const layers = [
    { key: "ordinary", fill: colors.ordinary },
    { key: "fd", fill: colors.fd },
    { key: "seek", fill: "url(#fdHatch)", stroke: colors.fd },
    { key: "temporal", fill: colors.temporal },
  ];
  let cumulative = withSeek.map(() => 0);
  const paths = layers.map((layer) => {
    const lower = cumulative;
    const upper = withSeek.map((q, i) => lower[i] + q[layer.key]);
    cumulative = upper;
    // Step edges for the annual hatched layer, smooth lines for quarterly layers.
    const top = upper.map((v, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join("");
    const bottom = lower
      .map((v, i) => [i, v])
      .reverse()
      .map(([i, v]) => `L${sx(i).toFixed(1)},${sy(v).toFixed(1)}`)
      .join("");
    return { ...layer, d: `${top}${bottom}Z` };
  });
  const years = [...new Set(quarters.map((q) => Number(q.quarter.slice(0, 4))))];
  const reformX = reformQuarter ? sx(idx(reformQuarter)) : null;
  const row = hover == null ? null : quarters[hover];
  const seek = row ? seekerByYear.get(Number(row.quarter.slice(0, 4))) : null;
  return (
    <div className="tsChart" ref={ref}>
      <svg role="img" aria-label="Asalariados por tipo de contrato y fijos discontinuos inactivos inscritos" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <pattern id="fdHatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke={colors.fd} strokeWidth="2" />
          </pattern>
        </defs>
        {ticks(0, y1, step).map((t) => (
          <g key={t}>
            <line className={t === 0 ? "tsChart__baseline" : "tsChart__grid"} x1={m.left} x2={m.left + innerW} y1={sy(t)} y2={sy(t)} />
            <text className="tsChart__tick" x={m.left - 6} y={sy(t) + 4} textAnchor="end">
              {t >= 1000 ? `${(t / 1000).toLocaleString("es-ES")} M` : t}
            </text>
          </g>
        ))}
        {paths.map((p) => (
          <path key={p.key} d={p.d} fill={p.fill} opacity={0.9} stroke={p.stroke} strokeDasharray={p.stroke ? "3 2" : undefined} strokeWidth={p.stroke ? 0.8 : 0} />
        ))}
        {years.map((y) => {
          const i = quarters.findIndex((q) => q.quarter === `${y}T1`);
          return i < 0 ? null : (
            <text key={y} className="tsChart__tick" x={sx(i)} y={height - 8} textAnchor="middle">
              {y}
            </text>
          );
        })}
        {reformX != null ? (
          <g>
            <line className="tsChart__note" x1={reformX} x2={reformX} y1={m.top - 6} y2={m.top + innerH} />
            <text className="tsChart__noteLabel" x={reformX + 3} y={m.top - 10}>
              Reforma 2022
            </text>
          </g>
        ) : null}
        {row ? <line className="tsChart__crosshair" x1={sx(hover)} x2={sx(hover)} y1={m.top} y2={m.top + innerH} /> : null}
        <rect
          x={m.left}
          y={0}
          width={innerW}
          height={height}
          fill="transparent"
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const px = ((e.clientX - rect.left) / rect.width) * innerW;
            setHover(Math.min(n - 1, Math.max(0, Math.round((px / innerW) * (n - 1)))));
          }}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      {row ? (
        <div className="tsChart__tooltip" style={{ left: sx(hover) > width * 0.6 ? undefined : sx(hover) + 12, right: sx(hover) > width * 0.6 ? width - sx(hover) + 12 : undefined, top: m.top }} role="status">
          <span className="tsChart__tooltipYear">{row.quarter.replace("T", " T")}</span>
          {[
            ["ordinary", "Indefinidos ordinarios"],
            ["fd", "Fijos discontinuos trabajando"],
            ["temporal", "Temporales"],
          ].map(([key, label]) => (
            <span className="tsChart__tooltipRow" key={key}>
              <span className="tsChart__key" style={{ background: colors[key] }} aria-hidden="true" />
              <strong>{fmt(row[key], "thousands")}</strong>
              <span className="tsChart__tooltipLabel">{label}</span>
            </span>
          ))}
          {seek ? (
            <span className="tsChart__tooltipRow">
              <span className="tsChart__key" style={{ background: `repeating-linear-gradient(45deg, ${colors.fd} 0 2px, transparent 2px 5px)` }} aria-hidden="true" />
              <strong>{fmt(seek, "thousands")}</strong>
              <span className="tsChart__tooltipLabel">fijos discontinuos inactivos inscritos (media del año)</span>
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// Scatter with both axes from zero: one dot per region, plus labelled reference points (country, EU).
export function RegionScatter({ points, refs = [], xLabel, yLabel, color, height = 380 }) {
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const m = { top: 14, right: 16, bottom: 42, left: 50 };
  const innerW = Math.max(120, width - m.left - m.right);
  const innerH = height - m.top - m.bottom;
  const all = [...points, ...refs];
  const xStep = 10;
  const yStep = 5;
  const x1 = Math.ceil(Math.max(...all.map((p) => p.x)) / xStep) * xStep;
  const y1 = Math.ceil(Math.max(...all.map((p) => p.y)) / yStep) * yStep;
  const sx = (v) => m.left + (v / x1) * innerW;
  const sy = (v) => m.top + (1 - v / y1) * innerH;
  const compact = width < 520;
  const active = hover == null ? null : all.find((p) => p.id === hover);
  // Greedy label placement: try right, left, above, below, then a farther nudge with a leader line; a label that still
  // collides with a placed label, a reference label or a dot is left to the tooltip and the table.
  const CH = 6.4;
  const LH = 12;
  const boxes = refs.map((p) => ({ x0: sx(p.x) + 8, x1: sx(p.x) + 10 + p.label.length * 7, y0: sy(p.y) - 8, y1: sy(p.y) + 6 }));
  const dots = [...points, ...refs].map((p) => ({ x0: sx(p.x) - 6, x1: sx(p.x) + 6, y0: sy(p.y) - 6, y1: sy(p.y) + 6 }));
  const hit = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  const placed = [];
  if (!compact) {
    for (const p of [...points].filter((q) => q.label).sort((a, b) => a.x - b.x)) {
      const cx = sx(p.x);
      const cy = sy(p.y);
      const w = p.label.length * CH;
      const options = [
        { tx: cx + 8, ty: cy + 4, anchor: "start", box: { x0: cx + 8, x1: cx + 8 + w, y0: cy - 8, y1: cy + 5 } },
        { tx: cx - 8, ty: cy + 4, anchor: "end", box: { x0: cx - 8 - w, x1: cx - 8, y0: cy - 8, y1: cy + 5 } },
        { tx: cx, ty: cy - 9, anchor: "middle", box: { x0: cx - w / 2, x1: cx + w / 2, y0: cy - 9 - LH + 2, y1: cy - 7 } },
        { tx: cx, ty: cy + 18, anchor: "middle", box: { x0: cx - w / 2, x1: cx + w / 2, y0: cy + 8, y1: cy + 20 } },
        ...[-1, 1].flatMap((dir) =>
          [22, 34, 46].map((dy) => ({
            tx: cx + 14, ty: cy + dir * dy + 4, anchor: "start", leader: true, lx: cx + 12, ly: cy + dir * dy,
            box: { x0: cx + 14, x1: cx + 14 + w, y0: cy + dir * dy - 8, y1: cy + dir * dy + 5 },
          })),
        ),
      ];
      const inside = (b) => b.x0 >= m.left && b.x1 <= m.left + innerW && b.y0 >= m.top - 4 && b.y1 <= m.top + innerH;
      const ok = options.find((o) => inside(o.box) && !boxes.some((b) => hit(o.box, b)) && !dots.some((d) => hit(o.box, d)));
      if (ok) {
        boxes.push(ok.box);
        placed.push({ id: p.id, text: p.label, ...ok, ax: cx, ay: cy });
      }
    }
  }
  return (
    <div className="tsChart" ref={ref}>
      <svg role="img" aria-label={`${yLabel} frente a ${xLabel} por comunidad autónoma`} width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {ticks(0, y1, yStep).map((t) => (
          <g key={`y${t}`}>
            <line className={t === 0 ? "tsChart__baseline" : "tsChart__grid"} x1={m.left} x2={m.left + innerW} y1={sy(t)} y2={sy(t)} />
            <text className="tsChart__tick" x={m.left - 6} y={sy(t) + 4} textAnchor="end">
              {t}%
            </text>
          </g>
        ))}
        {ticks(0, x1, xStep).map((t) => (
          <g key={`x${t}`}>
            <line className="tsChart__grid" x1={sx(t)} x2={sx(t)} y1={m.top} y2={m.top + innerH} />
            {t > 0 ? (
              <text className="tsChart__tick" x={sx(t)} y={m.top + innerH + 16} textAnchor="middle">
                {t} €
              </text>
            ) : null}
          </g>
        ))}
        <text className="tsChart__tick" x={m.left + innerW} y={height - 4} textAnchor="end">
          {xLabel}
        </text>
        {points.map((p) => (
          <circle
            key={p.id}
            cx={sx(p.x)}
            cy={sy(p.y)}
            r={hover === p.id ? 7 : 5.5}
            fill={color}
            opacity={0.85}
            stroke="var(--viz-surface)"
            strokeWidth={1}
            onPointerEnter={() => setHover(p.id)}
            onPointerLeave={() => setHover(null)}
          />
        ))}
        {placed.map((l) => (
          <g key={`l-${l.id}`}>
            {l.leader ? <line x1={l.ax} y1={l.ay} x2={l.lx} y2={l.ly} stroke="var(--viz-axis)" strokeWidth={1} /> : null}
            <text className="tsChart__noteLabel" x={l.tx} y={l.ty} textAnchor={l.anchor}>
              {l.text}
            </text>
          </g>
        ))}
        {refs.map((p) => (
          <g key={p.id} onPointerEnter={() => setHover(p.id)} onPointerLeave={() => setHover(null)}>
            <rect x={sx(p.x) - 6} y={sy(p.y) - 6} width={12} height={12} fill={p.color} stroke="var(--viz-surface)" strokeWidth={1} transform={`rotate(45 ${sx(p.x)} ${sy(p.y)})`} />
            <text className="tsChart__endLabel" x={sx(p.x) + 10} y={sy(p.y) + 4}>
              {p.label}
            </text>
          </g>
        ))}
      </svg>
      {active ? (
        <div className="tsChart__tooltip" style={{ left: sx(active.x) > width * 0.6 ? undefined : sx(active.x) + 12, right: sx(active.x) > width * 0.6 ? width - sx(active.x) + 12 : undefined, top: m.top }} role="status">
          <span className="tsChart__tooltipYear">{active.name || active.label}</span>
          <span className="tsChart__tooltipRow">
            <strong>{num(active.x)} €</strong>
            <span className="tsChart__tooltipLabel">{xLabel}</span>
          </span>
          <span className="tsChart__tooltipRow">
            <strong>{num(active.y)} %</strong>
            <span className="tsChart__tooltipLabel">{yLabel}</span>
          </span>
        </div>
      ) : null}
    </div>
  );
}
