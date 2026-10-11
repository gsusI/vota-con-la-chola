// Pure scoring and state helpers for the general-election voting aid (no DOM, no React).

export const ANSWER_VALUES = { agree: 1, neutral: 0, disagree: -1 };
export const POSITION_VALUES = { agree: 1, disagree: -1, abstain: 0, mixed: 0 };
export const POSITION_LABELS = {
  agree: "A favor",
  disagree: "En contra",
  abstain: "Abstención",
  mixed: "Votos distintos",
  no_data: "Sin datos",
};
export const ANSWER_LABELS = { agree: "De acuerdo", neutral: "Neutral", disagree: "En desacuerdo" };
export const STORAGE_KEY = "vclc.votingAid.generales.v1";

const ANSWER_CODES = { agree: "a", neutral: "n", disagree: "d" };
const CODE_ANSWERS = { a: "agree", n: "neutral", d: "disagree" };
const SHARE_PREFIX = "v1.";

// Similarity in [0, 1] between a user answer and a party position (both on -1..1).
function similarity(answer, position) {
  return 1 - Math.abs(ANSWER_VALUES[answer] - POSITION_VALUES[position]) / 2;
}

/**
 * Score every party against the user's answers.
 * Statements the user skipped, and cells without data, are excluded (never imputed).
 * `important` statements weigh double.
 */
export function scoreParties(snapshot, answers = {}, important = {}) {
  const statements = Array.isArray(snapshot?.statements) ? snapshot.statements : [];
  const answered = statements.filter((st) => ANSWER_VALUES[answers[st.statement_id]] !== undefined);
  const parties = Array.isArray(snapshot?.parties) ? snapshot.parties : [];
  const rows = parties.map((party) => {
    let weighted = 0;
    let weightTotal = 0;
    const details = [];
    for (const st of answered) {
      const answer = answers[st.statement_id];
      const position = st.cells?.[party.party_id]?.position || "no_data";
      const weight = important[st.statement_id] ? 2 : 1;
      if (POSITION_VALUES[position] === undefined) {
        details.push({ statementId: st.statement_id, answer, position, weight, similarity: null });
        continue;
      }
      const sim = similarity(answer, position);
      weighted += sim * weight;
      weightTotal += weight;
      details.push({ statementId: st.statement_id, answer, position, weight, similarity: sim });
    }
    const compared = details.filter((d) => d.similarity !== null).length;
    return {
      partyId: party.party_id,
      label: party.label,
      match: weightTotal > 0 ? weighted / weightTotal : null,
      compared,
      answered: answered.length,
      details,
    };
  });
  rows.sort((a, b) => {
    if (a.match === null && b.match === null) return a.label.localeCompare(b.label, "es");
    if (a.match === null) return 1;
    if (b.match === null) return -1;
    return b.match - a.match || b.compared - a.compared || a.label.localeCompare(b.label, "es");
  });
  return rows;
}

/** Encode answers as a compact share code aligned to statement order ("-" = skipped, uppercase = important). */
export function encodeShareCode(statements, answers = {}, important = {}) {
  const chars = statements.map((st) => {
    const code = ANSWER_CODES[answers[st.statement_id]];
    if (!code) return "-";
    return important[st.statement_id] ? code.toUpperCase() : code;
  });
  return SHARE_PREFIX + chars.join("");
}

/** Decode a share code; returns null when it does not match this statement set. */
export function decodeShareCode(statements, code) {
  const raw = String(code || "").trim();
  if (!raw.startsWith(SHARE_PREFIX)) return null;
  const chars = raw.slice(SHARE_PREFIX.length);
  if (chars.length !== statements.length || !/^[andAND-]*$/u.test(chars)) return null;
  const answers = {};
  const important = {};
  statements.forEach((st, i) => {
    const ch = chars[i];
    if (ch === "-") return;
    answers[st.statement_id] = CODE_ANSWERS[ch.toLowerCase()];
    if (ch !== ch.toLowerCase()) important[st.statement_id] = true;
  });
  return { answers, important };
}

/** Read the share code from a URL fragment such as "#r=v1.ad-n". */
export function shareCodeFromHash(hash) {
  const params = new URLSearchParams(String(hash || "").replace(/^#/u, ""));
  return params.get("r");
}

/** Keep only answers/flags for statements that still exist (the seed can change between visits). */
export function sanitizeState(statements, state) {
  const ids = new Set(statements.map((st) => st.statement_id));
  const answers = {};
  const important = {};
  for (const [id, value] of Object.entries(state?.answers || {})) {
    if (ids.has(id) && ANSWER_VALUES[value] !== undefined) answers[id] = value;
  }
  for (const [id, value] of Object.entries(state?.important || {})) {
    if (ids.has(id) && value === true) important[id] = true;
  }
  return { answers, important };
}

export function formatMatch(value) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

// Below this many answers a ranking is too noisy to read as a result.
export const MIN_ANSWERS_FOR_RANKING = 8;

const THEME_LABELS = {
  vivienda: "Vivienda",
  empleo: "Empleo y pensiones",
  sanidad: "Sanidad",
  educacion: "Educación",
  coste_vida: "Coste de vida",
  energia: "Energía y clima",
  transporte: "Transporte",
  seguridad_justicia: "Seguridad y justicia",
  inmigracion: "Inmigración",
  corrupcion: "Corrupción y transparencia",
  campo_rural: "Campo y mundo rural",
  igualdad: "Igualdad",
};
const PREFIX_THEMES = { cultura: "Cultura", exterior: "Política exterior", territorio: "Modelo territorial" };

/** Human theme label for a statement: concern label, else its id prefix, else "Otros". */
export function themeLabel(statement) {
  const prefix = String(statement?.statement_id || "").split("-")[0];
  return PREFIX_THEMES[prefix] || THEME_LABELS[statement?.concern_id] || "Otros";
}

/** How a user's answer relates to a party position: match, partial, clash or none (no data). */
export function agreementKind(answer, position) {
  if (ANSWER_VALUES[answer] === undefined || POSITION_VALUES[position] === undefined) return "none";
  const sim = similarity(answer, position);
  if (sim === 1) return "match";
  if (sim === 0) return "clash";
  return "partial";
}

/** Index of the first unanswered statement at or after `from` (wrapping); -1 when all are answered. */
export function nextUnansweredIndex(statements, answers = {}, from = 0) {
  const n = statements.length;
  for (let k = 0; k < n; k += 1) {
    const i = (from + k) % n;
    if (answers[statements[i].statement_id] === undefined) return i;
  }
  return -1;
}

// ---------------------------------------------------------------------------
// Endless mode: curated statements + pool of real votes as one question list.

export const POOL_ANSWER_LABELS = { agree: "Sí", neutral: "Me da igual", disagree: "No" };

/**
 * Merge curated statements and pool votes into one scorable list.
 * Every question has: statement_id, source ("curated" | "pool"), text, theme, cells {party: {position}}.
 */
export function buildQuestions(snapshot, pool) {
  const curated = (Array.isArray(snapshot?.statements) ? snapshot.statements : []).map((st) => ({
    ...st,
    source: "curated",
    theme: themeLabel(st),
  }));
  const items = (Array.isArray(pool?.items) ? pool.items : []).map((it) => ({
    statement_id: it.id,
    source: "pool",
    text: it.title,
    question: it.question,
    theme: it.theme,
    kind: it.kind,
    kind_label: it.kind_label,
    proposer: it.proposer,
    vote_date: it.vote_date,
    approved: it.approved,
    totals: it.totals,
    source_url: it.source_url,
    text_url: it.text_url,
    side: it.side,
    tier: it.tier,
    counts: it.counts,
    cells: Object.fromEntries(Object.entries(it.positions || {}).map(([pid, position]) => [pid, { position }])),
  }));
  return [...curated, ...items];
}

/** Small deterministic PRNG so each visitor gets a stable but personal order. */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffled(list, rand) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * Play order: curated statements first, then pool votes interleaving which bloc "Sí" favours
 * (psoe / pp / cross) so answering "Sí" to everything does not drift towards one side.
 * Divisive votes ("split") come before votes where a single party stood apart ("lone").
 */
export function playOrder(questions, seed = 1) {
  const rand = mulberry32(seed);
  const curated = questions.filter((q) => q.source === "curated").map((q) => q.statement_id);
  const buckets = { psoe: [], pp: [], cross: [] };
  for (const tier of ["split", "lone"]) {
    for (const side of Object.keys(buckets)) {
      const group = questions.filter((q) => q.source === "pool" && q.tier === tier && (q.side || "cross") === side);
      buckets[side].push(...shuffled(group, rand).map((q) => q.statement_id));
    }
  }
  const pool = [];
  const sides = ["psoe", "pp", "cross"];
  while (sides.some((s) => buckets[s].length)) {
    for (const s of sides) if (buckets[s].length) pool.push(buckets[s].shift());
  }
  return [...curated, ...pool];
}

/** Next question to ask: first in play order that is neither answered nor skipped; then skipped ones again. */
export function nextQuestionId(order, answers = {}, skipped = {}) {
  const fresh = order.find((id) => answers[id] === undefined && !skipped[id]);
  if (fresh) return fresh;
  return order.find((id) => answers[id] === undefined) || null;
}

/** How each party voted relative to the user's answer on one question. */
export function partyReactions(question, answer, parties) {
  const out = { with: [], against: [], partial: [], none: [] };
  for (const p of parties) {
    const position = question?.cells?.[p.party_id]?.position || "no_data";
    const kind = agreementKind(answer, position);
    const bucket = kind === "match" ? "with" : kind === "clash" ? "against" : kind === "partial" ? "partial" : "none";
    out[bucket].push({ ...p, position });
  }
  return out;
}

/** Split a party's score details into match / partial / clash / none lists. */
export function groupDetails(details = []) {
  const out = { match: [], partial: [], clash: [], none: [] };
  for (const d of details) out[agreementKind(d.answer, d.position)].push(d);
  return out;
}

export const MILESTONES = [
  { at: 5, title: "Público en la tribuna", emoji: "👀" },
  { at: 15, title: "Escaño novato", emoji: "🪑" },
  { at: 33, title: "Portavocía adjunta", emoji: "🎤" },
  { at: 60, title: "Portavocía", emoji: "📣" },
  { at: 100, title: "Presidencia de comisión", emoji: "🏛️" },
  { at: 200, title: "Presidencia de la Cámara", emoji: "🔔" },
  { at: 300, title: "Memoria viva del hemiciclo", emoji: "📚" },
];

/** Current rank and the next one to unlock for a number of answers. */
export function milestoneFor(count) {
  let current = null;
  for (const m of MILESTONES) if (count >= m.at) current = m;
  const next = MILESTONES.find((m) => count < m.at) || null;
  return { current, next };
}

// Share codes v2: sparse "<index base36><answer>" entries plus a checksum of the question ids,
// so links survive hundreds of answers and are rejected if the question set changes.
function idsChecksum(ids) {
  let h = 0x811c9dc5;
  for (const ch of ids.join("|")) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(36);
}

export function encodeShareCodeV2(questions, answers = {}, important = {}) {
  const ids = questions.map((q) => q.statement_id);
  const entries = [];
  ids.forEach((id, i) => {
    const code = ANSWER_CODES[answers[id]];
    if (!code) return;
    entries.push(i.toString(36) + (important[id] ? code.toUpperCase() : code));
  });
  return `v2.${idsChecksum(ids)}.${entries.join("-")}`;
}

export function decodeShareCodeV2(questions, code) {
  const raw = String(code || "").trim();
  const m = /^v2\.([0-9a-z]+)\.([0-9a-zA-Z-]*)$/u.exec(raw);
  if (!m) return null;
  const ids = questions.map((q) => q.statement_id);
  if (m[1] !== idsChecksum(ids)) return null;
  const answers = {};
  const important = {};
  for (const entry of m[2] ? m[2].split("-") : []) {
    const ch = entry.slice(-1);
    const idx = parseInt(entry.slice(0, -1), 36);
    const answer = CODE_ANSWERS[ch.toLowerCase()];
    if (!answer || !Number.isInteger(idx) || idx < 0 || idx >= ids.length) return null;
    answers[ids[idx]] = answer;
    if (ch !== ch.toLowerCase()) important[ids[idx]] = true;
  }
  return { answers, important };
}

/** Decode any supported share code: v2 over all questions, or legacy v1 over curated statements. */
export function decodeAnyShareCode(questions, code) {
  return (
    decodeShareCodeV2(questions, code) ||
    decodeShareCode(
      questions.filter((q) => q.source === "curated"),
      code,
    )
  );
}
