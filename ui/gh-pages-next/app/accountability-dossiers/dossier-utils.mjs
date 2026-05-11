import { withBasePath } from "../path-utils.mjs";
import { readPublicJson } from "../static-snapshot.mjs";

export const DOSSIER_DATA_PATH = "/accountability-dossiers/data/dossiers.json";
export const LEDGER_DATA_PATH = "/accountability-dossiers/data/ledger.json";

export function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

export function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function formatRole(role) {
  const labels = {
    abstained: "abstención",
    appointed: "nombró",
    approved: "aprobó",
    audited: "auditó",
    contracted: "contrató",
    current_owner: "responsable actual",
    delegated: "delegó",
    delegated_to: "delegó",
    dismissed: "cesó",
    enforced: "ejecutó",
    funded: "financió",
    implemented: "implementó",
    proposed: "propuso",
    published: "publicó",
    responsible: "responsable",
    subsidized: "subvencionó",
    unknown: "sin señal",
    voted_against: "votó no",
    voted_for: "votó sí",
  };
  return labels[role] || String(role || "sin rol").replaceAll("_", " ");
}

export function topPairs(map, limit = 4) {
  return Object.entries(safeObject(map))
    .map(([label, count]) => ({ label, count: Number(count) || 0 }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
    .slice(0, limit);
}

function stableHash(value) {
  let hash = 5381;
  for (const char of String(value || "")) {
    hash = (hash * 33) ^ char.charCodeAt(0);
  }
  return (hash >>> 0).toString(36);
}

export function dossierSlug(value) {
  const raw = String(value || "unknown");
  const base =
    raw
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 96) || "item";
  return `${base}-${stableHash(raw)}`;
}

export function actorSlug(actor) {
  return dossierSlug(actor?.actor_key || actor?.actor_label || "actor");
}

export function issueSlug(issue) {
  return dossierSlug(issue?.issue_id || issue?.label || "issue");
}

export function actorDossierHref(actor) {
  return withBasePath(`/accountability-dossiers/actors/${actorSlug(actor)}/`);
}

export function issueDossierHref(issue) {
  return withBasePath(`/accountability-dossiers/issues/${issueSlug(issue)}/`);
}

export function loadDossierPayload() {
  return readPublicJson(DOSSIER_DATA_PATH, {
    meta: {},
    coverage: {},
    actors: [],
    issues: [],
  });
}

export function loadLedgerPayload() {
  return readPublicJson(LEDGER_DATA_PATH, {
    issues: [],
  });
}

export function actorKeyFromEntry(entry) {
  const record = safeObject(entry);
  for (const field of ["person_id", "party_id", "parliamentary_group_id", "institution_id", "org_unit_id", "position_id"]) {
    const value = record[field];
    if (value !== null && value !== undefined && value !== "") {
      return `${field}:${value}`;
    }
  }
  const actorKind = String(record.actor_kind || "unknown").trim() || "unknown";
  const actorLabel = String(record.actor_label || "").trim().toLocaleLowerCase("es");
  return `${actorKind}:label:${actorLabel}`;
}

export function allLedgerEntries(ledger) {
  return safeArray(ledger?.issues).flatMap((issue) =>
    safeArray(issue.entries).map((entry) => ({
      ...entry,
      issue_id: issue.issue_id,
      issue_label: issue.label,
      issue_scope: issue.scope,
    })),
  );
}

export function findActorBySlug(payload, slug) {
  return safeArray(payload?.actors).find((actor) => actorSlug(actor) === slug) || null;
}

export function findIssueBySlug(payload, slug) {
  return safeArray(payload?.issues).find((issue) => issueSlug(issue) === slug) || null;
}

export function findIssueById(payload, issueId) {
  return safeArray(payload?.issues).find((issue) => issue.issue_id === issueId) || null;
}
