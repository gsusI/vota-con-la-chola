// Pure helpers for the Explorar section (/citizen/vota/explorar|partidos|diputados|votacion|temas/). No DOM, no React.
// Data: vote_atlas_v1.json (atlas) and vote_atlas_people_v1.json (people); see voteAtlasModel.mjs for the shapes.

import { LEG_LABELS, foldText, groupLabel, groupShortLabel, personChoice } from "./voteAtlasModel.mjs";

export const XV = "15";
export const ABSOLUTE_MAJORITY = 176;
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
export const CODE_WORDS = { S: "Sí", N: "No", A: "Abstención", "-": "No votó", "?": "sin dato", "=": "empate" };
const CODE_CLASS = { S: "x-c-S", N: "x-c-N", A: "x-c-A", "-": "x-c-absent", "=": "x-c-eq" };
/** CSS colour class of a vote code (explore.css). */
export function codeClass(code) {
  return CODE_CLASS[code] || "x-c-q";
}

/** Atlas votes of the XV legislature (no `leg`, or leg "15"). */
export function isXvVote(vote) {
  return !vote?.leg || String(vote.leg) === XV;
}

export function partyIndex(atlas, partyId) {
  return (atlas?.parties || []).findIndex((p) => p.party_id === partyId);
}

/** Per-party majority code of an atlas vote ("?" when missing). */
export function codeOf(vote, i) {
  return String(vote?.parties || "")[i] || "?";
}

/** XV votes in which the party has a recorded majority vote (code not "?"). */
export function partyVoteCount(atlas, partyId) {
  const i = partyIndex(atlas, partyId);
  if (i < 0) return 0;
  return (atlas.votes || []).filter((v) => isXvVote(v) && codeOf(v, i) !== "?").length;
}

/**
 * Share of XV votes in which two parties cast the same majority vote (both recorded, ties excluded),
 * for every other party, highest first.
 */
export function sameVoteShares(atlas, partyId) {
  const parties = atlas?.parties || [];
  const i = partyIndex(atlas, partyId);
  if (i < 0) return [];
  const xv = (atlas.votes || []).filter(isXvVote);
  const rows = [];
  parties.forEach((p, j) => {
    if (j === i) return;
    let n = 0;
    let same = 0;
    for (const v of xv) {
      const a = codeOf(v, i);
      const b = codeOf(v, j);
      if (a === "?" || b === "?" || a === "=" || b === "=") continue;
      n += 1;
      if (a === b) same += 1;
    }
    rows.push({ ...p, n, same, share: n ? same / n : null });
  });
  return rows.sort((x, y) => (y.share ?? -1) - (x.share ?? -1) || x.label.localeCompare(y.label, "es"));
}

/** Geometry of a diverging bar from the centre: percentages of the track. */
export function barGeometry(score) {
  if (!Number.isFinite(score)) return { left: 50, width: 0, side: "none" };
  const width = Math.min(50, Math.abs(score) * 50);
  return { left: score >= 0 ? 50 : 50 - width, width, side: score > 0 ? "pos" : score < 0 ? "neg" : "none" };
}

/** −1..1 → 0..100 (left edge = negative pole). */
export function axisPosition(score) {
  return Number.isFinite(score) ? Math.max(0, Math.min(100, 50 + score * 50)) : null;
}

/** "inclinación 34 % hacia «Más intervención pública»" style text for a diverging bar. */
export function leaningText(axis, score) {
  if (!Number.isFinite(score) || !axis) return "sin datos";
  const pole = score >= 0 ? axis.pos_short : axis.neg_short;
  return `inclinación ${Math.round(Math.abs(score) * 100)} % hacia «${pole}»`;
}

/**
 * A party's axes grouped by topic (codebook order). `minVotes` hides thinly evidenced axes;
 * returns { groups, shown, total } where total counts axes with any vote for the party.
 */
export function partyAxisGroups(atlas, partyId, { minVotes = 10 } = {}) {
  const cells = atlas?.party_axes?.[partyId] || {};
  const topics = atlas?.topics || [];
  let total = 0;
  let shown = 0;
  const byTopic = new Map(topics.map((t) => [t.topic_id, []]));
  for (const axis of atlas?.axes || []) {
    const cell = cells[axis.axis_id];
    if (!cell || !Number.isFinite(cell.score) || !(cell.votes > 0)) continue;
    total += 1;
    if (cell.votes < minVotes) continue;
    shown += 1;
    if (!byTopic.has(axis.topic_id)) byTopic.set(axis.topic_id, []);
    byTopic.get(axis.topic_id).push({ axis, score: cell.score, votes: cell.votes, initiatives: cell.initiatives, ...barGeometry(cell.score) });
  }
  const topicById = Object.fromEntries(topics.map((t) => [t.topic_id, t]));
  const groups = [...byTopic.entries()]
    .filter(([, rows]) => rows.length)
    .map(([topicId, rows]) => ({ topic: topicById[topicId] || { topic_id: topicId, label: topicId }, rows }));
  return { groups, shown, total };
}

/**
 * The n most recent XV atlas votes, newest first (atlas votes are stored oldest first).
 * `onAxes` keeps only votes placed on some axis (leaves out treaty ratifications and procedure).
 */
export function latestVotes(atlas, n = 5, { onAxes = false } = {}) {
  const out = [];
  const votes = atlas?.votes || [];
  for (let i = votes.length - 1; i >= 0 && out.length < n; i -= 1) {
    const v = votes[i];
    if (isXvVote(v) && (!onAxes || (v.axes || []).length)) out.push(v);
  }
  return out;
}

export function totalsText(totals, { long = false } = {}) {
  if (!Array.isArray(totals) || totals.length < 3) return "sin datos";
  const [y, n, a] = totals;
  return long ? `${y} sí · ${n} no · ${a} ${a === 1 ? "abstención" : "abstenciones"}` : `${y} sí · ${n} no · ${a} abst.`;
}

export function resultLabel(vote) {
  if (vote?.approved === true) return "Aprobada";
  if (vote?.approved === false) return "Rechazada";
  return "Resultado sin datos";
}

/** Text alternative of a row of party squares: "PSOE Sí, PP No, …". */
export function partyCodesAria(atlas, vote) {
  return (atlas?.parties || []).map((p, i) => `${p.label} ${CODE_WORDS[codeOf(vote, i)] || "sin dato"}`).join(", ");
}

/** Two-letter avatar: first letter of the first two words. */
export function initials(name) {
  const words = String(name || "").trim().split(/\s+/u).filter(Boolean);
  return words
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join("");
}

function tokens(query) {
  return foldText(query).trim().split(/\s+/u).filter(Boolean);
}

function matchesAll(haystack, toks) {
  return toks.every((t) => haystack.includes(t));
}

/** People seated in the XV legislature. */
export function xvPeople(people) {
  return (people?.people || []).filter((p) => (p.legislatures || []).includes(XV));
}

/**
 * Client-side search over parties, XV deputies and XV votes (summary + official title).
 * Every term must appear. Returns full match lists (newest votes first); callers slice.
 */
export function searchExplore({ atlas, people, query }) {
  const toks = tokens(query);
  const empty = { parties: [], people: [], votes: [], peopleReady: Boolean(people) };
  if (!toks.length) return empty;
  const parties = (atlas?.parties || people?.parties || []).filter((p) => matchesAll(foldText(`${p.label} ${p.party_id}`), toks));
  const persons = people ? xvPeople(people).filter((p) => matchesAll(foldText(p.name), toks)) : [];
  const votes = [];
  const list = atlas?.votes || [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const v = list[i];
    if (!isXvVote(v)) continue;
    const title = Number.isInteger(v.t) ? atlas.titles?.[v.t] || "" : "";
    if (matchesAll(foldText(`${v.summary_yes || ""} ${title}`), toks)) votes.push(v);
  }
  return { parties, people: persons, votes, peopleReady: Boolean(people) };
}

// ---------------------------------------------------------------------------
// People

/** Absolute vote indices (people.votes) of a legislature. */
export function legIndices(people, leg = XV) {
  const out = [];
  (people?.votes || []).forEach((v, i) => {
    if (String(v[6]) === String(leg)) out.push(i);
  });
  return out;
}

/** Most recent legislature a person sat in ("15" first). */
export function mainLeg(person) {
  const legs = (person?.legislatures || []).map(String);
  return legs.includes(XV) ? XV : legs.sort().pop() || XV;
}

/**
 * A person's record in one legislature: how many votes they were a deputy for, what they voted,
 * participation, loyalty (from the exporter) and how many times they voted unlike their party.
 * GOTCHA: `rebels` holds [voteIndex, PARTY majority code]; the person's own vote is in `votes`.
 */
export function personLegSummary(people, person, leg = XV) {
  const counts = { S: 0, N: 0, A: 0, "-": 0 };
  for (const i of legIndices(people, leg)) {
    const c = personChoice(person, i);
    if (c in counts) counts[c] += 1;
  }
  const seated = counts.S + counts.N + counts.A + counts["-"];
  const voted = counts.S + counts.N + counts.A;
  const rebels = (person?.rebels || []).filter(([i]) => String(people?.votes?.[i]?.[6]) === String(leg));
  const loyalty = person?.loyalty_by_leg?.[leg];
  return {
    leg: String(leg),
    counts,
    seated,
    voted,
    participation: seated ? voted / seated : null,
    loyalty: Array.isArray(loyalty) ? loyalty[0] : null,
    loyaltyVotes: Array.isArray(loyalty) ? loyalty[1] : 0,
    rebels: rebels.length,
  };
}

/** Votes where the person voted unlike their party (or group) majority, newest first. */
export function personDissents(person) {
  return [...(person?.rebels || [])]
    .map(([index, party]) => ({ index, own: personChoice(person, index), party }))
    .sort((a, b) => b.index - a.index);
}

/** Vote indices the person was seated for (any code but "."), newest first. */
export function personVoteIndices(person) {
  const out = [];
  const s = String(person?.votes || "");
  for (let k = s.length - 1; k >= 0; k -= 1) if (s[k] !== ".") out.push((person.first || 0) + k);
  return out;
}

/** Axis rows for the "person dot vs party ring" chart, most voted first. */
export function personVsPartyAxes(atlas, person) {
  const axisById = Object.fromEntries((atlas?.axes || []).map((a) => [a.axis_id, a]));
  const rows = [];
  for (const [axisId, pair] of Object.entries(person?.axes || {})) {
    const axis = axisById[axisId];
    if (!axis || !Array.isArray(pair)) continue;
    const [score, n] = pair;
    const party = person.party_id ? atlas?.party_axes?.[person.party_id]?.[axisId] : null;
    rows.push({
      axis,
      score,
      n,
      partyScore: party && Number.isFinite(party.score) ? party.score : null,
      gap: party && Number.isFinite(party.score) ? Math.abs(score - party.score) : 0,
    });
  }
  return rows.sort((a, b) => b.n - a.n || a.axis.label.localeCompare(b.axis.label, "es"));
}

export function voteIndexById(people) {
  return Object.fromEntries((people?.votes || []).map((v, i) => [v[0], i]));
}

/** Group a deputy belongs to for a vote: ballot party in the XV, parliamentary group before. */
export function seatGroupOf(person, leg, partyIds) {
  if (String(leg) === XV) return person.party_id && partyIds.has(person.party_id) ? person.party_id : "otros";
  const groups = person.groups_by_leg?.[leg] || [];
  return groups.length ? `g:${groups[groups.length - 1]}` : "otros";
}

/**
 * One block per party (or group) for a vote: every deputy's own code at that vote index.
 * Sorted from the most "Sí" to the most "No" (yes − no), "Otros" by the same rule.
 */
export function seatBlocks(people, index, parties = people?.parties || []) {
  const leg = String(people?.votes?.[index]?.[6] || XV);
  const partyIds = new Set(parties.map((p) => p.party_id));
  const labelOf = (key) => {
    if (key === "otros") return "Otros";
    if (key.startsWith("g:")) return groupShortLabel(key.slice(2));
    return parties.find((p) => p.party_id === key)?.label || key;
  };
  const blocks = new Map();
  for (const person of people?.people || []) {
    const code = personChoice(person, index);
    if (code === ".") continue;
    const key = seatGroupOf(person, leg, partyIds);
    if (!blocks.has(key)) blocks.set(key, { key, partyId: partyIds.has(key) ? key : null, label: labelOf(key), counts: { S: 0, N: 0, A: 0, "-": 0 }, codes: [] });
    const b = blocks.get(key);
    if (code in b.counts) b.counts[code] += 1;
    b.codes.push(code);
  }
  const order = { S: 0, A: 1, N: 2, "-": 3 };
  return [...blocks.values()]
    .map((b) => ({ ...b, codes: b.codes.sort((x, y) => (order[x] ?? 9) - (order[y] ?? 9)) }))
    .sort(
      (a, b) =>
        b.counts.S - b.counts.N - (a.counts.S - a.counts.N) ||
        (a.key === "otros") - (b.key === "otros") ||
        b.codes.length - a.codes.length ||
        a.label.localeCompare(b.label, "es"),
    );
}

/** "120 sí · 3 no · 2 no votó" for a block. */
export function countsText(counts) {
  const parts = [];
  if (counts.S) parts.push(`${counts.S} sí`);
  if (counts.N) parts.push(`${counts.N} no`);
  if (counts.A) parts.push(`${counts.A} abst.`);
  if (counts["-"]) parts.push(`${counts["-"]} no votó`);
  return parts.join(" · ") || "sin votos";
}

/** Totals counted from the deputies' own votes (fallback when the atlas has no totals). */
export function totalsFromPeople(people, index) {
  const t = [0, 0, 0];
  for (const person of people?.people || []) {
    const c = personChoice(person, index);
    if (c === "S") t[0] += 1;
    else if (c === "N") t[1] += 1;
    else if (c === "A") t[2] += 1;
  }
  return t;
}

/** Deputies whose own vote differs from their party (group) majority on that vote, from `rebels`. */
export function voteDissenters(people, index) {
  const out = [];
  for (const person of people?.people || []) {
    const hit = (person.rebels || []).find(([i]) => i === index);
    if (hit) out.push({ person, own: personChoice(person, index), party: hit[1] });
  }
  return out.sort((a, b) => a.person.name.localeCompare(b.person.name, "es"));
}

/**
 * Absolute-majority rule for an organic law's final vote (176 of 350). Only "votación final" of a
 * text whose title or kind says «Orgánica»: amendments to it pass by simple majority.
 */
export function organicMajority(vote, title) {
  const organic = vote?.kind === "final" && /org[aá]nica/iu.test(`${title || ""} ${vote?.kind || ""}`);
  if (!organic || !Array.isArray(vote?.totals)) return null;
  const yes = vote.totals[0];
  return { needed: ABSOLUTE_MAJORITY, yes, margin: yes - ABSOLUTE_MAJORITY, reached: yes >= ABSOLUTE_MAJORITY };
}

const SMALL = ["cero", "un", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez"];
export function votesWord(n) {
  const k = Math.abs(n);
  return `${SMALL[k] || k} ${k === 1 ? "voto" : "votos"}`;
}

/** Other atlas votes on the same official title, oldest first. */
export function relatedVotes(atlas, vote) {
  if (!Number.isInteger(vote?.t)) return [];
  return (atlas?.votes || []).filter((v) => v.t === vote.t && v.id !== vote.id).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

/** Short breadcrumb label: the first words of a long sentence. */
export function shortLabel(text, max = 48) {
  const s = String(text || "").trim();
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 20)).replace(/[,;:.]$/u, "")}…`;
}

/**
 * Spanish percent with one decimal and a comma: 0.987 → "98,7 %". `floor` keeps 99,96 % from reading as 100 %
 * (loyalty is usually 99–100 %).
 */
export function percent1(value, { floor = false } = {}) {
  return Number.isFinite(value) ? `${((floor ? Math.floor : Math.round)(value * 1000) / 10).toLocaleString("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %` : "—";
}

/** Party (XV ballot party) or group label of a person, for lists and headers. */
export function personPartyLabel(person, partiesById = {}) {
  if (person?.party_id) return partiesById[person.party_id]?.label || person.party_id;
  const legs = (person?.legislatures || []).map(String);
  if (!legs.includes(XV)) return `${groupShortLabel(person?.last_group)} (${legs.map((lg) => LEG_LABELS[lg] || lg).join(", ")})`;
  return person?.last_group === "GMx" ? "Grupo Mixto (sin partido de papeleta)" : groupLabel(person?.last_group);
}

/** "la XIV y la XV legislaturas" / "la XV legislatura". */
export function legislaturesText(person) {
  const legs = (person?.legislatures || []).map((lg) => LEG_LABELS[lg] || lg);
  if (!legs.length) return "";
  if (legs.length === 1) return `la ${legs[0]} legislatura`;
  return `${legs.slice(0, -1).map((l) => `la ${l}`).join(", ")} y la ${legs[legs.length - 1]} legislaturas`;
}
