function normalizeTopicId(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeTopicText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function topicDiscoveryScore(label, key, needle) {
  const normalizedLabel = normalizeTopicText(label);
  const normalizedKey = normalizeTopicText(key);
  if (!needle || (!normalizedLabel && !normalizedKey)) {
    return null;
  }
  if (normalizedKey === needle || normalizedLabel === needle) {
    return 0;
  }

  const labelTokens = normalizedLabel.split(/[^a-z0-9]+/).filter(Boolean);
  const keyTokens = normalizedKey.split(/[^a-z0-9]+/).filter(Boolean);
  if (keyTokens.some((token) => token === needle)) {
    return 1;
  }
  if (labelTokens.some((token) => token === needle)) {
    return 2;
  }
  if (normalizedKey.startsWith(needle)) {
    return 3;
  }
  if (normalizedLabel.startsWith(needle)) {
    return 4;
  }
  if (keyTokens.some((token) => token.startsWith(needle))) {
    return 5;
  }
  if (labelTokens.some((token) => token.startsWith(needle))) {
    return 6;
  }
  if (normalizedKey.includes(needle)) {
    return 7;
  }
  if (normalizedLabel.includes(needle)) {
    return 8;
  }
  return null;
}

function trimTopicPunctuation(value) {
  return String(value || "").trim().replace(/[.:;,\s]+$/g, "").trim();
}

function capitalizeFirst(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  return text[0].toUpperCase() + text.slice(1);
}

function inferTopicProcedure(label) {
  const text = String(label || "").trim();
  if (!text) {
    return "";
  }
  if (/^Votaci[oó]n\b/i.test(text)) {
    return "Votacion";
  }
  if (/^Moci[oó]n\b/i.test(text)) {
    return "Mocion";
  }
  if (/^Proposici[oó]n no de Ley\b/i.test(text)) {
    return "PNL";
  }
  if (/^Proyecto de Ley\b/i.test(text)) {
    return "Proyecto de ley";
  }
  if (/^Ley Org[aá]nica\b/i.test(text)) {
    return "Ley organica";
  }
  if (/^Ley\b/i.test(text)) {
    return "Ley";
  }
  return "";
}

function topicProcedurePriority(procedure) {
  const normalized = normalizeTopicText(procedure);
  if (normalized === "proyecto de ley" || normalized === "ley" || normalized === "ley organica") {
    return 0;
  }
  if (normalized === "pnl" || normalized === "mocion") {
    return 1;
  }
  if (normalized === "votacion") {
    return 2;
  }
  return 3;
}

function extractTopicHeadline(label) {
  const cleaned = trimTopicPunctuation(label);
  if (!cleaned) {
    return "";
  }

  const recursivePatterns = [
    /^Votaci[oó]n(?: final de conjunto)?(?: del dictamen)? del (.+)$/i,
  ];
  for (const pattern of recursivePatterns) {
    const matched = cleaned.match(pattern);
    if (matched?.[1]) {
      const nested = extractTopicHeadline(matched[1]);
      return nested || capitalizeFirst(trimTopicPunctuation(matched[1]));
    }
  }

  const directPatterns = [
    /^Proyecto de Ley de (.+)$/i,
    /^Proyecto de Ley por la que (.+)$/i,
    /^Proyecto de Ley por el que (.+)$/i,
    /^Proposici[oó]n no de Ley .*?,\s+sobre (.+)$/i,
    /^Proposici[oó]n no de Ley .*?,\s+relativa a (.+)$/i,
    /^Proposici[oó]n no de Ley .*?,\s+de (.+)$/i,
    /^Moci[oó]n consecuencia de interpelaci[oó]n urgente .*?,\s+sobre (.+)$/i,
    /^Moci[oó]n consecuencia de interpelaci[oó]n urgente .*?,\s+relativa a (.+)$/i,
    /^Moci[oó]n consecuencia de interpelaci[oó]n urgente .*?,\s+para (.+)$/i,
  ];
  for (const pattern of directPatterns) {
    const matched = cleaned.match(pattern);
    if (!matched?.[1]) {
      continue;
    }
    let headline = trimTopicPunctuation(matched[1]);
    headline = headline.replace(/^cu[aá]l es la\s+/i, "");
    return capitalizeFirst(headline);
  }

  return capitalizeFirst(cleaned);
}

function topicHeadlineFamilyKey(headline) {
  return normalizeTopicText(headline)
    .replace(/^(el|la|los|las|lo|un|una|unos|unas)\s+/i, "")
    .replace(/\bdel\b/gi, "de el")
    .replace(/\s+/g, " ")
    .trim();
}

const TOPIC_CLAIM_STOPWORDS = new Set([
  "a",
  "al",
  "ante",
  "bajo",
  "cual",
  "como",
  "con",
  "contra",
  "de",
  "del",
  "desde",
  "durante",
  "e",
  "el",
  "ella",
  "ellas",
  "ellos",
  "en",
  "entre",
  "es",
  "esa",
  "esas",
  "ese",
  "esos",
  "esta",
  "estas",
  "este",
  "estos",
  "hacia",
  "hasta",
  "la",
  "las",
  "lo",
  "los",
  "mediante",
  "o",
  "para",
  "pero",
  "por",
  "que",
  "se",
  "segun",
  "sin",
  "sobre",
  "su",
  "sus",
  "tras",
  "u",
  "un",
  "una",
  "unos",
  "unas",
  "y",
]);

const TOPIC_CLAIM_NOISE_TOKENS = new Set([
  "efectiva",
  "efectivas",
  "efectivo",
  "efectivos",
  "fracaso",
  "gobierno",
  "materia",
  "politica",
]);

function normalizeTopicClaimToken(token) {
  const normalized = normalizeTopicText(token).trim();
  if (!normalized || normalized.length < 3 || /^\d+$/.test(normalized)) {
    return "";
  }
  if (/^garantiz/.test(normalized) || /^asegur/.test(normalized)) {
    return "asegurar";
  }
  return normalized;
}

function topicHeadlineNearDuplicateKey(headline, matchedConcernIds = []) {
  const tokens = normalizeTopicText(headline)
    .split(/[^a-z0-9]+/)
    .map((token) => normalizeTopicClaimToken(token))
    .filter(Boolean)
    .filter((token) => !TOPIC_CLAIM_STOPWORDS.has(token))
    .filter((token) => !TOPIC_CLAIM_NOISE_TOKENS.has(token));
  if (tokens.length < 3) {
    return "";
  }

  const tailTokens = [];
  for (let index = tokens.length - 1; index >= 0 && tailTokens.length < 3; index -= 1) {
    const token = tokens[index];
    if (tailTokens[0] === token) {
      continue;
    }
    tailTokens.unshift(token);
  }
  if (tailTokens.length < 3) {
    return "";
  }

  const concernKey = Array.isArray(matchedConcernIds)
    ? matchedConcernIds.map((concernId) => normalizeTopicText(concernId)).filter(Boolean).sort().join("+")
    : "";
  return concernKey ? `${concernKey}:${tailTokens.join(" ")}` : tailTokens.join(" ");
}

function compareConcernPackTopicRows(a, b) {
  return (
    b.score - a.score
    || b.matchedConcernCount - a.matchedConcernCount
    || b.evidenceCountTotal - a.evidenceCountTotal
    || b.pointCount - a.pointCount
    || String(a.topicHeadline || a.label || "").localeCompare(String(b.topicHeadline || b.label || ""))
  );
}

function buildConcernPackFamilyVariant(row) {
  return {
    topicId: normalizeTopicId(row?.topicId),
    label: String(row?.label || "").trim(),
    topicHeadline: String(row?.topicHeadline || row?.label || "").trim(),
    topicProcedure: String(row?.topicProcedure || "").trim(),
  };
}

function compareConcernPackFamilyVariants(a, b) {
  return (
    topicProcedurePriority(a?.topicProcedure) - topicProcedurePriority(b?.topicProcedure)
    || String(a?.topicHeadline || a?.label || "").localeCompare(String(b?.topicHeadline || b?.label || ""))
    || String(a?.label || "").localeCompare(String(b?.label || ""))
    || normalizeTopicId(a?.topicId) - normalizeTopicId(b?.topicId)
  );
}

function sortConcernPackFamilyVariants(variants, representativeTopicId = 0) {
  const normalizedRepresentativeTopicId = normalizeTopicId(representativeTopicId);
  return [...(Array.isArray(variants) ? variants : [])].sort((a, b) => (
    (normalizeTopicId(a?.topicId) === normalizedRepresentativeTopicId ? 0 : 1)
    - (normalizeTopicId(b?.topicId) === normalizedRepresentativeTopicId ? 0 : 1)
    || compareConcernPackFamilyVariants(a, b)
  ));
}

export function buildTopicPreviewSelections({ topicIds, topicsById }) {
  const out = [];
  const seen = new Set();

  for (const rawTopicId of Array.isArray(topicIds) ? topicIds : []) {
    const topicId = normalizeTopicId(rawTopicId);
    if (!topicId || seen.has(topicId)) {
      continue;
    }
    seen.add(topicId);

    const topic = topicsById?.get?.(topicId);
    const label = String(topic?.label || "").trim();
    const key = String(topic?.key || "").trim();
    if (!label && !key) {
      continue;
    }

    out.push({
      topicId,
      label: label || key,
      key,
    });
  }

  return out;
}

export function buildTopicDiscoverySelections({ topics, rawValue, limit = 12 }) {
  const needle = normalizeTopicText(rawValue);
  if (!needle || needle.length < 3 || !Array.isArray(topics)) {
    return [];
  }

  const out = [];
  const seen = new Set();
  for (const topic of topics) {
    const topicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
    if (!topicId || seen.has(topicId)) {
      continue;
    }
    seen.add(topicId);

    const label = String(topic?.label || topic?.topic_label || "").trim();
    const key = String(topic?.key || topic?.topic_key || "").trim();
    const score = topicDiscoveryScore(label, key, needle);
    if (score === null) {
      continue;
    }
    out.push({
      topicId,
      label: label || key,
      key,
      score,
      length_rank: String(label || key).length || 0,
    });
  }

  out.sort((a, b) => (
    a.score - b.score
    || a.length_rank - b.length_rank
    || String(a.label || "").localeCompare(String(b.label || ""))
  ));
  return out.slice(0, Math.max(1, Number(limit) || 12)).map(({ score, length_rank, ...topic }) => topic);
}

function concernMatchScore(label, keywords, primaryTerms = []) {
  const haystack = normalizeTopicText(label);
  if (!haystack || !Array.isArray(keywords) || !keywords.length) {
    return 0;
  }
  let score = 0;
  for (const primaryTerm of primaryTerms) {
    const primaryNeedle = normalizeTopicText(primaryTerm);
    if (!primaryNeedle || primaryNeedle.length < 3) {
      continue;
    }
    if (haystack.includes(primaryNeedle)) {
      score += primaryNeedle.length > 8 ? 8 : 6;
    }
  }
  for (const keyword of keywords) {
    const needle = normalizeTopicText(keyword);
    if (!needle || needle.length < 3) {
      continue;
    }
    if (haystack.includes(needle)) {
      score += needle.length > 8 ? 3 : 2;
    }
  }
  return score;
}

function concernPrimaryTerms(concern) {
  return [
    String(concern?.label || "").trim(),
    ...((Array.isArray(concern?.keywords) ? concern.keywords : []).slice(0, 1)),
  ].filter(Boolean);
}

function matchedConcernSummary(concerns) {
  const items = Array.isArray(concerns) ? concerns.filter(Boolean) : [];
  if (!items.length) {
    return "";
  }
  const labels = items.map((concern) => String(concern?.label || concern?.id || "").trim()).filter(Boolean);
  const descriptions = items.map((concern) => String(concern?.description || "").trim()).filter(Boolean);
  const firstLabel = labels[0] || "esta preocupación";
  const firstDescription = descriptions[0] || "";
  if (items.length === 1) {
    return firstDescription ? `Encaja por ${firstLabel}: ${firstDescription}` : `Encaja por ${firstLabel}.`;
  }
  const extraLabels = labels.length === 2
    ? labels[1]
    : `${labels.slice(1, -1).join(", ")} y ${labels.at(-1)}`;
  if (firstDescription) {
    return `Cruza ${firstLabel} y ${extraLabels}. ${firstDescription}`;
  }
  return `Cruza ${labels.join(", ")}.`;
}

function collapseConcernPackTopicFamilies(rows, limit = 12) {
  const groups = new Map();
  for (const row of Array.isArray(rows) ? rows : []) {
    const exactFamilyKey = topicHeadlineFamilyKey(row?.topicHeadline || row?.label || row?.key || "");
    const nearDuplicateKey = topicHeadlineNearDuplicateKey(row?.topicHeadline || row?.label || row?.key || "", row?.matchedConcernIds);
    const groupKey = nearDuplicateKey || exactFamilyKey || `topic:${normalizeTopicId(row?.topicId)}`;
    const current = groups.get(groupKey);
    if (!current) {
      groups.set(groupKey, {
        ...row,
        familyKey: exactFamilyKey || groupKey,
        familyNearKey: nearDuplicateKey || "",
        familyExactKeys: [exactFamilyKey].filter(Boolean),
        familyTopicIds: [normalizeTopicId(row?.topicId)],
        familyLabels: [String(row?.label || "").trim()].filter(Boolean),
        familyProcedures: [String(row?.topicProcedure || "").trim()].filter(Boolean),
        familyCount: 1,
        familyVariants: [buildConcernPackFamilyVariant(row)],
      });
      continue;
    }

    current.familyTopicIds = Array.from(new Set([
      ...current.familyTopicIds,
      normalizeTopicId(row?.topicId),
    ].filter((topicId) => topicId > 0)));
    current.familyLabels = Array.from(new Set([
      ...current.familyLabels,
      String(row?.label || "").trim(),
    ].filter(Boolean)));
    current.familyProcedures = Array.from(new Set([
      ...current.familyProcedures,
      String(row?.topicProcedure || "").trim(),
    ].filter(Boolean)));
    current.familyCount = current.familyTopicIds.length;
    current.familyExactKeys = Array.from(new Set([
      ...current.familyExactKeys,
      exactFamilyKey,
    ].filter(Boolean)));
    if (!current.familyNearKey && nearDuplicateKey) {
      current.familyNearKey = nearDuplicateKey;
    }
    current.familyVariants = Array.from(new Map([
      ...current.familyVariants.map((variant) => [normalizeTopicId(variant?.topicId), variant]),
      [normalizeTopicId(row?.topicId), buildConcernPackFamilyVariant(row)],
    ]).values());

    const currentPriority = topicProcedurePriority(current.topicProcedure);
    const rowPriority = topicProcedurePriority(row?.topicProcedure);
    const shouldReplace = (
      rowPriority < currentPriority
      || (
        rowPriority === currentPriority
        && (
          toInt(row?.matchedConcernIds?.length) > toInt(current.matchedConcernIds?.length)
          || (
            toInt(row?.matchedConcernIds?.length) === toInt(current.matchedConcernIds?.length)
            && (
              toInt(row?.evidenceCountTotal) > toInt(current.evidenceCountTotal)
              || (
                toInt(row?.evidenceCountTotal) === toInt(current.evidenceCountTotal)
                && toInt(row?.pointCount) > toInt(current.pointCount)
              )
            )
          )
        )
      )
    );
    if (shouldReplace) {
      groups.set(groupKey, {
        ...row,
        familyKey: current.familyKey,
        familyNearKey: current.familyNearKey,
        familyExactKeys: current.familyExactKeys,
        familyTopicIds: current.familyTopicIds,
        familyLabels: current.familyLabels,
        familyProcedures: current.familyProcedures,
        familyCount: current.familyCount,
        familyVariants: current.familyVariants,
      });
    }
  }

  const out = Array.from(groups.values()).map((row) => {
    const familyExactKeys = Array.isArray(row.familyExactKeys) ? row.familyExactKeys.filter(Boolean) : [];
    const familyMatchMode = row.familyCount > 1 && familyExactKeys.length > 1 ? "near_duplicate" : "exact";
    return {
      ...row,
      familyKey: familyMatchMode === "near_duplicate"
        ? (row.familyNearKey || row.familyKey)
        : (familyExactKeys[0] || row.familyKey),
      familyMatchMode,
    };
  });
  out.sort(compareConcernPackTopicRows);
  return out.slice(0, Math.max(1, Number(limit) || 12));
}

export function buildConcernEntries({ topics, concerns }) {
  const topicList = Array.isArray(topics) ? topics : [];
  const concernList = Array.isArray(concerns) ? concerns : [];
  const out = [];

  for (const concern of concernList) {
    const concernId = String(concern?.id || "").trim();
    if (!concernId) {
      continue;
    }
    const label = String(concern?.label || concernId).trim();
    const description = String(concern?.description || "").trim();
    const keywords = Array.isArray(concern?.keywords) ? concern.keywords : [];
    const matchedTopicIds = [];

    for (const topic of topicList) {
      const topicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
      if (!topicId) {
        continue;
      }
      if (concernMatchScore(topic?.label || topic?.topic_label || "", keywords) > 0) {
        matchedTopicIds.push(topicId);
      }
    }

    out.push({
      id: concernId,
      label,
      description,
      keywords,
      topicIds: matchedTopicIds,
      topicCount: matchedTopicIds.length,
    });
  }

  out.sort((a, b) => (
    b.topicCount - a.topicCount
    || String(a.label || "").localeCompare(String(b.label || ""))
  ));
  return out;
}

export function buildConcernTopicSelections({ topics, concern, limit = 12 }) {
  const topicList = Array.isArray(topics) ? topics : [];
  const keywords = Array.isArray(concern?.keywords) ? concern.keywords : [];
  if (!keywords.length) {
    return [];
  }
  const primaryTerms = concernPrimaryTerms(concern);

  const out = [];
  for (const topic of topicList) {
    const topicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
    if (!topicId) {
      continue;
    }
    const label = String(topic?.label || topic?.topic_label || "").trim();
    const key = String(topic?.key || topic?.topic_key || "").trim();
    const score = concernMatchScore(label, keywords, primaryTerms);
    if (!score) {
      continue;
    }
    out.push({
      topicId,
      label: label || key,
      key,
      score,
      evidenceCountTotal: toInt(topic?.evidenceCountTotal || topic?.evidence_count_total),
      pointCount: toInt(topic?.pointCount || topic?.point_count),
    });
  }

  out.sort((a, b) => (
    b.score - a.score
    || b.evidenceCountTotal - a.evidenceCountTotal
    || b.pointCount - a.pointCount
    || String(a.label || "").localeCompare(String(b.label || ""))
  ));
  return out
    .slice(0, Math.max(1, Number(limit) || 12))
    .map(({ score, evidenceCountTotal, pointCount, ...topic }) => topic);
}

export function buildConcernPackEntries({ concernEntries, packs }) {
  const concernList = Array.isArray(concernEntries) ? concernEntries : [];
  const concernsById = new Map(
    concernList
      .map((concern) => [String(concern?.id || "").trim(), concern])
      .filter(([concernId]) => concernId),
  );
  const packList = Array.isArray(packs) ? packs : [];
  const out = [];

  for (const pack of packList) {
    const packId = String(pack?.id || "").trim();
    if (!packId) {
      continue;
    }
    const label = String(pack?.label || packId).trim();
    const tradeoff = String(pack?.tradeoff || "").trim();
    const concernIds = Array.isArray(pack?.concern_ids)
      ? pack.concern_ids.map((concernId) => String(concernId || "").trim()).filter(Boolean)
      : [];
    const matchedConcerns = concernIds
      .map((concernId) => concernsById.get(concernId))
      .filter(Boolean);
    const topicIds = Array.from(new Set(
      matchedConcerns.flatMap((concern) => (
        Array.isArray(concern?.topicIds)
          ? concern.topicIds.map((topicId) => normalizeTopicId(topicId)).filter((topicId) => topicId > 0)
          : []
      )),
    ));

    out.push({
      id: packId,
      label,
      tradeoff,
      concernIds: matchedConcerns.map((concern) => String(concern?.id || "").trim()).filter(Boolean),
      concernLabels: matchedConcerns.map((concern) => String(concern?.label || concern?.id || "").trim()).filter(Boolean),
      concerns: matchedConcerns.map((concern) => ({
        id: String(concern?.id || "").trim(),
        label: String(concern?.label || concern?.id || "").trim(),
        description: String(concern?.description || "").trim(),
        topicCount: toInt(concern?.topicCount),
      })),
      topicIds,
      topicCount: topicIds.length,
    });
  }

  return out;
}

export function buildConcernPackTopicSelections({ topics, concernsById, pack, limit = 12 }) {
  const topicList = Array.isArray(topics) ? topics : [];
  const packConcernIds = Array.isArray(pack?.concernIds)
    ? pack.concernIds
    : (Array.isArray(pack?.concern_ids) ? pack.concern_ids : []);
  const concernList = packConcernIds
    .map((concernId) => concernsById?.get?.(String(concernId || "").trim()) || null)
    .filter(Boolean);
  if (!concernList.length) {
    return [];
  }

  const out = [];
  for (const topic of topicList) {
    const topicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
    if (!topicId) {
      continue;
    }
    const label = String(topic?.label || topic?.topic_label || "").trim();
    const key = String(topic?.key || topic?.topic_key || "").trim();
    let score = 0;
    const matchedConcernLabels = [];
    const matchedConcernIds = [];
    const matchedConcerns = [];

    for (const concern of concernList) {
      const keywords = Array.isArray(concern?.keywords) ? concern.keywords : [];
      const concernScore = concernMatchScore(label, keywords, concernPrimaryTerms(concern));
      if (!concernScore) {
        continue;
      }
      score += concernScore;
      matchedConcernIds.push(String(concern?.id || "").trim());
      matchedConcernLabels.push(String(concern?.label || concern?.id || "").trim());
      matchedConcerns.push({
        id: String(concern?.id || "").trim(),
        label: String(concern?.label || concern?.id || "").trim(),
        description: String(concern?.description || "").trim(),
      });
    }
    if (!score) {
      continue;
    }
    const topicHeadline = extractTopicHeadline(label || key);
    const topicProcedure = inferTopicProcedure(label || key);
    out.push({
      topicId,
      label: label || key,
      key,
      topicHeadline,
      topicProcedure,
      score,
      matchedConcernIds,
      matchedConcernLabels,
      matchedConcernDescriptions: matchedConcerns.map((concern) => concern.description).filter(Boolean),
      editorialSummary: matchedConcernSummary(matchedConcerns),
      matchedConcernCount: matchedConcernIds.length,
      evidenceCountTotal: toInt(topic?.evidenceCountTotal || topic?.evidence_count_total),
      pointCount: toInt(topic?.pointCount || topic?.point_count),
    });
  }

  return collapseConcernPackTopicFamilies(out, limit).map(({
    score,
    matchedConcernCount,
    evidenceCountTotal,
    pointCount,
    familyNearKey,
    familyExactKeys,
    familyVariants,
    ...topic
  }) => ({
    ...topic,
    ...(topic.familyCount > 1 && Array.isArray(familyVariants) && familyVariants.length
      ? { familyVariants: sortConcernPackFamilyVariants(familyVariants, topic.topicId) }
      : {}),
  }));
}

export function resolveTopicDiscoveryOriginHighlight({ topic, originTopicId }) {
  const normalizedOriginTopicId = normalizeTopicId(originTopicId);
  if (!normalizedOriginTopicId) {
    return {
      isOriginFamily: false,
      isOriginVariant: false,
      representativeTopicId: normalizeTopicId(topic?.topicId || topic?.topic_id),
      variantTopicIds: Array.isArray(topic?.familyTopicIds)
        ? topic.familyTopicIds.map((topicId) => normalizeTopicId(topicId)).filter((topicId) => topicId > 0)
        : [],
    };
  }
  const representativeTopicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
  const variantTopicIds = Array.isArray(topic?.familyTopicIds)
    ? topic.familyTopicIds.map((topicId) => normalizeTopicId(topicId)).filter((topicId) => topicId > 0)
    : [];
  const isOriginVariant = representativeTopicId === normalizedOriginTopicId;
  const isOriginFamily = isOriginVariant || variantTopicIds.includes(normalizedOriginTopicId);
  return {
    isOriginFamily,
    isOriginVariant,
    representativeTopicId,
    variantTopicIds,
  };
}

export function resolveTopicDiscoveryOriginTargetTopicId({ topics, originTopicId }) {
  for (const topic of Array.isArray(topics) ? topics : []) {
    const highlight = resolveTopicDiscoveryOriginHighlight({ topic, originTopicId });
    if (highlight.isOriginFamily) {
      return normalizeTopicId(topic?.topicId || topic?.topic_id);
    }
  }
  return 0;
}

export function resolveTopicDiscoveryOriginResumeNotice({ topics, originTopicId }) {
  const normalizedOriginTopicId = normalizeTopicId(originTopicId);
  if (!normalizedOriginTopicId) {
    return null;
  }

  for (const topic of Array.isArray(topics) ? topics : []) {
    const highlight = resolveTopicDiscoveryOriginHighlight({ topic, originTopicId: normalizedOriginTopicId });
    if (!highlight.isOriginFamily) {
      continue;
    }

    const representativeTopicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
    const familyHeadline = String(topic?.topicHeadline || topic?.label || topic?.key || "").trim();
    const familyLabel = String(topic?.label || topic?.topicHeadline || topic?.key || "").trim();
    const familyCount = toInt(topic?.familyCount || 0);
    const familyMatchMode = String(topic?.familyMatchMode || "exact").trim() || "exact";
    const familyProcedures = Array.isArray(topic?.familyProcedures)
      ? topic.familyProcedures.map((value) => String(value || "").trim()).filter(Boolean)
      : [];

    let variant = null;
    if (representativeTopicId === normalizedOriginTopicId) {
      variant = {
        topicId: representativeTopicId,
        label: familyLabel,
        topicHeadline: familyHeadline,
        topicProcedure: String(topic?.topicProcedure || "").trim(),
      };
    } else if (Array.isArray(topic?.familyVariants)) {
      variant = topic.familyVariants.find((item) => normalizeTopicId(item?.topicId || item?.topic_id) === normalizedOriginTopicId) || null;
    }

    const variantTopicId = normalizeTopicId(variant?.topicId || variant?.topic_id || normalizedOriginTopicId);
    const variantLabel = String(variant?.label || variant?.topicHeadline || variant?.key || "").trim() || `#${variantTopicId}`;
    const variantHeadline = String(variant?.topicHeadline || variant?.label || "").trim() || variantLabel;
    const variantProcedure = String(variant?.topicProcedure || "").trim();

    return {
      originTopicId: normalizedOriginTopicId,
      representativeTopicId,
      familyHeadline: familyHeadline || familyLabel || `#${representativeTopicId}`,
      familyLabel: familyLabel || familyHeadline || `#${representativeTopicId}`,
      familyCount,
      familyMatchMode,
      familyProcedures,
      variantTopicId,
      variantHeadline,
      variantLabel,
      variantProcedure,
      isRepresentativeVariant: representativeTopicId === variantTopicId,
    };
  }

  return null;
}

export function resolveTopicDiscoveryOriginVariantSelection({ topics, originTopicId }) {
  const normalizedOriginTopicId = normalizeTopicId(originTopicId);
  if (!normalizedOriginTopicId) {
    return null;
  }

  for (const topic of Array.isArray(topics) ? topics : []) {
    const highlight = resolveTopicDiscoveryOriginHighlight({ topic, originTopicId: normalizedOriginTopicId });
    if (!highlight.isOriginFamily) {
      continue;
    }

    const representativeTopicId = normalizeTopicId(topic?.topicId || topic?.topic_id);
    if (representativeTopicId === normalizedOriginTopicId) {
      const label = String(topic?.label || topic?.topicHeadline || topic?.key || "").trim();
      if (!label) {
        return null;
      }
      return {
        topicId: representativeTopicId,
        label,
        key: String(topic?.key || "").trim(),
        topicHeadline: String(topic?.topicHeadline || label).trim(),
        topicProcedure: String(topic?.topicProcedure || "").trim(),
      };
    }

    if (!Array.isArray(topic?.familyVariants)) {
      return null;
    }
    const variant = topic.familyVariants.find((item) => normalizeTopicId(item?.topicId || item?.topic_id) === normalizedOriginTopicId);
    if (!variant) {
      return null;
    }
    const label = String(variant?.label || variant?.topicHeadline || variant?.key || "").trim();
    if (!label) {
      return null;
    }
    return {
      topicId: normalizeTopicId(variant?.topicId || variant?.topic_id),
      label,
      key: String(variant?.key || "").trim(),
      topicHeadline: String(variant?.topicHeadline || label).trim(),
      topicProcedure: String(variant?.topicProcedure || "").trim(),
    };
  }

  return null;
}

export function applyTopicPreviewSelection({ prevState, selection, sourceMode }) {
  const next = {
    ...(prevState || {}),
  };
  const exactTopic = String(selection?.label || selection?.key || "").trim();
  const exactTopicId = normalizeTopicId(selection?.topicId || selection?.topic_id);
  if (!exactTopic) {
    return next;
  }

  next.topic = exactTopic;
  next.topicId = exactTopicId;
  if (String(sourceMode || "") === "pack_discovery") {
    next.originPack = String(prevState?.pack || "").trim();
    next.originConcern = "";
    next.originTopicId = exactTopicId;
  } else if (String(sourceMode || "") === "concern_discovery") {
    next.originPack = "";
    next.originConcern = String(prevState?.concern || "").trim();
    next.originTopicId = exactTopicId;
  } else {
    next.originPack = "";
    next.originConcern = "";
    next.originTopicId = 0;
  }
  if (String(sourceMode || "").endsWith("_discovery")) {
    next.concern = "";
    next.pack = "";
  }
  if (String(sourceMode || "").startsWith("q_")) {
    next.q = "";
    next.searchMode = "auto";
  }

  return next;
}
