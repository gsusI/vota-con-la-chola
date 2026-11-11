// Pure helpers for /visualizaciones/democracia/partidos/ (shared by the page and its node test).

export const ROLE_LABEL = {
  national_government: "Gobierno de España",
  regional_government: "Gobierno autonómico",
  local_government: "Gobierno local",
  opposition: "Fuera del Gobierno (oposición o mayoría parlamentaria)",
  party_organization: "El partido como organización",
};

export const ATTRIBUTION_LABEL = {
  government_act: "acto de su Gobierno",
  group_initiative: "iniciativa de su grupo",
  office_holder: "cargo condenado",
  party: "el propio partido",
};

export const FINDING_LABEL = {
  court_annulment_full: "anulación total",
  court_annulment_partial: "anulación parcial",
  amparo: "amparo (derecho vulnerado)",
  binding_declaration: "declaración vinculante de atribución vulnerada",
  conviction_prison_ge1: "condena firme con prisión ≥ 1 año",
  conviction_other: "condena firme sin prisión o < 1 año",
  civil_liability_party: "responsabilidad civil del partido",
  sanction_jec: "sanción de la Junta Electoral",
  sanction_tcu: "Tribunal de Cuentas",
  nonbinding_finding: "conclusión no vinculante",
};

export const VOTE_CATEGORY_LABEL = {
  estructural_vinculante: "Reglas que obligarían a cualquier Gobierno (leyes, decretos, enmiendas)",
  estructural_declarativa: "Las mismas reglas en mociones y proposiciones no de ley",
  escrutinio: "Escrutinio del Gobierno de turno",
};

export const SEVERITY_LABEL = { 1: "no vinculante", 2: "vinculante parcial", 3: "vinculante plena" };

const NUM = (digits) => new Intl.NumberFormat("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return NUM(digits).format(value);
}

export function signed(value, digits = 2) {
  if (value === null || value === undefined) return "—";
  const s = num(Math.abs(value), digits);
  return value > 0 ? `+${s}` : value < 0 ? `−${s}` : s;
}

export function dateEs(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function partyLabel(data, pid) {
  return data.parties.find((p) => p.party_id === pid)?.label || pid;
}

// Counted attributions of an event for one party (predecessor lineage is shown but never counted).
export function countedFor(event, pid) {
  return event.attributions.find((a) => a.party_id === pid && a.lineage !== "predecessor") || null;
}

export function eventsFor(data, pid) {
  return data.events
    .filter((e) => e.attributions.some((a) => a.party_id === pid))
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

// Matrix totals: per indicator and side, how many items and parties carry them.
export function matrixTotals(data) {
  const out = {};
  for (const ind of data.codebook.indicators) {
    out[ind.id] = { gobierno: 0, fuera: 0 };
    for (const p of data.parties) {
      const cell = data.matrix[p.party_id][ind.id];
      out[ind.id].gobierno += cell.gobierno.n;
      out[ind.id].fuera += cell.fuera.n;
    }
  }
  return out;
}

export function headline(data) {
  const counted = data.events.filter((e) => e.attributions.some((a) => a.lineage !== "predecessor"));
  const govItems = counted.flatMap((e) => e.attributions.filter((a) => a.lineage !== "predecessor"))
    .filter((a) => ["national_government", "regional_government", "local_government"].includes(a.role)).length;
  const allAtts = counted.flatMap((e) => e.attributions.filter((a) => a.lineage !== "predecessor")).length;
  const withItems = data.parties.filter((p) => p.events_counted > 0).length;
  return {
    events: counted.length,
    attributions: allAtts,
    govShare: allAtts ? govItems / allAtts : null,
    partiesWithItems: withItems,
    partiesNoSignal: data.parties.length - withItems,
    reversals: data.sensitivity.reversal_count,
    composite: data.sensitivity.publish_composite,
    firstYear: counted.length ? counted.map((e) => e.date).sort()[0].slice(0, 4) : null,
  };
}

// Colour by maximum severity of the cell (sequential, one hue).
export const SEVERITY_FILL = { 0: "transparent", 1: "#f5d9c8", 2: "#e79a6c", 3: "#b8461b" };
export const SEVERITY_INK = { 0: "#6f6e69", 1: "#17191f", 2: "#17191f", 3: "#ffffff" };
