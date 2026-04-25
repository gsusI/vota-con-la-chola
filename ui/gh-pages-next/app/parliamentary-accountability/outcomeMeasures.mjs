function normalizeInlineText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function compactInlineText(value, maxLen = 180) {
  const text = normalizeInlineText(value);
  if (!text) {
    return "";
  }
  if (text.length <= maxLen) {
    return text;
  }
  const hard = Math.max(18, maxLen - 3);
  const sliced = text.slice(0, hard);
  const lastSpace = sliced.lastIndexOf(" ");
  const trimmed = lastSpace > 24 ? sliced.slice(0, lastSpace) : sliced;
  return `${trimmed}...`;
}

function normalizeSupportSide(value) {
  const key = normalizeInlineText(value).toLowerCase();
  if (key === "yes" || key === "no" || key === "mixed") {
    return key;
  }
  return "unknown";
}

export function normalizeOutcomeMeasurePreviews(row, { limit = 2 } = {}) {
  const rawMeasures = Array.isArray(row?.initiative_measures) ? row.initiative_measures : [];
  const previews = rawMeasures
    .map((measure) => {
      const title = compactInlineText(measure?.title, 140);
      const summary = compactInlineText(measure?.summary, 200);
      const policyArea = compactInlineText(measure?.policy_area || measure?.policyArea, 72);
      if (!title && !summary) {
        return null;
      }
      const rank = Number(measure?.rank);
      return {
        rank: Number.isFinite(rank) ? rank : 0,
        title,
        summary,
        policyArea,
        status: normalizeInlineText(measure?.status).toLowerCase() || "unknown",
        supportSide: normalizeSupportSide(measure?.support_side || measure?.supportSide),
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      const rankDiff = (left?.rank || 0) - (right?.rank || 0);
      if (rankDiff !== 0) {
        return rankDiff;
      }
      return String(left?.title || "").localeCompare(String(right?.title || ""), "es");
    });

  const safeLimit = Number(limit);
  if (!Number.isFinite(safeLimit) || safeLimit <= 0) {
    return previews;
  }
  return previews.slice(0, safeLimit);
}

export function buildOutcomeInitiativeSearchText(row, { limit = 6 } = {}) {
  const parts = [
    row?.initiative_id,
    row?.initiative_expediente,
    row?.initiative_title,
  ];
  for (const measure of normalizeOutcomeMeasurePreviews(row, { limit })) {
    parts.push(measure.title, measure.summary, measure.policyArea, measure.status, measure.supportSide);
  }
  return parts.map((part) => normalizeInlineText(part)).filter(Boolean).join(" ");
}
