"use client";

import { fmt } from "./FanChart";

// Causal map of slice 0. Each arrow is a card of the catalog (or an accounting identity); its line says how solid
// the evidence is (A continuous, B dashed, C/D dotted). Nodes are coloured by their deviation in the chosen year.
const W = 1000;
const H = 470;
const NW = 172;
const NH = 48;

export const NODES = [
  { id: "reval", label: "Revalorización real", x: 90, y: 48, kind: "lever" },
  { id: "age", label: "Edad de jubilación", x: 90, y: 124, kind: "lever" },
  { id: "contrib", label: "Cotización extra", x: 90, y: 200, kind: "lever" },
  { id: "closure", label: "Cómo se paga", x: 90, y: 276, kind: "lever" },
  { id: "migration", label: "Inmigración", x: 90, y: 352, kind: "context" },
  { id: "rate", label: "Tipos de mercado", x: 90, y: 428, kind: "context" },
  { id: "pension_media", label: "Pensión media", x: 300, y: 48 },
  { id: "pensionistas", label: "Pensionistas", x: 300, y: 124 },
  { id: "coste_laboral", label: "Coste laboral", x: 300, y: 210 },
  { id: "iva", label: "Tipo de IVA", x: 300, y: 296 },
  { id: "ipc", label: "Precios", x: 300, y: 386 },
  { id: "gasto", label: "Gasto en pensiones", x: 510, y: 86 },
  { id: "empleo", label: "Empleo", x: 510, y: 196 },
  { id: "salario", label: "Salario bruto", x: 510, y: 296 },
  { id: "pib", label: "PIB", x: 510, y: 436 },
  { id: "recaudacion", label: "Ingresos públicos", x: 720, y: 120 },
  { id: "saldo", label: "Déficit", x: 720, y: 210 },
  { id: "deuda", label: "Deuda", x: 720, y: 300 },
  { id: "tipo_deuda", label: "Interés de la deuda", x: 720, y: 424 },
  { id: "p4", label: "Caso 4 · pensionista", x: 912, y: 48, kind: "person" },
  { id: "p1", label: "Caso 1 · joven asalariada", x: 912, y: 386, kind: "person" },
];

export const LINKS = [
  { from: "reval", to: "pension_media", edge: "E01_pension_turnover", sign: "+" },
  { from: "age", to: "pensionistas", edge: "E02_retirement_cohort", sign: "−" },
  { from: "age", to: "empleo", edge: "E03_delay_employment", sign: "+" },
  { from: "pension_media", to: "gasto", sign: "+" },
  { from: "pensionistas", to: "gasto", sign: "+" },
  { from: "migration", to: "gasto", edge: "E21_migration_pensions", sign: "−" },
  { from: "gasto", to: "recaudacion", edge: "E04_pension_irpf", sign: "+" },
  { from: "gasto", to: "saldo", sign: "+" },
  { from: "gasto", to: "pib", edge: "E06_transfer_multiplier", sign: "+" },
  { from: "pib", to: "recaudacion", edge: "E07_budget_semi_elasticity", sign: "+" },
  { from: "empleo", to: "recaudacion", edge: "E11_revenue_per_job", sign: "+" },
  { from: "empleo", to: "pib", edge: "E20_labour_output", sign: "+" },
  { from: "contrib", to: "coste_laboral", sign: "+" },
  { from: "contrib", to: "recaudacion", edge: "E10_ssc_base", sign: "+" },
  { from: "closure", to: "coste_laboral", sign: "+", when: "cotizaciones" },
  { from: "closure", to: "iva", sign: "+", when: "iva" },
  { from: "closure", to: "deuda", sign: "+", when: "deuda" },
  { from: "coste_laboral", to: "empleo", edge: "E09_labour_demand", sign: "−", loop: "B1" },
  { from: "coste_laboral", to: "salario", edge: "E08_ssc_incidence", sign: "−" },
  { from: "iva", to: "recaudacion", edge: "E12_vat_yield", sign: "+" },
  { from: "iva", to: "ipc", edge: "E13_vat_passthrough", sign: "+" },
  { from: "ipc", to: "p1", edge: "E14_wage_indexation", sign: "−" },
  { from: "recaudacion", to: "saldo", sign: "−" },
  { from: "saldo", to: "deuda", edge: "E18_deficit_debt", sign: "+" },
  { from: "deuda", to: "tipo_deuda", edge: "E16_debt_risk_premium", sign: "+", loop: "R1" },
  { from: "tipo_deuda", to: "deuda", edge: "E17_refinancing", sign: "+", loop: "R1" },
  { from: "rate", to: "tipo_deuda", sign: "+" },
  { from: "pension_media", to: "p4", sign: "+" },
  { from: "salario", to: "p1", sign: "+" },
];

const pos = Object.fromEntries(NODES.map((n) => [n.id, n]));

/** Deviation shown in each node at year index t (value, unit, digits). */
export function nodeValues(run, t, levers) {
  const rev =
    run.irpf_back_pp[t] + run.labour_revenue_pp[t] + run.contrib_revenue_pp[t] + run.vat_revenue_pp[t] + run.cycle_revenue_pp[t];
  return {
    reval: [levers.reval, "pp", 1, "al año sobre el IPC"],
    age: [levers.age, "años", 1],
    contrib: [levers.contrib, "pp", 1, "de la base"],
    closure: [null, levers.closure],
    migration: [null, levers.migration === "low" ? "−33 %" : levers.migration === "high" ? "+33 %" : "base oficial"],
    rate: [levers.rateShock, "pp", 1],
    pension_media: [run.pension_dev[t] * 100, "pct", 1],
    pensionistas: [run.pensioners_dev[t] * 100, "pct", 1],
    coste_laboral: [run.labour_cost_dev[t] * 100, "pct", 2],
    iva: [run.closure_vat_pp[t], "pp", 1, "de tipo"],
    ipc: [run.price_level_dev[t] * 100, "pct", 2],
    gasto: [run.pension_gross_pp[t] + run.migration_pp[t], "pp", 2, "del PIB"],
    empleo: [run.employment_k[t], "k", 0],
    salario: [run.wage_dev[t] * 100, "pct", 2],
    pib: [run.gdp_dev[t], "pct", 2],
    recaudacion: [rev, "pp", 2, "del PIB"],
    saldo: [run.primary_dev_pp[t] + run.interest_dev_pp[t], "pp", 2, "del PIB"],
    deuda: [run.debt_dev_pp[t], "pp", 1, "del PIB"],
    tipo_deuda: [run.implicit_rate_dev[t], "pp", 2],
    p4: [run.p4_month[t], "eur", 0, "al mes"],
    p1: [run.p1_month[t], "eur", 0, "al mes"],
  };
}

const CLOSURE_LABEL = { deuda: "con deuda", cotizaciones: "con cotizaciones", iva: "con IVA" };

function valueText([v, unit, digits, suffix]) {
  if (v == null) return CLOSURE_LABEL[unit] || unit;
  if (unit === "años") return `${v > 0 ? "+" : ""}${Number(v).toLocaleString("es-ES")} años`;
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${fmt(Math.abs(v), unit, digits)}${suffix ? ` ${suffix}` : ""}`;
}

const isOn = ([v, unit, digits]) => v != null && Math.abs(v) >= 0.5 * 10 ** -(digits ?? 1);

export default function CausalMap({ run, t, levers, edges, selected, onSelect }) {
  const values = nodeValues(run, t, levers);
  const grade = Object.fromEntries(edges.map((e) => [e.id, e.grade]));
  const anchor = (a, b) => {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const sx = Math.abs(dx) / (NW / 2 + 6);
    const sy = Math.abs(dy) / (NH / 2 + 6);
    const s = Math.max(sx, sy) || 1;
    return [a.x + dx / s, a.y + dy / s];
  };
  return (
    <div className="cmap">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Mapa causal del módulo de pensiones y cuentas públicas">
        <defs>
          <marker id="cmap-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="cmap__arrowHead" />
          </marker>
        </defs>
        {LINKS.map((link) => {
          const a = pos[link.from];
          const b = pos[link.to];
          if (link.when && levers.closure !== link.when) return null;
          const back = link.from === "tipo_deuda" && link.to === "deuda";
          const [x1, y1] = anchor(a, b);
          const [x2, y2] = anchor(b, a);
          const offset = link.loop === "R1" ? (back ? 16 : -16) : 0;
          const g = link.edge ? grade[link.edge] : "A";
          const active = isOn(values[link.from]) && isOn(values[link.to]);
          const dash = g === "A" ? undefined : g === "B" ? "7 4" : "2 4";
          const mid = [(x1 + x2) / 2 + offset, (y1 + y2) / 2];
          return (
            <g
              key={`${link.from}-${link.to}`}
              className={`cmap__link${active ? " is-active" : ""}${selected === link.edge ? " is-selected" : ""}`}
              onClick={link.edge ? () => onSelect(link.edge) : undefined}
              role={link.edge ? "button" : undefined}
              tabIndex={link.edge ? 0 : undefined}
              aria-label={link.edge ? `Relación ${pos[link.from].label} → ${pos[link.to].label}: ver la ficha` : undefined}
              onKeyDown={link.edge ? (e) => (e.key === "Enter" || e.key === " ") && onSelect(link.edge) : undefined}
            >
              <path
                d={`M${x1 + offset},${y1} Q${mid[0] + offset},${mid[1]} ${x2 + offset},${y2}`}
                fill="none"
                strokeDasharray={dash}
                markerEnd="url(#cmap-arrow)"
              />
              {link.edge ? <path d={`M${x1 + offset},${y1} L${x2 + offset},${y2}`} className="cmap__hit" /> : null}
              <text x={mid[0] + 4} y={mid[1] - 4} className="cmap__sign">
                {link.sign}
              </text>
            </g>
          );
        })}
        <text x={720 - NW / 2 - 26} y={368} className="cmap__loop">R1</text>
        <text x={366} y={176} className="cmap__loop">B1</text>
        {NODES.map((node) => {
          const v = values[node.id];
          const on = isOn(v);
          const tone = !on || v[0] == null ? "none" : v[0] > 0 ? "up" : "down";
          return (
            <g key={node.id} className={`cmap__node cmap__node--${node.kind || "var"} is-${tone}`}>
              <rect x={node.x - NW / 2} y={node.y - NH / 2} width={NW} height={NH} rx={10} />
              <text x={node.x} y={node.y - 5} textAnchor="middle" className="cmap__label">
                {node.label}
              </text>
              <text x={node.x} y={node.y + 14} textAnchor="middle" className="cmap__value">
                {v[0] == null || on ? valueText(v) : "sin cambio"}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="cmap__swipe">Desliza el mapa a los lados para verlo entero.</p>
      <ActiveChain values={values} levers={levers} onSelect={onSelect} />
    </div>
  );
}

// The same propagation as text: every active arrow with the values at both ends (readable on a phone and by screen readers).
function ActiveChain({ values, levers, onSelect }) {
  const active = LINKS.filter((l) => (!l.when || levers.closure === l.when) && isOn(values[l.from]) && isOn(values[l.to]));
  if (!active.length) return null;
  return (
    <details className="cmap__chain" open>
      <summary>Relaciones activas ({active.length})</summary>
      <ul>
        {active.map((l) => (
          <li key={`${l.from}-${l.to}`}>
            {pos[l.from].label} <span className="sim__muted">({valueText(values[l.from])})</span> → {pos[l.to].label}{" "}
            <span className="sim__muted">({valueText(values[l.to])})</span>
            {l.edge ? (
              <>
                {" "}
                <button type="button" className="cmap__cardLink" onClick={() => onSelect(l.edge)}>
                  ficha
                </button>
              </>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}
