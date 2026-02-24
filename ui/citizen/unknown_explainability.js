// Citizen unknown/no_signal explainability helpers, shared by UI and tests.
(function bootstrapUnknownExplainability(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CitizenUnknownExplainability = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function unknownExplainabilityFactory() {
  function asNum(v, fallback) {
    const n = Number(v);
    if (!Number.isFinite(n)) return Number(fallback || 0);
    return n;
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

  function normalizedCounts(raw) {
    const c = raw && typeof raw === "object" ? raw : {};
    return {
      support: Math.max(0, asNum(c.support, 0)),
      oppose: Math.max(0, asNum(c.oppose, 0)),
      mixed: Math.max(0, asNum(c.mixed, 0)),
      unclear: Math.max(0, asNum(c.unclear, 0)),
      no_signal: Math.max(0, asNum(c.no_signal, 0)),
    };
  }

  function computeTotal(counts, totalInput) {
    const totalRaw = asNum(totalInput, NaN);
    if (Number.isFinite(totalRaw) && totalRaw > 0) return totalRaw;
    return counts.support + counts.oppose + counts.mixed + counts.unclear + counts.no_signal;
  }

  function dominantUnknown(unknownTotal, unclear, noSignal) {
    if (unknownTotal <= 0) return "none";
    const noSignalShare = noSignal / unknownTotal;
    const unclearShare = unclear / unknownTotal;
    if (noSignalShare >= 0.6) return "no_signal";
    if (unclearShare >= 0.6) return "unclear";
    return "mixed";
  }

  function messageForDominant(dominant, coverageRatio, unclearThreshold) {
    if (dominant === "no_signal") {
      return {
        reason_label: "unknown dominado por sin_senal",
        reason_detail: "La mayoria de celdas unknown no tienen posicion observable.",
        reduce_uncertainty: "Reducir incertidumbre: sumar evidencia verificable (votos, iniciativas o textos enlazados).",
      };
    }
    if (dominant === "unclear") {
      if (coverageRatio < unclearThreshold) {
        return {
          reason_label: "unknown por cobertura baja",
          reason_detail: "La cobertura clara queda por debajo del umbral operativo del 20%.",
          reduce_uncertainty: "Reducir incertidumbre: subir la cobertura clara (a_favor/en_contra/mixto) por encima del umbral.",
        };
      }
      return {
        reason_label: "unknown por senal ambigua",
        reason_detail: "Predominan casos inciertos frente a senal clara.",
        reduce_uncertainty: "Reducir incertidumbre: revisar los casos inciertos y reforzar senal clara por partido.",
      };
    }
    if (dominant === "mixed") {
      return {
        reason_label: "unknown mixto",
        reason_detail: "Unknown combina falta de senal y casos inciertos.",
        reduce_uncertainty: "Reducir incertidumbre: cerrar huecos sin_senal y resolver casos inciertos prioritarios.",
      };
    }
    return {
      reason_label: "sin unknown",
      reason_detail: "No hay celdas unknown en este agregado.",
      reduce_uncertainty: "Mantener cobertura y trazabilidad actuales.",
    };
  }

  function buildUnknownExplainability(input) {
    const i = input || {};
    const counts = normalizedCounts(i.counts);
    const total = computeTotal(counts, i.total);
    const clearTotal = counts.support + counts.oppose + counts.mixed;
    const unknownTotal = counts.unclear + counts.no_signal;
    const unclearThreshold = clamp01(i.unclear_threshold == null ? 0.2 : i.unclear_threshold);
    const fallbackCoverage = total > 0 ? clearTotal / total : 0;
    const coverageRatio = clamp01(i.coverage_ratio == null ? fallbackCoverage : i.coverage_ratio);
    const dominant = dominantUnknown(unknownTotal, counts.unclear, counts.no_signal);
    const msgs = messageForDominant(dominant, coverageRatio, unclearThreshold);

    return {
      explainability_version: "unknown_explainability_v1",
      total: round6(total),
      clear_total: round6(clearTotal),
      unknown_total: round6(unknownTotal),
      unknown_ratio: total > 0 ? round6(clamp01(unknownTotal / total)) : 0,
      unclear_total: round6(counts.unclear),
      no_signal_total: round6(counts.no_signal),
      unclear_ratio: total > 0 ? round6(clamp01(counts.unclear / total)) : 0,
      no_signal_ratio: total > 0 ? round6(clamp01(counts.no_signal / total)) : 0,
      coverage_ratio: round6(coverageRatio),
      unclear_threshold: round6(unclearThreshold),
      dominant_unknown: dominant,
      reason_label: msgs.reason_label,
      reason_detail: msgs.reason_detail,
      reduce_uncertainty: msgs.reduce_uncertainty,
      should_show: Boolean(total > 0 && unknownTotal > 0),
    };
  }

  return {
    buildUnknownExplainability,
  };
});
