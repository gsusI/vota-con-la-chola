// Citizen evidence-trust panel helpers, shared by UI and tests.
(function bootstrapEvidenceTrustPanel(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CitizenEvidenceTrustPanel = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function evidenceTrustPanelFactory() {
  const METHOD_LABELS = {
    combined: "combinado",
    votes: "votos",
    declared: "dichos",
  };

  function asNum(v, fallback) {
    const n = Number(v);
    if (!Number.isFinite(n)) return Number(fallback || 0);
    return n;
  }

  function asInt(v, fallback) {
    return Math.trunc(asNum(v, fallback));
  }

  function clamp01(v) {
    const n = asNum(v, 0);
    if (n < 0) return 0;
    if (n > 1) return 1;
    return n;
  }

  function round6(v) {
    return Number(asNum(v, 0).toFixed(6));
  }

  function normToken(v) {
    return String(v || "").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  }

  function parseDateUtc(v) {
    const s = String(v || "").trim();
    if (!s) return null;
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
      const t = Date.parse(`${s}T00:00:00Z`);
      if (!Number.isFinite(t)) return null;
      return new Date(t);
    }
    const t = Date.parse(s.endsWith("Z") ? s : `${s}T00:00:00Z`);
    if (!Number.isFinite(t)) return null;
    return new Date(t);
  }

  function sourceAgeDays(asOf, lastEvidenceDate) {
    const a = parseDateUtc(asOf);
    const b = parseDateUtc(lastEvidenceDate);
    if (!a || !b) return null;
    const diffMs = a.getTime() - b.getTime();
    if (!Number.isFinite(diffMs)) return null;
    if (diffMs < 0) return 0;
    return Math.floor(diffMs / 86400000);
  }

  function freshnessTier(ageDays) {
    if (ageDays == null) return "unknown";
    const n = asInt(ageDays, -1);
    if (n < 0) return "unknown";
    if (n <= 30) return "fresh";
    if (n <= 120) return "aging";
    return "stale";
  }

  function freshnessLabel(tier) {
    if (tier === "fresh") return "reciente";
    if (tier === "aging") return "vigente";
    if (tier === "stale") return "antigua";
    return "desconocida";
  }

  function trustLevel({ tier, coverageRatio, hasDrilldown }) {
    const c = clamp01(coverageRatio);
    if (tier === "fresh" && c >= 0.5 && hasDrilldown) return "high";
    if ((tier === "fresh" || tier === "aging") && c >= 0.25 && hasDrilldown) return "medium";
    if (tier === "unknown" && c >= 0.5 && hasDrilldown) return "medium";
    return "low";
  }

  function pickLinks(raw) {
    const links = raw && typeof raw === "object" ? raw : {};
    const out = {
      explorer_temas: String(links.explorer_temas || "").trim(),
      explorer_positions: String(links.explorer_positions || "").trim(),
      explorer_evidence: String(links.explorer_evidence || "").trim(),
    };
    return out;
  }

  function buildEvidenceTrustPanel(input) {
    const i = input || {};
    const methodToken = normToken(i.computed_method || i.method || "combined");
    const method = methodToken === "votes" || methodToken === "declared" ? methodToken : "combined";
    const methodLabel = METHOD_LABELS[method] || method;

    const coverage = i.coverage && typeof i.coverage === "object" ? i.coverage : {};
    const evidenceCount = Math.max(0, asInt(i.evidence_count_total != null ? i.evidence_count_total : coverage.evidence_count_total, 0));
    const membersTotal = Math.max(0, asInt(coverage.members_total, 0));
    const membersSignal = Math.max(0, asInt(coverage.members_with_signal, 0));
    const fallbackCoverage = membersTotal > 0 ? membersSignal / membersTotal : 0;
    const coverageRatio = clamp01(i.coverage_ratio != null ? i.coverage_ratio : fallbackCoverage);

    const asOf = String(i.as_of_date || "").trim();
    const lastEvidenceDate = String(i.last_evidence_date || coverage.last_evidence_date || "").trim();
    const ageDays = sourceAgeDays(asOf, lastEvidenceDate);
    const tier = freshnessTier(ageDays);
    const tierLabel = freshnessLabel(tier);

    const links = pickLinks(i.links);
    const drilldownTotal =
      Number(Boolean(links.explorer_temas)) +
      Number(Boolean(links.explorer_positions)) +
      Number(Boolean(links.explorer_evidence));
    const hasDrilldown = drilldownTotal > 0;

    const level = trustLevel({
      tier,
      coverageRatio,
      hasDrilldown,
    });

    const reasons = [];
    if (tier === "unknown") reasons.push("source_age_unknown");
    if (tier === "stale") reasons.push("source_age_stale");
    if (coverageRatio < 0.25) reasons.push("low_coverage_ratio");
    if (!hasDrilldown) reasons.push("missing_drilldown_links");

    return {
      panel_version: "evidence_trust_panel_v1",
      method,
      method_label: methodLabel,
      as_of_date: asOf || null,
      last_evidence_date: lastEvidenceDate || null,
      source_age_days: ageDays == null ? null : asInt(ageDays, 0),
      freshness_tier: tier,
      freshness_label: tierLabel,
      coverage_ratio: round6(coverageRatio),
      evidence_count_total: evidenceCount,
      members_total: membersTotal,
      members_with_signal: membersSignal,
      trust_level: level,
      trust_reasons: reasons,
      links,
      drilldown_total: drilldownTotal,
      has_drilldown: hasDrilldown,
      should_show: true,
    };
  }

  function normStance(v) {
    const token = normToken(v);
    if (token === "support" || token === "oppose" || token === "mixed" || token === "unclear" || token === "no_signal") return token;
    return "no_signal";
  }

  function trustPriority(level) {
    const token = normToken(level);
    if (token === "low") return 3;
    if (token === "medium") return 2;
    if (token === "high") return 1;
    return 2;
  }

  function reasonForCandidate(candidate) {
    const stance = normStance(candidate && candidate.stance);
    const trustLevelToken = normToken(candidate && candidate.trust_level);
    if ((stance === "unclear" || stance === "no_signal") && (trustLevelToken === "low" || trustLevelToken === "medium")) {
      return {
        reason_code: "unknown_with_trust_gap",
        reason_label: "unknown + confianza baja: conviene abrir evidencia",
      };
    }
    if (stance === "unclear" || stance === "no_signal") {
      return {
        reason_code: "unknown_needs_evidence",
        reason_label: "hay incertidumbre: revisar evidencia directa",
      };
    }
    if (trustLevelToken === "low" || trustLevelToken === "medium") {
      return {
        reason_code: "trust_gap",
        reason_label: "confianza parcial: valida con evidencia",
      };
    }
    return {
      reason_code: "audit_next",
      reason_label: "siguiente paso recomendado de auditoria",
    };
  }

  function buildTrustActionNudge(input) {
    const i = input || {};
    const concernId = String(i.concern_id || "").trim();
    const concernLabel = String(i.concern_label || concernId || "").trim();
    const topicIdRaw = asInt(i.topic_id, 0);
    const topicId = topicIdRaw > 0 ? topicIdRaw : null;
    const topicLabel = String(i.topic_label || "").trim();
    const viewModeToken = normToken(i.view_mode || "detail");
    const viewMode = viewModeToken || "detail";
    const rows = Array.isArray(i.rows) ? i.rows : [];

    const candidates = [];
    for (const raw of rows) {
      const row = raw && typeof raw === "object" ? raw : {};
      const links = pickLinks(row.links);
      const linkTarget = String(links.explorer_evidence || "").trim();
      if (!linkTarget) continue;

      const partyId = asInt(row.party_id, 0);
      const partyLabel = String(row.party_label || row.party || row.name || `party_${partyId || "unknown"}`).trim();
      const stance = normStance(row.stance);
      const trustLevelToken = normToken(row.trust_level || "low");
      const coverageRatio = clamp01(row.coverage_ratio);
      const evidenceCount = Math.max(0, asInt(row.evidence_count_total, 0));
      const unknownPriority = stance === "unclear" || stance === "no_signal" ? 2 : 0;
      const trustGapPriority = trustPriority(trustLevelToken);
      const coverageGap = 1.0 - coverageRatio;
      const score = round6(trustGapPriority * 2.0 + unknownPriority * 2.0 + coverageGap + (evidenceCount > 0 ? 0.25 : 0));

      candidates.push({
        party_id: partyId > 0 ? partyId : null,
        party_label: partyLabel || `party_${partyId || "unknown"}`,
        stance,
        trust_level: trustLevelToken || "low",
        coverage_ratio: round6(coverageRatio),
        evidence_count_total: evidenceCount,
        link_target: linkTarget,
        score,
      });
    }

    candidates.sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      const ta = trustPriority(a.trust_level);
      const tb = trustPriority(b.trust_level);
      if (tb !== ta) return tb - ta;
      const ua = Number(a.stance === "unclear" || a.stance === "no_signal");
      const ub = Number(b.stance === "unclear" || b.stance === "no_signal");
      if (ub !== ua) return ub - ua;
      const pa = String(a.party_label || "");
      const pb = String(b.party_label || "");
      const byLabel = pa.localeCompare(pb);
      if (byLabel !== 0) return byLabel;
      return Number(a.party_id || 0) - Number(b.party_id || 0);
    });

    if (!candidates.length) {
      return {
        nudge_version: "trust_action_nudge_v1",
        should_show: false,
        available_candidates_total: 0,
        selected: null,
      };
    }

    const selected = candidates[0];
    const reason = reasonForCandidate(selected);
    const locationLabel = topicLabel || concernLabel || "este bloque";
    const messageShort = `Siguiente paso: abrir evidencia de ${selected.party_label}`;
    const messageLong = `${reason.reason_label} en ${locationLabel}.`;
    const nudgeIdBase = [viewMode, concernId || "none", topicId != null ? String(topicId) : "none", String(selected.party_id || "none")].join(":");
    const nudgeId = nudgeIdBase.replace(/[^a-zA-Z0-9:_-]+/g, "_").toLowerCase();

    return {
      nudge_version: "trust_action_nudge_v1",
      should_show: true,
      available_candidates_total: candidates.length,
      selected: {
        ...selected,
        nudge_id: nudgeId,
        kind: "evidence_click",
        view_mode: viewMode,
        concern_id: concernId || null,
        concern_label: concernLabel || null,
        topic_id: topicId,
        topic_label: topicLabel || null,
        reason_code: reason.reason_code,
        reason_label: reason.reason_label,
        message_short: messageShort,
        message_long: messageLong,
      },
    };
  }

  return {
    buildEvidenceTrustPanel,
    buildTrustActionNudge,
  };
});
