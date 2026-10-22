// Build-time data for the indexable pages of the voting aid: one page per party, per key question and per topic,
// plus the crawlable summaries of the client-only pages. Every figure comes from the published snapshots
// (voting_aid_generales_v2.json for the test, vote_atlas_v1.json for all votes); nothing is typed by hand
// except slugs and short titles. Build-time only (reads public/ from disk).
import { readPublicJson } from "../../static-snapshot.mjs";
import { isXvVote, partyVoteCount, sameVoteShares } from "./exploreModel.mjs";
import { ATLAS_PATH, PEOPLE_PATH } from "./voteAtlasModel.mjs";
import { POSITION_LABELS, scorePercent } from "./votingAidModel.mjs";
import { loadVotingAidSnapshot } from "./votingAidHooks.mjs";
import { CURRENT_VERSION } from "./votingAidVersions.mjs";
import { partyPagePath } from "./votaPaths.mjs";

export { VOTA_PATHS, slugify, partySlug, partyPagePath, questionSlug, questionTitle, hasQuestionPage, questionPagePath, topicSlug, topicPagePath, ogPath } from "./votaPaths.mjs";

const KIND_FALLBACK = "Votación";
const CODE_LABELS = { S: "Sí", N: "No", A: "Abstención", "-": "No votó", "=": "Empate", "?": "Sin datos" };
export const codeLabel = (code) => CODE_LABELS[code] || "Sin datos";

let cache = null;

/** Snapshot (current test), atlas and people, read once per build worker. */
export function loadVotaData() {
  if (cache) return cache;
  const snapshot = loadVotingAidSnapshot(CURRENT_VERSION.id);
  const atlas = readPublicJson(ATLAS_PATH, { parties: [], topics: [], axes: [], votes: [], party_axes: {} });
  const people = readPublicJson(PEOPLE_PATH, { parties: [], people: [] });
  cache = { snapshot, atlas, people };
  return cache;
}

/** Numbers the copy may quote about the test, all read from the snapshot. */
export function testFacts(snapshot = loadVotaData().snapshot) {
  const meta = snapshot.meta || {};
  const statements = snapshot.statements || [];
  const themes = [...new Set(statements.map((st) => st.theme).filter(Boolean))];
  return {
    questions: statements.length,
    votes: meta.quality?.votes_total ?? statements.reduce((n, st) => n + (st.votes_total || 0), 0),
    initiatives: meta.quality?.initiatives_total ?? null,
    parties: (snapshot.parties || []).length,
    partyLabels: (snapshot.parties || []).map((p) => p.label),
    themes,
    firstDate: meta.votes_first_date || null,
    lastDate: meta.votes_last_date || null,
    legislature: meta.legislature || "15",
    released: CURRENT_VERSION.released,
    agreement: meta.classification_review?.agreement || null,
  };
}

/** "Sí" votes of an agree_vote means agreeing with the statement; returns "agree" | "disagree" | "abstain" | "absent" | "no_data". */
export function codeStance(code, agreeVote) {
  if (code === "S" || code === "N") return (code === "S") === (agreeVote !== "No") ? "agree" : "disagree";
  if (code === "A") return "abstain";
  if (code === "-") return "absent";
  return "no_data";
}

/** One party's position on a key question, ready to print (position label, % of push towards it, votes). */
export function cellSummary(statement, partyId) {
  const cell = statement.cells?.[partyId];
  if (!cell || !cell.votes_with_data) return { position: "no_data", label: POSITION_LABELS.no_data, pct: null, votes: 0, total: statement.votes_total || 0 };
  return {
    position: cell.position,
    label: POSITION_LABELS[cell.position] || cell.position,
    pct: scorePercent(cell.score),
    votes: cell.votes_with_data,
    total: cell.votes_total || statement.votes_total || 0,
  };
}

/** Topic (atlas) of a key question, through its axis. */
export function statementTopic(atlas, statement) {
  const axis = (atlas.axes || []).find((a) => a.axis_id === statement.axis_id);
  return (atlas.topics || []).find((t) => t.topic_id === axis?.topic_id) || null;
}

/** Topics that have at least one scored axis, in codebook order. */
export function topicsWithVotes(atlas = loadVotaData().atlas) {
  return (atlas.topics || []).filter((t) => (atlas.axes || []).some((a) => a.topic_id === t.topic_id && a.votes > 0));
}

/** Votes of a key question, newest first, with each party's vote mapped to agree/disagree. */
export function statementVotes(snapshot, statement) {
  const parties = snapshot.parties || [];
  return [...(statement.votes || [])]
    .sort((a, b) => String(b.vote_date).localeCompare(String(a.vote_date)))
    .map((v) => {
      const [yes = 0, no = 0, abstain = 0] = Array.isArray(v.totals) ? v.totals : [];
      return {
        id: v.id,
        date: v.vote_date,
        title: v.summary_yes || v.title,
        officialTitle: v.title,
        subgroup: v.subgroup || "",
        kind: v.kind,
        agreeVote: v.agree_vote,
        approved: v.approved,
        totals: { yes, no, abstain },
        margin: Math.abs(yes - no),
        sourceUrl: v.source_url,
        textUrl: v.text_url || null,
        parties: parties.map((p, i) => {
          const code = String(v.parties || "")[i] || "?";
          return { partyId: p.party_id, label: p.label, code, stance: codeStance(code, v.agree_vote) };
        }),
      };
    });
}

export function kindLabel(atlas, kind) {
  return atlas.kind_labels?.[kind] || KIND_FALLBACK;
}

/** Everything a party page prints. */
export function partySummary(partyId, data = loadVotaData()) {
  const { snapshot, atlas, people } = data;
  const party = (snapshot.parties || []).find((p) => p.party_id === partyId);
  if (!party) return null;
  const statements = snapshot.statements || [];
  const byTheme = new Map();
  const counts = { agree: 0, disagree: 0, mixed: 0, no_data: 0 };
  for (const st of statements) {
    const cell = cellSummary(st, partyId);
    counts[cell.position in counts ? cell.position : "no_data"] += 1;
    if (!byTheme.has(st.theme)) byTheme.set(st.theme, []);
    byTheme.get(st.theme).push({ statement: st, cell });
  }
  // Close votes (decided by 5 or fewer) in which the party took a side: where its vote weighed most.
  const seen = new Set();
  const closeVotes = [];
  for (const st of statements) {
    for (const v of statementVotes(snapshot, st)) {
      if (seen.has(v.id) || v.margin > 5) continue;
      seen.add(v.id);
      const own = v.parties.find((p) => p.partyId === partyId);
      if (own && (own.code === "S" || own.code === "N" || own.code === "A")) closeVotes.push({ ...v, own, statement: st });
    }
  }
  closeVotes.sort((a, b) => a.margin - b.margin || String(b.date).localeCompare(String(a.date)));
  const deputies = (people.people || []).filter((p) => p.party_id === partyId && (p.legislatures || []).includes("15")).length;
  return {
    party,
    counts,
    themes: [...byTheme.entries()].map(([theme, rows]) => ({ theme, rows })),
    allies: sameVoteShares(atlas, partyId).filter((r) => r.n > 0),
    atlasVotes: partyVoteCount(atlas, partyId),
    closeVotes: closeVotes.slice(0, 12),
    deputies,
  };
}

/** Parties sorted from most to least in favour of a key question (no data last). */
export function questionParties(snapshot, statement) {
  return (snapshot.parties || [])
    .map((p) => ({ ...p, cell: cellSummary(statement, p.party_id) }))
    .sort((a, b) => (b.cell.pct ?? -1) - (a.cell.pct ?? -1) || a.label.localeCompare(b.label, "es"));
}

/** "PSOE, PP y Vox" */
export function joinLabels(labels) {
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} y ${labels[labels.length - 1]}`;
}

/** Latest XV atlas votes (for the crawlable summary of /votacion/). */
export function latestAtlasVotes(atlas, n = 20) {
  const out = [];
  const votes = atlas.votes || [];
  for (let i = votes.length - 1; i >= 0 && out.length < n; i -= 1) if (isXvVote(votes[i])) out.push(votes[i]);
  return out;
}
