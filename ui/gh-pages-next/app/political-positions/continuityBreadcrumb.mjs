function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function cleanLabel(value) {
  return String(value || "").trim();
}

function normalizeOriginKind(kind) {
  return String(kind || "").trim().toLowerCase() === "concern" ? "concern" : "pack";
}

function buildOriginItem(originContext) {
  const label = cleanLabel(originContext?.label);
  if (!label) {
    return null;
  }
  return {
    kind: "origin",
    originKind: normalizeOriginKind(originContext?.kind),
    label,
  };
}

function buildExactItem(label, topicId) {
  const clean = cleanLabel(label);
  if (!clean) {
    return null;
  }
  return {
    kind: "exact",
    label: clean,
    topicId: toInt(topicId),
  };
}

function buildEntityItem({ selectedPoint, selectedPersonCard, selectedPartyCard }) {
  const scope = cleanLabel(selectedPoint?.scope);
  if (scope === "person") {
    const label = cleanLabel(
      selectedPersonCard?.full_name
      || selectedPoint?.personName
      || selectedPoint?.person_name,
    );
    if (!label) {
      return null;
    }
    return {
      kind: "entity",
      entityKind: "person",
      label,
      entityId: toInt(selectedPersonCard?.person_id || selectedPoint?.personId || selectedPoint?.person_id),
    };
  }
  if (scope === "party") {
    const label = cleanLabel(
      selectedPartyCard?.name
      || selectedPartyCard?.acronym
      || selectedPoint?.partyLabel
      || selectedPoint?.party_label,
    );
    if (!label) {
      return null;
    }
    return {
      kind: "entity",
      entityKind: "party",
      label,
      entityId: toInt(selectedPartyCard?.party_id || selectedPoint?.partyId || selectedPoint?.party_id),
    };
  }
  return null;
}

export function buildPoliticalPositionsContinuityBreadcrumb({
  exactTopicOriginContext,
  exactTopicLabel,
  resolvedTopicId,
  discoveryOriginContext,
  originDiscoveryResumeNotice,
  originDiscoveryVariantSelection,
}) {
  const discoveryFamilyLabel = cleanLabel(
    originDiscoveryResumeNotice?.familyHeadline || originDiscoveryResumeNotice?.familyLabel,
  );
  const discoveryExactLabel = cleanLabel(
    originDiscoveryResumeNotice?.variantLabel || originDiscoveryResumeNotice?.variantHeadline,
  );

  if (originDiscoveryResumeNotice && discoveryFamilyLabel) {
    const items = [
      buildOriginItem(discoveryOriginContext),
      {
        kind: "family",
        label: discoveryFamilyLabel,
      },
      buildExactItem(
        discoveryExactLabel,
        originDiscoveryResumeNotice?.variantTopicId || originDiscoveryResumeNotice?.originTopicId,
      ),
    ].filter(Boolean);

    if (!items.length) {
      return null;
    }

    return {
      mode: "discovery",
      statusLabel: "Ruta editorial retomada",
      items,
      primaryAction: originDiscoveryVariantSelection
        ? {
          kind: "open_exact",
          label: "Volver al tema exacto",
        }
        : null,
      dismissible: true,
      meta: {
        familyCount: toInt(originDiscoveryResumeNotice?.familyCount),
        familyMatchMode: cleanLabel(originDiscoveryResumeNotice?.familyMatchMode || "exact") || "exact",
      },
    };
  }

  const exactItem = buildExactItem(exactTopicLabel, resolvedTopicId);
  const originItem = buildOriginItem(exactTopicOriginContext);
  if (originItem && exactItem) {
    return {
      mode: "exact",
      statusLabel: "Ruta editorial activa",
      items: [originItem, exactItem],
      primaryAction: {
        kind: "restore_discovery",
        label: originItem.originKind === "concern" ? "Volver a la preocupación" : "Volver al paquete",
      },
      dismissible: false,
      meta: null,
    };
  }

  return null;
}

export function buildPoliticalPositionsDetailBreadcrumb({
  continuityBreadcrumb,
  selectedPoint,
  selectedPersonCard,
  selectedPartyCard,
}) {
  if (!continuityBreadcrumb || !selectedPoint) {
    return null;
  }

  const entityItem = buildEntityItem({ selectedPoint, selectedPersonCard, selectedPartyCard });
  if (!entityItem) {
    return null;
  }

  return {
    ...continuityBreadcrumb,
    statusLabel: "Detalle activo",
    items: [
      ...continuityBreadcrumb.items,
      entityItem,
    ],
    dismissible: false,
  };
}
