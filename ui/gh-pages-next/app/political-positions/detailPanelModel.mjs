function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function cleanLabel(value) {
  return String(value || "").trim();
}

function clamp01(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return 0;
  }
  return Math.max(0, Math.min(1, num));
}

function toPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }
  return `${(num * 100).toFixed(1)}%`;
}

function toScore(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }
  return num.toFixed(2);
}

function formatDate(value) {
  return cleanLabel(value) || "—";
}

function buildExactTraceCopy(scopeKind) {
  if (scopeKind === "party") {
    return {
      actionLabel: "Abrir rastro exacto del grupo y el tema",
      subtitleTarget: "del grupo y el tema activos",
    };
  }
  return {
    actionLabel: "Abrir rastro exacto de la persona y el tema",
    subtitleTarget: "de la persona y el tema activos",
  };
}

function buildExactTraceHint({ scopeKind, hasTruncatedSamples, hasAggregateGap, availableCount }) {
  const scopePrefix = scopeKind === "party" ? "mismo grupo y tema" : "misma persona y tema";
  if (hasTruncatedSamples && hasAggregateGap) {
    return `${scopePrefix}, tabla completa + evidencia extra`;
  }
  if (hasTruncatedSamples) {
    return `${scopePrefix}, tabla completa`;
  }
  if (hasAggregateGap && availableCount > 0) {
    return `${scopePrefix}, evidencia agregada no listada`;
  }
  if (hasAggregateGap) {
    return `${scopePrefix}, postura sin muestra puntual`;
  }
  return "";
}

export function buildPoliticalPositionsDetailPanelSummary({
  selectedPoint,
  resolvedTopicFilter,
  detailContinuityBreadcrumb,
}) {
  if (detailContinuityBreadcrumb) {
    return "La ruta superior resume el contexto editorial. Debajo tienes postura agregada, revision y drill-down reproducible.";
  }
  if (selectedPoint) {
    return "Vista puntual de evidencia, revision y Explorer para la fila activa.";
  }
  if (resolvedTopicFilter) {
    return "Tema exacto activo. Selecciona una fila para abrir evidencia puntual, revision y drill-down reproducible.";
  }
  return "Selecciona una fila para ver evidencia puntual, revision y drill-down reproducible.";
}

export function buildPoliticalPositionsDetailOverview(selectedPoint) {
  if (!selectedPoint) {
    return [];
  }

  const entries = [
    { label: "Postura", value: cleanLabel(selectedPoint.stance) || "no_signal", kind: "stance" },
    { label: "Metodo", value: cleanLabel(selectedPoint.method) || "—" },
    { label: "As of", value: cleanLabel(selectedPoint.asOf) || "—" },
    { label: "Score", value: toScore(selectedPoint.score) },
    { label: "Confianza", value: toPercent(selectedPoint.confidence) },
    { label: "Evidencias", value: String(toInt(selectedPoint.evidenceCount || 0)) },
    { label: "Ultima evidencia", value: formatDate(selectedPoint.lastEvidenceDate) },
  ];

  const windowDays = toInt(selectedPoint.windowDays);
  if (windowDays > 0) {
    entries.push({ label: "Ventana", value: `${windowDays} dias` });
  }

  return entries;
}

export function buildPoliticalPositionsDetailDrilldownLinks({
  basePath,
  selectedPoint,
  topicSetId,
}) {
  if (!selectedPoint) {
    return [];
  }

  const safeBasePath = cleanLabel(basePath);
  const topicId = toInt(selectedPoint.topicId);
  const safeTopicSetId = toInt(topicSetId) || 1;

  if (cleanLabel(selectedPoint.scope) === "person") {
    const personId = toInt(selectedPoint.personId);
    if (!personId || !topicId) {
      return [];
    }
    return [
      {
        label: "Rastro exacto: evidencia persona + tema",
        href: `${safeBasePath}/explorer/?t=topic_evidence&wc=person_id&wv=${personId}&wc=topic_id&wv=${topicId}&wc=topic_set_id&wv=${safeTopicSetId}`,
      },
      {
        label: "Votos base del mismo punto",
        hint: "misma persona y tema, solo votos base",
        href: `${safeBasePath}/explorer/?t=parl_vote_member_votes&wc=person_id&wv=${personId}&wc=topic_id&wv=${topicId}`,
      },
    ];
  }

  if (cleanLabel(selectedPoint.scope) === "party") {
    const partyId = toInt(selectedPoint.partyId);
    if (!partyId || !topicId) {
      return [];
    }
    return [
      {
        label: "Rastro exacto: grupo + tema",
        href: `${safeBasePath}/explorer/?t=topic_positions&wc=party_id&wv=${partyId}&wc=topic_id&wv=${topicId}&wc=topic_set_id&wv=${safeTopicSetId}`,
      },
      {
        label: "Otras posturas del grupo",
        hint: "mismo grupo, otros temas",
        href: `${safeBasePath}/explorer/?t=topic_positions&wc=party_id&wv=${partyId}&wc=topic_set_id&wv=${safeTopicSetId}`,
      },
    ];
  }

  return [];
}

export function buildPoliticalPositionsEvidenceTableHeader({
  selectedPoint,
  visibleSampleCount,
  availableSampleCount,
  reviewLabel,
  drilldownLinks,
}) {
  if (!selectedPoint) {
    return null;
  }

  const scopeKind = cleanLabel(selectedPoint.scope) === "party" ? "party" : "person";
  const scopeLabel = scopeKind === "party" ? "grupo" : "persona";
  const scopeArticle = scopeKind === "party" ? "del" : "de la";
  const exactTraceCopy = buildExactTraceCopy(scopeKind);
  const visibleCount = Math.max(0, toInt(visibleSampleCount));
  const availableCount = Math.max(visibleCount, toInt(availableSampleCount));
  const evidenceCount = Math.max(0, toInt(selectedPoint.evidenceCount || 0));
  const hasTruncatedSamples = availableCount > visibleCount && visibleCount > 0;
  const hasAggregateGap = evidenceCount > availableCount;
  const exactTraceHint = buildExactTraceHint({
    scopeKind,
    hasTruncatedSamples,
    hasAggregateGap,
    availableCount,
  });
  const subtitle = hasTruncatedSamples && hasAggregateGap
    ? `Ves ${visibleCount}/${availableCount} muestras; el score usa ${evidenceCount} evidencias. Abre el rastro exacto ${exactTraceCopy.subtitleTarget}.`
    : hasTruncatedSamples
    ? `Ves ${visibleCount}/${availableCount} muestras. Abre el rastro exacto ${exactTraceCopy.subtitleTarget}.`
    : availableCount > 0 && hasAggregateGap
    ? `Hay ${availableCount} muestras publicadas; el score usa ${evidenceCount} evidencias. Abre el rastro exacto ${exactTraceCopy.subtitleTarget}.`
    : availableCount === 0 && hasAggregateGap
    ? `No hay muestra puntual publicada; el score usa ${evidenceCount} evidencias. Abre el rastro exacto ${exactTraceCopy.subtitleTarget}.`
    : visibleCount > 0
    ? `Drill-down reproducible para la ${scopeLabel} y el tema activos.`
    : `No hay muestras puntuales listadas; usa Explorer para abrir el rastro completo ${scopeArticle} ${scopeLabel}.`;
  const links = (Array.isArray(drilldownLinks) ? drilldownLinks : [])
    .filter((link) => cleanLabel(link?.href))
    .map((link, index) => ({
      ...link,
      role: index === 0 ? "primary" : "secondary",
      label: (hasTruncatedSamples || hasAggregateGap) && index === 0
        ? exactTraceCopy.actionLabel
        : link.label,
      hint: index === 0 ? exactTraceHint : (link.hint || ""),
    }));

  return {
    title: "Muestras y auditoria",
    subtitle,
    chips: [
      {
        label: "Revision",
        value: cleanLabel(reviewLabel) || "Sin revision registrada",
      },
      {
        label: hasTruncatedSamples ? "Mostrando" : "Muestras puntuales",
        value: hasTruncatedSamples ? `${visibleCount} de ${availableCount}` : String(availableCount),
      },
      {
        label: "Evidencias agregadas",
        value: String(evidenceCount),
      },
    ],
    links,
  };
}
