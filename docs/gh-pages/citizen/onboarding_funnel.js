// Citizen onboarding funnel helpers, shared by UI and tests.
(function bootstrapOnboardingFunnel(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CitizenOnboardingFunnel = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function onboardingFunnelFactory() {
  function bool(v) {
    return Boolean(v);
  }

  function clamp01(x) {
    const n = Number(x || 0);
    if (!Number.isFinite(n)) return 0;
    if (n < 0) return 0;
    if (n > 1) return 1;
    return n;
  }

  function computeNextAction(input) {
    const i = input || {};
    const packReady = bool(i.packReady);
    const concernReady = bool(i.concernReady);
    const topicReady = bool(i.topicReady);
    const alignmentReady = bool(i.alignmentReady);
    const preferenceReady = bool(i.preferenceReady);
    const hasRecommendedPack = bool(i.hasRecommendedPack);
    const hasRecommendedConcern = bool(i.hasRecommendedConcern);
    const hasRecommendedTopic = bool(i.hasRecommendedTopic);

    if (!packReady && hasRecommendedPack) {
      return {
        id: "apply_pack",
        label: "Siguiente: aplicar pack",
        reason: "pack_pendiente",
      };
    }
    if (!concernReady && hasRecommendedConcern) {
      return {
        id: "select_concern",
        label: "Siguiente: elegir preocupacion",
        reason: "concern_pendiente",
      };
    }
    if (!topicReady && hasRecommendedTopic) {
      return {
        id: "open_topic",
        label: "Siguiente: abrir item",
        reason: "topic_pendiente",
      };
    }
    if (!alignmentReady) {
      return {
        id: "open_alignment",
        label: "Siguiente: ir a alineamiento",
        reason: "alignment_pendiente",
      };
    }
    if (!preferenceReady) {
      return {
        id: "set_preference",
        label: "Siguiente: marcar tu postura",
        reason: "preference_pendiente",
      };
    }
    return {
      id: "done",
      label: "Onboarding completo",
      reason: "done",
    };
  }

  function computeFunnelState(input) {
    const i = input || {};
    const packReady = bool(i.packReady);
    const concernReady = bool(i.concernReady);
    const topicReady = bool(i.topicReady);
    const alignmentReady = bool(i.alignmentReady);
    const preferenceReady = bool(i.preferenceReady);
    const hasRecommendedPack = bool(i.hasRecommendedPack);
    const hasRecommendedConcern = bool(i.hasRecommendedConcern);
    const hasRecommendedTopic = bool(i.hasRecommendedTopic);

    const steps = [
      {
        id: "pack",
        order: 0,
        required: false,
        done: packReady || !hasRecommendedPack,
      },
      {
        id: "concern",
        order: 1,
        required: true,
        done: concernReady,
      },
      {
        id: "topic",
        order: 2,
        required: true,
        done: topicReady,
      },
      {
        id: "alignment",
        order: 3,
        required: true,
        done: alignmentReady,
      },
      {
        id: "preference",
        order: 4,
        required: true,
        done: preferenceReady,
      },
    ];

    const requiredSteps = steps.filter((s) => s.required);
    const requiredTotal = requiredSteps.length;
    const requiredDone = requiredSteps.filter((s) => s.done).length;
    const requiredCompletionPct = requiredTotal > 0 ? clamp01(requiredDone / requiredTotal) : 0;
    const nextAction = computeNextAction({
      packReady,
      concernReady,
      topicReady,
      alignmentReady,
      preferenceReady,
      hasRecommendedPack,
      hasRecommendedConcern,
      hasRecommendedTopic,
    });

    return {
      checks: {
        pack_ready: packReady,
        concern_ready: concernReady,
        topic_ready: topicReady,
        alignment_ready: alignmentReady,
        preference_ready: preferenceReady,
      },
      signals: {
        has_recommended_pack: hasRecommendedPack,
        has_recommended_concern: hasRecommendedConcern,
        has_recommended_topic: hasRecommendedTopic,
      },
      required_total: requiredTotal,
      required_done: requiredDone,
      required_completion_pct: Number(requiredCompletionPct.toFixed(6)),
      steps,
      next_action: nextAction,
    };
  }

  return {
    computeFunnelState,
    computeNextAction,
  };
});
