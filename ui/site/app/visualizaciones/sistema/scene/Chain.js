"use client";

import { LINKS, NODES, nodeValues } from "../CausalMap";
import { HOUSING_LINKS, HOUSING_NODES, housingValues } from "../HousingMap";
import { Icon, PAL } from "./art";

// «Why»: the active causal links as a readable chain of steps, each with its icons, the values at both ends and the
// strength of its evidence; a click opens the card with source, range and what contradicts it.
const NODE_ICON = {
  reval: "pension", age: "age", contrib: "payroll", closure: "debt", migration: "people", rate: "rate", tax: "irpf",
  pension_media: "pension", pensionistas: "people", coste_laboral: "factory", iva: "cart", ipc: "cart", gasto: "pension",
  empleo: "people", salario: "payroll", pib: "top", recaudacion: "irpf", saldo: "debt", deuda: "debt", tipo_deuda: "rate",
  p4: "pension", p1: "people",
  pub: "building", land: "land", tour: "suitcase", cap: "cap", caps: "mortgage", obra_publica: "building", obra_privada: "building",
  turistica: "suitcase", oferta_alquiler: "key", credito: "mortgage", parque: "building", hogares: "people", alquiler: "key",
  precio: "mortgage", emancipacion: "people", alq_cubierto: "key", alq_libre: "key", p2: "people",
};
// Housing nodes that share an id with the pensions map but mean something else.
const HOUSING_ICON = { gasto: "building", deuda: "debt", p1: "key", p2: "mortgage", migration: "people" };
const iconOf = (l, id) => (l.set.prefix === "h" && HOUSING_ICON[id]) || NODE_ICON[id] || "rate";
const GRADE = {
  A: { label: "Evidencia fuerte", note: "contabilidad, ley o datos de España", color: PAL.green },
  B: { label: "Evidencia media", note: "estudios de otros países o meta-análisis", color: PAL.blue },
  C: { label: "Evidencia débil", note: "consenso sin estimación propia", color: PAL.yellow },
  D: { label: "Supuesto", note: "sin estimación", color: PAL.orange },
};
const LABEL = Object.fromEntries(NODES.map((n) => [n.id, n.label]));
const HLABEL = Object.fromEntries(HOUSING_NODES.map((n) => [n.id, n.label]));

function valueText([v, unit, digits, suffix, text]) {
  if (text) return text;
  if (v == null) return unit;
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const abs = Math.abs(v).toLocaleString("es-ES", { minimumFractionDigits: unit === "eur" || unit === "k" ? 0 : digits, maximumFractionDigits: unit === "eur" || unit === "k" ? 0 : digits });
  const u = { pct: " %", pp: " pp", eur: " €", k: " mil", años: " años" }[unit] ?? "";
  return `${sign}${abs}${u}${suffix ? ` ${suffix}` : ""}`;
}
const isOn = ([v, , digits]) => v != null && Math.abs(v) >= 0.5 * 10 ** -(digits ?? 1);

export default function Chain({ run, t, levers, edges, selected, onSelect }) {
  const grade = Object.fromEntries(edges.map((e) => [e.id, e.grade]));
  const sets = [
    { links: LINKS, values: nodeValues(run, t, levers), label: LABEL, prefix: "m" },
    { links: HOUSING_LINKS, values: housingValues(run, t, levers), label: HLABEL, prefix: "h" },
  ];
  const active = sets.flatMap((set) =>
    set.links
      .filter((l) => (!l.when || levers.closure === l.when) && set.values[l.from] && set.values[l.to] && isOn(set.values[l.from]) && isOn(set.values[l.to]))
      .map((l) => ({ ...l, set })),
  );
  if (!active.length) {
    return <p className="chain__empty">Mueve una palanca y aquí aparece, paso a paso, por dónde se transmite el cambio.</p>;
  }
  return (
    <ol className="chain">
      {active.map((l) => {
        const g = l.edge ? GRADE[grade[l.edge]] || GRADE.C : { label: "Contabilidad", note: "identidad", color: PAL.muted };
        return (
          <li key={`${l.set.prefix}-${l.from}-${l.to}`} className={selected && selected === l.edge ? "is-selected" : ""}>
            <span className="chain__node">
              <span className="chain__icon"><Icon name={iconOf(l, l.from)} size={20} /></span>
              <span>
                {l.set.label[l.from]} <b>{valueText(l.set.values[l.from])}</b>
              </span>
            </span>
            <span className="chain__arrow" aria-hidden="true">{l.sign === "−" ? "▼ baja" : "▲ sube"}</span>
            <span className="chain__node">
              <span className="chain__icon"><Icon name={iconOf(l, l.to)} size={20} /></span>
              <span>
                {l.set.label[l.to]} <b>{valueText(l.set.values[l.to])}</b>
              </span>
            </span>
            <span className="chain__grade" style={{ "--g": g.color }} title={g.note}>
              {g.label}
            </span>
            {l.edge ? (
              <button type="button" className="chip" onClick={() => onSelect(l.edge)}>
                De dónde sale
              </button>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
