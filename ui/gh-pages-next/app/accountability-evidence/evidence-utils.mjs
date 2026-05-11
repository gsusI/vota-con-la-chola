import { withBasePath } from "../path-utils.mjs";
import { readPublicJson } from "../static-snapshot.mjs";
import { dossierSlug, safeArray, safeObject } from "../accountability-dossiers/dossier-utils.mjs";

export { safeArray, safeObject };

export const EVIDENCE_API_DATA_PATH = "/accountability-evidence/data/evidence-api.json";

export function loadEvidenceApiPayload() {
  return readPublicJson(EVIDENCE_API_DATA_PATH, {
    meta: {},
    coverage: {},
    question_templates: [],
    actor_answers: [],
    issue_answers: [],
    issue_clusters: [],
    gap_answers: [],
    qa_answers: [],
    indexes: {},
  });
}

export function qaAnswerSlug(answer) {
  return dossierSlug(answer?.answer_id || answer?.question || "qa-answer");
}

export function qaAnswerHref(answer) {
  return withBasePath(`/accountability-evidence/questions/${qaAnswerSlug(answer)}/`);
}

export function findQaAnswerBySlug(payload, slug) {
  return safeArray(payload?.qa_answers).find((answer) => qaAnswerSlug(answer) === slug) || null;
}
