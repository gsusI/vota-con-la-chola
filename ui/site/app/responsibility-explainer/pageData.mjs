import fs from "node:fs";
import path from "node:path";
import { resolveBasePath, withBasePath } from "../path-utils.mjs";

export const DEFAULT_SITE_ORIGIN = process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://gsusI.github.io";
export { resolveBasePath, withBasePath };

function resolveDataDir() {
  return path.resolve(process.cwd(), "public", "responsibility-explainer", "data");
}

function readJsonIfExists(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

export function loadResponsibilityExplainerManifest() {
  const payload = readJsonIfExists(path.join(resolveDataDir(), "manifest.json"));
  if (!payload || !Array.isArray(payload.cases)) {
    return {
      meta: { generated_at: "", snapshot_date: "", schema_version: "responsibility_explainer_manifest_v1", total_cases: 0 },
      cases: [],
    };
  }
  return payload;
}

export function loadResponsibilityExplainerCasePayload(caseId) {
  const safeCaseId = String(caseId || "").trim();
  if (!safeCaseId) {
    return null;
  }
  return readJsonIfExists(path.join(resolveDataDir(), `${safeCaseId}.json`));
}

export function buildResponsibilityExplainerHref(caseId) {
  return withBasePath(`/responsibility-explainer/${encodeURIComponent(String(caseId || ""))}/`);
}

export function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return "0";
  }
  return parsed.toLocaleString("es-ES");
}

export function formatDate(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "sin fecha";
  }
  const parsed = new Date(`${raw}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return raw;
  }
  return new Intl.DateTimeFormat("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}
