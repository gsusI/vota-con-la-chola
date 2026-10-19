import { formatHealth } from "./format.mjs";

export const DIMENSION_COLORS = { renta: "#eb6834", edad: "#1baf7a", territorio: "#2a78d6" };
export const DIMENSION_LABELS = { renta: "Renta o clase social", edad: "Edad", territorio: "Tamaño del municipio" };

// Gaps between two groups, one row per service, every row on the same % scale from zero. Built with HTML so the
// labels keep their size on a phone: the track is positioned in % and the group labels sit under it.
export default function GapDumbbell({ rows, step = 10, ariaLabel }) {
  const max = step * Math.ceil(Math.max(...rows.flatMap((row) => [row.a, row.b, row.peak].filter(Boolean).map((g) => g.value + (g.moe || 0)))) / step);
  const x = (v) => `${(Math.max(0, Math.min(max, v)) / max) * 100}%`;
  const ticks = Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
  const pct = (v) => formatHealth(v, "pct", 1);
  return (
    <div role="figure" aria-label={ariaLabel} style={{ display: "grid", gap: 18 }}>
      {rows.map((row) => {
        const color = DIMENSION_COLORS[row.dimension];
        const lo = Math.min(row.a.value, row.b.value);
        const hi = Math.max(row.a.value, row.b.value);
        return (
          <div key={row.id} style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: "0.92rem", fontWeight: 600, color: "var(--viz-ink)" }}>
              {row.label}
              <span style={{ fontWeight: 400, color: "var(--viz-muted)" }}> · media de España {pct(row.national)}</span>
            </div>
            <div aria-hidden="true" style={{ position: "relative", height: 22, marginInline: 8 }}>
              <div style={{ position: "absolute", left: 0, right: 0, top: 10, height: 1, background: "var(--viz-grid)" }} />
              <div style={{ position: "absolute", left: x(lo), width: `calc(${x(hi)} - ${x(lo)})`, top: 9, height: 3, background: color, opacity: 0.45 }} />
              {[row.a, row.b].filter((g) => g.moe).map((g, i) => (
                <div key={`m${i}`} style={{ position: "absolute", left: x(g.value - g.moe), width: `calc(${x(g.value + g.moe)} - ${x(g.value - g.moe)})`, top: 4, height: 13, borderLeft: `1.5px solid ${color}`, borderRight: `1.5px solid ${color}`, boxSizing: "border-box" }}>
                  <div style={{ position: "absolute", left: 0, right: 0, top: 6, height: 1, background: color }} />
                </div>
              ))}
              <div title="Media de España" style={{ position: "absolute", left: x(row.national), top: 2, width: 2, height: 18, marginLeft: -1, background: "var(--viz-ref)" }} />
              {row.peak ? (
                <div style={{ position: "absolute", left: x(row.peak.value), top: 5, width: 9, height: 9, marginLeft: -4.5, transform: "rotate(45deg)", border: `2px solid ${color}`, background: "var(--viz-surface)" }} />
              ) : null}
              <div style={{ position: "absolute", left: x(row.b.value), top: 4, width: 13, height: 13, marginLeft: -6.5, borderRadius: "50%", border: `2.5px solid ${color}`, background: "var(--viz-surface)", boxSizing: "border-box" }} />
              <div style={{ position: "absolute", left: x(row.a.value), top: 4, width: 13, height: 13, marginLeft: -6.5, borderRadius: "50%", background: color }} />
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "2px 18px", fontSize: "0.82rem", color: "var(--viz-ink-2)" }}>
              <span><span aria-hidden="true" style={{ color }}>●</span> {row.a.label}: <strong>{pct(row.a.value)}</strong>{row.a.moe ? ` (±${formatHealth(row.a.moe, "ratio", 1)} p.)` : ""}</span>
              <span><span aria-hidden="true" style={{ color }}>○</span> {row.b.label}: <strong>{pct(row.b.value)}</strong>{row.b.moe ? ` (±${formatHealth(row.b.moe, "ratio", 1)} p.)` : ""}</span>
              {row.peak ? <span><span aria-hidden="true" style={{ color }}>◇</span> {row.peak.label}: <strong>{pct(row.peak.value)}</strong></span> : null}
            </div>
          </div>
        );
      })}
      <div aria-hidden="true" style={{ position: "relative", height: 18, marginInline: 8, borderTop: "1px solid var(--viz-axis)", fontSize: "0.75rem", color: "var(--viz-muted)" }}>
        {ticks.map((t, i) => (
          <span key={t} style={{ position: "absolute", left: x(t), top: 2, whiteSpace: "nowrap", transform: i === 0 ? "none" : i === ticks.length - 1 ? "translateX(-100%)" : "translateX(-50%)" }}>
            {t} %
          </span>
        ))}
      </div>
    </div>
  );
}
