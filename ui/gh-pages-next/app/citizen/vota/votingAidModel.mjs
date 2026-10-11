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
