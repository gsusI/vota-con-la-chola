// Pure helpers for /visualizaciones/decisiones/ (no React): labels, colours, the party ledger and the page copy, all
// computed from the published decisiones.json so every number on the page traces to the exporter.

export const DATA_PATH = "visualizaciones/data/decisiones.json";
export const PAGE_PATH = "/visualizaciones/decisiones/";

export const STANCE = {
  backed: { label: "A favor de la medida", short: "A favor", color: "#2a78d6" },
  opposed: { label: "En contra de la medida", short: "En contra", color: "#eb6834" },
  abstained: { label: "Abstención", short: "Abst.", color: "#b4b2a9" },
  split: { label: "Grupo dividido", short: "Dividido", color: "#e3e1da" },
  absent: { label: "No votó / sin escaño", short: "—", color: "transparent" },
};

export const VERDICT = {
  positivo: { label: "Evaluada: resultado positivo para su objetivo", short: "positiva", marker: "●" },
  negativo: { label: "Evaluada: resultado negativo para su objetivo", short: "negativa", marker: "▲" },
  mixto: { label: "Evaluada: resultado mixto", short: "mixta", marker: "◆" },
  no_evaluado: { label: "Sin evaluación posterior de calidad (A o B)", short: "sin evaluar", marker: "○" },
  pendiente: { label: "Pendiente de documentar", short: "pendiente", marker: "·" },
};

export const UNIT = {
  ley: "Ley (votación final)",
  decreto_ley: "Decreto-ley (convalidación)",
  presupuesto: "Presupuestos Generales (sección)",
  contrafactual: "Contrafactual: no llegó a tener efecto",
};

export const GRADE = {
  A: "A: evaluación causal de esta medida en España",
  B: "B: evaluación descriptiva de esta medida, o causal de una medida muy parecida fuera",
  C: "C: estimación previa o consenso de manual",
  D: "D: supuesto sin método",
};

export const PARTY_ORDER = ["psoe", "sumar", "up", "podemos", "erc", "bildu", "pnv", "bng", "cc", "junts", "plural", "mixto", "cs", "pp", "upn", "vox"];

export const CAUSAL_WORDS = /gracias a|por culpa de|provocó|causó|empleos creados|empleos destruidos|creó \d|destruyó \d/i;

export function num(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
}

export function dateEs(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  const months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${d} ${months[m - 1]} ${y}`;
}

export function yearFraction(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

export function measureName(m) {
  return m.name || m.title.replace(/^Votación (del dictamen|de conjunto|conjunta)[^:]*?(del|de la|al)\s+/i, "").slice(0, 90);
}

export function margin(m) {
  return Math.abs(m.totals.si - m.totals.no);
}

/** Parties that appear in any measure of the list, in a stable left-to-right order. */
export function partiesIn(measures) {
  const present = new Set(measures.flatMap((m) => Object.keys(m.parties)));
  return PARTY_ORDER.filter((p) => present.has(p));
}

/** Per party and domain: measures backed / opposed / abstained, each split by verdict, plus decisive votes. */
export function ledger(data) {
  const rows = [];
  for (const pid of partiesIn(data.measures)) {
    const row = { party: pid, label: data.party_labels[pid] || pid, domains: {} };
    for (const d of data.domains) {
      const cell = { backed: {}, opposed: {}, abstained: {}, decisive: [], total: 0 };
      for (const m of data.measures) {
        if (!m.domains.includes(d.id) || !m.parties[pid]) continue;
        const r = m.parties[pid];
        if (r.stance in cell && r.stance !== "decisive") {
          (cell[r.stance][m.verdict] ||= []).push(m.measure_id);
          cell.total += 1;
        }
        if (r.decisive_if_absent) cell.decisive.push(m.measure_id);
      }
      row.domains[d.id] = cell;
    }
    rows.push(row);
  }
  return rows;
}

export function count(cell, stance) {
  return Object.values(cell[stance] || {}).reduce((n, list) => n + list.length, 0);
}

/** Headline numbers for the hero, the stats row and the summary. */
export function headline(data) {
  const ms = data.measures;
  const evaluated = ms.filter((m) => ["positivo", "negativo", "mixto"].includes(m.verdict));
  const narrow = ms.filter((m) => margin(m) <= 10);
  const counterfactual = ms.filter((m) => m.unit === "contrafactual");
  const positions = Object.values(data.positions || {}).reduce((n, d) => n + (d.votes || 0), 0);
  const byDomain = Object.fromEntries(data.domains.map((d) => [d.id, d.measures]));
  return {
    measures: ms.length,
    documented: ms.filter((m) => m.documented).length,
    evaluated: evaluated.length,
    notEvaluated: ms.filter((m) => m.verdict === "no_evaluado").length,
    narrow: narrow.length,
    counterfactual: counterfactual.length,
    positions,
    byDomain,
    first: ms.length ? ms[0].date : null,
    last: ms.length ? ms.at(-1).date : null,
  };
}

export function pageTitle(h) {
  return `Qué votó cada partido en ${h.measures} leyes y decretos de empleo, sanidad e inmigración`;
}

export function pageDescription(h) {
  return `Empleo, autónomos, sanidad e inmigración: ${h.measures} leyes y decretos votados en el Congreso (2022-2026), quién los apoyó, si su voto decidía y qué dicen las evaluaciones.`;
}

/** "Se movió con": before/after wording for an indicator, never causal. */
export function movedWith(move, unit = "") {
  const dir = move.change > 0 ? "subió" : move.change < 0 ? "bajó" : "no cambió";
  const amount = move.change === 0 ? "" : ` ${num(Math.abs(move.change), 1)}${unit}`;
  return `${move.label}: ${num(move.before, 1)} en ${move.before_year} → ${num(move.after, 1)} en ${move.after_year} (${dir}${amount}). Se movió con esta medida y con todo lo demás; no prueba efecto.`;
}
