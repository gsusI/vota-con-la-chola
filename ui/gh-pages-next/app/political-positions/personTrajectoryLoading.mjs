function normalizeMode(mode) {
  return String(mode || "person") === "party" ? "party" : "person";
}

function hasTextValue(value) {
  return String(value || "").trim().length > 0;
}

function normalizeSort(value) {
  return String(value || "person").trim().toLowerCase();
}

function normalizeSearchMode(value) {
  const normalized = String(value || "auto").trim().toLowerCase();
  if (normalized === "topic" || normalized === "person") {
    return normalized;
  }
  return "auto";
}

function normalizeInt(value, fallback = 180) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeTopicId(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function normalizeTextFilter(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function normalizedChunkList(chunk, field) {
  return Array.isArray(chunk?.[field])
    ? chunk[field].map((value) => String(value || "").trim().toLowerCase()).filter(Boolean)
    : [];
}

function normalizedChunkIds(values) {
  return Array.isArray(values)
    ? values.map((value) => String(value || "").trim()).filter(Boolean)
    : [];
}

function normalizedTopicIds(values) {
  return Array.isArray(values)
    ? values
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value) && value > 0)
    : [];
}

function intersectChunkIdGroups(groups) {
  const normalizedGroups = Array.isArray(groups)
    ? groups
      .map((group) => normalizedChunkIds(group))
      .filter((group) => group.length)
    : [];
  if (!normalizedGroups.length) {
    return null;
  }
  return normalizedGroups.slice(1).reduce(
    (acc, group) => acc.filter((chunkId) => group.includes(chunkId)),
    normalizedGroups[0],
  );
}

function chunkListMayContain(chunk, field, filterValue) {
  const needles = normalizeTextFilter(filterValue)
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean);
  if (!needles.length) {
    return true;
  }
  const values = normalizedChunkList(chunk, field);
  if (!values.length) {
    return true;
  }
  return needles.every((needle) => values.some((value) => value.includes(needle)));
}

function queryTokensForChunkPreselection(value) {
  const normalized = normalizeTextFilter(value);
  if (!normalized || /\d/.test(normalized)) {
    return [];
  }
  const tokens = normalized
    .split(/[^a-z]+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2);
  return Array.from(new Set(tokens));
}

function queryCandidateChunkIdsFromIndexMap(indexMap, filterValue) {
  const needles = normalizeTextFilter(filterValue)
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean);
  if (!needles.length || !indexMap || typeof indexMap !== "object") {
    return null;
  }

  const candidateGroups = [];
  for (const needle of needles) {
    const chunkIds = Object.entries(indexMap)
      .filter(([token]) => normalizeTextFilter(token).includes(needle))
      .flatMap(([, ids]) => normalizedChunkIds(ids));
    if (!chunkIds.length) {
      return null;
    }
    candidateGroups.push(Array.from(new Set(chunkIds)));
  }

  return intersectChunkIdGroups(candidateGroups);
}

function queryCandidateChunkIdsFromExactIndexMap(indexMap, filterValue) {
  const needle = normalizeTextFilter(filterValue);
  if (!needle || !indexMap || typeof indexMap !== "object") {
    return null;
  }
  const chunkIds = normalizedChunkIds(indexMap?.[needle]);
  return chunkIds.length ? chunkIds : null;
}

function topicFilterTokens(value) {
  const normalized = normalizeTextFilter(value);
  if (!normalized || /\d/.test(normalized)) {
    return [];
  }
  return Array.from(new Set(
    normalized
      .split(/[^a-z]+/)
      .map((token) => token.trim())
      .filter((token) => token.length >= 3),
  ));
}

function topicCandidateIdsFromIndexMap(indexMap, filterValue) {
  const tokens = topicFilterTokens(filterValue);
  if (!tokens.length || !indexMap || typeof indexMap !== "object") {
    return null;
  }

  const candidateGroups = [];
  for (const token of tokens) {
    const topicIds = Object.entries(indexMap)
      .filter(([indexedToken]) => normalizeTextFilter(indexedToken).includes(token))
      .flatMap(([, ids]) => normalizedTopicIds(ids));
    if (!topicIds.length) {
      return null;
    }
    candidateGroups.push(Array.from(new Set(topicIds)));
  }

  if (!candidateGroups.length) {
    return null;
  }

  return candidateGroups.slice(1).reduce(
    (acc, group) => acc.filter((topicId) => group.includes(topicId)),
    candidateGroups[0],
  );
}

function queryCandidateChunkIdsFromSearchIndex(searchIndex, queryValue) {
  const tokens = queryTokensForChunkPreselection(queryValue);
  if (!tokens.length || !searchIndex || typeof searchIndex !== "object") {
    return null;
  }

  const candidateGroups = [];
  for (const token of tokens) {
    const chunkIds = new Set([
      ...(queryCandidateChunkIdsFromIndexMap(searchIndex?.topic_tokens, token) || []),
      ...(queryCandidateChunkIdsFromIndexMap(searchIndex?.party_tokens, token) || []),
      ...(queryCandidateChunkIdsFromExactIndexMap(searchIndex?.methods, token) || []),
      ...(queryCandidateChunkIdsFromExactIndexMap(searchIndex?.stances, token) || []),
    ]);
    if (!chunkIds.size) {
      return null;
    }
    candidateGroups.push(Array.from(chunkIds));
  }

  return intersectChunkIdGroups(candidateGroups);
}

function queryCandidateChunkIdsFromChunkMetadata(chunks, queryValue) {
  const tokens = queryTokensForChunkPreselection(queryValue);
  if (!tokens.length || !Array.isArray(chunks) || !chunks.length) {
    return null;
  }

  const ids = chunks
    .filter((chunk) => {
      const haystack = [
        ...normalizedChunkList(chunk, "topic_tokens"),
        ...normalizedChunkList(chunk, "party_tokens"),
        ...normalizedChunkList(chunk, "methods"),
      ];
      if (!haystack.length) {
        return true;
      }
      return tokens.every((token) => haystack.some((value) => value.includes(token)));
    })
    .map((chunk) => String(chunk?.chunk_id || "").trim())
    .filter(Boolean);

  return ids.length ? ids : null;
}

function queryCandidateChunkIdsFromPersonIndex(personIndex, queryValue) {
  const tokens = queryTokensForChunkPreselection(queryValue);
  if (!tokens.length || !Array.isArray(personIndex) || !personIndex.length) {
    return null;
  }

  const chunkIds = new Set();
  for (const person of personIndex) {
    const chunkId = String(person?.trajectory_chunk || "").trim();
    if (!chunkId) {
      continue;
    }
    const haystack = normalizeTextFilter(
      `${String(person?.full_name || "")} ${String(person?.canonical_key || "")}`,
    );
    if (!haystack) {
      continue;
    }
    if (tokens.every((token) => haystack.includes(token))) {
      chunkIds.add(chunkId);
    }
  }

  return chunkIds.size ? Array.from(chunkIds) : null;
}

function queryMatchesPersonIndex(personIndex, queryValue) {
  const tokens = queryTokensForChunkPreselection(queryValue);
  if (!tokens.length || !Array.isArray(personIndex) || !personIndex.length) {
    return false;
  }

  return personIndex.some((person) => {
    const haystack = normalizeTextFilter(
      `${String(person?.full_name || person?.fullName || "")} ${String(person?.canonical_key || person?.canonicalKey || "")}`,
    );
    return Boolean(haystack) && tokens.every((token) => haystack.includes(token));
  });
}

export function personTrajectoryHasActiveFilters(state) {
  return Boolean(
    hasTextValue(state?.q)
    || hasTextValue(state?.pack)
    || hasTextValue(state?.concern)
    || hasTextValue(state?.person)
    || hasTextValue(state?.topic)
    || hasTextValue(state?.party)
    || String(state?.method || "all").trim().toLowerCase() !== "all"
    || String(state?.stance || "all").trim().toLowerCase() !== "all"
  );
}

export function personTrajectoryNeedsExactTopicRows(state, resolvedTopicId = 0) {
  return normalizeMode(state?.mode) === "person" && normalizeTopicId(resolvedTopicId) > 0;
}

export function candidateTopicPreviewTopicIds({ state, searchIndex, personIndex }) {
  if (normalizeMode(state?.mode) !== "person") {
    return [];
  }
  const searchMode = normalizeSearchMode(state?.searchMode);
  if (hasTextValue(state?.topic)) {
    const topicIds = topicCandidateIdsFromIndexMap(searchIndex?.topic_tokens, state?.topic);
    return Array.isArray(topicIds) ? topicIds : [];
  }
  if (!hasTextValue(state?.q)) {
    return [];
  }
  if (searchMode === "person") {
    return [];
  }
  if (searchMode !== "topic" && queryMatchesPersonIndex(personIndex, state?.q)) {
    return [];
  }
  const topicIds = topicCandidateIdsFromIndexMap(searchIndex?.topic_tokens, state?.q);
  return Array.isArray(topicIds) ? topicIds : [];
}

export function personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId = 0, previewTopicIds = []) {
  return normalizeMode(state?.mode) === "person"
    && (
      normalizeTopicId(resolvedTopicId) > 0
      || normalizedTopicIds(previewTopicIds).length > 0
    );
}

export function personTrajectoryNeedsTopicDiscovery(state, resolvedTopicId = 0, previewTopicIds = [], discoveryTopicIds = []) {
  if (personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, previewTopicIds)) {
    return false;
  }
  return normalizeMode(state?.mode) === "person"
    && normalizedTopicIds(discoveryTopicIds).length > 0
    && (
      hasTextValue(state?.pack)
      || hasTextValue(state?.concern)
      || hasTextValue(state?.topic)
      || (hasTextValue(state?.q) && normalizeSearchMode(state?.searchMode) === "topic")
    );
}

export function personTrajectoryNeedsSortPreview(state, resolvedTopicId = 0, previewTopicIds = [], discoveryTopicIds = []) {
  if (personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, previewTopicIds)) {
    return false;
  }
  if (personTrajectoryNeedsTopicDiscovery(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return false;
  }
  return normalizeMode(state?.mode) === "person"
    && !personTrajectoryHasActiveFilters(state)
    && normalizeSort(state?.sort) !== "person";
}

export function personTrajectoryNeedsExhaustiveScan(state, resolvedTopicId = 0, previewTopicIds = [], discoveryTopicIds = []) {
  if (personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, previewTopicIds)) {
    return false;
  }
  if (personTrajectoryNeedsTopicDiscovery(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return false;
  }
  return normalizeSort(state?.sort) !== "person";
}

export function isDefaultPersonView(state, resolvedTopicId = 0, previewTopicIds = [], discoveryTopicIds = []) {
  if (personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, previewTopicIds)) {
    return false;
  }
  if (personTrajectoryNeedsTopicDiscovery(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return false;
  }
  return normalizeMode(state?.mode) === "person"
    && !personTrajectoryHasActiveFilters(state)
    && !personTrajectoryNeedsExhaustiveScan(state, resolvedTopicId, previewTopicIds, discoveryTopicIds);
}

export function personTrajectoryScanMode(state, resolvedTopicId = 0, previewTopicIds = [], discoveryTopicIds = []) {
  if (personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, previewTopicIds)) {
    return "topic_preview";
  }
  if (personTrajectoryNeedsTopicDiscovery(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return "topic_discovery";
  }
  if (isDefaultPersonView(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return "default_rows";
  }
  if (personTrajectoryNeedsSortPreview(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return "sort_preview";
  }
  return personTrajectoryNeedsExhaustiveScan(state, resolvedTopicId, previewTopicIds, discoveryTopicIds) ? "exhaustive" : "progressive";
}

export function candidatePersonTrajectoryChunkIds({
  state,
  chunks,
  personIndex,
  searchIndex,
  resolvedTopicId,
}) {
  const searchMode = normalizeSearchMode(state?.searchMode);
  const allChunkIds = Array.isArray(chunks)
    ? chunks
      .map((chunk) => String(chunk?.chunk_id || "").trim())
      .filter(Boolean)
    : [];
  const normalizedResolvedTopicId = Number.isFinite(Number(resolvedTopicId)) && Number(resolvedTopicId) > 0
    ? String(Number(resolvedTopicId))
    : "";
  const topicIds = normalizedResolvedTopicId
    ? queryCandidateChunkIdsFromExactIndexMap(searchIndex?.topic_ids, normalizedResolvedTopicId)
    : (
      queryCandidateChunkIdsFromIndexMap(searchIndex?.topic_tokens, state?.topic)
      || (Array.isArray(chunks)
        ? chunks
          .filter((chunk) => chunkListMayContain(chunk, "topic_tokens", state?.topic))
          .map((chunk) => String(chunk?.chunk_id || "").trim())
          .filter(Boolean)
        : null)
    );
  const partyIds = queryCandidateChunkIdsFromIndexMap(searchIndex?.party_tokens, state?.party)
    || (Array.isArray(chunks)
      ? chunks
        .filter((chunk) => chunkListMayContain(chunk, "party_tokens", state?.party))
        .map((chunk) => String(chunk?.chunk_id || "").trim())
        .filter(Boolean)
      : null);
  const personFilterIds = queryCandidateChunkIdsFromPersonIndex(personIndex, state?.person);
  const methodFilter = String(state?.method || "all").trim().toLowerCase() === "all" ? "" : state?.method;
  const methodIds = queryCandidateChunkIdsFromExactIndexMap(searchIndex?.methods, methodFilter)
    || (Array.isArray(chunks)
      ? chunks
        .filter((chunk) => chunkListMayContain(chunk, "methods", methodFilter))
        .map((chunk) => String(chunk?.chunk_id || "").trim())
        .filter(Boolean)
      : null);
  const stanceFilter = String(state?.stance || "all").trim().toLowerCase() === "all" ? "" : state?.stance;
  const stanceIds = queryCandidateChunkIdsFromExactIndexMap(searchIndex?.stances, stanceFilter)
    || (Array.isArray(chunks)
      ? chunks
        .filter((chunk) => chunkListMayContain(chunk, "stances", stanceFilter))
        .map((chunk) => String(chunk?.chunk_id || "").trim())
        .filter(Boolean)
      : null);

  const structuredIds = intersectChunkIdGroups([
    allChunkIds,
    personFilterIds,
    topicIds,
    partyIds,
    methodIds,
    stanceIds,
  ]) || allChunkIds;
  const structuredAllowed = new Set(structuredIds);
  const structuredChunks = Array.isArray(chunks)
    ? chunks.filter((chunk) => structuredAllowed.has(String(chunk?.chunk_id || "").trim()))
    : [];

  const queryIdsFromSearchIndex = searchMode === "person"
    ? null
    : queryCandidateChunkIdsFromSearchIndex(searchIndex, state?.q);
  const queryIdsFromChunkMetadata = searchMode === "person"
    ? null
    : (searchIndex
    ? null
    : queryCandidateChunkIdsFromChunkMetadata(structuredChunks, state?.q));
  const queryIdsFromPersonIndex = searchMode === "topic"
    ? null
    : queryCandidateChunkIdsFromPersonIndex(personIndex, state?.q);
  if (!queryIdsFromSearchIndex && !queryIdsFromChunkMetadata && !queryIdsFromPersonIndex) {
    return structuredIds;
  }

  const allowed = new Set([
    ...(queryIdsFromSearchIndex || []),
    ...(queryIdsFromChunkMetadata || []),
    ...(queryIdsFromPersonIndex || []),
  ]);
  return structuredIds.filter((chunkId) => allowed.has(chunkId));
}

export function nextPersonTrajectoryChunkIds({
  state,
  chunks,
  personIndex,
  searchIndex,
  resolvedTopicId,
  previewTopicIds,
  discoveryTopicIds,
  loadedChunks,
  currentRowsCount,
  limit,
}) {
  if (personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, previewTopicIds)) {
    return [];
  }
  if (personTrajectoryNeedsTopicDiscovery(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return [];
  }
  const chunkIds = candidatePersonTrajectoryChunkIds({
    state,
    chunks,
    personIndex,
    searchIndex,
    resolvedTopicId,
  });
  const missingChunkIds = chunkIds.filter((chunkId) => !loadedChunks?.[chunkId]);

  if (!missingChunkIds.length) {
    return [];
  }
  if (personTrajectoryNeedsSortPreview(state, resolvedTopicId, previewTopicIds, discoveryTopicIds) || isDefaultPersonView(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return [];
  }
  if (personTrajectoryNeedsExhaustiveScan(state, resolvedTopicId, previewTopicIds, discoveryTopicIds)) {
    return missingChunkIds;
  }

  const targetRows = Math.max(10, normalizeInt(limit ?? state?.limit, 180));
  if (normalizeInt(currentRowsCount, 0) >= targetRows) {
    return [];
  }
  return [missingChunkIds[0]];
}
