// Build-time facts for the voting-aid methodology page, read from the published data and the repo
// (seeds, review evidence, prompts) so the page never drifts from what /citizen/vota/ actually uses.
import fs from "node:fs";
import path from "node:path";
import { readPublicJson } from "../../../static-snapshot.mjs";
import { attachHighlights, buildAiPrompt, buildQuestions } from "../votingAidModel.mjs";

export const REPO_URL = "https://github.com/gsusI/vota-con-la-chola";
const REPO_ROOT = path.resolve(process.cwd(), "../..");

export const PROMPTS_DIR = "docs/etl/sprints/VOTING-AID-20261011/prompts";
export const STATEMENT_REVIEW = "docs/etl/sprints/VOTING-AID-20261011/evidence/voting-aid-statement-review-20261012.json";
export const STATEMENTS_SEED = "etl/data/seeds/voting_aid_generales_v1.json";
export const STATEMENTS_SEED_V2 = "etl/data/seeds/voting_aid_generales_v2.json";
export const AXES_SEED = "etl/data/seeds/vote_atlas_axes_v1.json";
export const CLASSIFICATIONS_SEED = "etl/data/seeds/vote_atlas_classifications_v1.json";
export const TEXTS_SEED = "etl/data/seeds/vote_atlas_texts_v1.json";
export const ATLAS_PROMPTS_DIR = "docs/etl/sprints/VOTE-ATLAS-20261013/prompts";
export const ATLAS_QA = "docs/etl/sprints/VOTE-ATLAS-20261013/evidence/vote-atlas-classification-agreement.json";
export const ATLAS_QA_XIV = "docs/etl/sprints/VOTE-ATLAS-20261013/evidence/vote-atlas-classification-agreement-xiv.json";
export const ATLAS_QA_ENM = "docs/etl/sprints/VOTE-ATLAS-20261013/evidence/vote-atlas-classification-agreement-enmiendas.json";
export const AMENDMENT_DOCS = "etl/data/seeds/vote_atlas_amendment_docs_v1.json";
export const AMENDMENT_PROMPT = "docs/etl/sprints/VOTE-ATLAS-20261013/prompts/clasificar-enmiendas.md";
export const SENADO_EVIDENCE = "docs/etl/sprints/VOTE-ATLAS-20261013/evidence/senado-votos-por-senador-probe-20261013.md";
export const BULLETS_SEED = "etl/data/seeds/voting_aid_vote_bullets_v1.json";

export function repoLink(rel) {
  return `${REPO_URL}/blob/main/${rel}`;
}

function readRepoText(rel) {
  try {
    return fs.readFileSync(path.join(REPO_ROOT, rel), "utf-8");
  } catch {
    return null;
  }
}

function readRepoJson(rel) {
  const text = readRepoText(rel);
  return text ? JSON.parse(text) : null;
}

const PROMPT_FILES = [
  {
    file: "vinetas-redaccion.md",
    title: "Redacción de las viñetas «Qué se votaba»",
    who: "Claude Sonnet 5.5 (subagentes, por lotes)",
  },
  {
    file: "vinetas-revision.md",
    title: "Revisión de cada viñeta contra el texto oficial",
    who: "Claude Sonnet 5.5 (otro subagente, segunda mano)",
  },
  {
    file: "afirmaciones-revision.md",
    title: "Revisión independiente de las afirmaciones",
    who: "Claude Sonnet 5.5 (dos revisores por afirmación, sin ver los votos de los partidos)",
  },
  {
    file: "clasificar-votaciones.md",
    dir: ATLAS_PROMPTS_DIR,
    title: "Clasificación de cada votación en un eje temático (mapa y preguntas clave)",
    who: "Claude Opus 5.5 (14 subagentes por lotes + 3 para la muestra de control, sin ver los votos de los partidos)",
  },
  {
    file: "clasificar-enmiendas.md",
    dir: ATLAS_PROMPTS_DIR,
    title: "Clasificación de cada enmienda con su texto del BOCG",
    who: "Claude Opus 5.5 (20 subagentes por lotes + 4 para reclasificar tras corregir el localizador + 3 para la muestra de control)",
  },
  {
    file: "encargos-subagentes.md",
    title: "Encargos concretos con los que se lanzó cada lote",
    who: "Claude Opus 5.5 (agente principal) → Claude Sonnet 5.5",
  },
];

function bulletReviewStats(seed) {
  const votes = Object.values(seed?.votes || {});
  const docs = new Map();
  for (const v of votes) {
    const key = v?.source?.doc_key || v?.source?.url;
    if (key && !docs.has(key)) docs.set(key, v.review || {});
  }
  const reviews = [...docs.values()];
  return {
    votes: votes.length,
    withBullets: votes.filter((v) => v.status === "ok" && (v.bullets || []).length).length,
    bullets: votes.reduce((n, v) => n + (v.bullets || []).length, 0),
    docs: docs.size,
    corrected: reviews.filter((r) => r.verdict === "corregido").length,
    changes: reviews.reduce((n, r) => n + (r.changes || []).length, 0),
    issues: reviews.reduce((n, r) => n + (r.issues || []).length, 0),
    humanReviewed: votes.filter((v) => v.review?.human_reviewed).length,
  };
}

function statementReviewStats(evidence) {
  const out = { statements: 0, checks: 0, correct: 0, wrong: 0, unclear: 0, wordingIssues: 0 };
  for (const st of Object.values(evidence?.statements || {})) {
    out.statements += 1;
    for (const r of st.reviews || []) {
      if (r.wording_verdict === "issue") out.wordingIssues += 1;
      for (const v of r.votes || []) {
        out.checks += 1;
        if (v.agree_vote_verdict in out) out[v.agree_vote_verdict] += 1;
      }
    }
  }
  return out;
}

export function loadMethodology() {
  const snapshot = readPublicJson("citizen/data/voting_aid_generales_v2.json", { meta: {}, parties: [], statements: [] });
  const snapshotV1 = readPublicJson("citizen/data/voting_aid_generales_v1.json", { meta: {}, parties: [], statements: [] });
  const atlas = readPublicJson("citizen/data/vote_atlas_v1.json", { meta: {}, axes: [], votes: [] });
  const axesSeed = readRepoJson(AXES_SEED) || { axes: [] };
  const pool = readPublicJson("citizen/data/voting_aid_pool_v1.json", { meta: {}, items: [] });
  const highlights = readPublicJson("citizen/data/voting_aid_highlights_v1.json", { meta: {} });
  const bullets = readPublicJson("citizen/data/voting_aid_vote_bullets_v1.json", { meta: {} });
  const seed = readRepoJson(STATEMENTS_SEED) || {};
  const bulletSeed = readRepoJson(BULLETS_SEED);
  const evidence = readRepoJson(STATEMENT_REVIEW);

  const questions = attachHighlights(buildQuestions(snapshot, pool), highlights, bullets);
  const curated = questions.find((q) => q.source === "curated");
  const poolQ = questions.find((q) => q.source === "pool" && (q.whatVoted || []).some((w) => w.status === "ok"));
  const examples = [];
  if (curated) {
    examples.push({
      title: `Antes de responder: «Explícame qué se vota» (afirmación «${curated.text}»)`,
      text: buildAiPrompt(curated, snapshot.parties, { mode: "explain" }),
    });
  }
  if (poolQ) {
    examples.push({
      title: `Después de responder: «¿Por qué votó así cada partido?» (${poolQ.kind_label}, ${poolQ.vote_date})`,
      text: buildAiPrompt(poolQ, snapshot.parties, { mode: "why" }),
    });
  }

  return {
    snapshot,
    snapshotV1,
    atlasMeta: atlas.meta || {},
    axes: atlas.axes || [],
    axesRules: axesSeed.rules || [],
    sampleAxis: (axesSeed.axes || [])[0] || null,
    pool,
    highlights,
    bullets,
    seed,
    sampleStatement: (seed.statements || [])[0] || null,
    bulletStats: bulletSeed ? bulletReviewStats(bulletSeed) : null,
    statementStats: evidence ? statementReviewStats(evidence) : null,
    statementReviewMethod: evidence?.method || null,
    prompts: PROMPT_FILES.map((p) => ({ ...p, path: `${p.dir || PROMPTS_DIR}/${p.file}`, text: readRepoText(`${p.dir || PROMPTS_DIR}/${p.file}`) })),
    examples,
  };
}
