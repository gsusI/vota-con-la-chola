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
// Answers are stored per test version: see `storageKey` in votingAidVersions.mjs.

const ANSWER_CODES = { agree: "a", neutral: "n", disagree: "d" };
const CODE_ANSWERS = { a: "agree", n: "neutral", d: "disagree" };
const SHARE_PREFIX = "v1.";

/**
 * Numeric value of a party cell on -1..1: the continuous `score` of a multi-vote statement when present
 * (how consistently the party pushed towards the statement), else the value of its discrete position.
 */
export function cellValue(position, score = null) {
  if (Number.isFinite(score) && position !== "no_data") return Math.max(-1, Math.min(1, score));
  return POSITION_VALUES[position];
}

// Similarity in [0, 1] between a user answer and a party position (both on -1..1).
function similarity(answer, position, score = null) {
  return 1 - Math.abs(ANSWER_VALUES[answer] - cellValue(position, score)) / 2;
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
      const cell = st.cells?.[party.party_id] || {};
      const position = cell.position || "no_data";
      const score = Number.isFinite(cell.score) ? cell.score : null;
      const weight = important[st.statement_id] ? 2 : 1;
      if (cellValue(position, score) === undefined) {
        details.push({ statementId: st.statement_id, answer, position, score, weight, similarity: null });
        continue;
      }
      const sim = similarity(answer, position, score);
      weighted += sim * weight;
      weightTotal += weight;
      details.push({ statementId: st.statement_id, answer, position, score, weight, similarity: sim });
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

/**
 * How a user's answer relates to a party position: match, partial, clash or none (no data).
 * With a continuous score, "match" means the party pushed that way in most votes (similarity ≥ 0.8).
 */
export function agreementKind(answer, position, score = null) {
  if (ANSWER_VALUES[answer] === undefined || cellValue(position, score) === undefined) return "none";
  const sim = similarity(answer, position, score);
  if (sim >= 0.8) return "match";
  if (sim <= 0.2) return "clash";
  return "partial";
}

/** Share (0-100) of a multi-vote statement's push that went towards it: score -1..1 -> 0..100. */
export function scorePercent(score) {
  return Number.isFinite(score) ? Math.round(((score + 1) / 2) * 100) : null;
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
    multi: Boolean(st.axis_id),
    theme: st.theme || themeLabel(st),
  }));
  const items = (Array.isArray(pool?.items) ? pool.items : []).map((it) => ({
    statement_id: it.id,
    vote_event_id: it.vote_event_id,
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
  return [...curated, ...items, ...attachSubQuestions(curated, items)];
}

// A multi-vote statement can be answered "por partes": a few concrete votes from different initiatives.
export const MAX_SUB_QUESTIONS = 6;
const CODE_POSITIONS = { S: "agree", N: "disagree", A: "abstain", "=": "mixed" };

/**
 * Give each multi-vote statement `subIds` (concrete votes, one per initiative) and return the sub-questions
 * that are not already pool items. A vote that is also in the endless pool reuses that pool question, so the
 * same vote is never answered twice. Sub-questions have no tier, so they stay out of the play order.
 */
function attachSubQuestions(curated, items) {
  const poolByVote = new Map(items.map((it) => [it.vote_event_id, it]));
  const created = [];
  for (const st of curated) {
    if (!st.axis_id) continue;
    const seen = new Set();
    st.subIds = [];
    for (const v of st.votes || []) {
      if (st.subIds.length >= MAX_SUB_QUESTIONS) break;
      if (!v.summary_yes || seen.has(v.g || v.id)) continue;
      seen.add(v.g || v.id);
      const pooled = poolByVote.get(v.vote_event_id);
      if (pooled) {
        pooled.parent = pooled.parent || st.statement_id;
        pooled.parentText = pooled.parentText || st.text;
        pooled.parentTheme = pooled.parentTheme || st.theme;
        st.subIds.push(pooled.statement_id);
        continue;
      }
      const codes = String(v.parties || "");
      const cells = {};
      Object.keys(st.cells || {}).forEach((pid, i) => {
        cells[pid] = { position: CODE_POSITIONS[codes[i]] || "no_data" };
      });
      const sub = {
        statement_id: `${st.statement_id}~${v.id}`,
        parent: st.statement_id,
        parentText: st.text,
        vote_event_id: v.vote_event_id,
        source: "pool",
        text: v.summary_yes,
        official_title: v.title,
        question: "¿Habrías votado Sí?",
        theme: st.theme,
        kind: v.kind,
        kind_label: "Votación concreta",
        vote_date: v.vote_date,
        approved: v.approved,
        totals: v.totals,
        source_url: v.source_url,
        text_url: v.text_url,
        cells,
      };
      st.subIds.push(sub.statement_id);
      created.push(sub);
    }
  }
  return created;
}

/** First unanswered (and not skipped) sub-question of the statements the user chose to split, in that order. */
export function pendingSubId(questionsById, split = {}, answers = {}, skipped = {}) {
  for (const parentId of Object.keys(split)) {
    const parent = questionsById[parentId];
    const id = (parent?.subIds || []).find((sid) => answers[sid] === undefined && !skipped[sid]);
    if (id) return id;
  }
  return null;
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

// Topics for navigation: the vote map's 14 topics (which the key questions use), then leftovers.
export const TOPIC_ORDER = [
  "Vivienda",
  "Empleo y protección social",
  "Impuestos y economía",
  "Sanidad",
  "Educación y lenguas",
  "Energía, clima y transporte",
  "Campo y medio rural",
  "Seguridad y justicia",
  "Inmigración",
  "Corrupción y control del Gobierno",
  "Igualdad y derechos civiles",
  "Modelo territorial",
  "Memoria e instituciones",
  "Política exterior y defensa",
  "Cultura",
  "Otros",
];
// Endless-mode votes and the first version's statements carry an older, finer theme list.
const THEME_TOPICS = {
  "Empleo y pensiones": "Empleo y protección social",
  "Servicios sociales": "Empleo y protección social",
  "Coste de vida": "Impuestos y economía",
  Educación: "Educación y lenguas",
  "Energía y clima": "Energía, clima y transporte",
  Transporte: "Energía, clima y transporte",
  "Campo y mundo rural": "Campo y medio rural",
  "Corrupción y transparencia": "Corrupción y control del Gobierno",
  Igualdad: "Igualdad y derechos civiles",
  Instituciones: "Memoria e instituciones",
  "Política exterior": "Política exterior y defensa",
  Defensa: "Política exterior y defensa",
};

/** Navigation topic of a question (one list for key questions and endless-mode votes). */
export function questionTopic(question) {
  // A vote that also backs a key question is listed with it, so «por partes» stays inside one topic.
  const theme = question?.parentTheme || question?.theme || "Otros";
  return THEME_TOPICS[theme] || theme;
}

/**
 * Questions grouped by topic for the topic/question menus, in play order: key questions first, then the
 * endless-mode votes. A statement the user split is followed by its concrete votes (they are not in the order).
 * Returns [{ topic, ids }] in TOPIC_ORDER, unknown topics before «Otros».
 */
export function topicGroups(order, questionsById, split = {}) {
  const byTopic = new Map();
  const listed = new Set(order);
  const add = (id) => {
    const topic = questionTopic(questionsById[id]);
    if (!byTopic.has(topic)) byTopic.set(topic, []);
    byTopic.get(topic).push(id);
  };
  for (const id of order) {
    if (!questionsById[id]) continue;
    add(id);
    if (split[id]) for (const sid of questionsById[id].subIds || []) if (!listed.has(sid) && questionsById[sid]) add(sid);
  }
  const rank = (topic) => {
    const i = TOPIC_ORDER.indexOf(topic);
    return i === -1 ? TOPIC_ORDER.length - 1.5 : i;
  };
  return [...byTopic.entries()].map(([topic, ids]) => ({ topic, ids })).sort((a, b) => rank(a.topic) - rank(b.topic));
}

/**
 * Next question inside one topic: a pending concrete vote of a split statement first, then the first one in the
 * topic's order that is neither answered nor skipped (split statements excluded), then skipped ones again.
 * Null when every question of the topic is answered.
 */
export function nextInTopic(ids, questionsById, answers = {}, skipped = {}, split = {}) {
  const inTopic = new Set(ids);
  const splitHere = Object.fromEntries(Object.keys(split).filter((id) => inTopic.has(id)).map((id) => [id, true]));
  const sub = pendingSubId(questionsById, splitHere, answers, skipped);
  if (sub) return sub;
  return nextQuestionId(
    ids.filter((id) => !split[id]),
    answers,
    skipped,
  );
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
    const cell = question?.cells?.[p.party_id] || {};
    const position = cell.position || "no_data";
    const score = Number.isFinite(cell.score) ? cell.score : null;
    const kind = agreementKind(answer, position, score);
    const bucket = kind === "match" ? "with" : kind === "clash" ? "against" : kind === "partial" ? "partial" : "none";
    out[bucket].push({ ...p, position, score, mix: voteMix(question, p.party_id) });
  }
  return out;
}

/** A party's split behind a question as fractions { yes, abstain, no }: deputies for one vote, votes for an axis
    («yes» = voted the way that supports the statement; split party votes count as abstain). Null without data. */
export function voteMix(question, partyId) {
  let yes = 0;
  let no = 0;
  let abstain = 0;
  const counts = question?.counts?.[partyId];
  if (Array.isArray(counts)) [yes, no, abstain] = counts.map((n) => Number(n) || 0);
  else if (question?.axis_id) {
    const i = Object.keys(question.cells || {}).indexOf(partyId); // vote codes follow the cells' party order
    for (const v of i < 0 ? [] : question.votes || []) {
      const code = String(v.parties || "")[i];
      if (code === "S" || code === "N") (code === "S") === (v.agree_vote !== "No") ? yes++ : no++;
      else if (code === "A" || code === "=") abstain++;
    }
  } else {
    const position = question?.cells?.[partyId]?.position;
    if (position === "agree") yes = 1;
    else if (position === "disagree") no = 1;
    else if (position === "abstain" || position === "mixed") abstain = 1;
  }
  const total = yes + no + abstain;
  return total ? { yes: yes / total, abstain: abstain / total, no: no / total } : null;
}

/** Split a party's score details into match / partial / clash / none lists. */
export function groupDetails(details = []) {
  const out = { match: [], partial: [], clash: [], none: [] };
  for (const d of details) out[agreementKind(d.answer, d.position, d.score)].push(d);
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

/** Spoiler-free, shareable podium text (no answers, just the top parties and how many questions). */
export function podiumShareText(results, answeredCount, url) {
  const top = results.filter((r) => r.match !== null).slice(0, 3);
  const medals = ["🥇", "🥈", "🥉"];
  const lines = top.map((r, i) => `${medals[i]} ${r.label} ${formatMatch(r.match)}`);
  return [`Mi podio en «¿Con quién coincides?» tras ${answeredCount} votaciones del Congreso:`, ...lines, url].filter(Boolean).join("\n");
}

// ---------------------------------------------------------------------------
// "Ask an AI" links: a self-contained prompt with exactly what was voted, never the user's answers.

const POSITION_WORDS = { agree: "a favor (Sí)", disagree: "en contra (No)", abstain: "abstención", mixed: "votos divididos", no_data: "sin datos" };

// Multi-vote statements can rest on 80+ votes: the AI prompt lists the most recent ones and says how many.
const MAX_PROMPT_VOTES = 6;

// A law states a rule; to weigh it people need its scale and knock-on effects, not only what it says.
export const RAMIFICATIONS_ASK =
  "Explica también sus ramificaciones: a quién afecta y a cuántas personas aproximadamente (con cifras oficiales y su año), qué cambia para cada colectivo y qué efectos de segundo orden podrían producirse, con los argumentos y la evidencia en ambos sentidos. Distingue lo que está medido de lo que son previsiones.";

const EVIDENCE_WORDS = { organismo_publico: "organismo público", estudio: "estudio", debate: "debate en el Congreso" };

function voteLines(question, parties) {
  // One block per roll-call vote behind the question, with each party's majority vote and counts.
  const votes =
    question.source === "pool"
      ? [
          {
            title: question.text,
            date: question.vote_date,
            kind: question.kind_label,
            proposer: question.proposer,
            totals: question.totals,
            approved: question.approved,
            source_url: question.source_url,
            text_url: question.text_url,
            agree_vote: "Sí",
            party: Object.fromEntries(
              parties.map((p) => [p.party_id, { position: question.cells?.[p.party_id]?.position || "no_data", counts: question.counts?.[p.party_id] }]),
            ),
          },
        ]
      : question.axis_id
      ? (question.votes || []).slice(0, MAX_PROMPT_VOTES).map((v) => ({
          title: v.summary_yes ? `${v.summary_yes} (${v.title}${v.subgroup ? `, ${v.subgroup}` : ""})` : v.title,
          date: v.vote_date,
          totals: v.totals,
          approved: v.approved,
          source_url: v.source_url,
          text_url: v.text_url,
          agree_vote: v.agree_vote,
          party: Object.fromEntries(
            parties.map((p, i) => {
              const code = String(v.parties || "")[i];
              const raw = code === "S" ? "Sí" : code === "N" ? "No" : code === "A" ? "Abstención" : null;
              return [p.party_id, raw ? { position: raw === v.agree_vote ? "agree" : raw === "Abstención" ? "abstain" : "disagree", raw } : { position: "no_data" }];
            }),
          ),
        }))
      : (question.votes || []).map((v) => ({
          title: v.title,
          date: v.vote_date,
          kind: v.note,
          totals: v.totals ? [v.totals.yes, v.totals.no, v.totals.abstain] : null,
          approved: v.totals ? v.totals.yes > v.totals.no : null,
          source_url: v.source_url,
          text_url: v.text_url,
          agree_vote: v.agree_vote,
          party: Object.fromEntries(
            parties.map((p) => {
              const pv = v.party_votes?.[p.party_id];
              return [p.party_id, { position: pv?.choice === "Sí" ? "agree" : pv?.choice === "No" ? "disagree" : pv?.position || "no_data", counts: pv ? [pv.yes, pv.no, pv.abstain] : null, raw: pv?.choice }];
            }),
          ),
        }));
  return votes;
}

// Before answering, the prompt must not say who proposed what (titles sometimes name the groups).
// Mirrors anonymize_title in scripts/export_voting_aid_pool.py: the proposer runs from "Grupo(s)
// Parlamentario(s)" up to the purpose clause, so lists like "SUMAR, Republicano, ... y Mixto, para ..." go whole.
const PURPOSE_END = String.raw`(?:(,)\s+(?=(?:orgánica|relativ|referid|sobre|para|de |del |por |en |a |al |que |contra|reguladora|con |acerca|ante))|\s+(?=(?:sobre|relativa|relativo|para la|para el|por la que|de medidas)\b)|(?=[.;]|$))`;
const PRESENTED_BY_RE = new RegExp(String.raw`,?\s*presentad[ao]s? por (?:el|los|la|las)? ?Grupos? Parlamentari[oa]s?[^.;]*?` + PURPOSE_END, "giu");
const PROPOSER_RE = new RegExp(String.raw`\b(?:del|de los|de las|de la) (Grupos? Parlamentari[oa]s?)\s[^.;]*?` + PURPOSE_END, "giu");
// Safety net for any other mention ("el Grupo Parlamentario X").
const GROUP_MENTION_RE = /\b(?:(?:el|los|del?|de los|de las|de la)\s+)?Grupos? Parlamentari[oa]s?\s+[^,.;]*/gu;

export function maskProposers(text) {
  let out = String(text || "");
  out = out.replace(PRESENTED_BY_RE, (_, comma) => (comma ? ", " : " "));
  out = out.replace(PROPOSER_RE, (_, group, comma) => {
    const label = /^grupos/iu.test(group) ? "de varios grupos parlamentarios" : "de un grupo parlamentario";
    return `${label}${comma || ""} `;
  });
  out = out.replace(GROUP_MENTION_RE, (match) => (/^de/iu.test(match) ? "de un grupo parlamentario" : "un grupo parlamentario"));
  return out.replace(/,\s*,/gu, ",").replace(/\s+([.,;])/gu, "$1").replace(/\s+/gu, " ").trim();
}

/**
 * Build the prompt for an AI assistant.
 * mode "explain": what is being voted, in simple words, without how parties voted (used before answering).
 * mode "why": what was voted and why each party (or `partyId`) voted as it did, with sources.
 */
export function buildAiPrompt(question, parties = [], { mode = "why", partyId = null, compact = false } = {}) {
  const votes = voteLines(question, parties);
  const lines = [];
  if (mode === "explain") {
    lines.push("Explícame en términos sencillos, para alguien sin conocimientos de política, qué se votó en esta votación del Congreso de los Diputados de España y qué cambiaría en la práctica si se aprueba. No me digas qué votar ni cómo votó cada partido.");
  } else if (partyId) {
    const label = parties.find((p) => p.party_id === partyId)?.label || partyId;
    lines.push(`Explícame en términos sencillos qué se votó en esta votación del Congreso de los Diputados de España y por qué ${label} votó como votó, según sus argumentos públicos (debate en el Pleno, notas de prensa, programa).`);
  } else {
    lines.push("Explícame en términos sencillos qué se votó en esta votación del Congreso de los Diputados de España y por qué cada partido votó como votó, según sus argumentos públicos (debate en el Pleno, notas de prensa, programa).");
  }
  lines.push("Distingue claramente los hechos comprobables de tus interpretaciones, cita fuentes oficiales cuando puedas y di si no estás seguro. Sé neutral.");
  lines.push(RAMIFICATIONS_ASK);
  if (question.omnibus) {
    lines.push(
      mode === "explain"
        ? "Ojo: es una votación ómnibus que mezcla varias materias; enumera las principales y no te quedes solo con el título."
        : "Ojo: es una votación ómnibus que mezcla varias materias; explica qué partes concretas motivaron el voto de cada partido, no solo el título.",
    );
  }
  if (question.source === "curated") lines.push("", `Tema planteado: «${question.text}»`);
  if (question.source === "curated" && question.context) lines.push(`Contexto: ${question.context}`);
  if (question.axis_id && question.votes_total) {
    lines.push(
      `Esta afirmación resume ${question.votes_total} votaciones del Congreso (XV legislatura); abajo van las ${Math.min(MAX_PROMPT_VOTES, question.votes_total)} más recientes.`,
    );
    if (mode !== "explain") {
      const dir = parties
        .map((p) => {
          const pct = scorePercent(question.cells?.[p.party_id]?.score);
          return pct === null ? null : `${p.label}: ${pct} %`;
        })
        .filter(Boolean);
      if (dir.length) lines.push(`Cuánto empujó cada partido en el sentido de la afirmación (0 % = siempre en contra, 100 % = siempre a favor): ${dir.join("; ")}`);
    }
  }
  // A clipped link prompt loses its tail: in the compact one the official figures go before the vote details.
  const rl = ramificationLines(question, compact);
  if (compact && rl.length) lines.push("", ...rl);
  votes.forEach((v, i) => {
    lines.push("");
    lines.push(votes.length > 1 ? `Votación ${i + 1}:` : "Votación:");
    lines.push(`- Qué se votó (título oficial): ${mode === "explain" ? maskProposers(v.title) : v.title}`);
    // Curated "kind" is our note, which can state the outcome: keep it out of the neutral explanation.
    if (v.kind && (mode !== "explain" || question.source === "pool")) lines.push(`- Tipo: ${v.kind}`);
    if (v.date) lines.push(`- Fecha: ${v.date}`);
    if (mode !== "explain") {
      if (v.proposer) lines.push(`- Propuesta por: ${v.proposer}`);
      if (v.totals) lines.push(`- Resultado: ${v.approved ? "aprobada" : "rechazada"} (${v.totals[0]} sí, ${v.totals[1]} no, ${v.totals[2]} abst.)`);
      const partyEntries = parties
        .filter((p) => !partyId || p.party_id === partyId)
        .map((p) => {
          const pv = v.party[p.party_id];
          if (!pv) return null;
          const word = pv.raw ? `${pv.raw}` : POSITION_WORDS[pv.position] || pv.position;
          return `${p.label}: ${word}${pv.counts ? ` (${pv.counts[0]} sí, ${pv.counts[1]} no, ${pv.counts[2]} abst.)` : ""}`;
        })
        .filter(Boolean);
      if (partyEntries.length) lines.push(`- Voto de ${partyId ? "ese partido" : "los partidos"} (mayoría de sus diputados): ${partyEntries.join("; ")}`);
    }
    if (v.text_url) lines.push(`- Texto oficial (BOCG): ${v.text_url}`);
    if (v.source_url) lines.push(`- Datos oficiales de la votación: ${v.source_url}`);
  });
  // Plain-language bullets come first (they say what was voted); literal headings follow as evidence.
  const wv = whatVotedLines(question, compact);
  if (wv.length) lines.push("", ...wv);
  if (!compact && rl.length) lines.push("", ...rl);
  const hl = highlightLines(question, compact, wv.length > 0);
  if (hl.length) lines.push("", ...hl);
  return lines.join("\n");
}

export const AI_TARGETS = [
  { id: "chatgpt", label: "ChatGPT", url: (q) => `https://chatgpt.com/?q=${encodeURIComponent(q)}`, prefill: true },
  { id: "claude", label: "Claude", url: (q) => `https://claude.ai/new?q=${encodeURIComponent(q)}`, prefill: true },
  // Gemini has no supported way to prefill a prompt from a link: the page copies it first.
  { id: "gemini", label: "Gemini", url: () => "https://gemini.google.com/app", prefill: false },
];

// Keep prefilled links well under common URL limits; the full prompt is always available to copy.
export const MAX_LINK_PROMPT_CHARS = 6000;

/** Prompt to put in a link: the full one if it fits, else a compact one, else clipped with a note. */
export function linkPrompt(question, parties, opts = {}) {
  const full = buildAiPrompt(question, parties, opts);
  if (encodeURIComponent(full).length <= MAX_LINK_PROMPT_CHARS) return full;
  const compact = buildAiPrompt(question, parties, { ...opts, compact: true });
  if (encodeURIComponent(compact).length <= MAX_LINK_PROMPT_CHARS) return compact;
  let clipped = compact;
  while (encodeURIComponent(clipped).length > MAX_LINK_PROMPT_CHARS - 200) clipped = clipped.slice(0, Math.floor(clipped.length * 0.9));
  return `${clipped}\n[… recortado; consulta los enlaces oficiales para el texto completo]`;
}

export function aiLinks(prompt) {
  return AI_TARGETS.map((t) => ({ id: t.id, label: t.label, href: t.url(prompt), prefill: t.prefill }));
}

// ---------------------------------------------------------------------------
// What is really inside each vote (from the official text): bullets, modified norms, omnibus flags.

function questionVoteIds(question) {
  if (question.source === "pool") return question.vote_event_id ? [question.vote_event_id] : [];
  // Multi-vote statements summarise dozens of votes: their evidence is the vote list, not per-vote bullets.
  if (question.axis_id) return [];
  return (question.votes || []).map((v) => v.vote_event_id);
}

// voting_aid_vote_impacts_v1.json is an index (statement figures); each vote's figures and effects live in
// voting_aid_vote_impacts_v1/<key>.json, bucketed like shard_key() in scripts/export_voting_aid_vote_impacts.py.
export const IMPACT_SHARDS = 128;

export function impactShardKey(voteId) {
  let h = 0x811c9dc5;
  for (const b of new TextEncoder().encode(voteId)) h = Math.imul(h ^ b, 0x01000193) >>> 0;
  return (h % IMPACT_SHARDS).toString(16).padStart(2, "0");
}

/** Shard files a question needs for its «Ramificaciones» (none for multi-vote statements: the index has them). */
export function impactShardKeys(question) {
  return [...new Set(questionVoteIds(question).map(impactShardKey))];
}

/** Index plus the loaded shards, in the shape ramificationsFor() reads. */
export function mergeImpacts(index, shards) {
  if (!index) return null;
  const facts = { ...(index.facts || {}) };
  const byVote = {};
  for (const s of shards) {
    Object.assign(facts, s.facts || {});
    Object.assign(byVote, s.by_vote || {});
  }
  return { ...index, facts, by_vote: byVote };
}

// At most this many official figures in «A quién afecta», so the answers stay in reach.
const MAX_RAMIFICATION_FACTS = 3;

/**
 * «Ramificaciones» of a question (voting_aid_vote_impacts_v1.json): official figures on who it affects
 * (statement-level first, then each vote's, deduplicated) and, per vote, what changes for each group and the
 * second-order effects someone expects or fears, with their evidence. Null when there is nothing to show.
 */
function ramificationsFor(question, impacts) {
  if (!impacts) return null;
  const facts = impacts.facts || {};
  const ids = [...(impacts.by_statement?.[question.statement_id]?.facts || [])];
  const votes = questionVoteIds(question)
    .map((vid) => {
      const v = impacts.by_vote?.[vid];
      if (!v) return null;
      ids.push(...(v.facts || []));
      const vote = question.source === "pool" ? { vote_date: question.vote_date } : (question.votes || []).find((x) => x.vote_event_id === vid) || {};
      return { vote_event_id: vid, vote_date: vote.vote_date, direct: v.direct || [], indirect: v.indirect || [], gaps: v.gaps || "", review: v.review };
    })
    .filter(Boolean);
  const factList = [...new Set(ids)].map((id) => (facts[id] ? { id, ...facts[id] } : null)).filter(Boolean).slice(0, MAX_RAMIFICATION_FACTS);
  if (!factList.length && !votes.length) return null;
  return { facts: factList, votes };
}

/**
 * Attach official-text highlights to each question; `omnibus` is true if any of its votes is omnibus.
 * With `bullets` (voting_aid_vote_bullets_v1.json), `whatVoted` lists, per vote, the plain-language
 * «Qué se votaba» bullets (status "ok"), or "sin_texto_oficial" when there is no official text.
 * With `impacts` (voting_aid_vote_impacts_v1.json), `ramifications` holds who it affects and what may follow.
 */
export function attachHighlights(questions, highlights, bullets = null, impacts = null) {
  const byVote = highlights?.by_vote || {};
  const docs = highlights?.docs || {};
  const bulletsByVote = bullets?.by_vote || {};
  return questions.map((q) => {
    const items = questionVoteIds(q)
      .map((vid) => {
        const doc = docs[byVote[vid]];
        if (!doc) return null;
        const vote = q.source === "pool" ? { vote_date: q.vote_date, title: q.text } : (q.votes || []).find((v) => v.vote_event_id === vid) || {};
        return { vote_event_id: vid, vote_date: vote.vote_date, title: vote.title, doc };
      })
      .filter(Boolean);
    // Several votes on the same text (e.g. two stages of one bill) show it once.
    const seen = new Set();
    const unique = items.filter((h) => (seen.has(h.doc.url) ? false : seen.add(h.doc.url)));
    const voted = questionVoteIds(q).map((vid) => {
      const b = bulletsByVote[vid];
      const vote = q.source === "pool" ? { vote_date: q.vote_date } : (q.votes || []).find((v) => v.vote_event_id === vid) || {};
      const doc = docs[byVote[vid]];
      if (b?.status === "ok") return { vote_event_id: vid, vote_date: vote.vote_date, ...b, doc };
      return { vote_event_id: vid, vote_date: vote.vote_date, status: b ? b.status : "pending", bullets: [], doc };
    });
    const seenVoted = new Set();
    const whatVoted = voted.filter((w) => (w.status !== "ok" ? true : seenVoted.has(w.url) ? false : seenVoted.add(w.url)));
    return {
      ...q,
      highlights: unique,
      whatVoted,
      ramifications: ramificationsFor(q, impacts),
      omnibus: unique.some((h) => h.doc.omnibus),
      offtopic: unique.some((h) => (h.doc.offtopic_riders || []).length > 0),
    };
  });
}

/** «Qué se votaba» lines for AI prompts: plain-language bullets with their locators and source. */
function whatVotedLines(question, compact = false) {
  const items = (question.whatVoted || []).filter((w) => w.status === "ok");
  if (!items.length) return [];
  const lines = [];
  for (const w of items) {
    lines.push(`Qué se votaba (resumen en lenguaje llano del texto oficial${w.vote_date && items.length > 1 ? `, votación del ${w.vote_date}` : ""}; puede tener errores):`);
    if (w.simple) lines.push(`  En pocas palabras: ${w.simple}`);
    for (const b of w.bullets.slice(0, compact ? 4 : 6)) lines.push(compact ? `  • ${b.text}` : `  • ${b.text} [${b.locator}]`);
    if (w.text_status_label) lines.push(`  (${w.text_status_label})`);
    lines.push(`  Texto oficial: ${w.url}`);
  }
  return lines;
}

/** «Ramificaciones» lines for AI prompts: official figures, then (full prompt only) effects with their sources. */
function ramificationLines(question, compact = false) {
  const r = question.ramifications;
  if (!r) return [];
  const lines = [];
  if (r.facts.length) {
    lines.push("A quién afecta (cifras oficiales):");
    for (const f of r.facts) lines.push(compact ? `  • ${f.text} (${f.period})` : `  • ${f.text} (${f.source}, ${f.period}: ${f.url})`);
  }
  if (compact) return lines;
  const many = r.votes.length > 1;
  for (const v of r.votes) {
    const when = many && v.vote_date ? `, votación del ${v.vote_date}` : "";
    if (v.direct.length) {
      lines.push(`Qué cambiaría para cada colectivo (del texto oficial${when}):`);
      for (const d of v.direct) lines.push(`  • ${d.actor}: ${d.text} [${d.locator}]`);
    }
    if (v.indirect.length) {
      lines.push(`Posibles efectos indirectos que se han señalado${when} (previsiones, no hechos; compruébalas):`);
      for (const e of v.indirect) {
        const label = e.kind === "beneficio_esperado" ? "Beneficio esperado" : "Riesgo señalado";
        lines.push(`  • ${label}: ${e.text} [${EVIDENCE_WORDS[e.evidence] || e.evidence}: ${e.source}, ${e.locator}]`);
      }
    }
    if (v.gaps) lines.push(`Lo que no se sabe: ${v.gaps}`);
  }
  return lines;
}

function highlightLines(question, compact = false, hasPlainBullets = false) {
  const lines = [];
  const maxBullets = compact ? (hasPlainBullets ? 0 : 4) : hasPlainBullets ? 6 : 10;
  for (const h of question.highlights || []) {
    const d = h.doc;
    if (compact && hasPlainBullets) {
      // The plain bullets already say what was voted: keep only the scope warnings.
      if ((d.offtopic_riders || []).length) lines.push(`También cambia, en disposiciones finales, normas de otros temas: ${d.offtopic_riders.slice(0, 2).join("; ")}`);
      if (d.omnibus) lines.push(`Es una votación ómnibus: abarca ${d.themes.join(", ")}.`);
      continue;
    }
    lines.push(`Contenido según el texto oficial (${d.source}${h.vote_date ? `, votación del ${h.vote_date}` : ""}; encabezados literales):`);
    const bullets = (d.bullets || []).slice(0, maxBullets);
    for (const b of bullets) lines.push(`  • ${b}`);
    if (d.bullets_total > bullets.length) lines.push(`  • … y ${d.bullets_total - bullets.length} apartados más`);
    if (!compact && (d.modified_norms || []).length && d.bullets_basis !== "normas") {
      lines.push(`  Modifica ${d.modified_norms_total} normas, entre ellas: ${d.modified_norms.slice(0, 5).join("; ")}`);
    }
    if ((d.offtopic_riders || []).length) {
      lines.push(`  También cambia, en disposiciones finales, normas de otros temas: ${d.offtopic_riders.slice(0, compact ? 2 : 10).join("; ")}`);
    }
    if (d.omnibus) lines.push(`  Es una votación ómnibus: abarca ${d.themes.join(", ")}.`);
    lines.push(`  Fuente: ${d.url}`);
  }
  return lines;
}
