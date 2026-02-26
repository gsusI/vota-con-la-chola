"use client";

import { useEffect, useMemo, useState } from "react";
import { ColumnFiltersRow, applyColumnFilters } from "../components/column-filters";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function normalizePartySlugValue(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function slugifyPartyLabel(value) {
  return normalizePartySlugValue(value) || "sin-valor";
}

function personProfileUrl(personId) {
  if (!personId) {
    return "";
  }
  const id = Number(personId);
  if (!Number.isFinite(id) || id <= 0) {
    return "";
  }
  return `${resolveBasePath()}/people/?person_id=${id}`;
}

function toPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${Number(value).toFixed(2)}%`;
}

function formatInt(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return Number(value).toLocaleString("es-ES");
}

function humanizeCode(value) {
  const normalized = String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) {
    return "";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

const OUTCOME_LABELS = {
  passed: "Aprobada",
  failed: "Rechazada",
  tied: "Empate",
  no_signal: "Sin señal",
};

const CHAMBER_LABELS = {
  congreso: "Congreso",
  senado: "Senado",
};

const TOPIC_LABELS = {
  derived: "Derivado (sin clasificar)",
};

const CONTEXT_LABELS = {
  other: "General",
};

function formatOutcomeLabel(outcome) {
  const key = String(outcome || "").trim().toLowerCase();
  return OUTCOME_LABELS[key] || humanizeCode(key) || "Sin señal";
}

function formatChamberLabel(sourceBucket) {
  const key = String(sourceBucket || "").trim().toLowerCase();
  return CHAMBER_LABELS[key] || humanizeCode(sourceBucket) || "Sin cámara";
}

function formatTopicLabel(topic) {
  const key = String(topic || "").trim().toLowerCase();
  return TOPIC_LABELS[key] || humanizeCode(topic) || "Sin tema";
}

function formatContextLabel(context) {
  const key = String(context || "").trim().toLowerCase();
  return CONTEXT_LABELS[key] || humanizeCode(context) || "General";
}

function formatOutcomeMargin(margin) {
  const numeric = Number(margin);
  if (!Number.isFinite(numeric)) {
    return "—";
  }
  if (numeric === 0) {
    return "0 (empate)";
  }
  const abs = formatInt(Math.abs(numeric));
  return numeric > 0 ? `+${abs} (se aprueba por ${abs})` : `-${abs} (se rechaza por ${abs})`;
}

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

const OUTCOME_MISSING_LABELS = {
  missing_vote_subject: "pregunta de votacion",
  missing_initiative_link: "iniciativa vinculada",
  missing_official_source_url: "fuente oficial",
};

function getOutcomeSubject(row) {
  return compactInlineText(row?.vote_subject || row?.title || row?.expediente_text || "", 200);
}

function getOutcomeInitiativeId(row) {
  return normalizeInlineText(row?.initiative_id);
}

function getOutcomeInitiativeLabel(row) {
  const initiativeId = getOutcomeInitiativeId(row);
  const expediente = compactInlineText(row?.initiative_expediente, 80);
  const title = compactInlineText(row?.initiative_title, 140);
  if (expediente && title) {
    return `${expediente}: ${title}`;
  }
  if (title) {
    return title;
  }
  if (expediente) {
    return expediente;
  }
  if (initiativeId) {
    return `Iniciativa ${initiativeId}`;
  }
  return "Sin iniciativa vinculada";
}

function getOutcomeInitiativeHref(row) {
  const initiativeId = getOutcomeInitiativeId(row);
  if (!initiativeId) {
    return "";
  }
  return `${resolveBasePath()}/initiative-lifecycle/?initiative=${encodeURIComponent(initiativeId)}`;
}

function getOutcomeSourceUrl(row) {
  return normalizeInlineText(row?.source_url || row?.initiative_doc_url || row?.initiative_source_url || "");
}

function getOutcomeMissingLabels(row) {
  const missing = Array.isArray(row?.quality?.missing) ? row.quality.missing : [];
  const labels = missing
    .map((code) => OUTCOME_MISSING_LABELS[code] || humanizeCode(code))
    .filter(Boolean);
  return labels.join(", ");
}

function isOutcomeInterpretable(row) {
  if (row?.quality && Object.prototype.hasOwnProperty.call(row.quality, "is_interpretable")) {
    return Boolean(row.quality.is_interpretable);
  }
  return Boolean(getOutcomeSubject(row) && getOutcomeInitiativeId(row) && getOutcomeSourceUrl(row));
}

function renderOutcomePill(outcome) {
  const key = String(outcome || "").trim().toLowerCase();
  const cls = key === "passed" ? "pill-success" : key === "failed" ? "pill-danger" : key === "tied" ? "pill-warning" : "pill-muted";
  return (
    <span className={`pill ${cls}`} title={key || undefined}>
      {formatOutcomeLabel(key)}
    </span>
  );
}

function isPartyCode(value) {
  return typeof value === "string" && /^\d{1,3}:\d{3,}$/.test(value.trim());
}

function resolvePartyLinkFromData(row, partySlugById, availablePartySlugs = {}) {
  const partyId = Number(row?.party_id);
  if (!Number.isFinite(partyId) || partyId <= 0) {
    return "";
  }

  const directSlug = partySlugById?.[partyId];
  if (directSlug && availablePartySlugs[directSlug]) {
    return `${resolveBasePath()}/people/xray/party/?group=${encodeURIComponent(directSlug)}`;
  }

  const fallbackLabel = firstPartyLabel(row?.party_name, row?.party_acronym, row?.acronym, row?.name);
  if (!fallbackLabel) {
    return "";
  }

  const fallbackSlug = slugifyPartyLabel(fallbackLabel);
  if (fallbackSlug && availablePartySlugs[fallbackSlug]) {
    return `${resolveBasePath()}/people/xray/party/?group=${encodeURIComponent(fallbackSlug)}`;
  }

  return "";
}

const PARTY_LABEL_MAX_LEN = 72;

const PARTY_LABEL_OVERRIDES = {
  68283: "Grupo Parlamentario Izquierda Confederal",
  68286: "Grupo Parlamentario Democratico",
};

function normalizeComparablePartyLabel(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\bgrupo parlamentario\b/g, "")
    .replace(/[^a-z0-9]+/g, "")
    .trim();
}

function compactPartyLabel(value, maxLen = PARTY_LABEL_MAX_LEN) {
  const label = String(value || "").replace(/\s+/g, " ").trim();
  if (!label) {
    return "";
  }

  const dupMatch = label.match(/^(.+?)\s*\((.+)\)$/);
  if (dupMatch) {
    const outer = dupMatch[1].trim();
    const inner = dupMatch[2].trim();
    const outerNorm = normalizeComparablePartyLabel(outer);
    const innerNorm = normalizeComparablePartyLabel(inner);
    if (outerNorm && innerNorm && (outerNorm === innerNorm || innerNorm.includes(outerNorm) || outerNorm.includes(innerNorm))) {
      const preferred = outer.length <= inner.length ? outer : inner;
      return compactPartyLabel(preferred, maxLen);
    }
  }

  if (label.length <= maxLen) {
    return label;
  }
  const hard = Math.max(12, maxLen - 3);
  const sliced = label.slice(0, hard);
  const lastSpace = sliced.lastIndexOf(" ");
  const trimmed = lastSpace > 20 ? sliced.slice(0, lastSpace) : sliced;
  return `${trimmed}...`;
}

function PersonLink({ personId, children }) {
  const href = personProfileUrl(personId);
  if (!href) {
    return <>{children}</>;
  }

  return (
    <a href={href} title="Ver perfil completo (x-ray)">
      {children}
    </a>
  );
}

function firstPartyLabel(...values) {
  const readable = values.find((value) => value && !isPartyCode(value));
  if (readable) {
    return readable;
  }

  return values.find((value) => value) || "";
}

function extractPartyBrand(row) {
  const candidates = [row?.party_acronym, row?.acronym, row?.party_name, row?.name];
  const fromText = candidates.find((value) => value && !isPartyCode(value) && (value.includes("(") && value.includes(")")));
  if (fromText) {
    const match = String(fromText).match(/\(([^)]+)\)\s*$/);
    if (match && match[1] && !isPartyCode(match[1])) {
      return match[1].trim();
    }
  }
  const acronym = candidates.find((value) => value && !isPartyCode(value));
  return acronym ? String(acronym).trim() : "";
}

function normalizePartyBase(label) {
  const trimmed = String(label || "").trim();
  if (!trimmed) {
    return "";
  }
  const withoutTrailingBrand = trimmed.replace(/\s*\([^)]*\)\s*$/, "");
  return withoutTrailingBrand
    .replace(/\bGRUPO PARLAMENTARIO DE\b/gi, "")
    .replace(/\bGRUPO PARLAMENTARIO\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function hashToHue(input) {
  const value = String(input || "");
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) % 360;
    if (hash < 0) {
      hash += 360;
    }
  }
  return hash;
}

function buildPartyMeta(partiesById) {
  const byParty = {};
  const groups = {};

  for (const partyId of Object.keys(partiesById)) {
    const party = partiesById[partyId];
    if (!party) {
      continue;
    }
    const label = firstPartyLabel(party.acronym, party.name, `Partido ${party.party_id}`);
    const base = normalizePartyBase(label);
    const brand = extractPartyBrand(party);

    const baseKey = base || `partido-${partyId}`;
    if (!groups[baseKey]) {
      groups[baseKey] = {
        baseLabel: base || label,
        brands: new Set(),
      };
    }
    if (brand && brand.toUpperCase() !== (base || "").toUpperCase() && !isPartyCode(brand)) {
      groups[baseKey].brands.add(brand);
    }

    byParty[partyId] = {
      partyId: Number(partyId),
      baseKey,
      fallbackLabel: label,
      brand,
    };
  }

  const groupMeta = {};
  for (const [baseKey, data] of Object.entries(groups)) {
    const sortedBrands = [...data.brands].sort((left, right) => String(left).localeCompare(String(right), "es-ES"));
    const label = sortedBrands.length
      ? `${data.baseLabel} (${sortedBrands.join(", ")})`
      : data.baseLabel;
    const hue = hashToHue(baseKey);
    groupMeta[baseKey] = {
      label,
      style: {
        backgroundColor: `hsl(${hue}, 78%, 92%)`,
        color: `hsl(${hue}, 62%, 28%)`,
        borderColor: `hsl(${hue}, 75%, 82%)`,
      },
    };
  }

  for (const id of Object.keys(byParty)) {
    const item = byParty[id];
    const meta = groupMeta[item.baseKey] || {
      label: item.fallbackLabel,
      style: {},
    };
    byParty[id] = {
      ...item,
      label: meta.label,
      style: meta.style,
      sortLabel: meta.label,
    };
  }

  return byParty;
}

function resolvePartyLabel(partiesById, row, partyMetaById, fallback = "Partido") {
  if (!row?.party_id) {
    return fallback || "Sin partido";
  }

  const override = PARTY_LABEL_OVERRIDES[Number(row.party_id)];
  if (override) {
    return override;
  }

  const rowLabel = firstPartyLabel(row.party_acronym, row.party_name, row.party_1_name, row.party_2_name, row.acronym, row.name);

  const partyMeta = partyMetaById?.[row.party_id];
  if (partyMeta?.label) {
    if (!isPartyCode(partyMeta.label)) {
      return partyMeta.label;
    }
    if (rowLabel && !isPartyCode(rowLabel)) {
      return rowLabel;
    }
  }

  const party = partiesById[row.party_id];
  if (!party) {
    if (rowLabel) {
      return rowLabel;
    }
    return `${fallback} ${row.party_id}`.trim() || fallback;
  }

  if (rowLabel) {
    return rowLabel;
  }

  const resolved = firstPartyLabel(
    row.party_acronym,
    row.party_name,
    row.acronym,
    row.name,
    party.acronym,
    party.name,
  );

  return resolved || `${fallback} ${row.party_id}`;
}

function resolvePartySortValue(partiesById, row, partyMetaById, fallback = "Partido") {
  if (!row?.party_id) {
    return fallback || "Sin partido";
  }
  if (partyMetaById?.[row.party_id]?.sortLabel) {
    return partyMetaById[row.party_id].sortLabel;
  }
  return resolvePartyLabel(partiesById, row, partyMetaById, fallback);
}

function PartyLabel({
  partiesById,
  partyMetaById,
  partySlugById,
  availablePartySlugs,
  row,
  fallback = "Partido",
}) {
  const partyId = row?.party_id;
  const fullLabel = resolvePartyLabel(partiesById, row, partyMetaById, fallback);
  const label = compactPartyLabel(fullLabel);
  const style = partyMetaById?.[partyId]?.style;
  const pill = style?.backgroundColor ? (
    <span className="partyPill" style={style} title={fullLabel || label}>
      {label}
    </span>
  ) : (
    <span title={fullLabel || label}>{label}</span>
  );
  const partyHref = resolvePartyLinkFromData(row, partySlugById, availablePartySlugs);

  if (!partyHref) {
    return pill;
  }

  return (
    <a
      className="tableButton"
      href={partyHref}
      title={`Ver x-ray del partido: ${fullLabel || label}`}
    >
      {pill}
    </a>
  );
}

function toPartyScopeRows(rows, scopeFilter, scopeColumn = "scope") {
  if (!scopeFilter) {
    return rows;
  }
  return rows.filter(
    (row) =>
      String(row[scopeColumn] || "").startsWith(`${scopeFilter}:`) ||
      String(row[scopeColumn] || "") === scopeFilter,
  );
}

function scopeOptionsFromData(data) {
  const set = new Set(["all"]);
  if (!data?.discipline) {
    return ["all"];
  }

  for (const row of data.discipline.parties_by_legislature || []) {
    const s = String(row.scope || "").split(":");
    if (s[0]) {
      set.add(s[0]);
    }
  }
  return Array.from(set);
}

const DEFAULT_TABLE_SORTS = {
  members: { key: "rebels", direction: "desc" },
  parties: { key: "rebels", direction: "desc" },
  partyScope: { key: "rebellion_rate_pct", direction: "desc" },
  partyContext: { key: "absence_rate_pct", direction: "desc" },
  memberContext: { key: "absence_rate_pct", direction: "desc" },
  outcomes: { key: "vote_date", direction: "desc" },
  coalitions: { key: "cosine", direction: "desc" },
  issues: { key: "topic_minus_global", direction: "desc" },
};

function normalizeSortValue(value) {
  if (Array.isArray(value)) {
    return value.length;
  }
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "boolean") {
    return value ? 1 : 0;
  }
  return value;
}

function compareSortValues(a, b) {
  const av = normalizeSortValue(a);
  const bv = normalizeSortValue(b);
  const aEmpty = av === "";
  const bEmpty = bv === "";

  if (aEmpty && bEmpty) {
    return 0;
  }
  if (aEmpty) {
    return 1;
  }
  if (bEmpty) {
    return -1;
  }

  if (typeof av === "number" && typeof bv === "number") {
    return av - bv;
  }

  const as = String(av);
  const bs = String(bv);
  return as.localeCompare(bs, "es-ES", { numeric: true, sensitivity: "base" });
}

function sortRows(rows, sortSpec, valueGetter) {
  if (!Array.isArray(rows) || !rows.length || !sortSpec?.key) {
    return rows || [];
  }

  const dir = sortSpec.direction === "asc" ? 1 : -1;
  const sorted = [...rows];
  sorted.sort((a, b) => dir * compareSortValues(valueGetter(sortSpec.key, a), valueGetter(sortSpec.key, b)));
  return sorted;
}

function SortHeader({ tableId, columnKey, label, sortByTable, onSort, defaultDirection = "asc" }) {
  const activeSort = sortByTable[tableId] || {};
  const isActive = activeSort.key === columnKey;
  const direction = isActive ? activeSort.direction : "none";
  const arrow = !isActive ? "↕" : direction === "asc" ? "▲" : "▼";

  return (
    <th aria-sort={isActive ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" className={`sortHeaderButton${isActive ? " isActive" : ""}`} onClick={() => onSort(tableId, columnKey, defaultDirection)}>
        <span>{label}</span>
        <span className="sortHeaderIcon" aria-hidden="true">{arrow}</span>
      </button>
    </th>
  );
}

function useAccountabilityData() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const base = resolveBasePath();
    const url = `${base}/parliamentary-accountability/data/accountability.json`;

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

function usePeopleXrayIndex() {
  const [state, setState] = useState({ loading: true, error: null, data: null, hasSnapshot: false });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/people/data/xray.json`;

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Respuesta no válida: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setState({ loading: false, error: null, data: payload, hasSnapshot: true });
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        setState({
          loading: false,
          error: error.message || String(error),
          data: null,
          hasSnapshot: false,
        });
      });

    return () => controller.abort();
  }, []);

  return state;
}

export default function AccountabilityPageClient({ view = "all" }) {
  const { loading, error, data } = useAccountabilityData();
  const { data: peopleXrayData } = usePeopleXrayIndex();
  const [scopeFilter, setScopeFilter] = useState("all");
  const [sortByTable, setSortByTable] = useState(DEFAULT_TABLE_SORTS);
  const [filtersByTable, setFiltersByTable] = useState({});

  const onSort = (tableId, columnKey, defaultDirection = "asc") => {
    setSortByTable((prev) => {
      const current = prev[tableId] || {};
      const direction = current.key === columnKey ? (current.direction === "asc" ? "desc" : "asc") : defaultDirection;
      return { ...prev, [tableId]: { key: columnKey, direction } };
    });
  };
  const onFilterChange = (tableId, columnKey, value) => {
    setFiltersByTable((prev) => ({
      ...prev,
      [tableId]: {
        ...(prev[tableId] || {}),
        [columnKey]: value,
      },
    }));
  };

  const partiesById = useMemo(() => {
    const map = {};
    for (const p of data?.parties || []) {
      map[p.party_id] = p;
    }
    return map;
  }, [data]);
  const partySlugById = useMemo(() => {
    const map = {};
    const partyIndex = peopleXrayData?.group_index?.party;
    if (!partyIndex || typeof partyIndex !== "object") {
      return map;
    }

    for (const [slug, groupKey] of Object.entries(partyIndex)) {
      if (typeof slug !== "string" || !slug || typeof groupKey !== "string") {
        continue;
      }
      if (!groupKey.startsWith("party:")) {
        continue;
      }
      const parsedId = Number(groupKey.slice("party:".length));
      if (!Number.isFinite(parsedId) || parsedId <= 0) {
        continue;
      }
      map[parsedId] = slug;
    }
    return map;
  }, [peopleXrayData]);
  const availablePartySlugs = useMemo(() => {
    const map = {};
    const partyIndex = peopleXrayData?.group_index?.party;
    if (!partyIndex || typeof partyIndex !== "object") {
      return map;
    }
    for (const slug of Object.keys(partyIndex)) {
      if (typeof slug === "string" && slug.trim()) {
        map[slug] = true;
      }
    }
    return map;
  }, [peopleXrayData]);
  const partyMetaById = useMemo(() => buildPartyMeta(partiesById), [partiesById]);

  const scopeOptions = useMemo(() => scopeOptionsFromData(data), [data]);

  const memberRows = useMemo(() => {
    return (data?.discipline?.members || []).slice(0, 120);
  }, [data]);

  const partyRows = useMemo(() => {
    return (data?.discipline?.parties || []).slice(0, 120);
  }, [data]);

  const partyLegRows = useMemo(() => {
    const rows = data?.discipline?.parties_by_legislature || [];
    return toPartyScopeRows(rows, scopeFilter === "all" ? null : scopeFilter, "scope");
  }, [data, scopeFilter]);

  const outcomes = useMemo(() => {
    const rows = data?.outcomes?.critical_by_margin || [];
    if (scopeFilter === "all") {
      return rows;
    }
    return rows.filter((row) => String(row.source_bucket || "").startsWith(scopeFilter));
  }, [data, scopeFilter]);

  const coalitionRows = useMemo(() => {
    const rows = data?.coalitions?.pairs || [];
    if (scopeFilter === "all") {
      return rows;
    }
    return rows.filter((row) => String(row.scope || "").startsWith(scopeFilter));
  }, [data, scopeFilter]);

  const issueRows = useMemo(() => {
    const rows = data?.coalitions?.issue_coalitions || [];
    if (scopeFilter === "all") {
      return rows;
    }
    return rows.filter((row) => String(row.scope || "").startsWith(scopeFilter));
  }, [data, scopeFilter]);

  const memberContextRows = useMemo(() => {
    const rows = data?.discipline?.attendance_by_member_context || [];
    return rows.slice(0, 120);
  }, [data]);

  const partyContextRows = useMemo(() => {
    const rows = data?.discipline?.attendance_by_party_context || [];
    return rows.slice(0, 120);
  }, [data]);

  const getMemberValue = (key, row) => {
    if (key === "person") return row.full_name || `Persona ${row.person_id || ""}`;
    if (key === "party") return resolvePartySortValue(partiesById, row, partyMetaById);
    return row[key];
  };
  const filteredMemberRows = useMemo(() => {
    return applyColumnFilters(memberRows, filtersByTable.members, getMemberValue);
  }, [memberRows, filtersByTable.members, partiesById, partyMetaById]);
  const sortedMemberRows = useMemo(() => {
    return sortRows(filteredMemberRows, sortByTable.members, getMemberValue);
  }, [filteredMemberRows, sortByTable.members, partiesById, partyMetaById]);

  const getPartyValue = (key, row) => {
    if (key === "party") return resolvePartySortValue(partiesById, row, partyMetaById, "Partido");
    if (key === "absence_rate_pct") return 100 - (Number(row.discipline_rate_pct) || 0);
    return row[key];
  };
  const filteredPartyRows = useMemo(() => {
    return applyColumnFilters(partyRows, filtersByTable.parties, getPartyValue);
  }, [partyRows, filtersByTable.parties, partiesById, partyMetaById]);
  const sortedPartyRows = useMemo(() => {
    return sortRows(filteredPartyRows, sortByTable.parties, getPartyValue);
  }, [filteredPartyRows, sortByTable.parties, partiesById, partyMetaById]);

  const getPartyScopeValue = (key, row) => {
    if (key === "party") return resolvePartySortValue(partiesById, row, partyMetaById, "Partido");
    return row[key];
  };
  const filteredPartyLegRows = useMemo(() => {
    return applyColumnFilters(partyLegRows, filtersByTable.partyScope, getPartyScopeValue);
  }, [partyLegRows, filtersByTable.partyScope, partiesById, partyMetaById]);
  const sortedPartyLegRows = useMemo(() => {
    return sortRows(filteredPartyLegRows, sortByTable.partyScope, getPartyScopeValue);
  }, [filteredPartyLegRows, sortByTable.partyScope, partiesById, partyMetaById]);

  const getPartyContextValue = (key, row) => {
    if (key === "party") return resolvePartySortValue(partiesById, row, partyMetaById, "Partido");
    return row[key];
  };
  const filteredPartyContextRows = useMemo(() => {
    return applyColumnFilters(partyContextRows, filtersByTable.partyContext, getPartyContextValue);
  }, [partyContextRows, filtersByTable.partyContext, partiesById, partyMetaById]);
  const sortedPartyContextRows = useMemo(() => {
    return sortRows(filteredPartyContextRows, sortByTable.partyContext, getPartyContextValue);
  }, [filteredPartyContextRows, sortByTable.partyContext, partiesById, partyMetaById]);

  const getMemberContextValue = (key, row) => {
    if (key === "person") return row.full_name || `Persona ${row.person_id || ""}`;
    return row[key];
  };
  const filteredMemberContextRows = useMemo(() => {
    return applyColumnFilters(memberContextRows, filtersByTable.memberContext, getMemberContextValue);
  }, [memberContextRows, filtersByTable.memberContext]);
  const sortedMemberContextRows = useMemo(() => {
    return sortRows(filteredMemberContextRows, sortByTable.memberContext, getMemberContextValue).slice(0, 60);
  }, [filteredMemberContextRows, sortByTable.memberContext]);

  const getOutcomeValue = (key, row) => {
    if (key === "margin") return row.totals?.margin ?? row.margin;
    if (key === "pivotal_count") return row.pivotal_parties?.length || 0;
    if (key === "vote_subject") return getOutcomeSubject(row);
    if (key === "initiative") return getOutcomeInitiativeLabel(row);
    if (key === "source_url") return getOutcomeSourceUrl(row);
    if (key === "interpretability") return isOutcomeInterpretable(row) ? "completa" : "incompleta";
    if (key === "source_bucket") return formatChamberLabel(row.source_bucket);
    if (key === "outcome") return formatOutcomeLabel(row.outcome);
    if (key === "topic") return formatTopicLabel(row.topic);
    if (key === "context") return formatContextLabel(row.context);
    return row[key];
  };
  const filteredOutcomes = useMemo(() => {
    return applyColumnFilters(outcomes, filtersByTable.outcomes, getOutcomeValue);
  }, [outcomes, filtersByTable.outcomes]);
  const sortedOutcomes = useMemo(() => {
    return sortRows(filteredOutcomes, sortByTable.outcomes, getOutcomeValue).slice(0, 100);
  }, [filteredOutcomes, sortByTable.outcomes]);

  const getCoalitionValue = (key, row) => {
    if (key === "party_a") {
      return resolvePartySortValue(
        partiesById,
        {
          party_id: row.party_1_id,
          party_name: row.party_1_name,
          party_acronym: row.party_1_acronym,
        },
        partyMetaById,
        `Partido ${row.party_1_id}`,
      );
    }
    if (key === "party_b") {
      return resolvePartySortValue(
        partiesById,
        {
          party_id: row.party_2_id,
          party_name: row.party_2_name,
          party_acronym: row.party_2_acronym,
        },
        partyMetaById,
        `Partido ${row.party_2_id}`,
      );
    }
    return row[key];
  };
  const filteredCoalitionRows = useMemo(() => {
    return applyColumnFilters(coalitionRows, filtersByTable.coalitions, getCoalitionValue);
  }, [coalitionRows, filtersByTable.coalitions, partiesById, partyMetaById]);
  const sortedCoalitionRows = useMemo(() => {
    return sortRows(filteredCoalitionRows, sortByTable.coalitions, getCoalitionValue);
  }, [filteredCoalitionRows, sortByTable.coalitions, partiesById, partyMetaById]);

  const getIssueValue = (key, row) => {
    if (key === "party_a") {
      return resolvePartySortValue(
        partiesById,
        {
          party_id: row.party_1_id,
          party_name: row.party_1_name,
          party_acronym: row.party_1_acronym,
        },
        partyMetaById,
        `Partido ${row.party_1_id}`,
      );
    }
    if (key === "party_b") {
      return resolvePartySortValue(
        partiesById,
        {
          party_id: row.party_2_id,
          party_name: row.party_2_name,
          party_acronym: row.party_2_acronym,
        },
        partyMetaById,
        `Partido ${row.party_2_id}`,
      );
    }
    return row[key];
  };
  const filteredIssueRows = useMemo(() => {
    return applyColumnFilters(issueRows, filtersByTable.issues, getIssueValue);
  }, [issueRows, filtersByTable.issues, partiesById, partyMetaById]);
  const sortedIssueRows = useMemo(() => {
    return sortRows(filteredIssueRows, sortByTable.issues, getIssueValue).slice(0, 80);
  }, [filteredIssueRows, sortByTable.issues, partiesById, partyMetaById]);

  if (loading) {
    return <main className="shell"><section className="card block"><p className="sub">Cargando snapshot de accountability…</p></section></main>;
  }

  if (error || !data) {
    return (
      <main className="shell">
        <section className="card block">
          <h2>Cuenta de datos sin datos</h2>
          <p className="sub">No pude cargar el snapshot estático de accountability.</p>
          <p className="sub">Error: {error || "sin datos"}</p>
          <p className="sub">
            Asegura ejecutar <code>just explorer-gh-pages-build</code> para regenerar <code>docs/gh-pages/parliamentary-accountability/data/accountability.json</code>.
          </p>
        </section>
      </main>
    );
  }

  const outcomeSummary = data.outcomes?.summary || {};
  const totalEvents = Number(data.meta?.total_events || 0);
  const selectedView = String(view || "all");
  const showDiscipline = selectedView === "all" || selectedView === "discipline";
  const showAttendance = selectedView === "all" || selectedView === "attendance";
  const showOutcomes = selectedView === "all" || selectedView === "outcomes";
  const showCoalitions = selectedView === "all" || selectedView === "coalitions";

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Accountability parlamentaria</p>
        <h1>Analítica de disciplina y conducta de voto</h1>
        <p className="sub">
          Snapshot estático para GH Pages. Métricas de disciplina de grupo, asistencia, similitud
          entre bloques y resultados por votación (con membresía temporal).
        </p>
        <div className="chips">
          <span className="chip">Snapshot: {data.meta.generated_at}</span>
          <span className="chip">Votaciones analizadas: {formatInt(totalEvents)}</span>
          <span className="chip">Pares de coalición: {formatInt(data.coalitions?.pairs?.length || 0)}</span>
        </div>
        <div className="chips">
          <a className="chip" href={`${resolveBasePath()}/parliamentary-accountability/discipline`}>Disciplina</a>
          <a className="chip" href={`${resolveBasePath()}/parliamentary-accountability/attendance`}>Asistencia</a>
          <a className="chip" href={`${resolveBasePath()}/parliamentary-accountability/outcomes`}>Resultados</a>
          <a className="chip" href={`${resolveBasePath()}/parliamentary-accountability/coalitions`}>Coaliciones</a>
        </div>
      </section>

      {showDiscipline ? (
      <>
      <section className="card block">
        <div className="blockHead"><h2>Métricas rápidas</h2></div>
        <div className="kpiGrid">
          <article className="kpiCard">
            <span className="kpiLabel">Aprobadas</span>
            <strong className="kpiValue">{formatInt(outcomeSummary.passed || 0)}</strong>
          </article>
          <article className="kpiCard">
            <span className="kpiLabel">Rechazadas</span>
            <strong className="kpiValue">{formatInt(outcomeSummary.failed || 0)}</strong>
          </article>
          <article className="kpiCard">
            <span className="kpiLabel">Empates / sin señal</span>
            <strong className="kpiValue">{formatInt((outcomeSummary.tied || 0) + (outcomeSummary.no_signal || 0))}</strong>
          </article>
          <article className="kpiCard">
            <span className="kpiLabel">Partidos</span>
            <strong className="kpiValue">{formatInt(data.parties?.length || 0)}</strong>
          </article>
        </div>
        <div className="inlineFilters">
          <label>
            Cámara:
            <select value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)}>
              {scopeOptions.map((scope) => (
                <option key={scope} value={scope}>
                  {scope === "all" ? "Todas" : scope}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead"><h2>Disciplina por persona (rebeldía)</h2></div>
        <p className="sub">Se calcula con pertenencia a grupo reconstruida por fecha de voto.</p>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <SortHeader tableId="members" columnKey="person" label="Persona" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="members" columnKey="party" label="Partido" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="members" columnKey="directional_votes" label="Votos direccionales" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="members" columnKey="aligned" label="Alineados" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="members" columnKey="rebels" label="Rebeldes" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="members" columnKey="discipline_rate_pct" label="Tasa alineación" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="members" columnKey="rebellion_rate_pct" label="Tasa rebeldía" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="members" columnKey="absence_rate_pct" label="Ausencias" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
              </tr>
              <ColumnFiltersRow
                tableId="members"
                columns={[
                  { key: "person", label: "Persona", type: "text" },
                  { key: "party", label: "Partido", type: "text" },
                  { key: "directional_votes", label: "Votos direccionales", type: "number" },
                  { key: "aligned", label: "Alineados", type: "number" },
                  { key: "rebels", label: "Rebeldes", type: "number" },
                  { key: "discipline_rate_pct", label: "Tasa alineacion", type: "number" },
                  { key: "rebellion_rate_pct", label: "Tasa rebeldia", type: "number" },
                  { key: "absence_rate_pct", label: "Ausencias", type: "number" },
                ]}
                filtersByTable={filtersByTable}
                onFilterChange={onFilterChange}
              />
            </thead>
            <tbody>
              {sortedMemberRows.map((row) => (
                <tr key={row.person_id}>
                  <td>
                    <PersonLink personId={row.person_id}>{row.full_name || `Persona ${row.person_id}`}</PersonLink>
                  </td>
                  <td>
                    <PartyLabel
                      partiesById={partiesById}
                      partyMetaById={partyMetaById}
                      partySlugById={partySlugById}
                      availablePartySlugs={availablePartySlugs}
                      row={row}
                    />
                  </td>
                  <td>{formatInt(row.directional_votes)}</td>
                  <td>{formatInt(row.aligned)}</td>
                  <td>{formatInt(row.rebels)}</td>
                  <td>{toPercent(row.discipline_rate_pct)}</td>
                  <td>{toPercent(row.rebellion_rate_pct)}</td>
                  <td>{toPercent(row.absence_rate_pct)}</td>
                </tr>
              ))}
              {!sortedMemberRows.length ? (
                <tr>
                  <td colSpan="8">Sin filas</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead"><h2>Disciplina por partido (global)</h2></div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <SortHeader tableId="parties" columnKey="party" label="Partido" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="parties" columnKey="directional_votes" label="Votos direccionales" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="parties" columnKey="aligned" label="Alineados" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="parties" columnKey="rebels" label="Rebeldes" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="parties" columnKey="rebellion_rate_pct" label="Tasa rebeldía" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="parties" columnKey="absence_rate_pct" label="Ausencias" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
              </tr>
              <ColumnFiltersRow
                tableId="parties"
                columns={[
                  { key: "party", label: "Partido", type: "text" },
                  { key: "directional_votes", label: "Votos direccionales", type: "number" },
                  { key: "aligned", label: "Alineados", type: "number" },
                  { key: "rebels", label: "Rebeldes", type: "number" },
                  { key: "rebellion_rate_pct", label: "Tasa rebeldia", type: "number" },
                  { key: "absence_rate_pct", label: "Ausencias", type: "number" },
                ]}
                filtersByTable={filtersByTable}
                onFilterChange={onFilterChange}
              />
            </thead>
            <tbody>
              {sortedPartyRows.map((row) => {
                const partyLabel = (
                  <PartyLabel
                    partiesById={partiesById}
                    partyMetaById={partyMetaById}
                    partySlugById={partySlugById}
                    availablePartySlugs={availablePartySlugs}
                    row={row}
                    fallback="Partido"
                  />
                );
                return (
                  <tr key={`${row.party_id}`}>
                    <td>{partyLabel}</td>
                    <td>{formatInt(row.directional_votes)}</td>
                    <td>{formatInt(row.aligned)}</td>
                    <td>{formatInt(row.rebels)}</td>
                    <td>{toPercent(row.rebellion_rate_pct)}</td>
                    <td>{toPercent(100 - (row.discipline_rate_pct || 0))}</td>
                  </tr>
                );
              })}
              {!sortedPartyRows.length ? (
                <tr>
                  <td colSpan="6">Sin filas</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      </>
      ) : null}

      {showAttendance ? (
      <section className="card block">
        <div className="blockHead"><h2>Disciplina por partido, cámara/legislatura</h2></div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <SortHeader tableId="partyScope" columnKey="party" label="Partido" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="partyScope" columnKey="scope" label="Cámara/leg" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="partyScope" columnKey="directional_votes" label="Votos direccionales" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="partyScope" columnKey="rebels" label="Rebeldes" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="partyScope" columnKey="rebellion_rate_pct" label="Tasa rebeldía" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
              </tr>
              <ColumnFiltersRow
                tableId="partyScope"
                columns={[
                  { key: "party", label: "Partido", type: "text" },
                  { key: "scope", label: "Camara/leg", type: "text" },
                  { key: "directional_votes", label: "Votos direccionales", type: "number" },
                  { key: "rebels", label: "Rebeldes", type: "number" },
                  { key: "rebellion_rate_pct", label: "Tasa rebeldia", type: "number" },
                ]}
                filtersByTable={filtersByTable}
                onFilterChange={onFilterChange}
              />
            </thead>
            <tbody>
              {sortedPartyLegRows.map((row) => (
                  <tr key={`${row.party_id}:${row.scope}`}>
                  <td>
                    <PartyLabel
                      partiesById={partiesById}
                      partyMetaById={partyMetaById}
                      partySlugById={partySlugById}
                      availablePartySlugs={availablePartySlugs}
                      row={row}
                      fallback="Partido"
                    />
                  </td>
                  <td>{row.scope}</td>
                  <td>{formatInt(row.directional_votes)}</td>
                  <td>{formatInt(row.rebels)}</td>
                  <td>{toPercent(row.rebellion_rate_pct)}</td>
                </tr>
              ))}
              {!sortedPartyLegRows.length ? (
                <tr>
                  <td colSpan="5">Sin filas para esta cámara</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      ) : null}

      {showOutcomes ? (
      <>
        <section className="card block">
          <div className="blockHead"><h2>Asistencia y participación</h2></div>
          <div className="twoCols">
            <div>
              <h3>Partido por contexto</h3>
              <div className="tableWrap">
                <table className="table">
                  <thead>
                    <tr>
                      <SortHeader tableId="partyContext" columnKey="party" label="Partido" sortByTable={sortByTable} onSort={onSort} />
                      <SortHeader tableId="partyContext" columnKey="context" label="Contexto" sortByTable={sortByTable} onSort={onSort} />
                      <SortHeader tableId="partyContext" columnKey="presence_rate_pct" label="Asistencia" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                      <SortHeader tableId="partyContext" columnKey="absence_rate_pct" label="Ausencias" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                    </tr>
                    <ColumnFiltersRow
                      tableId="partyContext"
                      columns={[
                        { key: "party", label: "Partido", type: "text" },
                        { key: "context", label: "Contexto", type: "text" },
                        { key: "presence_rate_pct", label: "Asistencia", type: "number" },
                        { key: "absence_rate_pct", label: "Ausencias", type: "number" },
                      ]}
                      filtersByTable={filtersByTable}
                      onFilterChange={onFilterChange}
                    />
                  </thead>
                  <tbody>
                    {sortedPartyContextRows.map((row) => (
                      <tr key={`${row.party_id}:${row.context}`}>
                        <td>
                          <PartyLabel
                            partiesById={partiesById}
                            partyMetaById={partyMetaById}
                            partySlugById={partySlugById}
                            availablePartySlugs={availablePartySlugs}
                            row={row}
                            fallback="Partido"
                          />
                        </td>
                        <td>{row.context}</td>
                        <td>{toPercent(row.presence_rate_pct)}</td>
                        <td>{toPercent(row.absence_rate_pct)}</td>
                      </tr>
                    ))}
                    {!sortedPartyContextRows.length ? (
                      <tr>
                        <td colSpan="4">Sin filas</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <h3>Miembros con más ausencias por contexto</h3>
              <div className="tableWrap">
                <table className="table">
                  <thead>
                    <tr>
                      <SortHeader tableId="memberContext" columnKey="person" label="Persona" sortByTable={sortByTable} onSort={onSort} />
                      <SortHeader tableId="memberContext" columnKey="context" label="Contexto" sortByTable={sortByTable} onSort={onSort} />
                      <SortHeader tableId="memberContext" columnKey="absence_rate_pct" label="Ausencias" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                    </tr>
                    <ColumnFiltersRow
                      tableId="memberContext"
                      columns={[
                        { key: "person", label: "Persona", type: "text" },
                        { key: "context", label: "Contexto", type: "text" },
                        { key: "absence_rate_pct", label: "Ausencias", type: "number" },
                      ]}
                      filtersByTable={filtersByTable}
                      onFilterChange={onFilterChange}
                    />
                  </thead>
                  <tbody>
                    {sortedMemberContextRows.map((row) => (
                      <tr key={`${row.person_id}:${row.context}`}>
                        <td>
                          <PersonLink personId={row.person_id}>
                            {row.person_id ? `Persona ${row.person_id}` : "Sin id"}
                          </PersonLink>
                        </td>
                        <td>{row.context}</td>
                        <td>{toPercent(row.absence_rate_pct)}</td>
                      </tr>
                    ))}
                    {!sortedMemberContextRows.length ? (
                      <tr>
                        <td colSpan="3">Sin filas</td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      </>
      ) : null}

      {showCoalitions ? (
      <>
      <section className="card block">
        <div className="blockHead"><h2>Resultados de votaciones y partidos habilitantes</h2></div>
        <p className="sub" style={{ marginTop: "8px" }}>
          Cada fila representa una votación. El margen es la diferencia entre votos favorables y contrarios:
          positivo = se aprueba, negativo = se rechaza, 0 = empate. Los partidos pivotales son los que podrían
          cambiar el resultado si alteran su posición.
        </p>
        <p className="sub" style={{ marginTop: "6px" }}>
          `Completa` exige tres piezas: pregunta de votación, iniciativa vinculada y al menos una fuente oficial enlazada.
        </p>
        <div className="chips" style={{ marginBottom: "10px" }}>
          <span className="chip">Aprobadas: {formatInt(outcomeSummary.passed || 0)}</span>
          <span className="chip">Rechazadas: {formatInt(outcomeSummary.failed || 0)}</span>
          <span className="chip">Empates: {formatInt(outcomeSummary.tied || 0)}</span>
          <span className="chip">Sin señal: {formatInt(outcomeSummary.no_signal || 0)}</span>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <SortHeader tableId="outcomes" columnKey="vote_date" label="Fecha" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="outcomes" columnKey="source_bucket" label="Cámara" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="legislature" label="Legislatura" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="outcomes" columnKey="vote_subject" label="Que se voto" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="initiative" label="Iniciativa" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="interpretability" label="Lectura" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="outcome" label="Resultado" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="margin" label="Margen" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="outcomes" columnKey="topic" label="Tema" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="pivotal_count" label="Pivotales" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="outcomes" columnKey="source_url" label="Fuente" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="outcomes" columnKey="context" label="Contexto" sortByTable={sortByTable} onSort={onSort} />
              </tr>
              <ColumnFiltersRow
                tableId="outcomes"
                columns={[
                  { key: "vote_date", label: "Fecha", type: "text" },
                  { key: "source_bucket", label: "Camara", type: "text" },
                  { key: "legislature", label: "Legislatura", type: "number" },
                  { key: "vote_subject", label: "Que se voto", type: "text" },
                  { key: "initiative", label: "Iniciativa", type: "text" },
                  { key: "interpretability", label: "Lectura", type: "text" },
                  { key: "outcome", label: "Resultado", type: "text" },
                  { key: "margin", label: "Margen", type: "number" },
                  { key: "topic", label: "Tema", type: "text" },
                  { key: "pivotal_count", label: "Pivotales", type: "number" },
                  { key: "source_url", label: "Fuente", type: "text" },
                  { key: "context", label: "Contexto", type: "text" },
                ]}
                filtersByTable={filtersByTable}
                onFilterChange={onFilterChange}
              />
            </thead>
            <tbody>
              {sortedOutcomes.map((row) => (
                <tr key={row.vote_event_id}>
                  <td>{row.vote_date || ""}</td>
                  <td>{formatChamberLabel(row.source_bucket)}</td>
                  <td>{row.legislature || "-"}</td>
                  <td>
                    <div>{getOutcomeSubject(row) || "Sin pregunta de votacion"}</div>
                    {!isOutcomeInterpretable(row) ? (
                      <div style={{ marginTop: "4px", color: "#8a4b3d", fontSize: "0.72rem" }}>
                        Falta: {getOutcomeMissingLabels(row) || "datos esenciales"}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    {getOutcomeInitiativeHref(row) ? (
                      <a href={getOutcomeInitiativeHref(row)}>{getOutcomeInitiativeLabel(row)}</a>
                    ) : (
                      getOutcomeInitiativeLabel(row)
                    )}
                  </td>
                  <td>
                    <span className={`pill ${isOutcomeInterpretable(row) ? "pill-success" : "pill-warning"}`}>
                      {isOutcomeInterpretable(row) ? "Completa" : "Incompleta"}
                    </span>
                  </td>
                  <td>{renderOutcomePill(row.outcome)}</td>
                  <td>{formatOutcomeMargin(row.totals?.margin ?? row.margin)}</td>
                  <td>{formatTopicLabel(row.topic)}</td>
                  <td>{formatInt(row.pivotal_parties?.length || 0)}</td>
                  <td>
                    {getOutcomeSourceUrl(row) ? (
                      <a href={getOutcomeSourceUrl(row)} target="_blank" rel="noreferrer">Fuente oficial</a>
                    ) : (
                      "Sin fuente"
                    )}
                  </td>
                  <td>{formatContextLabel(row.context)}</td>
                </tr>
              ))}
              {!sortedOutcomes.length ? (
                <tr>
                  <td colSpan="11">Sin filas</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead"><h2>Similitud de partidos (coseno/Jaccard)</h2></div>
        <p className="sub">Alto valor indica coalición estable de comportamiento en votaciones.</p>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <SortHeader tableId="coalitions" columnKey="scope" label="Ámbito" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="coalitions" columnKey="party_a" label="Partido A" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="coalitions" columnKey="party_b" label="Partido B" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="coalitions" columnKey="shared_events" label="Eventos" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="coalitions" columnKey="cosine" label="Coseno" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="coalitions" columnKey="jaccard" label="Jaccard" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
              </tr>
              <ColumnFiltersRow
                tableId="coalitions"
                columns={[
                  { key: "scope", label: "Ambito", type: "text" },
                  { key: "party_a", label: "Partido A", type: "text" },
                  { key: "party_b", label: "Partido B", type: "text" },
                  { key: "shared_events", label: "Eventos", type: "number" },
                  { key: "cosine", label: "Coseno", type: "number" },
                  { key: "jaccard", label: "Jaccard", type: "number" },
                ]}
                filtersByTable={filtersByTable}
                onFilterChange={onFilterChange}
              />
            </thead>
                <tbody>
                  {sortedCoalitionRows.map((row) => (
                    <tr key={`${row.scope}:${row.party_1_id}:${row.party_2_id}`}>
                      <td>{row.scope}</td>
                  <td>
                    <PartyLabel
                      partiesById={partiesById}
                      partyMetaById={partyMetaById}
                      partySlugById={partySlugById}
                      availablePartySlugs={availablePartySlugs}
                      row={{
                        party_id: row.party_1_id,
                        party_name: row.party_1_name,
                        party_acronym: row.party_1_acronym,
                      }}
                      fallback={`Partido ${row.party_1_id}`}
                    />
                  </td>
                  <td>
                    <PartyLabel
                      partiesById={partiesById}
                      partyMetaById={partyMetaById}
                      partySlugById={partySlugById}
                      availablePartySlugs={availablePartySlugs}
                      row={{
                        party_id: row.party_2_id,
                        party_name: row.party_2_name,
                        party_acronym: row.party_2_acronym,
                      }}
                      fallback={`Partido ${row.party_2_id}`}
                    />
                  </td>
                  <td>{formatInt(row.shared_events)}</td>
                  <td>{row.cosine.toFixed(3)}</td>
                  <td>{row.jaccard.toFixed(3)}</td>
                </tr>
              ))}
              {!sortedCoalitionRows.length ? (
                <tr>
                  <td colSpan="6">Sin filas</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      </>
      ) : null}

      <section className="card block">
        <div className="blockHead"><h2>Coaliciones por tema</h2></div>
        <p className="sub">Partidos con alta similitud en un tema y baja similitud global.</p>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <SortHeader tableId="issues" columnKey="scope" label="Ámbito" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="issues" columnKey="topic" label="Tema" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="issues" columnKey="party_a" label="Partido A" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="issues" columnKey="party_b" label="Partido B" sortByTable={sortByTable} onSort={onSort} />
                <SortHeader tableId="issues" columnKey="topic_cosine" label="Coseno tema" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="issues" columnKey="global_cosine" label="Coseno global" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
                <SortHeader tableId="issues" columnKey="topic_minus_global" label="Diferencia" sortByTable={sortByTable} onSort={onSort} defaultDirection="desc" />
              </tr>
              <ColumnFiltersRow
                tableId="issues"
                columns={[
                  { key: "scope", label: "Ambito", type: "text" },
                  { key: "topic", label: "Tema", type: "text" },
                  { key: "party_a", label: "Partido A", type: "text" },
                  { key: "party_b", label: "Partido B", type: "text" },
                  { key: "topic_cosine", label: "Coseno tema", type: "number" },
                  { key: "global_cosine", label: "Coseno global", type: "number" },
                  { key: "topic_minus_global", label: "Diferencia", type: "number" },
                ]}
                filtersByTable={filtersByTable}
                onFilterChange={onFilterChange}
              />
            </thead>
                <tbody>
                  {sortedIssueRows.map((row) => (
                    <tr key={`${row.scope}:${row.topic}:${row.party_1_id}:${row.party_2_id}`}>
                      <td>{row.scope}</td>
                      <td>{row.topic}</td>
                  <td>
                    <PartyLabel
                      partiesById={partiesById}
                      partyMetaById={partyMetaById}
                      partySlugById={partySlugById}
                      availablePartySlugs={availablePartySlugs}
                      row={{
                        party_id: row.party_1_id,
                        party_name: row.party_1_name,
                        party_acronym: row.party_1_acronym,
                      }}
                      fallback={`Partido ${row.party_1_id}`}
                    />
                  </td>
                  <td>
                    <PartyLabel
                      partiesById={partiesById}
                      partyMetaById={partyMetaById}
                      partySlugById={partySlugById}
                      availablePartySlugs={availablePartySlugs}
                      row={{
                        party_id: row.party_2_id,
                        party_name: row.party_2_name,
                        party_acronym: row.party_2_acronym,
                      }}
                      fallback={`Partido ${row.party_2_id}`}
                    />
                  </td>
                  <td>{row.topic_cosine.toFixed(3)}</td>
                  <td>{row.global_cosine.toFixed(3)}</td>
                  <td>{row.topic_minus_global.toFixed(3)}</td>
                </tr>
              ))}
              {!sortedIssueRows.length ? (
                <tr>
                  <td colSpan="7">Sin filas</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
