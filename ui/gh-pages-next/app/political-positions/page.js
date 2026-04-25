"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import concernConfig from "../../public/legacy/citizen/data/concerns_v1.json";
import {
  candidateTopicPreviewTopicIds,
  candidatePersonTrajectoryChunkIds,
  isDefaultPersonView,
  nextPersonTrajectoryChunkIds,
  personTrajectoryHasActiveFilters,
  personTrajectoryNeedsExactTopicRows,
  personTrajectoryNeedsExhaustiveScan,
  personTrajectoryNeedsTopicPreviewRows,
  personTrajectoryScanMode,
} from "./personTrajectoryLoading.mjs";
import {
  resolveExactTopicFilterSelection,
  topicFilterMatches,
} from "./filterMatching.mjs";
import {
  applyTopicPreviewSelection,
  buildConcernEntries,
  buildConcernPackEntries,
  buildConcernPackTopicSelections,
  buildConcernTopicSelections,
  buildTopicDiscoverySelections,
  buildTopicPreviewSelections,
  resolveTopicDiscoveryOriginHighlight,
  resolveTopicDiscoveryOriginResumeNotice,
  resolveTopicDiscoveryOriginVariantSelection,
  resolveTopicDiscoveryOriginTargetTopicId,
} from "./topicPreviewSelections.mjs";
import {
  buildPoliticalPositionsUrlSearch,
  defaultPoliticalPositionsState,
  normalizePoliticalPositionsSearchMode as normalizeSearchMode,
  readPoliticalPositionsUrlState,
  restorePoliticalPositionsDiscoveryState,
} from "./urlState.mjs";
import {
  buildPoliticalPositionsContinuityBreadcrumb,
  buildPoliticalPositionsDetailBreadcrumb,
} from "./continuityBreadcrumb.mjs";
import {
  buildPoliticalPositionsDetailDrilldownLinks,
  buildPoliticalPositionsDetailOverview,
  buildPoliticalPositionsDetailPanelSummary,
  buildPoliticalPositionsEvidenceTableHeader,
} from "./detailPanelModel.mjs";
import { resolveBasePath } from "../path-utils.mjs";

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }
  return `${(num * 100).toFixed(1)}%`;
}

function toScore(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }
  return num.toFixed(2);
}

function clamp01(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return 0;
  }
  return Math.max(0, Math.min(1, num));
}

function formatDate(value) {
  return String(value || "—");
}

function continuityBreadcrumbItemLabel(item) {
  if (!item || !item.label) {
    return "";
  }
  if (item.kind === "origin") {
    return item.originKind === "concern" ? `Preocupación: ${item.label}` : `Pack: ${item.label}`;
  }
  if (item.kind === "family") {
    return `Familia: ${item.label}`;
  }
  if (item.kind === "exact") {
    const topicId = toInt(item.topicId);
    return `Tema exacto: ${item.label}${topicId > 0 ? ` (#${topicId})` : ""}`;
  }
  if (item.kind === "entity") {
    const entityId = toInt(item.entityId);
    const prefix = item.entityKind === "party" ? "Partido" : "Persona";
    return `${prefix}: ${item.label}${entityId > 0 ? ` (#${entityId})` : ""}`;
  }
  return String(item.label);
}

function stancePillClass(stance) {
  switch (String(stance || "").toLowerCase()) {
    case "support":
    case "supportive":
      return "pill-success";
    case "oppose":
      return "pill-danger";
    case "mixed":
      return "pill-warning";
    case "unclear":
      return "pill-muted";
    default:
      return "pill-muted";
  }
}

function methodPriority(method) {
  const m = String(method || "").toLowerCase();
  if (m === "combined") {
    return 0;
  }
  if (m === "votes") {
    return 1;
  }
  if (m === "declared") {
    return 2;
  }
  return 3;
}

function pointDetailKey(point) {
  return `${toInt(point?.topic_id || point?.topicId)}|${String(point?.as_of_date || point?.asOf || "")}|${String(point?.computed_method || point?.method || "")}`;
}

function normalizeMode(mode) {
  return String(mode || "person") === "party" ? "party" : "person";
}

function normalizeSortKey(sort) {
  return String(sort || "person").trim().toLowerCase() || "person";
}

function trajectoryMetaPathKey(mode) {
  return normalizeMode(mode) === "party" ? "party_trajectories_path" : "person_trajectories_path";
}

function resolvePersonSortPreviewPath(payload, sortKey) {
  const normalizedSort = normalizeSortKey(sortKey);
  const path = payload?.meta?.person_sort_preview_paths?.[normalizedSort];
  return String(path || "").trim();
}

function resolvePersonSearchIndexPath(payload) {
  return String(payload?.meta?.person_search_index_path || "").trim();
}

function resolveTopicSearchIndexPath(payload) {
  return String(payload?.meta?.topic_search_index_path || "").trim();
}

function resolveTopicPersonRowsPath(payload, topicId) {
  const normalizedTopicId = toInt(topicId);
  const dir = String(payload?.meta?.topic_person_rows_dir || "").trim();
  if (!dir || !normalizedTopicId) {
    return "";
  }
  return `${dir}/${normalizedTopicId}.json`;
}

function resolveExactTopicSelection(topics, rawValue, rawTopicId = 0) {
  const topicIdHint = toInt(rawTopicId);
  if (topicIdHint && Array.isArray(topics)) {
    for (const topic of topics) {
      const topicId = toInt(topic?.topic_id || topic?.topicId);
      if (topicId !== topicIdHint) {
        continue;
      }
      const label = String(topic?.label || topic?.topic_label || "").trim();
      const key = String(topic?.key || topic?.topic_key || "").trim();
      if (!label && !key) {
        break;
      }
      return {
        topicId,
        label: label || key,
        key,
      };
    }
  }
  return resolveExactTopicFilterSelection(topics, rawValue);
}

function compareTrajectoryRows(a, b, sortMode) {
  if (sortMode === "confidence_desc") {
    return clamp01(b.confidence) - clamp01(a.confidence) || b.score - a.score || b.evidenceCount - a.evidenceCount;
  }
  if (sortMode === "confidence_asc") {
    return clamp01(a.confidence) - clamp01(b.confidence) || a.score - b.score;
  }
  if (sortMode === "method") {
    if (a.method !== b.method) {
      return methodPriority(a.method) - methodPriority(b.method);
    }
  }
  if (sortMode === "stance") {
    if (a.stance !== b.stance) {
      return String(a.stance).localeCompare(String(b.stance));
    }
  }
  if (sortMode === "as_of") {
    return String(b.asOf || "").localeCompare(String(a.asOf || ""));
  }
  if (sortMode === "topic") {
    return String(a.topicLabel || "").localeCompare(String(b.topicLabel || "")) || String(a.asOf || "").localeCompare(String(b.asOf || ""));
  }
  if (sortMode === "party") {
    const ap = normalize(a.partyLabel || "");
    const bp = normalize(b.partyLabel || "");
    if (ap !== bp) {
      return ap.localeCompare(bp);
    }
  }

  if (a.scope === b.scope) {
    if (a.scope === "person") {
      return String(a.personName || "").localeCompare(String(b.personName || ""))
        || String(a.topicLabel || "").localeCompare(String(b.topicLabel || ""))
        || String(b.asOf || "").localeCompare(String(a.asOf || ""))
        || methodPriority(a.method) - methodPriority(b.method);
    }
    return String(a.partyLabel || "").localeCompare(String(b.partyLabel || ""))
      || String(a.topicLabel || "").localeCompare(String(b.topicLabel || ""))
      || String(b.asOf || "").localeCompare(String(a.asOf || ""))
      || methodPriority(a.method) - methodPriority(b.method);
  }

  return String(a.scope).localeCompare(String(b.scope));
}

function filterAndSortTopicPersonRows(rows, state, resolvedTopicFilter, topicsById) {
  const query = normalize(state.q);
  const personFilter = normalize(state.person);
  const methodFilter = String(state.method || "all").trim().toLowerCase();
  const stanceFilter = String(state.stance || "all").trim().toLowerCase();
  const partyFilter = normalize(state.party);
  const out = [];

  for (const row of Array.isArray(rows) ? rows : []) {
    const topicId = toInt(row.topicId || resolvedTopicFilter?.topicId || 0);
    const topicCard = topicId ? topicsById?.get(topicId) : null;
    const topicLabel = String(row.topicLabel || resolvedTopicFilter?.label || topicCard?.label || "").trim();
    const topicKey = String(row.topicKey || resolvedTopicFilter?.key || topicCard?.key || "").trim();
    const personHaystack = normalize(`${String(row.personName || "")} ${String(row.canonicalKey || "")}`);
    if (personFilter && !personHaystack.includes(personFilter)) {
      continue;
    }
    if (methodFilter !== "all" && String(row.method || "").toLowerCase() !== methodFilter) {
      continue;
    }
    if (stanceFilter !== "all" && String(row.stance || "").toLowerCase() !== stanceFilter) {
      continue;
    }
    if (partyFilter && !normalize(row.partyLabel || "").includes(partyFilter)) {
      continue;
    }
    const rowHaystack = [
      String(row.personName || ""),
      String(row.canonicalKey || ""),
      topicLabel,
      String(row.partyLabel || ""),
      String(row.asOf || ""),
      String(row.method || ""),
      topicKey,
    ].map(normalize).join(" ");
    if (query && !rowHaystack.includes(query)) {
      continue;
    }
    out.push({
      ...row,
      scope: "person",
      topicId,
      topicLabel,
      topicKey,
      samples: Array.isArray(row.samples) ? row.samples : [],
    });
  }

  out.sort((a, b) => compareTrajectoryRows(a, b, String(state.sort || "person")));
  return out.slice(0, Math.max(10, Number(state.limit || 180)));
}

function defaultStateFromUrl() {
  if (typeof window === "undefined") {
    return defaultPoliticalPositionsState();
  }
  return readPoliticalPositionsUrlState(window.location.search);
}

function usePositionsPayload() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/stances.json`;

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Respuesta no válida: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setState({ loading: false, error: null, data: payload });
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        setState({ loading: false, error: error.message || String(error), data: null });
      });

    return () => controller.abort();
  }, []);

  return state;
}

function formatEvidenceSummary(item) {
  const breakdown = item?.evidence_breakdown || {};
  const total = toInt(item?.evidence_count || 0);
  if (!total) {
    return "Sin evidencia agregada";
  }
  const entries = [];
  if (toInt(breakdown.declared)) {
    entries.push(`declarada:${toInt(breakdown.declared)}`);
  }
  if (toInt(breakdown.revealed)) {
    entries.push(`votos:${toInt(breakdown.revealed)}`);
  }
  if (toInt(breakdown.other)) {
    entries.push(`otra:${toInt(breakdown.other)}`);
  }
  return entries.length ? entries.join(" · ") : `Total ${total}`;
}

function compactReviewLabel(item) {
  const pending = toInt(item?.review_summary?.pending || 0);
  const resolved = toInt(item?.review_summary?.resolved || 0);
  const ignored = toInt(item?.review_summary?.ignored || 0);

  if (!pending && !resolved && !ignored) {
    return "Sin revisión registrada";
  }
  return `Pendiente ${pending} · Aprobada ${resolved} · Ignorada ${ignored}`;
}

export default function PoliticalPositionsPage() {
  const { loading, error, data } = usePositionsPayload();
  const [state, setState] = useState(() => defaultStateFromUrl());
  const [selectedPoint, setSelectedPoint] = useState(null);
  const lastOriginDiscoveryTargetRef = useRef("");
  const [dismissedOriginNoticeTopicId, setDismissedOriginNoticeTopicId] = useState(0);
  const [personDefaultRows, setPersonDefaultRows] = useState(null);
  const [personDefaultRowsState, setPersonDefaultRowsState] = useState({ loading: false, error: null });
  const [personSortPreviewRowsBySort, setPersonSortPreviewRowsBySort] = useState({});
  const [personSortPreviewState, setPersonSortPreviewState] = useState({ loading: false, error: null, sort: "" });
  const [trajectoryPayloads, setTrajectoryPayloads] = useState({ person: null, party: null });
  const [trajectoryState, setTrajectoryState] = useState({ loading: false, error: null, mode: "" });
  const [personTrajectoryManifest, setPersonTrajectoryManifest] = useState(null);
  const [personSearchIndex, setPersonSearchIndex] = useState(null);
  const [personSearchIndexState, setPersonSearchIndexState] = useState({ loading: false, error: null });
  const [topicSearchIndex, setTopicSearchIndex] = useState(null);
  const [topicSearchIndexState, setTopicSearchIndexState] = useState({ loading: false, error: null });
  const [topicPersonRowsByTopicId, setTopicPersonRowsByTopicId] = useState({});
  const [topicPersonRowsState, setTopicPersonRowsState] = useState({ loading: false, error: null, topicIdsKey: "" });
  const [loadedPersonTrajectoryChunks, setLoadedPersonTrajectoryChunks] = useState({});
  const [personDetails, setPersonDetails] = useState({});
  const [detailState, setDetailState] = useState({ loading: false, error: null, personId: 0 });

  useEffect(() => {
    const initial = defaultStateFromUrl();
    setState({
      ...initial,
      limit: Number.isFinite(initial.limit) && initial.limit > 0 ? Math.min(initial.limit, 400) : 180,
    });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const query = buildPoliticalPositionsUrlSearch(state);
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  }, [state.concern, state.limit, state.method, state.mode, state.originConcern, state.originPack, state.originTopicId, state.pack, state.party, state.person, state.q, state.searchMode, state.sort, state.stance, state.topic, state.topicId]);

  useEffect(() => {
    if (!data) {
      return;
    }
    setTrajectoryPayloads({
      person: data.person_trajectories && Object.keys(data.person_trajectories).length ? data.person_trajectories : null,
      party: data.party_trajectories && Object.keys(data.party_trajectories).length ? data.party_trajectories : null,
    });
    setPersonDefaultRows(null);
    setPersonDefaultRowsState({ loading: false, error: null });
    setPersonSortPreviewRowsBySort({});
    setPersonSortPreviewState({ loading: false, error: null, sort: "" });
    setPersonTrajectoryManifest(null);
    setPersonSearchIndex(null);
    setPersonSearchIndexState({ loading: false, error: null });
    setTopicSearchIndex(null);
    setTopicSearchIndexState({ loading: false, error: null });
    setTopicPersonRowsByTopicId({});
    setTopicPersonRowsState({ loading: false, error: null, topicIdsKey: "" });
    setLoadedPersonTrajectoryChunks({});
    setTrajectoryState({ loading: false, error: null, mode: "" });
  }, [data]);

  const topicFilterOptions = useMemo(() => (
    (data?.topics || [])
      .map((topic) => ({
        topicId: toInt(topic.topic_id),
        label: String(topic.topic_label || topic.label || "").trim(),
        key: String(topic.topic_key || topic.key || "").trim(),
        pointCount: toInt(topic.point_count),
        evidenceCountTotal: toInt(topic.evidence_count_total),
      }))
      .filter((topic) => topic.topicId && topic.label)
  ), [data?.topics]);
  const concernEntries = useMemo(() => (
    buildConcernEntries({
      topics: topicFilterOptions,
      concerns: concernConfig?.concerns || [],
    })
  ), [topicFilterOptions]);
  const concernsById = useMemo(() => (
    new Map(concernEntries.map((concern) => [String(concern.id || "").trim(), concern]))
  ), [concernEntries]);
  const concernPackEntries = useMemo(() => (
    buildConcernPackEntries({
      concernEntries,
      packs: concernConfig?.packs || [],
    })
  ), [concernEntries]);
  const activePackEntry = useMemo(() => (
    concernPackEntries.find((pack) => pack.id === String(state.pack || "").trim()) || null
  ), [concernPackEntries, state.pack]);
  const visibleConcernEntries = useMemo(() => {
    if (!activePackEntry) {
      return concernEntries;
    }
    const allowed = new Set(activePackEntry.concernIds || []);
    return concernEntries.filter((concern) => allowed.has(String(concern.id || "").trim()));
  }, [activePackEntry, concernEntries]);
  const activeConcernEntry = useMemo(() => (
    concernEntries.find((concern) => concern.id === String(state.concern || "").trim()) || null
  ), [concernEntries, state.concern]);
  const originPackEntry = useMemo(() => (
    concernPackEntries.find((pack) => pack.id === String(state.originPack || "").trim()) || null
  ), [concernPackEntries, state.originPack]);
  const originConcernEntry = useMemo(() => (
    concernEntries.find((concern) => concern.id === String(state.originConcern || "").trim()) || null
  ), [concernEntries, state.originConcern]);
  const originTopicId = toInt(state.originTopicId || 0);
  const resolvedTopicFilter = useMemo(
    () => resolveExactTopicSelection(topicFilterOptions, state.topic, state.topicId),
    [state.topic, state.topicId, topicFilterOptions],
  );
  const resolvedTopicId = toInt(resolvedTopicFilter?.topicId || 0);
  const normalizedSearchMode = useMemo(
    () => normalizeSearchMode(state.searchMode),
    [state.searchMode],
  );
  const exactTopicPreviewActive = useMemo(
    () => personTrajectoryNeedsExactTopicRows(state, resolvedTopicId),
    [resolvedTopicId, state],
  );
  const needsTopicSearchIndex = useMemo(() => (
    Boolean(
      data
      && normalizeMode(state.mode) === "person"
      && !resolvedTopicFilter
      && (Boolean(state.topic) || (Boolean(state.q) && normalizedSearchMode !== "person"))
      && toInt(data?.meta?.topic_search_index_counts?.topic_tokens || 0) > 0
      && resolveTopicSearchIndexPath(data)
    )
  ), [data, normalizedSearchMode, resolvedTopicFilter, state.mode, state.q, state.topic]);
  const selectiveTopicPreviewTopicIds = useMemo(() => (
    exactTopicPreviewActive
      ? []
      : candidateTopicPreviewTopicIds({ state, searchIndex: topicSearchIndex, personIndex: data?.persons || [] })
  ), [data?.persons, exactTopicPreviewActive, state, topicSearchIndex]);
  const topicPreviewTopicIds = useMemo(() => (
    exactTopicPreviewActive ? [resolvedTopicId] : selectiveTopicPreviewTopicIds
  ), [exactTopicPreviewActive, resolvedTopicId, selectiveTopicPreviewTopicIds]);
  const topicPreviewIdsKey = useMemo(() => (
    Array.isArray(topicPreviewTopicIds)
      ? topicPreviewTopicIds
        .map((topicId) => String(toInt(topicId)))
        .filter((topicId) => topicId !== "0")
        .sort((a, b) => Number(a) - Number(b))
        .join(",")
      : ""
  ), [topicPreviewTopicIds]);
  const topicPreviewActive = useMemo(
    () => personTrajectoryNeedsTopicPreviewRows(state, resolvedTopicId, selectiveTopicPreviewTopicIds),
    [resolvedTopicId, selectiveTopicPreviewTopicIds, state],
  );
  const topicPreviewModeLabel = useMemo(() => {
    if (!topicPreviewActive) {
      return "";
    }
    if (exactTopicPreviewActive) {
      return "exact";
    }
    return state.topic ? "topic_filter" : "q_search";
  }, [exactTopicPreviewActive, state.q, state.topic, topicPreviewActive]);
  const qInterpretationLabel = useMemo(() => {
    if (!state.q || normalizeMode(state.mode) !== "person") {
      return "";
    }
    if (normalizedSearchMode === "topic") {
      return "tema";
    }
    if (normalizedSearchMode === "person") {
      return "persona";
    }
    if (topicPreviewModeLabel === "q_search") {
      return "auto -> tema";
    }
    return "auto";
  }, [normalizedSearchMode, state.mode, state.q, topicPreviewModeLabel]);
  const concernTopicSelections = useMemo(() => (
    activeConcernEntry
      ? buildConcernTopicSelections({
        topics: topicFilterOptions,
        concern: activeConcernEntry,
        limit: 12,
      })
      : []
  ), [activeConcernEntry, topicFilterOptions]);
  const packTopicSelections = useMemo(() => (
    activePackEntry
      ? buildConcernPackTopicSelections({
        topics: topicFilterOptions,
        concernsById,
        pack: activePackEntry,
        limit: 12,
      })
      : []
  ), [activePackEntry, concernsById, topicFilterOptions]);
  const topicDiscoveryContext = useMemo(() => {
    if (normalizeMode(state.mode) !== "person" || resolvedTopicFilter || topicPreviewActive) {
      return { rawValue: "", sourceMode: "", sourceLabel: "" };
    }
    if (activePackEntry) {
      return {
        rawValue: activePackEntry.label,
        sourceMode: "pack_discovery",
        sourceLabel: activePackEntry.label,
      };
    }
    if (activeConcernEntry) {
      return {
        rawValue: activeConcernEntry.label,
        sourceMode: "concern_discovery",
        sourceLabel: activeConcernEntry.label,
      };
    }
    if (state.topic) {
      return { rawValue: state.topic, sourceMode: "topic_filter", sourceLabel: "Tema" };
    }
    if (state.q && normalizedSearchMode === "topic") {
      return { rawValue: state.q, sourceMode: "q_discovery", sourceLabel: "Buscar" };
    }
    return { rawValue: "", sourceMode: "", sourceLabel: "" };
  }, [activeConcernEntry, activePackEntry, normalizedSearchMode, resolvedTopicFilter, state.mode, state.q, state.topic, topicPreviewActive]);
  const topicDiscoverySelections = useMemo(() => (
    activePackEntry
      ? packTopicSelections
      : activeConcernEntry
      ? concernTopicSelections
      : buildTopicDiscoverySelections({
        topics: topicFilterOptions,
        rawValue: topicDiscoveryContext.rawValue,
        limit: 12,
      })
  ), [activeConcernEntry, activePackEntry, concernTopicSelections, packTopicSelections, topicDiscoveryContext.rawValue, topicFilterOptions]);
  const topicDiscoveryTopicIds = useMemo(
    () => topicDiscoverySelections.map((topic) => toInt(topic.topicId)).filter((topicId) => topicId > 0),
    [topicDiscoverySelections],
  );
  const topicDiscoveryActive = useMemo(() => (
    normalizeMode(state.mode) === "person"
    && !resolvedTopicFilter
    && !topicPreviewActive
    && topicDiscoverySelections.length > 0
    && Boolean(topicDiscoveryContext.rawValue)
    && (Boolean(activePackEntry) || Boolean(activeConcernEntry) || !needsTopicSearchIndex || Boolean(topicSearchIndex) || Boolean(topicSearchIndexState.error))
  ), [
    activeConcernEntry,
    activePackEntry,
    needsTopicSearchIndex,
    resolvedTopicFilter,
    state.mode,
    topicDiscoveryContext.rawValue,
    topicDiscoverySelections.length,
    topicPreviewActive,
    topicSearchIndex,
    topicSearchIndexState.error,
  ]);
  const topicDiscoveryTitle = useMemo(() => {
    if (!topicDiscoveryActive) {
      return "";
    }
    if (topicDiscoveryContext.sourceMode === "pack_discovery") {
      return `Temas para ${topicDiscoveryContext.sourceLabel || "el pack seleccionado"}`;
    }
    if (topicDiscoveryContext.sourceMode === "concern_discovery") {
      return `Temas para ${topicDiscoveryContext.sourceLabel || "la preocupación seleccionada"}`;
    }
    return `Explorar temas desde ${topicDiscoveryContext.sourceLabel || "tema"}`;
  }, [topicDiscoveryActive, topicDiscoveryContext.sourceLabel]);
  const topicDiscoverySub = useMemo(() => {
    if (!topicDiscoveryActive) {
      return "";
    }
    if (topicDiscoveryContext.sourceMode === "pack_discovery") {
      const tradeoff = String(activePackEntry?.tradeoff || "").trim();
      const concernLabels = Array.isArray(activePackEntry?.concernLabels) ? activePackEntry.concernLabels.filter(Boolean) : [];
      return `${tradeoff || "Ruta curada con varias preocupaciones cotidianas."}${concernLabels.length ? ` Prioriza ${concernLabels.join(", ")}.` : ""} Elige un tema exacto para abrir una vista estática antes de cargar trayectorias.`;
    }
    if (topicDiscoveryContext.sourceMode === "concern_discovery") {
      return "Esta preocupación agrupa varios temas legislativos. Elige uno para abrir una vista estática exacta antes de cargar trayectorias.";
    }
    if (topicDiscoveryContext.sourceMode === "q_discovery") {
      return "La búsqueda temática sigue siendo amplia. Elige un tema exacto para evitar descargar trayectorias de personas sin necesidad.";
    }
    return "El filtro Tema sigue siendo amplio. Elige una coincidencia exacta para abrir una vista estática reproducible.";
  }, [activePackEntry, topicDiscoveryActive, topicDiscoveryContext.sourceMode]);
  const originDiscoveryTargetTopicId = useMemo(
    () => resolveTopicDiscoveryOriginTargetTopicId({ topics: topicDiscoverySelections, originTopicId }),
    [originTopicId, topicDiscoverySelections],
  );
  const originDiscoveryResumeNotice = useMemo(
    () => resolveTopicDiscoveryOriginResumeNotice({ topics: topicDiscoverySelections, originTopicId }),
    [originTopicId, topicDiscoverySelections],
  );
  const originDiscoveryVariantSelection = useMemo(
    () => resolveTopicDiscoveryOriginVariantSelection({ topics: topicDiscoverySelections, originTopicId }),
    [originTopicId, topicDiscoverySelections],
  );
  const concernSectionTitle = useMemo(() => (
    activePackEntry ? `Preocupaciones dentro de ${activePackEntry.label}` : "Explorar por preocupación"
  ), [activePackEntry]);
  const concernSectionSub = useMemo(() => {
    if (!activePackEntry) {
      return "Entrada más humana para descubrimiento temático amplio. Cada chip abre una lista estática de temas relacionados antes de cargar trayectorias.";
    }
    return `${String(activePackEntry.tradeoff || "").trim() || "Ruta curada con tradeoff explícito."} Si quieres acotar más antes de elegir tema exacto, baja a una preocupación concreta.`;
  }, [activePackEntry]);
  const exactTopicOriginContext = useMemo(() => {
    if (!resolvedTopicFilter || activePackEntry || activeConcernEntry) {
      return null;
    }
    if (originPackEntry) {
      return {
        kind: "pack",
        id: originPackEntry.id,
        label: originPackEntry.label,
      };
    }
    if (originConcernEntry) {
      return {
        kind: "concern",
        id: originConcernEntry.id,
        label: originConcernEntry.label,
      };
    }
    return null;
  }, [activeConcernEntry, activePackEntry, originConcernEntry, originPackEntry, resolvedTopicFilter]);
  const continuityDiscoveryOriginContext = useMemo(() => {
    if (activePackEntry) {
      return { kind: "pack", label: activePackEntry.label };
    }
    if (activeConcernEntry) {
      return { kind: "concern", label: activeConcernEntry.label };
    }
    return null;
  }, [activeConcernEntry, activePackEntry]);

  const needsPersonSearchIndex = useMemo(() => (
    Boolean(
      data
      && normalizeMode(state.mode) === "person"
      && !topicPreviewActive
      && (
        (Boolean(state.q) && normalizedSearchMode !== "topic")
        || Boolean(state.party)
        || String(state.method || "all").trim().toLowerCase() !== "all"
        || String(state.stance || "all").trim().toLowerCase() !== "all"
      )
      && resolvePersonSearchIndexPath(data),
    )
  ), [data, normalizedSearchMode, state, topicPreviewActive]);

  useEffect(() => {
    if (!needsPersonSearchIndex || personSearchIndex || personSearchIndexState.loading || personSearchIndexState.error) {
      return undefined;
    }

    const path = resolvePersonSearchIndexPath(data);
    if (!path) {
      return undefined;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/${path}`;
    setPersonSearchIndexState({ loading: true, error: null });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Índice de búsqueda no disponible: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setPersonSearchIndex(payload && typeof payload === "object" ? payload : {});
        setPersonSearchIndexState({ loading: false, error: null });
      })
      .catch((searchIndexError) => {
        if (searchIndexError.name === "AbortError") {
          return;
        }
        setPersonSearchIndexState({ loading: false, error: searchIndexError.message || String(searchIndexError) });
      });

    return () => controller.abort();
  }, [data, needsPersonSearchIndex, personSearchIndex, personSearchIndexState.error, personSearchIndexState.loading]);

  useEffect(() => {
    if (!needsTopicSearchIndex || topicSearchIndex || topicSearchIndexState.loading || topicSearchIndexState.error) {
      return undefined;
    }

    const path = resolveTopicSearchIndexPath(data);
    if (!path) {
      return undefined;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/${path}`;
    setTopicSearchIndexState({ loading: true, error: null });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Índice temático no disponible: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setTopicSearchIndex(payload && typeof payload === "object" ? payload : {});
        setTopicSearchIndexState({ loading: false, error: null });
      })
      .catch((topicIndexError) => {
        if (topicIndexError.name === "AbortError") {
          return;
        }
        setTopicSearchIndexState({ loading: false, error: topicIndexError.message || String(topicIndexError) });
      });

    return () => controller.abort();
  }, [data, needsTopicSearchIndex, topicSearchIndex, topicSearchIndexState.error, topicSearchIndexState.loading]);

  useEffect(() => {
    if (!data || !isDefaultPersonView(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds) || personDefaultRows || personDefaultRowsState.loading || personDefaultRowsState.error) {
      return undefined;
    }

    const path = String(data?.meta?.person_default_rows_path || "").trim();
    if (!path) {
      return undefined;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/${path}`;
    setPersonDefaultRowsState({ loading: true, error: null });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Filas por defecto no disponibles: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setPersonDefaultRows(Array.isArray(payload) ? payload : []);
        setPersonDefaultRowsState({ loading: false, error: null });
      })
      .catch((rowsError) => {
        if (rowsError.name === "AbortError") {
          return;
        }
        setPersonDefaultRowsState({ loading: false, error: rowsError.message || String(rowsError) });
      });

    return () => controller.abort();
  }, [data, personDefaultRows, personDefaultRowsState.loading, resolvedTopicId, selectiveTopicPreviewTopicIds, state, topicDiscoveryTopicIds]);

  useEffect(() => {
    if (!data || personTrajectoryScanMode(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds) !== "sort_preview") {
      return undefined;
    }

    const sortKey = normalizeSortKey(state.sort);
    const path = resolvePersonSortPreviewPath(data, sortKey);
    if (!path) {
      return undefined;
    }
    if (Array.isArray(personSortPreviewRowsBySort[sortKey])) {
      return undefined;
    }
    if (personSortPreviewState.loading && personSortPreviewState.sort === sortKey) {
      return undefined;
    }
    if (personSortPreviewState.sort === sortKey && personSortPreviewState.error) {
      return undefined;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/${path}`;
    setPersonSortPreviewState({ loading: true, error: null, sort: sortKey });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Vista ordenada no disponible: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setPersonSortPreviewRowsBySort((prev) => ({
          ...prev,
          [sortKey]: Array.isArray(payload) ? payload : [],
        }));
        setPersonSortPreviewState({ loading: false, error: null, sort: sortKey });
      })
      .catch((previewError) => {
        if (previewError.name === "AbortError") {
          return;
        }
        setPersonSortPreviewState({ loading: false, error: previewError.message || String(previewError), sort: sortKey });
      });

    return () => controller.abort();
  }, [data, personSortPreviewRowsBySort, personSortPreviewState.error, personSortPreviewState.loading, personSortPreviewState.sort, resolvedTopicId, selectiveTopicPreviewTopicIds, state, topicDiscoveryTopicIds]);

  useEffect(() => {
    if (!data || !topicPreviewActive) {
      return undefined;
    }

    const topicIds = topicPreviewTopicIds
      .map((topicId) => toInt(topicId))
      .filter((topicId) => topicId > 0);
    if (!topicIds.length) {
      return undefined;
    }
    const missingTopicIds = topicIds.filter((topicId) => !Array.isArray(topicPersonRowsByTopicId[topicId]));
    if (!missingTopicIds.length) {
      return undefined;
    }
    if (topicPersonRowsState.loading && topicPersonRowsState.topicIdsKey === topicPreviewIdsKey) {
      return undefined;
    }
    if (topicPersonRowsState.topicIdsKey === topicPreviewIdsKey && topicPersonRowsState.error) {
      return undefined;
    }

    const controller = new AbortController();
    setTopicPersonRowsState({ loading: true, error: null, topicIdsKey: topicPreviewIdsKey });

    Promise.all(
      missingTopicIds.map((topicId) => {
        const path = resolveTopicPersonRowsPath(data, topicId);
        if (!path) {
          throw new Error(`Vista temática no disponible para ${topicId}`);
        }
        const url = `${resolveBasePath()}/political-positions/data/${path}`;
        return fetch(url, { signal: controller.signal })
          .then((response) => {
            if (!response.ok) {
              throw new Error(`Vista temática no disponible: ${response.status}`);
            }
            return response.json();
          })
          .then((payload) => [topicId, Array.isArray(payload) ? payload : []]);
      }),
    )
      .then((entries) => {
        setTopicPersonRowsByTopicId((prev) => {
          const next = { ...prev };
          for (const [topicId, payload] of entries) {
            next[topicId] = payload;
          }
          return next;
        });
        setTopicPersonRowsState({ loading: false, error: null, topicIdsKey: topicPreviewIdsKey });
      })
      .catch((topicRowsError) => {
        if (topicRowsError.name === "AbortError") {
          return;
        }
        setTopicPersonRowsState({ loading: false, error: topicRowsError.message || String(topicRowsError), topicIdsKey: topicPreviewIdsKey });
      });

    return () => controller.abort();
  }, [data, topicPersonRowsByTopicId, topicPersonRowsState.error, topicPersonRowsState.loading, topicPersonRowsState.topicIdsKey, topicPreviewActive, topicPreviewIdsKey, topicPreviewTopicIds]);

  useEffect(() => {
    if (!data) {
      return undefined;
    }

    const mode = normalizeMode(state.mode);
    if (mode !== "party") {
      return undefined;
    }
    if (trajectoryState.mode === mode && trajectoryState.error) {
      return undefined;
    }
    if (trajectoryPayloads.party || (trajectoryState.loading && trajectoryState.mode === mode)) {
      return undefined;
    }

    const path = String(data?.meta?.[trajectoryMetaPathKey(mode)] || "").trim();
    if (!path) {
      return undefined;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/${path}`;
    setTrajectoryState({ loading: true, error: null, mode });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Trayectorias no disponibles: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setTrajectoryPayloads((prev) => ({ ...prev, [mode]: payload || {} }));
        setTrajectoryState({ loading: false, error: null, mode });
      })
      .catch((trajectoryError) => {
        if (trajectoryError.name === "AbortError") {
          return;
        }
        setTrajectoryState({ loading: false, error: trajectoryError.message || String(trajectoryError), mode });
      });

    return () => controller.abort();
  }, [data, state.mode, trajectoryPayloads.party, trajectoryState.loading, trajectoryState.mode]);

  useEffect(() => {
    if (!data) {
      return undefined;
    }

    const personScanMode = personTrajectoryScanMode(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds);
    if (isDefaultPersonView(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds)) {
      return undefined;
    }
    if (personScanMode === "topic_discovery") {
      return undefined;
    }
    if (topicPreviewActive) {
      const topicLoaded = topicPreviewTopicIds.every((topicId) => Array.isArray(topicPersonRowsByTopicId[toInt(topicId)]));
      const topicLoading = topicPersonRowsState.loading && topicPersonRowsState.topicIdsKey === topicPreviewIdsKey;
      const topicErrored = topicPersonRowsState.topicIdsKey === topicPreviewIdsKey && topicPersonRowsState.error;
      if (topicLoaded || topicLoading || !topicErrored) {
        return undefined;
      }
    }
    if (normalizeMode(state.mode) !== "person") {
      return undefined;
    }
    const mode = normalizeMode(state.mode);
    const sortKey = normalizeSortKey(state.sort);
    const sortPreviewPath = resolvePersonSortPreviewPath(data, sortKey);
    const hasSortPreviewPath = personScanMode === "sort_preview" && Boolean(sortPreviewPath);
    const hasSortPreviewRows = hasSortPreviewPath && Array.isArray(personSortPreviewRowsBySort[sortKey]);
    const isSortPreviewLoading = hasSortPreviewPath && personSortPreviewState.loading && personSortPreviewState.sort === sortKey;
    const hasSortPreviewError = hasSortPreviewPath && personSortPreviewState.sort === sortKey && personSortPreviewState.error;
    if (hasSortPreviewPath && !hasSortPreviewError && (hasSortPreviewRows || isSortPreviewLoading)) {
      return undefined;
    }
    if (trajectoryState.mode === mode && trajectoryState.error) {
      return undefined;
    }
    if (trajectoryPayloads.person || personTrajectoryManifest || (trajectoryState.loading && trajectoryState.mode === mode)) {
      return undefined;
    }

    const path = String(data?.meta?.person_trajectories_path || "").trim();
    if (!path) {
      return undefined;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/${path}`;
    setTrajectoryState({ loading: true, error: null, mode });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Trayectorias no disponibles: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        if (payload && Array.isArray(payload.chunks)) {
          setPersonTrajectoryManifest(payload);
        } else {
          setTrajectoryPayloads((prev) => ({ ...prev, person: payload || {} }));
        }
        setTrajectoryState({ loading: false, error: null, mode });
      })
      .catch((trajectoryError) => {
        if (trajectoryError.name === "AbortError") {
          return;
        }
        setTrajectoryState({ loading: false, error: trajectoryError.message || String(trajectoryError), mode });
      });

    return () => controller.abort();
  }, [
    data,
    personSortPreviewRowsBySort,
    personSortPreviewState.error,
    personSortPreviewState.loading,
    personSortPreviewState.sort,
    personTrajectoryManifest,
    resolvedTopicId,
    selectiveTopicPreviewTopicIds,
    state,
    topicDiscoveryTopicIds,
    topicPersonRowsByTopicId,
    topicPersonRowsState.error,
    topicPersonRowsState.loading,
    topicPersonRowsState.topicIdsKey,
    topicPreviewActive,
    topicPreviewIdsKey,
    topicPreviewTopicIds,
    trajectoryPayloads.person,
    trajectoryState.loading,
    trajectoryState.mode,
  ]);

  useEffect(() => {
    if (!selectedPoint || selectedPoint.scope !== "person") {
      setDetailState({ loading: false, error: null, personId: 0 });
      return undefined;
    }

    const personId = toInt(selectedPoint.personId);
    if (!personId) {
      setDetailState({ loading: false, error: null, personId: 0 });
      return undefined;
    }
    if (personDetails[personId]) {
      setDetailState({ loading: false, error: null, personId });
      return undefined;
    }

    const controller = new AbortController();
    const detailDir = String(data?.meta?.person_detail_dir || "person-details");
    const url = `${resolveBasePath()}/political-positions/data/${detailDir}/${personId}.json`;

    setDetailState({ loading: true, error: null, personId });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Detalle no disponible: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setPersonDetails((prev) => ({ ...prev, [personId]: payload || { evidence_samples_by_point: {} } }));
        setDetailState({ loading: false, error: null, personId });
      })
      .catch((detailError) => {
        if (detailError.name === "AbortError") {
          return;
        }
        setPersonDetails((prev) => ({ ...prev, [personId]: { evidence_samples_by_point: {}, _error: detailError.message || String(detailError) } }));
        setDetailState({ loading: false, error: detailError.message || String(detailError), personId });
      });

    return () => controller.abort();
  }, [data?.meta?.person_detail_dir, personDetails, selectedPoint]);

  const topicsById = useMemo(() => {
    const out = new Map();
    for (const topic of data?.topics || []) {
      out.set(toInt(topic.topic_id), {
        topic_id: toInt(topic.topic_id),
        label: String(topic.topic_label || topic.label || "").trim(),
        key: String(topic.topic_key || "").trim(),
      });
    }
    return out;
  }, [data?.topics]);
  const topicPreviewSelections = useMemo(
    () => buildTopicPreviewSelections({ topicIds: topicPreviewTopicIds, topicsById }),
    [topicPreviewTopicIds, topicsById],
  );
  const topicPreviewQuickPickTitle = useMemo(() => {
    if (normalizeMode(state.mode) !== "person" || topicPreviewModeLabel === "exact" || !topicPreviewSelections.length) {
      return "";
    }
    if (topicPreviewModeLabel === "q_search") {
      return "Temas detectados desde Buscar";
    }
    if (topicPreviewModeLabel === "topic_filter") {
      return "Temas detectados desde Tema";
    }
    return "Temas detectados";
  }, [state.mode, topicPreviewModeLabel, topicPreviewSelections.length]);
  const topicPreviewQuickPickSub = useMemo(() => {
    if (!topicPreviewQuickPickTitle) {
      return "";
    }
    if (topicPreviewModeLabel === "q_search") {
      return "Fija un tema exacto para dejar una URL compartible sin depender de la interpretación del buscador.";
    }
    return "Elige una coincidencia para convertir la vista actual en un tema exacto reproducible.";
  }, [topicPreviewModeLabel, topicPreviewQuickPickTitle]);

  const personsById = useMemo(() => {
    const out = new Map();
    for (const person of data?.persons || []) {
      out.set(toInt(person.person_id), {
        person_id: toInt(person.person_id),
        full_name: String(person.full_name || person.name || "").trim(),
        canonical_key: String(person.canonical_key || "").trim(),
        point_count: toInt(person.point_count || person.points_count || 0),
        latest_as_of: String(person.latest_as_of || ""),
        trajectory_chunk: String(person.trajectory_chunk || ""),
      });
    }
    return out;
  }, [data?.persons]);

  const personFilterOptions = useMemo(() => (
    (data?.persons || [])
      .map((person) => ({
        personId: toInt(person.person_id),
        fullName: String(person.full_name || person.name || "").trim(),
        canonicalKey: String(person.canonical_key || "").trim(),
      }))
      .filter((person) => person.fullName)
  ), [data?.persons]);

  const personTrajectoryChunkSummary = useMemo(() => {
    const chunks = Array.isArray(personTrajectoryManifest?.chunks) ? personTrajectoryManifest.chunks : [];
    if (!chunks.length) {
      return null;
    }
    const candidateChunkIds = candidatePersonTrajectoryChunkIds({
      state,
      chunks,
      personIndex: data?.persons || [],
      searchIndex: personSearchIndex,
      resolvedTopicId,
    });
    const loadedTotal = chunks.filter((chunk) => loadedPersonTrajectoryChunks[String(chunk?.chunk_id || "")]).length;
    const loadedCandidateTotal = candidateChunkIds.filter((chunkId) => loadedPersonTrajectoryChunks[chunkId]).length;
    return {
      total: chunks.length,
      loadedTotal,
      candidateTotal: candidateChunkIds.length,
      loadedCandidateTotal,
      scanMode: personTrajectoryScanMode(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds),
      filtered: personTrajectoryHasActiveFilters(state),
      exhaustive: personTrajectoryNeedsExhaustiveScan(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds),
    };
  }, [data?.persons, loadedPersonTrajectoryChunks, personSearchIndex, personTrajectoryManifest, resolvedTopicId, selectiveTopicPreviewTopicIds, state, topicDiscoveryTopicIds]);

  const activePersonScanMode = useMemo(() => (
    normalizeMode(state.mode) === "person" ? personTrajectoryScanMode(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds) : ""
  ), [resolvedTopicId, selectiveTopicPreviewTopicIds, state, topicDiscoveryTopicIds]);

  const partiesById = useMemo(() => {
    const out = new Map();
    for (const party of data?.parties || []) {
      out.set(toInt(party.party_id), {
        party_id: toInt(party.party_id),
        name: String(party.name || party.party || "").trim(),
        acronym: String(party.acronym || "").trim(),
      });
    }
    return out;
  }, [data?.parties]);

  const rows = useMemo(() => {
    const mode = normalizeMode(state.mode);
    const personScanMode = personTrajectoryScanMode(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds);
    const defaultPersonView = personScanMode === "default_rows";
    const sortPreviewKey = normalizeSortKey(state.sort);
    const maxRows = Math.max(10, Number(state.limit || 180));
    if (mode === "person" && defaultPersonView && Array.isArray(personDefaultRows)) {
      return personDefaultRows.slice(0, maxRows);
    }
    if (mode === "person" && personScanMode === "sort_preview" && Array.isArray(personSortPreviewRowsBySort[sortPreviewKey])) {
      return personSortPreviewRowsBySort[sortPreviewKey].slice(0, maxRows);
    }
    if (mode === "person" && topicPreviewActive) {
      const previewRows = topicPreviewTopicIds.flatMap((topicId) => {
        const normalizedTopicId = toInt(topicId);
        const topic = topicsById.get(normalizedTopicId) || {};
        return (Array.isArray(topicPersonRowsByTopicId[normalizedTopicId]) ? topicPersonRowsByTopicId[normalizedTopicId] : [])
          .map((row) => ({
            ...row,
            topicId: normalizedTopicId,
            topicLabel: String(topic.label || ""),
            topicKey: String(topic.key || ""),
          }));
      });
      if (previewRows.length) {
        return filterAndSortTopicPersonRows(previewRows, state, resolvedTopicFilter, topicsById);
      }
    }

    const query = normalize(state.q);
    const personFilter = normalize(state.person);
    const methodFilter = String(state.method || "all").trim().toLowerCase();
    const stanceFilter = String(state.stance || "all").trim().toLowerCase();
    const partyFilter = normalize(state.party);
    const personSeries = trajectoryPayloads.person || data?.person_trajectories || {};
    const partySeries = trajectoryPayloads.party || data?.party_trajectories || {};

    const out = [];

    if (mode === "party") {
      const entries = Object.entries(partySeries);
      for (const [partyIdRaw, points] of entries) {
        const party = partiesById.get(toInt(partyIdRaw));
        if (!party) {
          continue;
        }
        const partyLabel = `${party.name || `Partido ${party.party_id}`}` + (party.acronym ? ` (${party.acronym})` : "");
        if (partyFilter && !normalize(partyLabel).includes(partyFilter)) {
          continue;
        }
        for (const point of Array.isArray(points) ? points : []) {
          const topic = topicsById.get(toInt(point.topic_id)) || {};
          const topicLabel = String(point.topic_label || topic.label || "").trim();
          if (!topicFilterMatches({
            rawFilter: state.topic,
            resolvedTopic: resolvedTopicFilter,
            topicId: toInt(point.topic_id || topic.topic_id || 0),
            topicKey: String(point.topic_key || topic.key || ""),
            topicLabel,
          })) {
            continue;
          }
          const method = String(point.computed_method || "").toLowerCase();
          if (methodFilter !== "all" && method !== methodFilter) {
            continue;
          }
          const stance = String(point.stance || "").toLowerCase();
          if (stanceFilter !== "all" && stance !== stanceFilter) {
            continue;
          }
          if (query && ![topicLabel, partyLabel, String(point.as_of_date || "")].map(normalize).some((value) => value.includes(query))) {
            continue;
          }
          out.push({
            scope: "party",
            key: `p-${party.party_id}-${topic.topic_id || 0}-${point.as_of_date || ""}-${method}`,
            partyId: party.party_id,
            partyLabel,
            party,
            personId: 0,
            personName: "",
            topicId: toInt(point.topic_id || 0),
            topicLabel,
            topicKey: String(topic.key || point.topic_key || ""),
            asOf: String(point.as_of_date || ""),
            windowDays: toInt(point.window_days),
            method,
            stance,
            score: clamp01(point.score),
            confidence: clamp01(point.confidence),
            evidenceCount: toInt(point.evidence_count || 0),
            lastEvidenceDate: String(point.last_evidence_date || ""),
            evidenceBreakdown: point.evidence_breakdown || {},
            reviewSummary: point.review_summary || {},
            samples: Array.isArray(point.evidence_samples) ? point.evidence_samples : [],
          });
        }
      }
    } else {
      for (const [personIdRaw, points] of Object.entries(personSeries)) {
        const person = personsById.get(toInt(personIdRaw));
        if (!person) {
          continue;
        }
        const personHaystack = normalize(`${String(person.full_name || "")} ${String(person.canonical_key || "")}`);
        if (personFilter && !personHaystack.includes(personFilter)) {
          continue;
        }
        for (const point of Array.isArray(points) ? points : []) {
          const topic = topicsById.get(toInt(point.topic_id)) || {};
          const topicLabel = String(point.topic_label || topic.label || "").trim();
          if (!topicFilterMatches({
            rawFilter: state.topic,
            resolvedTopic: resolvedTopicFilter,
            topicId: toInt(point.topic_id || topic.topic_id || 0),
            topicKey: String(point.topic_key || topic.key || ""),
            topicLabel,
          })) {
            continue;
          }
          const method = String(point.computed_method || "").toLowerCase();
          if (methodFilter !== "all" && method !== methodFilter) {
            continue;
          }
          const stance = String(point.stance || "").toLowerCase();
          if (stanceFilter !== "all" && stance !== stanceFilter) {
            continue;
          }
          const partyCard = partiesById.get(toInt(point.party_id || 0));
          const partyLabel = String(
            point.party_label
            || partyCard?.name
            || partyCard?.acronym
            || ""
          ).trim();
          const rowHaystack = [
            String(person.full_name || ""),
            String(person.canonical_key || ""),
            String(topicLabel || ""),
            partyLabel,
            String(point.as_of_date || ""),
            String(method || ""),
            String(point.topic_key || topic.key || ""),
          ].map(normalize).join(" ");
          if (query && !rowHaystack.includes(query)) {
            continue;
          }
          if (partyFilter) {
            if (!normalize(partyLabel).includes(partyFilter)) {
              continue;
            }
          }
          out.push({
            scope: "person",
            key: `i-${personIdRaw}-${topic.topic_id || 0}-${point.as_of_date || ""}-${method}`,
            personId: toInt(person.person_id || personIdRaw),
            personName: String(person.full_name || ""),
            person,
            partyId: toInt(point.party_id || 0),
            partyLabel,
            topicId: toInt(point.topic_id || 0),
            topicLabel,
            topicKey: String(point.topic_key || topic.key || ""),
            asOf: String(point.as_of_date || ""),
            windowDays: toInt(point.window_days),
            method,
            stance,
            score: clamp01(point.score),
            confidence: clamp01(point.confidence),
            evidenceCount: toInt(point.evidence_count || 0),
            lastEvidenceDate: String(point.last_evidence_date || ""),
            evidenceBreakdown: point.evidence_breakdown || {},
            reviewSummary: point.review_summary || {},
            samples: Array.isArray(point.evidence_samples) ? point.evidence_samples : [],
          });
        }
      }
    }

    out.sort((a, b) => compareTrajectoryRows(a, b, String(state.sort || "person")));

    return out.slice(0, maxRows);
  }, [data, partiesById, personDefaultRows, personSortPreviewRowsBySort, personsById, resolvedTopicFilter, resolvedTopicId, selectiveTopicPreviewTopicIds, state, topicDiscoveryTopicIds, topicPersonRowsByTopicId, topicPreviewActive, topicPreviewTopicIds, topicsById, trajectoryPayloads]);

  const personTrajectoryTargetChunkIds = useMemo(() => nextPersonTrajectoryChunkIds({
    state,
    chunks: personTrajectoryManifest?.chunks || [],
    personIndex: data?.persons || [],
    searchIndex: personSearchIndex,
    resolvedTopicId,
    previewTopicIds: selectiveTopicPreviewTopicIds,
    discoveryTopicIds: topicDiscoveryTopicIds,
    loadedChunks: loadedPersonTrajectoryChunks,
    currentRowsCount: normalizeMode(state.mode) === "person" ? rows.length : 0,
    limit: state.limit,
  }), [data?.persons, loadedPersonTrajectoryChunks, personSearchIndex, personTrajectoryManifest, resolvedTopicId, rows.length, selectiveTopicPreviewTopicIds, state, topicDiscoveryTopicIds]);

  useEffect(() => {
    if (!data) {
      return undefined;
    }
    const personScanMode = personTrajectoryScanMode(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds);
    if (isDefaultPersonView(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds)) {
      return undefined;
    }
    if (normalizeMode(state.mode) !== "person") {
      return undefined;
    }
    if (personScanMode === "topic_discovery") {
      return undefined;
    }
    if (topicPreviewActive) {
      return undefined;
    }
    if (trajectoryPayloads.person && !personTrajectoryManifest) {
      return undefined;
    }
    if (!personTrajectoryManifest || (trajectoryState.loading && trajectoryState.mode === "person")) {
      return undefined;
    }
    if (trajectoryState.mode === "person" && trajectoryState.error) {
      return undefined;
    }
    if (!personTrajectoryTargetChunkIds.length) {
      return undefined;
    }
    if (needsPersonSearchIndex && !personSearchIndex && !personSearchIndexState.error) {
      return undefined;
    }

    const chunkDir = String(
      data?.meta?.person_trajectory_chunk_dir
      || personTrajectoryManifest?.meta?.chunk_dir
      || "person-trajectory-chunks"
    ).trim();
    if (!chunkDir) {
      return undefined;
    }

    const controller = new AbortController();
    setTrajectoryState({ loading: true, error: null, mode: "person" });

    Promise.all(
      personTrajectoryTargetChunkIds.map((chunkId) => {
        const url = `${resolveBasePath()}/political-positions/data/${chunkDir}/${chunkId}.json`;
        return fetch(url, { signal: controller.signal })
          .then((response) => {
            if (!response.ok) {
              throw new Error(`Chunk no disponible: ${response.status}`);
            }
            return response.json();
          })
          .then((payload) => [chunkId, payload || {}]);
      }),
    )
      .then((entries) => {
        const mergedSeries = {};
        for (const [chunkId, payload] of entries) {
          if (payload && typeof payload === "object") {
            Object.assign(mergedSeries, payload);
          }
        }
        setLoadedPersonTrajectoryChunks((prev) => {
          const next = { ...prev };
          for (const [chunkId] of entries) {
            next[chunkId] = true;
          }
          return next;
        });
        setTrajectoryPayloads((prev) => ({ ...prev, person: { ...(prev.person || {}), ...mergedSeries } }));
        setTrajectoryState({ loading: false, error: null, mode: "person" });
      })
      .catch((trajectoryError) => {
        if (trajectoryError.name === "AbortError") {
          return;
        }
        setTrajectoryState({ loading: false, error: trajectoryError.message || String(trajectoryError), mode: "person" });
      });

    return () => controller.abort();
  }, [
    data,
    personTrajectoryManifest,
    personSearchIndex,
    personSearchIndexState.error,
    personTrajectoryTargetChunkIds,
    needsPersonSearchIndex,
    resolvedTopicId,
    selectiveTopicPreviewTopicIds,
    state,
    topicDiscoveryTopicIds,
    topicPreviewActive,
    trajectoryPayloads.person,
    trajectoryState.error,
    trajectoryState.loading,
    trajectoryState.mode,
  ]);

  const activeTrajectoryLoading = trajectoryState.loading && trajectoryState.mode === normalizeMode(state.mode);
  const activeTrajectoryError = trajectoryState.mode === normalizeMode(state.mode) ? trajectoryState.error : null;
  const activeDefaultRowsLoading = isDefaultPersonView(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds) && personDefaultRowsState.loading;
  const activeDefaultRowsError = isDefaultPersonView(state, resolvedTopicId, selectiveTopicPreviewTopicIds, topicDiscoveryTopicIds) ? personDefaultRowsState.error : null;
  const activeSortPreviewLoading = activePersonScanMode === "sort_preview"
    && personSortPreviewState.loading
    && personSortPreviewState.sort === normalizeSortKey(state.sort);
  const activeSortPreviewError = activePersonScanMode === "sort_preview"
    && personSortPreviewState.sort === normalizeSortKey(state.sort)
    ? personSortPreviewState.error
    : null;
  const activeTopicPreviewLoading = activePersonScanMode === "topic_preview"
    && topicPersonRowsState.loading
    && topicPersonRowsState.topicIdsKey === topicPreviewIdsKey;
  const activeTopicPreviewError = activePersonScanMode === "topic_preview"
    && topicPersonRowsState.topicIdsKey === topicPreviewIdsKey
    ? topicPersonRowsState.error
    : null;
  const activeTopicSearchIndexLoading = normalizeMode(state.mode) === "person"
    && needsTopicSearchIndex
    && topicSearchIndexState.loading;
  const activeTopicSearchIndexError = normalizeMode(state.mode) === "person"
    && needsTopicSearchIndex
    ? topicSearchIndexState.error
    : null;
  const activePersonSearchIndexLoading = normalizeMode(state.mode) === "person"
    && personTrajectoryHasActiveFilters(state)
    && needsPersonSearchIndex
    && personSearchIndexState.loading;
  const activePersonSearchIndexError = normalizeMode(state.mode) === "person"
    && personTrajectoryHasActiveFilters(state)
    && needsPersonSearchIndex
    ? personSearchIndexState.error
    : null;

  const selectedPersonCard = useMemo(() => {
    if (!selectedPoint || selectedPoint.scope !== "person") {
      return null;
    }
    const person = personsById.get(selectedPoint.personId);
    if (!person) {
      return null;
    }
    return person;
  }, [selectedPoint, personsById]);

  const selectedPartyCard = useMemo(() => {
    if (!selectedPoint || selectedPoint.scope !== "party") {
      return null;
    }
    return partiesById.get(selectedPoint.partyId);
  }, [selectedPoint, partiesById]);

  const selectedPointWithDetails = useMemo(() => {
    if (!selectedPoint || selectedPoint.scope !== "person") {
      return selectedPoint;
    }
    const detailPayload = personDetails[toInt(selectedPoint.personId)];
    if (!detailPayload || typeof detailPayload !== "object") {
      return selectedPoint;
    }
    const samples = detailPayload?.evidence_samples_by_point?.[pointDetailKey(selectedPoint)];
    return {
      ...selectedPoint,
      samples: Array.isArray(samples) ? samples : [],
    };
  }, [personDetails, selectedPoint]);

  const selectedPointDetailLoading = Boolean(
    selectedPoint
    && selectedPoint.scope === "person"
    && detailState.loading
    && toInt(detailState.personId) === toInt(selectedPoint.personId)
  );

  const continuityBreadcrumb = useMemo(() => buildPoliticalPositionsContinuityBreadcrumb({
    exactTopicOriginContext,
    exactTopicLabel: resolvedTopicFilter?.label || resolvedTopicFilter?.key || "",
    resolvedTopicId,
    discoveryOriginContext: continuityDiscoveryOriginContext,
    originDiscoveryResumeNotice,
    originDiscoveryVariantSelection,
  }), [
    continuityDiscoveryOriginContext,
    exactTopicOriginContext,
    originDiscoveryResumeNotice,
    originDiscoveryVariantSelection,
    resolvedTopicFilter,
    resolvedTopicId,
  ]);
  const detailContinuityBreadcrumb = useMemo(() => buildPoliticalPositionsDetailBreadcrumb({
    continuityBreadcrumb,
    selectedPoint: selectedPointWithDetails,
    selectedPersonCard,
    selectedPartyCard,
  }), [
    continuityBreadcrumb,
    selectedPartyCard,
    selectedPersonCard,
    selectedPointWithDetails,
  ]);
  const detailPanelSummary = useMemo(() => (
    buildPoliticalPositionsDetailPanelSummary({
      selectedPoint: selectedPointWithDetails,
      resolvedTopicFilter,
      detailContinuityBreadcrumb,
    })
  ), [detailContinuityBreadcrumb, resolvedTopicFilter, selectedPointWithDetails]);
  const detailOverviewEntries = useMemo(
    () => buildPoliticalPositionsDetailOverview(selectedPointWithDetails),
    [selectedPointWithDetails],
  );
  const detailReviewLabel = useMemo(
    () => selectedPointWithDetails ? compactReviewLabel(selectedPointWithDetails) : "",
    [selectedPointWithDetails],
  );
  const detailDrilldownLinks = useMemo(() => (
    buildPoliticalPositionsDetailDrilldownLinks({
      basePath: resolveBasePath(),
      selectedPoint: selectedPointWithDetails,
      topicSetId: data?.meta?.topic_set_id,
    })
  ), [data?.meta?.topic_set_id, selectedPointWithDetails]);
  const evidenceTableHeader = useMemo(() => (
    buildPoliticalPositionsEvidenceTableHeader({
      selectedPoint: selectedPointWithDetails,
      visibleSampleCount: Array.isArray(selectedPointWithDetails?.samples) ? Math.min(selectedPointWithDetails.samples.length, 6) : 0,
      availableSampleCount: Array.isArray(selectedPointWithDetails?.samples) ? selectedPointWithDetails.samples.length : 0,
      reviewLabel: detailReviewLabel,
      drilldownLinks: detailDrilldownLinks,
    })
  ), [detailDrilldownLinks, detailReviewLabel, selectedPointWithDetails]);
  const evidenceTablePrimaryLink = useMemo(
    () => evidenceTableHeader?.links?.find((link) => link.role === "primary") || null,
    [evidenceTableHeader],
  );
  const evidenceTableSecondaryLinks = useMemo(
    () => evidenceTableHeader?.links?.filter((link) => link.role === "secondary") || [],
    [evidenceTableHeader],
  );
  const visibleEvidenceSamples = useMemo(
    () => Array.isArray(selectedPointWithDetails?.samples) ? selectedPointWithDetails.samples.slice(0, 6) : [],
    [selectedPointWithDetails],
  );

  useEffect(() => {
    if (typeof document === "undefined" || !topicDiscoveryActive || !originDiscoveryTargetTopicId) {
      lastOriginDiscoveryTargetRef.current = "";
      return;
    }
    const targetKey = String(originDiscoveryTargetTopicId);
    if (lastOriginDiscoveryTargetRef.current === targetKey) {
      return;
    }
    const target = document.querySelector(`[data-topic-discovery-origin-target="${targetKey}"]`);
    if (!target) {
      return;
    }
    if (typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    if (typeof target.focus === "function") {
      try {
        target.focus({ preventScroll: true });
      } catch {
        target.focus();
      }
    }
    lastOriginDiscoveryTargetRef.current = targetKey;
  }, [originDiscoveryTargetTopicId, topicDiscoveryActive]);

  useEffect(() => {
    if (!topicDiscoveryActive || !originTopicId) {
      setDismissedOriginNoticeTopicId(0);
      return;
    }
    setDismissedOriginNoticeTopicId((prev) => (prev === originTopicId ? prev : 0));
  }, [originTopicId, topicDiscoveryActive]);

  if (loading) {
    return (
      <main className="shell">
        <section className="card block">
          <p className="sub">Cargando posturas trazables…</p>
        </section>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="shell">
        <section className="card block">
          <h2>Error de publicación</h2>
          <p className="sub">No pude cargar <code>political-positions/data/stances.json</code>.</p>
          <p className="sub">Error: {error || "sin datos"}</p>
          <p className="sub">Genera el snapshot con: <code>python3 scripts/export_political_positions_snapshot.py --db etl/data/staging/politicos-es.db --snapshot-date 2026-02-12</code>.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Postura política explicable</p>
        <h1>Topic stance scoring (por persona y partido)</h1>
        <p className="sub">
          Vistas explicables de posición por tema con evidencia rastreable y estado de revisión para auditoría.
        </p>
        <div className="chips" style={{ marginTop: 12 }}>
          <span className="chip">Snapshot: {data.meta?.snapshot_date || "—"}</span>
          <span className="chip">Personas: {toInt((data.persons || []).length)}</span>
          <span className="chip">Partidos: {toInt((data.parties || []).length)}</span>
          <span className="chip">Topics: {toInt((data.topics || []).length)}</span>
          <span className="chip">Pendientes de revisión: {toInt(data.meta?.review_pending || 0)}</span>
        </div>
      </section>

      <section className="card block">
        <div className="filterGrid">
          <label className="field">
            Vista
            <select value={state.mode} onChange={(e) => setState((prev) => ({ ...prev, mode: e.target.value }))}>
              <option value="person">Personas</option>
              <option value="party">Partidos</option>
            </select>
          </label>
          <label className="field">
            Buscar
            <input
              className="textInput"
              type="search"
              value={state.q}
              placeholder="Persona, partido, tema, método"
              onChange={(e) => setState((prev) => ({ ...prev, q: e.target.value, pack: "", concern: "", originPack: "", originConcern: "", originTopicId: 0 }))}
            />
          </label>
          <label className="field">
            Buscar como
            <select
              value={normalizeSearchMode(state.searchMode)}
              onChange={(e) => setState((prev) => ({ ...prev, searchMode: normalizeSearchMode(e.target.value) }))}
            >
              <option value="auto">Auto</option>
              <option value="topic">Tema</option>
              <option value="person">Persona</option>
            </select>
          </label>
          <label className="field">
            Persona
            <input
              className="textInput"
              type="search"
              list="political-positions-person-options"
              value={state.person}
              placeholder="Nombre o clave canónica"
              onChange={(e) => setState((prev) => ({ ...prev, person: e.target.value }))}
            />
            <datalist id="political-positions-person-options">
              {personFilterOptions.map((person) => (
                <option
                  key={`person-filter-${person.personId}`}
                  value={person.fullName}
                  label={person.canonicalKey ? `${person.fullName} · ${person.canonicalKey}` : person.fullName}
                />
              ))}
            </datalist>
          </label>
          <label className="field">
            Método
            <select value={state.method} onChange={(e) => setState((prev) => ({ ...prev, method: e.target.value }))}>
              <option value="all">Todos</option>
              <option value="combined">Combined</option>
              <option value="votes">Votos</option>
              <option value="declared">Declarado</option>
            </select>
          </label>
          <label className="field">
            Postura
            <select value={state.stance} onChange={(e) => setState((prev) => ({ ...prev, stance: e.target.value }))}>
              <option value="all">Todas</option>
              <option value="support">Support</option>
              <option value="oppose">Oppose</option>
              <option value="mixed">Mixto</option>
              <option value="unclear">Poco claro</option>
              <option value="no_signal">Sin señal</option>
            </select>
          </label>
          <label className="field">
            Tema
            <input
              className="textInput"
              list="political-positions-topic-options"
              value={state.topic}
              placeholder="Tema exacto sugerido o texto libre"
              onChange={(e) => setState((prev) => ({ ...prev, topic: e.target.value, topicId: 0, pack: "", concern: "", originPack: "", originConcern: "", originTopicId: 0 }))}
            />
            <datalist id="political-positions-topic-options">
              {topicFilterOptions.map((topic) => (
                <option
                  key={`topic-filter-${topic.topicId}`}
                  value={topic.label}
                  label={topic.key || topic.label}
                />
              ))}
            </datalist>
          </label>
          <label className="field">
            Partido
            <input
              className="textInput"
              value={state.party}
              placeholder="Filtrar por partido"
              onChange={(e) => setState((prev) => ({ ...prev, party: e.target.value }))}
            />
          </label>
          <label className="field">
            Ordenar
            <select value={state.sort} onChange={(e) => setState((prev) => ({ ...prev, sort: e.target.value }))}>
              <option value="person">Persona/Partido + Tema</option>
              <option value="topic">Tema</option>
              <option value="party">Partido</option>
              <option value="as_of">Fecha (más reciente)</option>
              <option value="confidence_desc">Confianza (alta)</option>
              <option value="confidence_asc">Confianza (baja)</option>
              <option value="method">Método</option>
              <option value="stance">Postura</option>
            </select>
          </label>
          <label className="field">
            Límite filas
            <select
              value={String(state.limit || 180)}
              onChange={(e) => setState((prev) => ({ ...prev, limit: Number(e.target.value) || 180 }))}
            >
              <option value={120}>120</option>
              <option value={180}>180</option>
              <option value={240}>240</option>
              <option value={320}>320</option>
              <option value={400}>400</option>
            </select>
          </label>
        </div>

        {state.mode === "person" ? (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">Rutas por pack</span>
            <p className="sub" style={{ marginTop: 4 }}>
              Agrupaciones editoriales de preocupaciones con tradeoff explícito. Cada pack abre una exploración temática estática antes de tocar trayectorias de personas.
            </p>
            <div className="chips" style={{ marginTop: 10 }}>
              {concernPackEntries.map((pack) => {
                const active = activePackEntry?.id === pack.id;
                return (
                  <button
                    key={`concern-pack-${pack.id}`}
                    type="button"
                    className="chip"
                    onClick={() => setState((prev) => ({
                      ...prev,
                      pack: active ? "" : pack.id,
                      concern: "",
                      originPack: "",
                      originConcern: "",
                      originTopicId: 0,
                      q: "",
                      topic: "",
                      topicId: 0,
                      searchMode: "auto",
                    }))}
                    style={active ? {
                      cursor: "pointer",
                      appearance: "none",
                      background: "#12344a",
                      borderColor: "#0f2c40",
                      color: "#eef7fb",
                    } : { cursor: "pointer", appearance: "none" }}
                    title={pack.tradeoff || pack.label}
                  >
                    {pack.label} · {pack.topicCount}
                  </button>
                );
              })}
            </div>
            {activePackEntry ? (
              <>
                <p className="sub" style={{ marginTop: 10 }}>
                  {activePackEntry.tradeoff || "Pack curado para exploración temática más guiada."}
                </p>
                <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
                  {(activePackEntry.concerns || []).map((concern) => (
                    <div
                      key={`active-pack-concern-${concern.id}`}
                      style={{
                        border: "1px solid rgba(18, 52, 74, 0.12)",
                        borderRadius: 12,
                        padding: "10px 12px",
                        background: "#f7fafb",
                      }}
                    >
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                        <strong>{concern.label}</strong>
                        <span className="chip">{concern.topicCount} temas</span>
                      </div>
                      {concern.description ? (
                        <p className="sub" style={{ marginTop: 6 }}>
                          {concern.description}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </article>
        ) : null}

        {state.mode === "person" ? (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">{concernSectionTitle}</span>
            <p className="sub" style={{ marginTop: 4 }}>
              {concernSectionSub}
            </p>
            <div className="chips" style={{ marginTop: 10 }}>
              {visibleConcernEntries.map((concern) => {
                const active = activeConcernEntry?.id === concern.id;
                return (
                  <button
                    key={`concern-entry-${concern.id}`}
                    type="button"
                    className="chip"
                    onClick={() => setState((prev) => ({
                      ...prev,
                      pack: "",
                      concern: active ? "" : concern.id,
                      originPack: "",
                      originConcern: "",
                      originTopicId: 0,
                      q: "",
                      topic: "",
                      topicId: 0,
                      searchMode: "auto",
                    }))}
                    style={active ? {
                      cursor: "pointer",
                      appearance: "none",
                      background: "#e45838",
                      borderColor: "#d24a2f",
                      color: "#fff7f0",
                    } : { cursor: "pointer", appearance: "none" }}
                    title={concern.description || concern.label}
                  >
                    {concern.label} · {concern.topicCount}
                  </button>
                );
              })}
            </div>
          </article>
        ) : null}

        {continuityBreadcrumb && !(continuityBreadcrumb.mode === "discovery" && dismissedOriginNoticeTopicId === originTopicId) ? (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">{continuityBreadcrumb.statusLabel}</span>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
              {continuityBreadcrumb.items.map((item, index) => (
                <span key={`continuity-breadcrumb-${item.kind}-${index}`} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {index > 0 ? <span className="sub">›</span> : null}
                  <span className="chip">{continuityBreadcrumbItemLabel(item)}</span>
                </span>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
              {continuityBreadcrumb.primaryAction ? (
                <button
                  type="button"
                  className="chip"
                  onClick={() => {
                    if (continuityBreadcrumb.primaryAction.kind === "restore_discovery") {
                      setState((prev) => restorePoliticalPositionsDiscoveryState(prev));
                      return;
                    }
                    if (continuityBreadcrumb.primaryAction.kind === "open_exact" && originDiscoveryVariantSelection) {
                      setState((prev) => applyTopicPreviewSelection({
                        prevState: prev,
                        selection: originDiscoveryVariantSelection,
                        sourceMode: topicDiscoveryContext.sourceMode,
                      }));
                    }
                  }}
                  style={{ cursor: "pointer", appearance: "none" }}
                >
                  {continuityBreadcrumb.primaryAction.label}
                </button>
              ) : null}
              {continuityBreadcrumb.meta?.familyCount > 1 ? (
                <span className="chip">{continuityBreadcrumb.meta.familyCount} variantes</span>
              ) : null}
              {continuityBreadcrumb.meta?.familyMatchMode === "near_duplicate" ? (
                <span className="chip">Claim compartido</span>
              ) : null}
              {continuityBreadcrumb.dismissible ? (
                <button
                  type="button"
                  className="chip"
                  onClick={() => setDismissedOriginNoticeTopicId(originTopicId)}
                  style={{ cursor: "pointer", appearance: "none" }}
                >
                  Ocultar ruta
                </button>
              ) : null}
            </div>
          </article>
        ) : null}

        {topicPreviewQuickPickTitle ? (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">
              {topicPreviewQuickPickTitle} ({topicPreviewSelections.length})
            </span>
            <p className="sub" style={{ marginTop: 4 }}>
              {topicPreviewQuickPickSub}
            </p>
            <div className="chips" style={{ marginTop: 10 }}>
              {topicPreviewSelections.map((topic) => (
                <button
                  key={`topic-preview-selection-${topic.topicId}`}
                  type="button"
                  className="chip"
                  onClick={() => setState((prev) => applyTopicPreviewSelection({
                    prevState: prev,
                    selection: topic,
                    sourceMode: topicPreviewModeLabel,
                  }))}
                  style={{ cursor: "pointer", appearance: "none" }}
                  title={topic.key || topic.label}
                >
                  {topic.label}
                </button>
              ))}
            </div>
          </article>
        ) : null}
        {topicDiscoveryActive ? (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">
              {topicDiscoveryTitle} ({topicDiscoverySelections.length})
            </span>
            <p className="sub" style={{ marginTop: 4 }}>
              {topicDiscoverySub}
            </p>
            {topicDiscoveryContext.sourceMode === "pack_discovery" ? (
              <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
                {topicDiscoverySelections.map((topic) => {
                  const originHighlight = resolveTopicDiscoveryOriginHighlight({ topic, originTopicId });
                  return (
                  <div
                    key={`topic-discovery-selection-${topic.topicId}`}
                    data-topic-discovery-origin-target={originHighlight.isOriginFamily ? String(toInt(topic.topicId)) : undefined}
                    tabIndex={originHighlight.isOriginFamily ? -1 : undefined}
                    style={{
                      border: originHighlight.isOriginFamily ? "1px solid rgba(228, 88, 56, 0.45)" : "1px solid rgba(18, 52, 74, 0.14)",
                      borderRadius: 14,
                      background: originHighlight.isOriginFamily ? "#fff3ed" : "#fffdf9",
                      boxShadow: originHighlight.isOriginFamily ? "0 0 0 2px rgba(228, 88, 56, 0.12)" : "none",
                      scrollMarginTop: originHighlight.isOriginFamily ? 96 : undefined,
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setState((prev) => applyTopicPreviewSelection({
                        prevState: prev,
                        selection: topic,
                        sourceMode: topicDiscoveryContext.sourceMode,
                      }))}
                      style={{
                        cursor: "pointer",
                        appearance: "none",
                        textAlign: "left",
                        padding: "12px 14px",
                        width: "100%",
                        border: "none",
                        background: "transparent",
                      }}
                      title={topic.key || topic.label}
                    >
                      <strong style={{ display: "block" }}>
                        {topic.topicHeadline || topic.label}
                      </strong>
                      {topic.topicHeadline && topic.topicHeadline !== topic.label ? (
                        <span className="sub" style={{ display: "block", marginTop: 4 }}>
                          {topic.label}
                        </span>
                      ) : null}
                      {topic.editorialSummary ? (
                        <span className="sub" style={{ display: "block", marginTop: 6 }}>
                          {topic.editorialSummary}
                        </span>
                      ) : null}
                      {(topic.topicProcedure || (Array.isArray(topic.matchedConcernLabels) && topic.matchedConcernLabels.length)) ? (
                        <span style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                          {Array.isArray(topic.familyProcedures) && topic.familyProcedures.length
                            ? topic.familyProcedures.map((procedure) => (
                              <span key={`topic-discovery-selection-${topic.topicId}-${procedure}`} className="chip">
                                {procedure}
                              </span>
                            ))
                            : topic.topicProcedure ? (
                              <span className="chip">{topic.topicProcedure}</span>
                            ) : null}
                          {Number(topic.familyCount || 0) > 1 && topic.familyMatchMode === "near_duplicate" ? (
                            <span className="chip">Claim compartido</span>
                          ) : null}
                          {Number(topic.familyCount || 0) > 1 ? (
                            <span className="chip">{topic.familyCount} variantes</span>
                          ) : null}
                          {originHighlight.isOriginFamily ? (
                            <span className="chip">Tema retomado</span>
                          ) : null}
                          {topic.matchedConcernLabels.map((label) => (
                            <span key={`topic-discovery-selection-${topic.topicId}-${label}`} className="chip">
                              {label}
                            </span>
                          ))}
                        </span>
                      ) : null}
                    </button>
                    {Array.isArray(topic.familyVariants) && topic.familyVariants.length > 1 ? (
                      <div
                        className="sub"
                        style={{
                          display: "block",
                          padding: "0 14px 12px",
                          borderTop: "1px solid rgba(18, 52, 74, 0.08)",
                        }}
                      >
                        <span style={{ display: "block", marginTop: 8, fontWeight: 600, color: "#12344a" }}>
                          Variantes agrupadas
                        </span>
                        <span style={{ display: "block", marginTop: 4 }}>
                          Elige una variante para fijar ese tema exacto.
                        </span>
                        <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
                          {topic.familyVariants.map((variant) => {
                            const isRepresentative = toInt(variant.topicId) === toInt(topic.topicId);
                            const isOriginVariant = toInt(variant.topicId) === originTopicId;
                            return (
                              <button
                                key={`topic-discovery-selection-${topic.topicId}-variant-${variant.topicId}`}
                                type="button"
                                onClick={() => setState((prev) => applyTopicPreviewSelection({
                                  prevState: prev,
                                  selection: variant,
                                  sourceMode: topicDiscoveryContext.sourceMode,
                                }))}
                                style={{
                                  cursor: "pointer",
                                  appearance: "none",
                                  textAlign: "left",
                                  width: "100%",
                                  border: isOriginVariant ? "1px solid rgba(228, 88, 56, 0.45)" : "1px solid rgba(18, 52, 74, 0.12)",
                                  borderRadius: 10,
                                  background: isOriginVariant ? "#ffece3" : (isRepresentative ? "#fff4e8" : "#ffffff"),
                                  padding: "8px 10px",
                                }}
                                title={variant.label || variant.topicHeadline || ""}
                              >
                                <span style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                                  {variant.topicProcedure ? (
                                    <span className="chip">{variant.topicProcedure}</span>
                                  ) : null}
                                  {isRepresentative ? (
                                    <span className="chip">Representativa</span>
                                  ) : null}
                                  {isOriginVariant ? (
                                    <span className="chip">Variante retomada</span>
                                  ) : null}
                                </span>
                                <span style={{ display: "block", marginTop: 6 }}>
                                  {variant.label || variant.topicHeadline}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ) : null}
                  </div>
                );})}
              </div>
            ) : (
              <div className="chips" style={{ marginTop: 10 }}>
                {topicDiscoverySelections.map((topic) => {
                  const originHighlight = resolveTopicDiscoveryOriginHighlight({ topic, originTopicId });
                  return (
                    <button
                      key={`topic-discovery-selection-${topic.topicId}`}
                      type="button"
                      data-topic-discovery-origin-target={originHighlight.isOriginFamily ? String(toInt(topic.topicId)) : undefined}
                      className="chip"
                      onClick={() => setState((prev) => applyTopicPreviewSelection({
                        prevState: prev,
                        selection: topic,
                        sourceMode: topicDiscoveryContext.sourceMode,
                      }))}
                      style={originHighlight.isOriginFamily
                        ? { cursor: "pointer", appearance: "none", background: "#e45838", borderColor: "#d24a2f", color: "#fff7f0" }
                        : { cursor: "pointer", appearance: "none" }}
                      title={topic.key || topic.label}
                    >
                      {topic.label}{originHighlight.isOriginFamily ? " · retomado" : ""}
                    </button>
                  );
                })}
              </div>
            )}
          </article>
        ) : null}

        <div className="chips" style={{ marginTop: 10 }}>
          <span className="chip">Filas mostradas: {rows.length}</span>
          <span className="chip">Filas calculadas: {rows.length}</span>
          {state.mode === "person" ? (
            <span className="chip">Modo: comparación persona · tema · método</span>
          ) : (
            <span className="chip">Modo: agregación por grupo parlamentario</span>
          )}
          {qInterpretationLabel ? (
            <span className="chip">Buscar: {qInterpretationLabel}</span>
          ) : null}
          {activePackEntry ? (
            <span className="chip">Pack: {activePackEntry.label}</span>
          ) : null}
          {activeConcernEntry ? (
            <span className="chip">Preocupación: {activeConcernEntry.label}</span>
          ) : null}
          {activeDefaultRowsLoading ? (
            <span className="chip">Cargando filas iniciales…</span>
          ) : null}
          {!activeDefaultRowsLoading && activeDefaultRowsError ? (
            <span className="chip">Error de filas iniciales</span>
          ) : null}
          {state.mode === "person" && activePersonScanMode === "default_rows" && Array.isArray(personDefaultRows) ? (
            <span className="chip">Vista rápida sin chunks</span>
          ) : null}
          {activeSortPreviewLoading ? (
            <span className="chip">Cargando vista ordenada…</span>
          ) : null}
          {!activeSortPreviewLoading && activeSortPreviewError ? (
            <span className="chip">Error de vista ordenada</span>
          ) : null}
          {state.mode === "person" && activePersonScanMode === "sort_preview" && Array.isArray(personSortPreviewRowsBySort[normalizeSortKey(state.sort)]) ? (
            <span className="chip">Vista ordenada estática</span>
          ) : null}
          {activeTopicPreviewLoading ? (
            <span className="chip">Cargando vista temática…</span>
          ) : null}
          {!activeTopicPreviewLoading && activeTopicPreviewError ? (
            <span className="chip">Error de vista temática</span>
          ) : null}
          {activeTopicSearchIndexLoading ? (
            <span className="chip">Cargando índice temático…</span>
          ) : null}
          {!activeTopicSearchIndexLoading && activeTopicSearchIndexError ? (
            <span className="chip">Error de índice temático</span>
          ) : null}
          {state.mode === "person" && needsTopicSearchIndex && topicSearchIndex && !activeTopicSearchIndexLoading && !activeTopicSearchIndexError ? (
            <span className="chip">Índice temático estático</span>
          ) : null}
          {state.mode === "person" && activePersonScanMode === "topic_preview" && topicPreviewTopicIds.every((topicId) => Array.isArray(topicPersonRowsByTopicId[toInt(topicId)])) ? (
            <span className="chip">
              {topicPreviewModeLabel === "exact"
                ? "Vista temática estática"
                : topicPreviewModeLabel === "q_search"
                  ? "Vista temática por búsqueda"
                  : "Vista temática selectiva"}
            </span>
          ) : null}
          {state.mode === "person" && activePersonScanMode === "topic_discovery" ? (
            <span className="chip">Exploración temática sin chunks</span>
          ) : null}
          {activePersonSearchIndexLoading ? (
            <span className="chip">Cargando índice de búsqueda…</span>
          ) : null}
          {!activePersonSearchIndexLoading && activePersonSearchIndexError ? (
            <span className="chip">Error de índice de búsqueda</span>
          ) : null}
          {state.mode === "person" && needsPersonSearchIndex && personSearchIndex && !activePersonSearchIndexLoading && !activePersonSearchIndexError ? (
            <span className="chip">Índice estático de búsqueda</span>
          ) : null}
          {resolvedTopicFilter ? (
            <span className="chip">
              {toInt(state.topicId || 0) > 0 ? `Tema exacto #${toInt(state.topicId)}` : "Tema exacto"}
            </span>
          ) : null}
          {activeTrajectoryLoading ? (
            <span className="chip">Cargando trayectorias…</span>
          ) : null}
          {!activeTrajectoryLoading && activeTrajectoryError ? (
            <span className="chip">Error de trayectorias</span>
          ) : null}
          {state.mode === "person" && personTrajectoryChunkSummary && personTrajectoryChunkSummary.scanMode !== "default_rows" && personTrajectoryChunkSummary.scanMode !== "sort_preview" && personTrajectoryChunkSummary.scanMode !== "topic_preview" ? (
            <span className="chip">
              Chunks persona: {personTrajectoryChunkSummary.loadedCandidateTotal}/{personTrajectoryChunkSummary.candidateTotal}
              {personTrajectoryChunkSummary.candidateTotal !== personTrajectoryChunkSummary.total
                ? ` · ${personTrajectoryChunkSummary.total} totales`
                : ""}
            </span>
          ) : null}
          {state.mode === "person" && activePersonScanMode === "progressive" ? (
            <span className="chip">Escaneo progresivo exacto</span>
          ) : null}
          {state.mode === "person" && activePersonScanMode === "exhaustive" ? (
            <span className="chip">Escaneo completo por orden avanzado</span>
          ) : null}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Trayectorias y evidencia</h2>
          <p className="sub">Selecciona una fila para ver muestra de evidencia + estado de revisión.</p>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Ámbito</th>
                <th>Entidad</th>
                <th>Tema</th>
                <th>Método</th>
                <th>As Of</th>
                <th>Postura</th>
                <th>Score</th>
                <th>Confianza</th>
                <th>Evidencia</th>
                <th>Revisión</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isSelected = selectedPoint?.key === row.key;
                const rowLabel = row.scope === "person"
                  ? `${row.personName || row.personId} · ${row.partyLabel || "Sin partido"}`
                  : `${row.partyLabel || row.partyId}`;
                const rowText = `/${row.scope}/`;
                return (
                  <tr
                    key={row.key}
                    className={isSelected ? "rowSelected" : ""}
                    onClick={() => setSelectedPoint(row)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        setSelectedPoint(row);
                      }
                    }}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{rowText}</td>
                    <td>{rowLabel}</td>
                    <td>{row.topicLabel || "Sin tema"}</td>
                    <td>{row.method || "—"}</td>
                    <td>{formatDate(row.asOf)}{row.windowDays ? ` (${row.windowDays}d)` : ""}</td>
                    <td>
                      <span className={`pill ${stancePillClass(row.stance)}`}>
                        {row.stance || "no_signal"}
                      </span>
                    </td>
                    <td>{toScore(row.score)}</td>
                    <td>{toPercent(row.confidence)}</td>
                    <td>{formatEvidenceSummary(row)}</td>
                    <td>{compactReviewLabel(row)}</td>
                  </tr>
                );
              })}
              {activeTrajectoryLoading && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    Cargando trayectorias para el modo actual…
                  </td>
                </tr>
              )}
              {activeDefaultRowsLoading && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    Cargando filas iniciales para la vista por persona…
                  </td>
                </tr>
              )}
              {activeSortPreviewLoading && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    Cargando vista ordenada estática para la comparación por persona…
                  </td>
                </tr>
              )}
              {activeTopicSearchIndexLoading && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    Cargando índice temático estático para el filtro de tema…
                  </td>
                </tr>
              )}
              {activeTopicPreviewLoading && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    {topicPreviewModeLabel === "exact"
                      ? "Cargando vista temática estática para el tema exacto seleccionado…"
                      : topicPreviewModeLabel === "q_search"
                        ? "Cargando vista temática estática para la búsqueda temática…"
                      : "Cargando vista temática estática para los temas filtrados…"}
                    </td>
                </tr>
              )}
              {activePersonScanMode === "topic_discovery" && !activeTopicSearchIndexLoading && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    {activePackEntry
                      ? `El pack ${activePackEntry.label} abre varias preocupaciones y temas. Elige uno de los temas sugeridos para fijar un tema exacto antes de cargar trayectorias de personas.`
                      : activeConcernEntry
                      ? `La preocupación ${activeConcernEntry.label} agrupa varios temas. Elige uno de los temas sugeridos para fijar un tema exacto antes de cargar trayectorias de personas.`
                      : "La búsqueda temática sigue siendo amplia. Elige uno de los temas sugeridos para fijar un tema exacto antes de cargar trayectorias de personas."}
                  </td>
                </tr>
              )}
              {!activeTrajectoryLoading && activeTrajectoryError && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    No pude cargar las trayectorias del modo actual: {activeTrajectoryError}
                  </td>
                </tr>
              )}
              {!activeDefaultRowsLoading && activeDefaultRowsError && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    No pude cargar las filas iniciales: {activeDefaultRowsError}
                  </td>
                </tr>
              )}
              {!activeSortPreviewLoading && activeSortPreviewError && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    No pude cargar la vista ordenada estática: {activeSortPreviewError}
                  </td>
                </tr>
              )}
              {!activeTopicSearchIndexLoading && activeTopicSearchIndexError && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    No pude cargar el índice temático estático: {activeTopicSearchIndexError}
                  </td>
                </tr>
              )}
              {!activeTopicPreviewLoading && activeTopicPreviewError && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    No pude cargar la vista temática estática: {activeTopicPreviewError}
                  </td>
                </tr>
              )}
              {!activeTrajectoryLoading && !activeTrajectoryError && !activeDefaultRowsLoading && !activeDefaultRowsError && !activeSortPreviewLoading && !activeSortPreviewError && !activeTopicSearchIndexLoading && !activeTopicSearchIndexError && !activeTopicPreviewLoading && !activeTopicPreviewError && activePersonScanMode !== "topic_discovery" && !rows.length && (
                <tr>
                  <td colSpan={10} className="sub">
                    No hay datos para los filtros actuales.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Detalle de evidencia</h2>
          <p className="sub">{detailPanelSummary}</p>
        </div>
        {detailContinuityBreadcrumb ? (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">{detailContinuityBreadcrumb.statusLabel}</span>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
              {detailContinuityBreadcrumb.items.map((item, index) => (
                <span key={`detail-continuity-breadcrumb-${item.kind}-${index}`} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {index > 0 ? <span className="sub">›</span> : null}
                  <span className="chip">{continuityBreadcrumbItemLabel(item)}</span>
                </span>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
              {detailContinuityBreadcrumb.primaryAction ? (
                <button
                  type="button"
                  className="chip"
                  onClick={() => {
                    if (detailContinuityBreadcrumb.primaryAction.kind === "restore_discovery") {
                      setState((prev) => restorePoliticalPositionsDiscoveryState(prev));
                      return;
                    }
                    if (detailContinuityBreadcrumb.primaryAction.kind === "open_exact" && originDiscoveryVariantSelection) {
                      setState((prev) => applyTopicPreviewSelection({
                        prevState: prev,
                        selection: originDiscoveryVariantSelection,
                        sourceMode: topicDiscoveryContext.sourceMode,
                      }));
                    }
                  }}
                  style={{ cursor: "pointer", appearance: "none" }}
                >
                  {detailContinuityBreadcrumb.primaryAction.label}
                </button>
              ) : null}
            </div>
          </article>
        ) : null}
        {!selectedPointWithDetails ? (
          <p className="sub">Selecciona una fila para mostrar las evidencias puntuales y su estado de revisión.</p>
        ) : (
          <article className="kpiCard" style={{ marginTop: 12 }}>
            <span className="kpiLabel">Lectura rápida</span>
            {detailOverviewEntries.map((entry) => (
              <p key={`detail-overview-${entry.label}`} className="sub">
                {entry.label}:{" "}
                {entry.kind === "stance" ? (
                  <span className={`pill ${stancePillClass(selectedPointWithDetails.stance)}`}>{entry.value}</span>
                ) : (
                  entry.value
                )}
              </p>
            ))}
          </article>
        )}

        {selectedPointWithDetails ? (
          <div className="tableWrap" style={{ marginTop: 12 }}>
            {evidenceTableHeader ? (
              <div className="blockHead" style={{ marginBottom: 10 }}>
                <div>
                  <h3 style={{ margin: 0 }}>{evidenceTableHeader.title}</h3>
                  <p className="sub">{evidenceTableHeader.subtitle}</p>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  {evidenceTableHeader.chips.map((chip) => (
                    <span key={`evidence-table-header-chip-${chip.label}`} className="chip">
                      {chip.label}: {chip.value}
                    </span>
                  ))}
                  {evidenceTablePrimaryLink ? (
                    <a
                      key={evidenceTablePrimaryLink.href}
                      href={evidenceTablePrimaryLink.href}
                      className="chip"
                      title={evidenceTablePrimaryLink.hint ? `${evidenceTablePrimaryLink.label}: ${evidenceTablePrimaryLink.hint}` : evidenceTablePrimaryLink.label}
                      style={{ textDecoration: "none", fontWeight: 700 }}
                    >
                      {evidenceTablePrimaryLink.label}
                      {evidenceTablePrimaryLink.hint ? (
                        <span style={{ opacity: 0.75 }}> · {evidenceTablePrimaryLink.hint}</span>
                      ) : null}
                    </a>
                  ) : null}
                  {evidenceTableSecondaryLinks.length ? (
                    <span className="sub" style={{ alignSelf: "center" }}>Otras vistas:</span>
                  ) : null}
                  {evidenceTableSecondaryLinks.map((link) => (
                    <a
                      key={link.href}
                      href={link.href}
                      className="chip"
                      style={{ textDecoration: "none" }}
                      title={link.hint ? `${link.label}: ${link.hint}` : link.label}
                    >
                      {link.label}
                      {link.hint ? (
                        <span style={{ opacity: 0.75 }}> · {link.hint}</span>
                      ) : null}
                    </a>
                  ))}
                </div>
              </div>
            ) : null}
            {selectedPointDetailLoading ? (
              <p className="sub" style={{ marginBottom: 8 }}>Cargando evidencia puntual…</p>
            ) : null}
            {!selectedPointDetailLoading && detailState.error && selectedPointWithDetails.scope === "person" && toInt(detailState.personId) === toInt(selectedPointWithDetails.personId) ? (
              <p className="sub" style={{ marginBottom: 8 }}>No pude cargar el detalle puntual: {detailState.error}</p>
            ) : null}
            <table className="table">
              <thead>
                <tr>
                  <th>Fuente</th>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>Postura</th>
                  <th>Confianza</th>
                  <th>Extracto</th>
                  <th>Revisión</th>
                </tr>
              </thead>
              <tbody>
                {visibleEvidenceSamples.map((sample) => {
                  const sourceUrl = String(sample.source_url || "");
                  return (
                    <tr key={`${sample.source_id || "src"}-${sample.evidence_id || sample.evidence_record_id || ""}-${sample.evidence_type || ""}`}>
                      <td>
                        {sourceUrl ? (
                          <a href={sourceUrl} target="_blank" rel="noreferrer">
                            {sample.source_id || "fuente"}
                          </a>
                        ) : (
                          sample.source_id || "—"
                        )}
                      </td>
                      <td>{formatDate(sample.evidence_date || "")}</td>
                      <td>{sample.evidence_type || "—"}</td>
                      <td>{sample.stance || "—"}</td>
                      <td>{toPercent(sample.confidence || 0)}</td>
                      <td>{String(sample.excerpt || sample.title || "—").slice(0, 280)}</td>
                      <td>
                        <span className="sub">
                          {sample.review && sample.review.status ? sample.review.status : "sin revisión"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {(!selectedPointDetailLoading && !visibleEvidenceSamples.length) ? (
                  <tr>
                    <td colSpan={7} className="sub">
                      Esta postura no tiene evidencia puntual listada para su rastro.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </main>
  );
}
