// Shareable "hook" pages: one static page + OG card per curated statement (/citizen/vota/t/<id>/).
// Build-time only (reads the public snapshot from disk).
import { readPublicJson } from "../../static-snapshot.mjs";
import { resolveBasePath } from "../../path-utils.mjs";
import { CURRENT_VERSION, VOTING_AID_VERSIONS, versionById } from "./votingAidVersions.mjs";

export const SITE_ORIGIN = (process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://votaconlachola.org").replace(/\/+$/u, "");
export const SNAPSHOT_PATH = CURRENT_VERSION.snapshot;
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

export function loadVotingAidSnapshot(versionId = CURRENT_VERSION.id) {
  return readPublicJson(versionById(versionId).snapshot, { meta: {}, parties: [], statements: [] });
}

/** Version a statement belongs to: the newest version that has it (hook pages of old versions keep working). */
export function statementVersion(statementId) {
  for (const v of VOTING_AID_VERSIONS) {
    if ((loadVotingAidSnapshot(v.id).statements || []).some((st) => st.statement_id === statementId)) return v;
  }
  return CURRENT_VERSION;
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

export function hookStatements() {
  const seen = new Set();
  return VOTING_AID_VERSIONS.flatMap((v) => loadVotingAidSnapshot(v.id).statements || []).filter(
    (st) => st.statement_id && st.text && !seen.has(st.statement_id) && seen.add(st.statement_id),
  );
}
