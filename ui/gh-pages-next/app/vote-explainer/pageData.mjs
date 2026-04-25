import fs from "node:fs";
import path from "node:path";
import { resolveBasePath, withBasePath } from "../path-utils.mjs";

export const DEFAULT_SITE_ORIGIN = process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://gsusI.github.io";
export { resolveBasePath, withBasePath };

function resolveDataDir() {
  return path.resolve(process.cwd(), "public", "vote-explainer", "data");
}

function readJsonIfExists(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

export function loadVoteExplainerManifest() {
  const payload = readJsonIfExists(path.join(resolveDataDir(), "manifest.json"));
  if (!payload || !Array.isArray(payload.votes)) {
    return { meta: { total_votes: 0, demo_public_vote_id: "" }, votes: [] };
  }
  return payload;
}

export function loadVoteExplainerPayload(publicVoteId) {
  const safeId = String(publicVoteId || "").trim();
  if (!safeId) {
    return null;
  }
  return readJsonIfExists(path.join(resolveDataDir(), `${safeId}.json`));
}

export function buildVoteExplainerHref(publicVoteId) {
  return withBasePath(`/vote-explainer/${encodeURIComponent(String(publicVoteId || ""))}/`);
}

export function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return "0";
  }
  return parsed.toLocaleString("es-ES");
}

export function formatVoteDate(value) {
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

export function caveatSeverityClass(severity) {
  if (severity === "block") {
    return "caveatBlock";
  }
  if (severity === "warn") {
    return "caveatWarn";
  }
  return "caveatInfo";
}

export function resultToneClass(status) {
  if (status === "approved" || status === "assent") {
    return "votePillApproved";
  }
  if (status === "rejected") {
    return "votePillRejected";
  }
  return "votePillNeutral";
}

export function freshnessToneClass(tier) {
  if (tier === "fresh") {
    return "votePillApproved";
  }
  if (tier === "aging" || tier === "stale") {
    return "votePillWarn";
  }
  return "votePillNeutral";
}

export function buildSiteImageUrl() {
  return `${DEFAULT_SITE_ORIGIN}${resolveBasePath()}/favicon.svg`;
}

export function buildOfficialLinks(payload) {
  const links = [];
  const seen = new Set();
  const push = (label, url) => {
    const href = String(url || "").trim();
    if (!href || seen.has(href)) {
      return;
    }
    seen.add(href);
    links.push({ label, url: href });
  };

  const event = payload?.event || {};
  const initiative = payload?.initiative || {};
  const documents = initiative?.documents?.docs || [];

  push("Fuente oficial principal", event.primary_source_url);
  push("URL oficial del evento", event.source_url);
  push("Ficha oficial de la iniciativa", initiative.url);
  for (const doc of documents) {
    push(`Documento ${doc.kind || "oficial"}`, doc.url);
  }
  return links;
}

export function topVisibleCaveat(caveats) {
  const items = Array.isArray(caveats) ? caveats : [];
  return items.find((item) => item?.severity === "block") || items.find((item) => item?.severity === "warn") || items[0] || null;
}

export function percentWidth(value, total) {
  const parsedValue = Number(value);
  const parsedTotal = Number(total);
  if (!Number.isFinite(parsedValue) || !Number.isFinite(parsedTotal) || parsedTotal <= 0) {
    return "0%";
  }
  return `${Math.max(0, Math.min(100, (parsedValue / parsedTotal) * 100)).toFixed(2)}%`;
}
