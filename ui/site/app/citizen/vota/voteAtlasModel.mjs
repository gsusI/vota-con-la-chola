// Pure helpers for the vote atlas pages (/citizen/vota/temas/ and /citizen/vota/diputados/). No DOM, no React.

export const ATLAS_PATH = "/citizen/data/vote_atlas_v1.json";
export const PEOPLE_PATH = "/citizen/data/vote_atlas_people_v1.json";
export const CHOICE_LABELS = { S: "Sí", N: "No", A: "Abstención", "-": "No vota", "=": "Empate", "?": "Sin datos", ".": "No era diputado/a" };
export const CONFIDENCE_LABELS = { alta: "confianza alta", media: "confianza media", baja: "confianza baja (no cuenta)" };
const OFFICIAL_PREFIX = "https://www.congreso.es/webpublica/opendata/votaciones/";

export function officialVoteUrl(path) {
  return path ? `${OFFICIAL_PREFIX}${path}` : null;
}

/** Index axes by id and topics by id; axes keep codebook order. */
export function indexAtlas(atlas) {
  const axes = Array.isArray(atlas?.axes) ? atlas.axes : [];
  const topics = Array.isArray(atlas?.topics) ? atlas.topics : [];
  return {
    axes,
    topics,
    axisById: Object.fromEntries(axes.map((a) => [a.axis_id, a])),
    topicById: Object.fromEntries(topics.map((t) => [t.topic_id, t])),
    parties: Array.isArray(atlas?.parties) ? atlas.parties : [],
  };
}

/** Verbal band for a direction score in [-1, 1]. */
export function directionBand(score) {
  if (!Number.isFinite(score)) return "sin datos";
  const a = Math.abs(score);
  if (a < 0.2) return "dividido o neutral";
  if (a < 0.5) return "tiende";
  if (a < 0.8) return "claramente";
  return "casi siempre";
}

/** "Casi siempre hacia «Subir impuestos»" style sentence for a party/person score on an axis. */
export function directionText(axis, score) {
  if (!Number.isFinite(score) || !axis) return "Sin votaciones clasificadas";
  if (Math.abs(score) < 0.2) return "Dividido o neutral";
  const pole = score > 0 ? axis.pos_short : axis.neg_short;
  const band = directionBand(score);
  const lead = band.charAt(0).toUpperCase() + band.slice(1);
  return `${lead} hacia «${pole}»`;
}

/** Parties with a score on the axis, sorted from the negative to the positive pole. */
export function axisParties(atlas, axisId) {
  const rows = [];
  for (const p of atlas?.parties || []) {
    const cell = atlas?.party_axes?.[p.party_id]?.[axisId];
    if (cell && Number.isFinite(cell.score)) rows.push({ ...p, ...cell });
  }
  return rows.sort((a, b) => a.score - b.score || a.label.localeCompare(b.label, "es"));
}

/** Spread between the most extreme parties: a crude "how contested is this axis" measure. */
export function axisSpread(atlas, axisId) {
  const rows = axisParties(atlas, axisId);
  return rows.length < 2 ? 0 : rows[rows.length - 1].score - rows[0].score;
}

// Parliamentary groups of earlier legislatures, for deputies who are not (or no longer) in a ballot party.
export const GROUP_LABELS = {
  GS: "Grupo Socialista",
  GP: "Grupo Popular",
  GVOX: "Grupo VOX",
  GR: "Grupo Republicano (ERC)",
  "GEH Bildu": "Grupo EH Bildu",
  "GV (EAJ-PNV)": "Grupo Vasco (PNV)",
  "GCUP-EC-GC": "Grupo Unidas Podemos",
  GCs: "Grupo Ciudadanos",
  GPlu: "Grupo Plural",
  GMx: "Grupo Mixto",
  GSUMAR: "Grupo Sumar",
  GJxCAT: "Grupo Junts",
};
export const LEG_LABELS = { 14: "XIV", 15: "XV" };

export function groupLabel(code) {
  return GROUP_LABELS[code] || code || "Sin grupo";
}

// Short names, so a XIV-only deputy reads «PP (XIV)» next to the XV ones listed by party («PP»).
const GROUP_SHORT = {
  GS: "PSOE",
  GP: "PP",
  GVOX: "VOX",
  GR: "ERC",
  "GEH Bildu": "EH Bildu",
  "GV (EAJ-PNV)": "PNV",
  "GCUP-EC-GC": "Unidas Podemos",
  GCs: "Ciudadanos",
  GSUMAR: "Sumar",
  GJxCAT: "Junts",
};

export function groupShortLabel(code) {
  return GROUP_SHORT[code] || groupLabel(code);
}

/**
 * Votes placed on an axis (any confidence), newest first, with the sign of a Sí vote.
 * Earlier legislatures (`leg`) count only for deputies, so the party map leaves them out unless asked.
 */
export function votesForAxis(atlas, axisId, { includeEarlier = false } = {}) {
  const out = [];
  for (const v of atlas?.votes || []) {
    if (v.leg && !includeEarlier) continue;
    const hit = (v.axes || []).find((a) => a[0] === axisId);
    if (hit) out.push({ ...v, sign: hit[1], confidence: hit[2], primary: v.axes[0][0] === axisId });
  }
  return out.sort((a, b) => String(b.date).localeCompare(String(a.date)));
}

/** Official title of an atlas vote (titles are stored once in `atlas.titles`). */
export function voteTitle(atlas, vote) {
  if (vote?.title) return vote.title;
  return Number.isInteger(vote?.t) ? atlas?.titles?.[vote.t] || "" : "";
}

/** Party majority choices of a vote as [{party, code}] in party order. */
export function partyChoices(atlas, vote) {
  const codes = String(vote?.parties || "");
  return (atlas?.parties || []).map((p, i) => ({ ...p, code: codes[i] || "?" }));
}

/** Where a party's choice on a vote pushes the axis: "pos", "neg" or "none". */
export function pushOf(code, sign) {
  if (code !== "S" && code !== "N") return "none";
  const yesPos = sign === "+";
  return (code === "S") === yesPos ? "pos" : "neg";
}

// ---------------------------------------------------------------------------
// People

/** Choice code of a person on vote index i ("." when not seated then). */
export function personChoice(person, i) {
  const k = i - (person?.first || 0);
  if (k < 0) return ".";
  return String(person?.votes || "")[k] || ".";
}

/** Case/accent-insensitive search key. */
export function foldText(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/gu, "")
    .toLowerCase();
}

export function filterPeople(people, { query = "", partyId = "" } = {}) {
  const q = foldText(query).trim();
  return (people || []).filter((p) => (!partyId || p.party_id === partyId) && (!q || foldText(p.name).includes(q)));
}

/** Axis comparison rows for a person: own score vs party score, biggest gaps first. */
export function personAxisRows(atlas, person) {
  const { axisById } = indexAtlas(atlas);
  const rows = [];
  for (const [axisId, [score, n]] of Object.entries(person?.axes || {})) {
    const axis = axisById[axisId];
    if (!axis) continue;
    const party = person.party_id ? atlas?.party_axes?.[person.party_id]?.[axisId] : null;
    rows.push({ axis, score, n, partyScore: party ? party.score : null, gap: party ? Math.abs(score - party.score) : 0 });
  }
  return rows.sort((a, b) => b.gap - a.gap || b.n - a.n);
}

/** Classified-vote lookup by short id, for showing what a person's vote pushed. */
export function classifiedById(atlas) {
  return Object.fromEntries((atlas?.votes || []).map((v) => [v.id, v]));
}

export function percent(value) {
  return Number.isFinite(value) ? `${Math.round(value * 100)} %` : "—";
}

export function formatDate(value) {
  if (!value) return "";
  const [y, m, d] = String(value).split("-");
  return d && m && y ? `${Number(d)}/${Number(m)}/${y}` : String(value);
}

/** Whole numbers with a thousands dot. es-ES leaves 4-digit ones ungrouped («1023»); the site writes «1.023» everywhere. */
export function formatCount(value) {
  return Number.isFinite(value) ? String(Math.trunc(value)).replace(/\B(?=(\d{3})+(?!\d))/gu, ".") : "—";
}

/** Read "#k=v&k2=v2" into an object (shareable view state; never user preferences). */
export function readHash(hash) {
  const params = new URLSearchParams(String(hash || "").replace(/^#/u, ""));
  return Object.fromEntries(params.entries());
}

export function writeHash(state) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(state || {})) if (v) params.set(k, v);
  const s = params.toString();
  return s ? `#${s}` : "";
}
