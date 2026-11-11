import { SEVERITY_FILL, SEVERITY_INK, VOTE_CATEGORY_LABEL, num, signed } from "./model.mjs";

const SHORT = {
  reglas: "Reglas del juego",
  legitimidad: "Legitimidad del rival",
  violencia: "Violencia",
  libertades: "Libertades",
  minorias: "Minorías",
  justicia: "Justicia",
  corrupcion: "Corrupción",
  medios: "Medios",
  contrapesos: "Contrapesos",
};

function Half({ cell, side, party, indicator }) {
  const sev = cell.max_severity;
  const label = `${party} · ${indicator} · ${side === "gobierno" ? "gobernando" : "sin gobernar"}: ${cell.n} ${cell.n === 1 ? "resolución" : "resoluciones"}${sev ? `, gravedad máxima ${sev}` : ""}`;
  return (
    <span
      className={`dpxCell__half dpxCell__half--${side}`}
      style={{ background: SEVERITY_FILL[sev], color: SEVERITY_INK[sev] }}
      title={label}
      aria-label={label}
    >
      {cell.n ? cell.n : "·"}
    </span>
  );
}

// Consolidated figure: parties × indicators, each cell split into «gobernando» (left) and «sin gobernar» (right).
export function ConductMatrix({ data }) {
  const inds = data.codebook.indicators;
  const parties = [...data.parties].sort((a, b) => b.severity_sum - a.severity_sum || a.label.localeCompare(b.label));
  return (
    <div className="dpxMatrix__scroll">
      <table className="dpxMatrix">
        <thead>
          <tr>
            <th scope="col" className="dpxMatrix__corner">
              Partido
            </th>
            {inds.map((ind) => (
              <th scope="col" key={ind.id} className="dpxMatrix__ind" title={ind.definition}>
                <span>{SHORT[ind.id]}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {parties.map((p) => (
            <tr key={p.party_id}>
              <th scope="row">
                <a href={`#perfil-${p.party_id}`}>{p.party_id === "cc" ? "CC" : p.label}</a>
                <span className="dpxMatrix__years">
                  {p.national_government_years_in_window ? `${num(p.national_government_years_in_window, 1)} años` : "0 años"}
                </span>
              </th>
              {inds.map((ind) => {
                const cell = data.matrix[p.party_id][ind.id];
                return (
                  <td key={ind.id} className="dpxCell">
                    <Half cell={cell.gobierno} side="gobierno" party={p.label} indicator={SHORT[ind.id]} />
                    <Half cell={cell.fuera} side="fuera" party={p.label} indicator={SHORT[ind.id]} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SeverityLegend() {
  return (
    <ul className="vizLegend dpxLegend" aria-label="Leyenda">
      <li>
        <span className="dpxCell dpxCell--legend">
          <span className="dpxCell__half dpxCell__half--gobierno">2</span>
          <span className="dpxCell__half dpxCell__half--fuera">1</span>
        </span>
        izquierda: gobernando · derecha: sin gobernar (número de resoluciones)
      </li>
      {[1, 2, 3].map((s) => (
        <li key={s}>
          <span className="vizLegend__key" style={{ background: SEVERITY_FILL[s], width: 12, height: 12 }} aria-hidden="true" />
          gravedad máxima {s}
          {s === 1 ? " (no vinculante)" : s === 2 ? " (vinculante parcial)" : " (anulación total o prisión ≥ 1 año)"}
        </li>
      ))}
    </ul>
  );
}

// Dot plot: score from −1 (always against more checks) to +1 (always for), per category, legislature and role.
export function VoteDots({ data, category }) {
  const order = data.votes.parties_order;
  const rows = order
    .map((pid) => ({ pid, label: pid === "cc" ? "CC" : data.parties.find((p) => p.party_id === pid)?.label || pid, s: data.votes.summary[pid] }))
    .filter((r) => ["14", "15"].some((leg) => r.s?.[leg]?.[category]?.votes));
  const W = 480;
  const L = 84;
  const R = 16;
  const rowH = 26;
  const H = rows.length * rowH + 40;
  const x = (v) => L + ((v + 1) / 2) * (W - L - R);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="dpxDots" role="img" aria-label={`Posición de cada partido: ${VOTE_CATEGORY_LABEL[category]}`}>
      {[-1, -0.5, 0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={18} y2={H - 18} stroke={t === 0 ? "var(--viz-ref)" : "var(--viz-grid)"} strokeWidth={t === 0 ? 1.2 : 1} />
          <text x={x(t)} y={H - 4} textAnchor="middle" className="dpxAxis">
            {t === 0 ? "0" : signed(t, 1)}
          </text>
        </g>
      ))}
      <text x={x(-1)} y={11} className="dpxAxis" textAnchor="start">
        siempre contra más controles
      </text>
      <text x={x(1)} y={11} className="dpxAxis" textAnchor="end">
        siempre a favor
      </text>
      {rows.map((r, i) => {
        const y = 28 + i * rowH;
        return (
          <g key={r.pid}>
            <text x={L - 14} y={y + 4} textAnchor="end" className="dpxRowLabel">
              {r.label}
            </text>
            <line x1={x(-1)} x2={x(1)} y1={y} y2={y} stroke="var(--viz-grid)" strokeDasharray="2 3" />
            {["14", "15"].map((leg) => {
              const c = r.s?.[leg]?.[category];
              if (!c?.votes || c.score === null) return null;
              const gov = r.s[leg].role === "gobierno";
              const color = gov ? "var(--viz-s2)" : "var(--viz-s1)";
              return (
                <circle key={leg} cx={x(c.score)} cy={y} r={6} fill={leg === "15" ? color : "var(--viz-surface)"} stroke={color} strokeWidth={2}>
                  <title>{`${r.label}, ${leg === "15" ? "XV" : "XIV"} legislatura (${gov ? "en el Gobierno" : "fuera del Gobierno"}): ${signed(c.score)} en ${c.votes} votaciones de ${c.initiatives} iniciativas`}</title>
                </circle>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}

export function DecreeBars({ series, governments }) {
  const W = 520;
  const H = 250;
  const L = 30;
  const R = 6;
  const T = 14;
  const B = 28;
  const max = Math.max(...series.map((s) => s.rdl));
  const top = Math.ceil(max / 10) * 10;
  const bw = (W - L - R) / series.length;
  const y = (v) => T + (1 - v / top) * (H - T - B);
  const party = new Map(governments.map((g) => [g.id, g.party]));
  const color = (gid) => {
    const p = party.get(gid) || "";
    if (p.startsWith("PSOE")) return "var(--viz-s2)";
    if (p.startsWith("PP")) return "var(--viz-s1)";
    return "var(--viz-peer)";
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="dpxBars" role="img" aria-label="Reales decretos-leyes por año, 1979-2026">
      {[0, top / 2, top].map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--viz-grid)" />
          <text x={L - 4} y={y(t) + 4} textAnchor="end" className="dpxAxis">
            {t}
          </text>
        </g>
      ))}
      {series.map((s, i) => (
        <g key={s.year}>
          <rect
            x={L + i * bw + 1}
            y={y(s.rdl)}
            width={Math.max(bw - 2, 1)}
            height={y(0) - y(s.rdl)}
            fill={color(s.government_mid_year)}
            opacity={s.partial_year ? 0.5 : 1}
          >
            <title>{`${s.year}: ${s.rdl} decretos-leyes, ${s.laws} leyes y ${s.organic_laws} leyes orgánicas (${num(s.rdl_share_pct, 0)} % decretos)${s.partial_year ? " · año en curso" : ""}`}</title>
          </rect>
          {s.year % 10 === 0 ? (
            <text x={L + i * bw + bw / 2} y={H - 10} textAnchor="middle" className="dpxAxis">
              {s.year}
            </text>
          ) : null}
        </g>
      ))}
    </svg>
  );
}

export function VPartyDots({ rows }) {
  const W = 480;
  const L = 150;
  const R = 34;
  const rowH = 26;
  const H = rows.length * rowH + 34;
  const x = (v) => L + v * (W - L - R);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="dpxDots" role="img" aria-label="Índice de antipluralismo de V-Party, elección de noviembre de 2019">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={10} y2={H - 18} stroke="var(--viz-grid)" />
          <text x={x(t)} y={H - 4} textAnchor="middle" className="dpxAxis">
            {num(t, 2)}
          </text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = 20 + i * rowH;
        return (
          <g key={r.label}>
            <text x={L - 8} y={y + 4} textAnchor="end" className="dpxRowLabel">
              {r.label}
            </text>
            <line x1={x(r.low)} x2={x(r.high)} y1={y} y2={y} stroke="var(--viz-s1)" strokeWidth={3} opacity={0.35} />
            <circle cx={x(r.value)} cy={y} r={5.5} fill="var(--viz-s1)">
              <title>{`${r.label}: ${num(r.value, 3)} (intervalo ${num(r.low, 3)}–${num(r.high, 3)})`}</title>
            </circle>
            <text x={x(r.high) + 6} y={y + 4} className="dpxAxis">
              {num(r.value, 2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
