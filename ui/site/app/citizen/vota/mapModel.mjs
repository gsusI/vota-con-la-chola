// Pure helpers for the party map (/citizen/vota/mapa/): Mapa, Brújula and Adivina. No DOM, no React.
// Positions come from vote_atlas_v1.json (`party_axes[party][axis].score`, −1..1) and are shown as −100..+100.

export const MIN_AXIS_VOTES = 10;
export const VIEWS = ["mapa", "brujula", "adivina"];
export const DEFAULT_PICKS = ["psoe", "pp"];
export const MAX_PICKS = 4;
export const MAX_PICKS_MOBILE = 3;
export const DEFAULT_X = "fiscalidad";
export const DEFAULT_Y = "territorial_autogobierno";
export const ROUNDS = 10;
export const BEST_KEY = "vclc.mapa.best";
export const SURPRISE_LIMIT = 35;
export const DIANA = 10;

export const PARTY_ABBR = {
  psoe: "PSOE",
  pp: "PP",
  vox: "VOX",
  sumar: "SUM",
  podemos: "POD",
  erc: "ERC",
  junts: "JxC",
  bildu: "BIL",
  pnv: "PNV",
  bng: "BNG",
  cc: "CC",
  upn: "UPN",
};

// How the party reads inside a sentence («¿Dónde está el PSOE…?»).
const PARTY_IN_SENTENCE = { psoe: "el PSOE", pp: "el PP", pnv: "el PNV", bng: "el BNG" };

export const COMPASS_PRESETS = [
  { label: "Impuestos × Autogobierno", x: "fiscalidad", y: "territorial_autogobierno" },
  { label: "Mano dura × Inmigración", x: "seguridad_penal", y: "inmigracion" },
  { label: "Vivienda × Prestaciones sociales", x: "vivienda_intervencion", y: "proteccion_social" },
  { label: "Gasto militar × Israel y Palestina", x: "defensa_otan", y: "israel_palestina" },
];

const ANSWER_VALUES = { agree: 1, neutral: 0, disagree: -1 };
// Axis labels that start with a proper noun keep their capital inside a sentence.
const PROPER_START = new Set(["Israel", "Sáhara", "Venezuela", "OTAN", "UE"]);

export function partyInSentence(party) {
  return PARTY_IN_SENTENCE[party?.party_id] || party?.label || "";
}

export function axisInSentence(label) {
  const s = String(label || "");
  const first = s.split(/\s/u)[0];
  if (!s || PROPER_START.has(first) || (first.length > 1 && first === first.toUpperCase())) return s;
  return s.charAt(0).toLowerCase() + s.slice(1);
}

/** «+65», «−77», «0» (real minus sign). */
export function formatSigned(v) {
  if (!Number.isFinite(v)) return "sin datos";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)}`;
}

/** A party's position on an axis in −100..+100, or null when there is no data. */
export function partyPoint(atlas, partyId, axisId) {
  const score = atlas?.party_axes?.[partyId]?.[axisId]?.score;
  return Number.isFinite(score) ? Math.round(score * 100) : null;
}

/** Axes for the map, grouped in topic order (codebook order inside a topic); only ≥10 votes unless `all`. */
export function mapAxes(atlas, { all = false } = {}) {
  const topics = Array.isArray(atlas?.topics) ? atlas.topics : [];
  const order = Object.fromEntries(topics.map((t, i) => [t.topic_id, i]));
  const axes = (Array.isArray(atlas?.axes) ? atlas.axes : []).map((a, i) => ({ a, i }));
  return axes
    .filter(({ a }) => all || (a.votes || 0) >= MIN_AXIS_VOTES)
    .sort((p, q) => (order[p.a.topic_id] ?? 999) - (order[q.a.topic_id] ?? 999) || p.i - q.i)
    .map(({ a }) => a);
}

/**
 * Greedy lanes (ported from the mockup): sort by x and put each item in the first lane whose last item is far
 * enough to the left. Separation is `gap` or, when items carry a width `w` (same units as x), half their widths.
 * Mutates items (sets `lane`) and returns the number of lanes (≥1).
 */
export function lanes(items, gap) {
  items.sort((a, b) => a.x - b.x);
  const ends = [];
  for (const t of items) {
    let l = 0;
    const need = (prev) => Math.max(gap, ((prev.w || 0) + (t.w || 0)) / 2);
    while (ends[l] !== undefined && t.x - ends[l].x < need(ends[l])) l++;
    ends[l] = t;
    t.lane = l;
  }
  return Math.max(ends.length, 1);
}

/** Read the answers object from the test's stored state (localStorage JSON). Only valid answer values. */
export function storedAnswers(raw) {
  const out = {};
  for (const [id, v] of Object.entries(raw?.answers || {})) if (ANSWER_VALUES[v] !== undefined) out[id] = v;
  return out;
}

/**
 * The user's position per axis (−1..1): answer (agree 1, neutral 0, disagree −1) × (pole '+' ? 1 : −1), averaged
 * over the key statements of that axis. Answers to anything else (pool votes, unknown ids) are ignored.
 */
export function userAxisValues(snapshot, answers) {
  const sums = {};
  for (const st of Array.isArray(snapshot?.statements) ? snapshot.statements : []) {
    const v = ANSWER_VALUES[answers?.[st.statement_id]];
    if (v === undefined || !st.axis_id || (st.pole !== "+" && st.pole !== "-")) continue;
    const s = (sums[st.axis_id] ||= { total: 0, n: 0 });
    s.total += v * (st.pole === "+" ? 1 : -1);
    s.n += 1;
  }
  return Object.fromEntries(Object.entries(sums).map(([k, s]) => [k, s.total / s.n]));
}

/** Closest party to a user value (−1..1) on one axis, by absolute distance; ties keep the atlas party order. */
export function nearestParty(atlas, axisId, userValue) {
  let best = null;
  for (const p of atlas?.parties || []) {
    const pt = partyPoint(atlas, p.party_id, axisId);
    if (pt === null || !Number.isFinite(userValue)) continue;
    const d = Math.abs(pt - userValue * 100);
    if (!best || d < best.d) best = { party: p, d };
  }
  return best;
}

/** Parties by distance to the user on a plane of two axes (−100..100 units). */
export function rankByDistance(atlas, xId, yId, ux, uy) {
  const out = [];
  for (const p of atlas?.parties || []) {
    const px = partyPoint(atlas, p.party_id, xId);
    const py = partyPoint(atlas, p.party_id, yId);
    if (px === null || py === null) continue;
    out.push({ party: p, d: Math.round(Math.hypot(px - ux * 100, py - uy * 100)) });
  }
  return out.sort((a, b) => a.d - b.d);
}

/** Toggle a party in the picks: adding past `max` drops the oldest pick. */
export function togglePick(picks, id, max = MAX_PICKS) {
  if (picks.includes(id)) return picks.filter((p) => p !== id);
  const next = [...picks, id];
  return next.length > max ? next.slice(next.length - max) : next;
}

/** Hash → view state. Unknown values fall back to defaults; `p=` (empty) means no picks. */
export function parseMapHash(hash, { partyIds = [], axisIds = [] } = {}) {
  const params = new URLSearchParams(String(hash || "").replace(/^#/u, ""));
  const view = VIEWS.includes(params.get("vista")) ? params.get("vista") : "mapa";
  const out = { view };
  if (params.has("p")) {
    const ids = params.get("p").split(",").filter((id) => partyIds.includes(id));
    out.picks = [...new Set(ids)].slice(-MAX_PICKS);
  }
  if (axisIds.includes(params.get("x"))) out.x = params.get("x");
  if (axisIds.includes(params.get("y"))) out.y = params.get("y");
  const game = Number(params.get("partida"));
  if (Number.isInteger(game) && game > 0 && game < 2 ** 31) out.game = game;
  return out;
}

/** View state → hash, only with the params of that view (commas kept readable). */
export function mapHash({ view = "mapa", picks, x, y, game } = {}) {
  const parts = [`vista=${view}`];
  if (view === "mapa" && Array.isArray(picks)) parts.push(`p=${picks.join(",")}`);
  if (view === "brujula" && x) parts.push(`x=${encodeURIComponent(x)}`);
  if (view === "brujula" && y) parts.push(`y=${encodeURIComponent(y)}`);
  if (view === "adivina" && game) parts.push(`partida=${game}`);
  return `#${parts.join("&")}`;
}

// ---------------------------------------------------------------------------
// Brújula

/** Pixel position of a −100..100 value on a square plane of side `size` with padding `pad` (y grows upwards). */
export function planeX(v, size, pad) {
  return pad + ((v + 100) / 200) * (size - 2 * pad);
}

export function planeY(v, size, pad) {
  return pad + ((100 - v) / 200) * (size - 2 * pad);
}

/**
 * Label placement (ported from the mockup): labels go right of the dot, or left near the right edge; a label that
 * would overlap one already placed is pushed down a line and gets a short leader. Points need x, y in px.
 */
export function placeLabels(points, size, { labelW = 120, lineH = 16 } = {}) {
  const pts = points.map((p) => ({ ...p })).sort((a, b) => a.y - b.y || a.x - b.x);
  const placed = [];
  for (const p of pts) {
    const right = p.x < size - labelW - 30;
    p.align = right ? "left" : "right";
    p.tx = right ? p.x + 14 : p.x - 14 - labelW;
    // Whole pixels: with fractional positions `q.ty + lineH` can round back to `ty` (gap 14.999… < 15) and
    // the loop never ends. Each push must also move the label down by at least a pixel.
    let ty = Math.round(p.y);
    let clash = true;
    for (let guard = 0; clash && guard < points.length * 4; guard++) {
      clash = false;
      for (const q of placed) {
        if (Math.abs(q.ty - ty) < lineH && Math.abs(q.tx - p.tx) < labelW - 10) {
          ty = Math.max(ty + 1, q.ty + lineH);
          clash = true;
        }
      }
    }
    p.ty = ty;
    p.lead = ty !== Math.round(p.y);
    placed.push(p);
  }
  return pts;
}

// ---------------------------------------------------------------------------
// Adivina

/** Small deterministic PRNG (mulberry32) → floats in [0, 1). */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle(list, rand) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export function newSeed() {
  return 1 + Math.floor(Math.random() * (2 ** 31 - 2));
}

/**
 * Rounds of one game, deterministic per seed: party × axis (axes with ≥10 votes, party with data), about 4
 * «surprising» ones (|position| < 35) mixed with clear ones, never the same party × axis twice, at most two per
 * party and per axis, and no axis twice in a row.
 */
export function generateRounds(atlas, seed, n = ROUNDS) {
  const rand = rng(seed);
  const axes = mapAxes(atlas);
  const cands = [];
  for (const p of atlas?.parties || []) {
    for (const a of axes) {
      const real = partyPoint(atlas, p.party_id, a.axis_id);
      if (real === null) continue;
      cands.push({ party_id: p.party_id, axis_id: a.axis_id, real, votes: atlas.party_axes[p.party_id][a.axis_id].votes || a.votes });
    }
  }
  const surprising = shuffle(cands.filter((c) => Math.abs(c.real) < SURPRISE_LIMIT), rand);
  const clear = shuffle(cands.filter((c) => Math.abs(c.real) >= SURPRISE_LIMIT), rand);
  const wantSurprising = Math.min(Math.round(n * 0.4), surprising.length);
  const picked = [];
  const used = new Set();
  const perParty = {};
  const perAxis = {};
  const take = (pool, count, strict) => {
    for (const c of pool) {
      if (count <= 0) break;
      const key = `${c.party_id}|${c.axis_id}`;
      if (used.has(key)) continue;
      if (strict && ((perParty[c.party_id] || 0) >= 2 || (perAxis[c.axis_id] || 0) >= 2)) continue;
      used.add(key);
      perParty[c.party_id] = (perParty[c.party_id] || 0) + 1;
      perAxis[c.axis_id] = (perAxis[c.axis_id] || 0) + 1;
      picked.push(c);
      count--;
    }
    return count;
  };
  let left = take(surprising, wantSurprising, true);
  left = take(clear, n - wantSurprising + left, true);
  if (picked.length < n) take(shuffle(cands, rand), n - picked.length, false);
  // Mix them, then avoid the same axis twice in a row when a swap can fix it.
  const rounds = shuffle(picked, rand);
  for (let i = 1; i < rounds.length; i++) {
    if (rounds[i].axis_id !== rounds[i - 1].axis_id) continue;
    const j = rounds.findIndex((r, k) => k > i && r.axis_id !== rounds[i - 1].axis_id && (k + 1 >= rounds.length || rounds[k + 1].axis_id !== rounds[i].axis_id));
    if (j > 0) [rounds[i], rounds[j]] = [rounds[j], rounds[i]];
  }
  return rounds.slice(0, n);
}

export function roundPoints(guess, real) {
  return Math.max(0, 100 - Math.abs(guess - real));
}

export function verdict(off) {
  if (off <= DIANA) return "¡Diana!";
  if (off <= 25) return "Muy cerca";
  if (off <= 50) return "Te has quedado lejos";
  return "Ni de lejos";
}

/** Consecutive dianas at the end of the history of points. */
export function streakOf(history) {
  let s = 0;
  for (let k = history.length - 1; k >= 0 && history[k] >= 100 - DIANA; k--) s++;
  return s;
}

/** One factual line about where a party sits on an axis (score in −100..100). */
export function factLine(real, axis) {
  const pole = real >= 0 ? axis?.pos_short : axis?.neg_short;
  if (Math.abs(real) < 20) return "Casi en el centro: votó en los dos sentidos, dividido o absteniéndose.";
  if (Math.abs(real) >= 70) return `Muy constante hacia «${pole}».`;
  return `Inclinado hacia «${pole}», con excepciones.`;
}

export function levelLine(total) {
  if (total >= 850) return "Nivel: te sabes el Congreso de memoria.";
  if (total >= 650) return "Nivel: buen ojo. Algunos partidos te han sorprendido.";
  return "Nivel: los votos no siempre son lo que parece. Mira el mapa y repite.";
}
