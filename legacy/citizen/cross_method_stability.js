// Citizen cross-method stability helpers, shared by UI and tests.
(function bootstrapCrossMethodStability(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CitizenCrossMethodStability = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function crossMethodStabilityFactory() {
  const PAIRS = [
    ["votes", "declared", "votes_declared"],
    ["combined", "votes", "combined_votes"],
    ["combined", "declared", "combined_declared"],
  ];

  function asNum(v, fallback) {
    const n = Number(v);
    if (!Number.isFinite(n)) return Number(fallback || 0);
    return n;
  }

  function round6(v) {
    return Number(asNum(v, 0).toFixed(6));
  }

  function normStance(v) {
    const s = String(v || "").trim().toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
    if (s === "support" || s === "oppose" || s === "mixed" || s === "unclear" || s === "no_signal") return s;
    return "no_signal";
  }

  function isComparableStance(s) {
    const k = normStance(s);
    return k === "support" || k === "oppose";
  }

  function isUnknownStance(s) {
    const k = normStance(s);
    return k === "unclear" || k === "no_signal" || k === "mixed";
  }

  function pairStats(rows, a, b) {
    const total = rows.length;
    let comparable = 0;
    let match = 0;
    let mismatch = 0;
    let notComparable = 0;
    for (const row of rows) {
      const sa = normStance(row[a]);
      const sb = normStance(row[b]);
      if (isComparableStance(sa) && isComparableStance(sb)) {
        comparable += 1;
        if (sa === sb) match += 1;
        else mismatch += 1;
      } else {
        notComparable += 1;
      }
    }
    const comparablePct = total > 0 ? comparable / total : 0;
    const mismatchPctComparable = comparable > 0 ? mismatch / comparable : 0;
    return {
      total_cells: total,
      comparable,
      comparable_pct_total: round6(comparablePct),
      match,
      mismatch,
      mismatch_pct_of_comparable: round6(mismatchPctComparable),
      not_comparable: notComparable,
    };
  }

  function methodCoverage(rows, key) {
    const total = rows.length;
    let support = 0;
    let oppose = 0;
    let mixed = 0;
    let unclear = 0;
    let noSignal = 0;
    for (const row of rows) {
      const s = normStance(row[key]);
      if (s === "support") support += 1;
      else if (s === "oppose") oppose += 1;
      else if (s === "mixed") mixed += 1;
      else if (s === "unclear") unclear += 1;
      else noSignal += 1;
    }
    const clear = support + oppose + mixed;
    const unknown = unclear + noSignal + mixed;
    return {
      total_cells: total,
      counts: {
        support,
        oppose,
        mixed,
        unclear,
        no_signal: noSignal,
      },
      clear,
      clear_pct: round6(total > 0 ? clear / total : 0),
      unknown,
      unknown_pct: round6(total > 0 ? unknown / total : 0),
    };
  }

  function buildReasonLabel(primaryReason) {
    if (primaryReason === "low_votes_declared_comparable") return "comparables bajos entre votos y dichos";
    if (primaryReason === "declared_unknown_dominant") return "dichos con incertidumbre dominante";
    if (primaryReason === "high_votes_declared_mismatch") return "mismatch alto entre votos y dichos";
    if (primaryReason === "combined_tracks_votes_not_declared") return "combinado sigue votos, no dichos";
    return "estabilidad sin alertas fuertes";
  }

  function buildReasonDetail(primaryReason) {
    if (primaryReason === "low_votes_declared_comparable") {
      return "La comparabilidad votes-vs-declared cae por debajo del umbral operativo.";
    }
    if (primaryReason === "declared_unknown_dominant") {
      return "La capa declarada concentra unknown (unclear/no_signal/mixed), reduciendo trazabilidad cruzada.";
    }
    if (primaryReason === "high_votes_declared_mismatch") {
      return "Cuando ambos son comparables, los desacuerdos votes-vs-declared superan el umbral de estabilidad.";
    }
    if (primaryReason === "combined_tracks_votes_not_declared") {
      return "La salida combinada se alinea con votos y diverge de dichos para la misma celda comparable.";
    }
    return "No se detectan señales fuertes de inestabilidad para este corte.";
  }

  function computeWeightedStability(pairStatsById) {
    let wSum = 0;
    let acc = 0;
    for (const [_a, _b, id] of PAIRS) {
      const p = pairStatsById[id];
      const w = asNum((p || {}).comparable_pct_total, 0);
      const mismatch = asNum((p || {}).mismatch_pct_of_comparable, 0);
      const stable = 1 - mismatch;
      if (w <= 0) continue;
      wSum += w;
      acc += w * stable;
    }
    if (wSum <= 0) return 0;
    return round6(acc / wSum);
  }

  function buildCrossMethodStability(input) {
    const i = input || {};
    const rowsRaw = Array.isArray(i.rows) ? i.rows : [];
    const rows = rowsRaw.map((r) => ({
      votes: normStance(r && r.votes),
      declared: normStance(r && r.declared),
      combined: normStance(r && r.combined),
    }));

    const minComparableRatio = Math.max(0, asNum(i.min_comparable_ratio == null ? 0.15 : i.min_comparable_ratio, 0.15));
    const highMismatchThreshold = Math.max(0, asNum(i.high_mismatch_threshold == null ? 0.35 : i.high_mismatch_threshold, 0.35));

    const pairStatsById = {};
    for (const [a, b, id] of PAIRS) {
      pairStatsById[id] = pairStats(rows, a, b);
    }

    const coverageByMethod = {
      votes: methodCoverage(rows, "votes"),
      declared: methodCoverage(rows, "declared"),
      combined: methodCoverage(rows, "combined"),
    };

    const votesDeclared = pairStatsById.votes_declared;
    const combinedVotes = pairStatsById.combined_votes;
    const combinedDeclared = pairStatsById.combined_declared;
    const declaredUnknownPct = asNum((coverageByMethod.declared || {}).unknown_pct, 0);

    const reasons = [];
    if (asNum(votesDeclared.comparable_pct_total, 0) < minComparableRatio) {
      reasons.push("low_votes_declared_comparable");
    }
    if (declaredUnknownPct >= 0.8) {
      reasons.push("declared_unknown_dominant");
    }
    if (
      asNum(votesDeclared.comparable, 0) > 0 &&
      asNum(votesDeclared.mismatch_pct_of_comparable, 0) >= highMismatchThreshold
    ) {
      reasons.push("high_votes_declared_mismatch");
    }
    if (
      asNum(combinedVotes.comparable, 0) > 0 &&
      asNum(combinedVotes.mismatch_pct_of_comparable, 0) <= 0.05 &&
      asNum(combinedDeclared.comparable, 0) > 0 &&
      asNum(combinedDeclared.mismatch_pct_of_comparable, 0) >= 0.3
    ) {
      reasons.push("combined_tracks_votes_not_declared");
    }

    const weightedStability = computeWeightedStability(pairStatsById);
    const primaryReason = reasons.length ? String(reasons[0]) : "no_strong_alert";

    let uncertaintyLevel = "low";
    if (declaredUnknownPct >= 0.9 || asNum(votesDeclared.comparable_pct_total, 0) < 0.1) uncertaintyLevel = "high";
    else if (declaredUnknownPct >= 0.7 || asNum(votesDeclared.comparable_pct_total, 0) < 0.2) uncertaintyLevel = "medium";

    let status = "stable";
    if (!rows.length) status = "unknown";
    else if (reasons.includes("low_votes_declared_comparable") || reasons.includes("declared_unknown_dominant")) status = "uncertain";
    else if (weightedStability >= 0.8 && asNum(votesDeclared.mismatch_pct_of_comparable, 0) <= 0.25) status = "stable";
    else if (weightedStability >= 0.55) status = "mixed";
    else status = "unstable";

    return {
      stability_version: "cross_method_stability_v1",
      total_cells: rows.length,
      thresholds: {
        min_comparable_ratio: round6(minComparableRatio),
        high_mismatch_threshold: round6(highMismatchThreshold),
      },
      pair_stats: pairStatsById,
      coverage_by_method: coverageByMethod,
      weighted_stability_score: round6(weightedStability),
      status,
      uncertainty_level: uncertaintyLevel,
      uncertainty_reasons: reasons,
      reason_label: buildReasonLabel(primaryReason),
      reason_detail: buildReasonDetail(primaryReason),
      should_show: rows.length > 0,
    };
  }

  return {
    buildCrossMethodStability,
    isComparableStance,
    isUnknownStance,
  };
});
