import fs from "node:fs";
import path from "node:path";
import { XRAY_KIND_META, XRAY_KIND_ORDER } from "./xrayKinds.mjs";

function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDateValue(value) {
  return String(value || "").trim();
}

export function resolveXrayDataPath() {
  return path.resolve(process.cwd(), "public", "people", "data", "xray.json");
}

export function loadXrayPayload() {
  const dataPath = resolveXrayDataPath();
  if (!fs.existsSync(dataPath)) {
    return null;
  }
  const raw = fs.readFileSync(dataPath, "utf-8");
  return JSON.parse(raw);
}

export function buildXrayKindSummaries(payload) {
  return XRAY_KIND_ORDER.map((kind) => {
    const meta = XRAY_KIND_META[kind];
    const groups = Array.isArray(payload?.groups?.[kind]) ? payload.groups[kind] : [];
    const topGroup = groups.reduce((best, group) => {
      if (!best) {
        return group;
      }
      const bestCount = toInt(best?.person_count);
      const groupCount = toInt(group?.person_count);
      if (groupCount !== bestCount) {
        return groupCount > bestCount ? group : best;
      }
      const bestLabel = String(best?.label || "");
      const groupLabel = String(group?.label || "");
      return groupLabel.localeCompare(bestLabel, "es") < 0 ? group : best;
    }, null);
    const latestActionDate = groups.reduce((best, group) => {
      const candidate = formatDateValue(group?.last_action_date);
      if (!candidate) {
        return best;
      }
      return !best || candidate > best ? candidate : best;
    }, "");

    return {
      ...meta,
      groupCount: groups.length,
      latestActionDate,
      topGroupLabel: String(topGroup?.label || "").trim(),
      topGroupPeople: toInt(topGroup?.person_count),
    };
  });
}
