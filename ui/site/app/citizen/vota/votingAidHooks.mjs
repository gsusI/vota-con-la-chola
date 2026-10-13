// Shareable "hook" pages: one static page + OG card per curated statement (/citizen/vota/t/<id>/).
// Build-time only (reads the public snapshot from disk).
import { readPublicJson } from "../../static-snapshot.mjs";
import { resolveBasePath } from "../../path-utils.mjs";

export const SITE_ORIGIN = (process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://votaconlachola.org").replace(/\/+$/u, "");
export const SNAPSHOT_PATH = "citizen/data/voting_aid_generales_v2.json";
// v1: the earlier one-vote-per-statement set; kept so shared /citizen/vota/t/<id>/ links keep working.
export const LEGACY_SNAPSHOT_PATH = "citizen/data/voting_aid_generales_v1.json";
// A vote decided by this many votes or fewer gets the "se decidió por N votos" badge.
const CLOSE_MARGIN = 5;

// concern_id values from the snapshot; statements without one fall back to their id prefix.
const CONCERN_LABELS = {
  vivienda: "Vivienda",
  empleo: "Empleo y pensiones",
  coste_vida: "Coste de la vida",
  energia: "Energía",
  transporte: "Transporte",
  sanidad: "Sanidad",
  educacion: "Educación",
  seguridad_justicia: "Seguridad y justicia",
  inmigracion: "Inmigración",
  corrupcion: "Corrupción",
  igualdad: "Igualdad",
  campo_rural: "Campo y mundo rural",
  cultura: "Cultura",
  exterior: "Política exterior",
};

export function loadVotingAidSnapshot() {
  return readPublicJson(SNAPSHOT_PATH, { meta: {}, parties: [], statements: [] });
}

/** Hook data for one statement; never includes party positions (the card must not spoil the reveal). */
export function statementHook(statement) {
  const votes = (statement.votes || []).filter((v) => v.found !== false && v.totals);
  const margin = votes.length === 1 ? Math.abs((votes[0].totals.yes || 0) - (votes[0].totals.no || 0)) : null;
  return {
    id: statement.statement_id,
    text: statement.text,
    concern: statement.theme || CONCERN_LABELS[statement.concern_id || String(statement.statement_id).split("-")[0]] || null,
    closeMargin: margin !== null && margin <= CLOSE_MARGIN ? margin : null,
  };
}

export function closeMarginLabel(margin) {
  return margin === 1 ? "Se decidió por 1 voto" : `Se decidió por ${margin} votos`;
}

export function hookPagePath(id) {
  return `${resolveBasePath()}/citizen/vota/t/${id}/`;
}

export function hookImagePath(id) {
  return `${resolveBasePath()}/citizen/vota/og/${id}.png`;
}

export function hookStatements(snapshot = loadVotingAidSnapshot()) {
  const legacy = readPublicJson(LEGACY_SNAPSHOT_PATH, { statements: [] });
  const seen = new Set();
  return [...(snapshot.statements || []), ...(legacy.statements || [])].filter(
    (st) => st.statement_id && st.text && !seen.has(st.statement_id) && seen.add(st.statement_id),
  );
}
