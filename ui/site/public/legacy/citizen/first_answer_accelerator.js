// Citizen first-answer accelerator helpers, shared by UI and tests.
(function bootstrapFirstAnswerAccelerator(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CitizenFirstAnswerAccelerator = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function firstAnswerAcceleratorFactory() {
  const CLEAR_STANCES = new Set(["support", "oppose", "mixed"]);
  const SIGNAL_STANCES = new Set(["support", "oppose", "mixed", "unclear"]);

  function clamp01(x) {
    const n = Number(x || 0);
    if (!Number.isFinite(n)) return 0;
    if (n < 0) return 0;
    if (n > 1) return 1;
    return n;
  }

  function asInt(v, fallback) {
    const n = Number(v);
    if (!Number.isFinite(n)) return Number(fallback || 0);
    return Math.trunc(n);
  }

  function asNum(v, fallback) {
    const n = Number(v);
    if (!Number.isFinite(n)) return Number(fallback || 0);
    return n;
  }

  function normToken(v) {
    return String(v || "").trim().toLowerCase();
  }

  function uniqIds(values) {
    const out = [];
    const seen = new Set();
    for (const raw of values || []) {
      const token = String(raw || "").trim();
      if (!token || seen.has(token)) continue;
      seen.add(token);
      out.push(token);
    }
    return out;
  }

  function round6(x) {
    return Number(asNum(x, 0).toFixed(6));
  }

  function topicOrderKey(topic) {
    const t = topic || {};
    const high = t.is_high_stakes ? 1 : 0;
    const rankRaw = asNum(t.stakes_rank, Number.POSITIVE_INFINITY);
    const rank = Number.isFinite(rankRaw) ? rankRaw : Number.POSITIVE_INFINITY;
    const tid = asInt(t.topic_id, Number.MAX_SAFE_INTEGER);
    return {
      high,
      rank,
      tid,
    };
  }

  function compareTopicOrder(a, b) {
    const ak = topicOrderKey(a);
    const bk = topicOrderKey(b);
    if (bk.high !== ak.high) return bk.high - ak.high;
    if (ak.rank !== bk.rank) return ak.rank - bk.rank;
    if (ak.tid !== bk.tid) return ak.tid - bk.tid;
    const al = String((a && a.label) || "");
    const bl = String((b && b.label) || "");
    return al.localeCompare(bl);
  }

  function scoreTopic(stats, topic) {
    const clearPct = clamp01(stats && stats.clear_pct);
    const anySignalPct = clamp01(stats && stats.any_signal_pct);
    const unknownPct = clamp01(stats && stats.unknown_pct);
    const confAvg = clamp01(stats && stats.confidence_avg_signal);
    const isHighStakes = Boolean(topic && topic.is_high_stakes);
    const stakesRank = asNum(topic && topic.stakes_rank, 0);

    const highStakesBonus = isHighStakes ? 0.08 : 0;
    const rankBonus = stakesRank > 0 ? Math.min(0.05, 0.2 / (stakesRank + 1)) : 0;

    const base =
      clearPct * 0.5 +
      anySignalPct * 0.2 +
      (1.0 - unknownPct) * 0.1 +
      confAvg * 0.2 +
      highStakesBonus +
      rankBonus;
    return round6(clamp01(base));
  }

  function buildTopicStats(topic, parties, posByKey) {
    const tid = asInt(topic && topic.topic_id, 0);
    const partyIds = Array.isArray(parties)
      ? parties.map((p) => asInt(p && p.party_id, 0)).filter((x) => x > 0)
      : [];
    const uniquePartyIds = uniqIds(partyIds).map((x) => asInt(x, 0));
    const partiesTotal = uniquePartyIds.length;
    if (!partiesTotal) {
      return {
        parties_total: 0,
        clear_total: 0,
        signal_total: 0,
        unknown_total: 0,
        clear_pct: 0,
        any_signal_pct: 0,
        unknown_pct: 0,
        confidence_avg_signal: 0,
        score: 0,
      };
    }

    let clearTotal = 0;
    let signalTotal = 0;
    let unknownTotal = 0;
    let confSum = 0;
    let confN = 0;

    for (const pid of uniquePartyIds) {
      const key = `${tid}:${pid}`;
      const row = posByKey.get(key) || null;
      const stance = normToken(row && row.stance ? row.stance : "no_signal");
      if (SIGNAL_STANCES.has(stance)) signalTotal += 1;
      if (CLEAR_STANCES.has(stance)) clearTotal += 1;
      if (stance === "unclear" || stance === "no_signal") unknownTotal += 1;
      if (SIGNAL_STANCES.has(stance)) {
        confSum += clamp01(asNum(row && row.confidence, 0));
        confN += 1;
      }
    }

    const clearPct = partiesTotal > 0 ? clearTotal / partiesTotal : 0;
    const anySignalPct = partiesTotal > 0 ? signalTotal / partiesTotal : 0;
    const unknownPct = partiesTotal > 0 ? unknownTotal / partiesTotal : 0;
    const confAvg = confN > 0 ? confSum / confN : 0;

    const stats = {
      parties_total: partiesTotal,
      clear_total: clearTotal,
      signal_total: signalTotal,
      unknown_total: unknownTotal,
      clear_pct: round6(clamp01(clearPct)),
      any_signal_pct: round6(clamp01(anySignalPct)),
      unknown_pct: round6(clamp01(unknownPct)),
      confidence_avg_signal: round6(clamp01(confAvg)),
    };
    stats.score = scoreTopic(stats, topic);
    return stats;
  }

  function deriveParties(parties, positions) {
    const explicit = Array.isArray(parties)
      ? parties
          .map((p) => ({ party_id: asInt(p && p.party_id, 0) }))
          .filter((p) => p.party_id > 0)
      : [];
    if (explicit.length) return explicit;

    const out = [];
    const seen = new Set();
    for (const row of positions || []) {
      const pid = asInt(row && row.party_id, 0);
      if (pid <= 0 || seen.has(pid)) continue;
      seen.add(pid);
      out.push({ party_id: pid });
    }
    out.sort((a, b) => a.party_id - b.party_id);
    return out;
  }

  function pickFallbackRecommendation(concerns, topics) {
    const concernsSorted = (concerns || [])
      .map((c) => ({
        concern_id: String((c && c.id) || "").trim(),
        concern_label: String((c && (c.label || c.id)) || "").trim(),
      }))
      .filter((c) => c.concern_id)
      .sort((a, b) => {
        const byLabel = String(a.concern_label || a.concern_id).localeCompare(String(b.concern_label || b.concern_id));
        if (byLabel !== 0) return byLabel;
        return String(a.concern_id).localeCompare(String(b.concern_id));
      });

    const topicsSorted = (topics || []).slice().sort(compareTopicOrder);
    let concernId = concernsSorted.length ? concernsSorted[0].concern_id : "";
    let concernLabel = concernsSorted.length ? concernsSorted[0].concern_label : "";
    let topic = null;

    if (concernId) {
      const forConcern = topicsSorted.filter((t) => (t && Array.isArray(t.concern_ids) ? t.concern_ids : []).includes(concernId));
      if (forConcern.length) topic = forConcern[0];
    }
    if (!topic && topicsSorted.length) topic = topicsSorted[0];

    if (topic && !concernId) {
      const ids = uniqIds(Array.isArray(topic.concern_ids) ? topic.concern_ids : []);
      if (ids.length) {
        concernId = ids[0];
        concernLabel = concernId;
      }
    }

    if (!topic || !concernId) {
      return { recommended: null, reason: "fallback_empty" };
    }

    return {
      recommended: {
        concern_id: concernId,
        concern_label: concernLabel || concernId,
        topic_id: asInt(topic.topic_id, 0),
        topic_label: String(topic.label || `topic_id=${asInt(topic.topic_id, 0)}`),
        score: 0,
        links: {
          explorer_temas: String((topic.links && topic.links.explorer_temas) || ""),
          explorer_positions: String((topic.links && topic.links.explorer_positions) || ""),
          explorer_evidence: String((topic.links && topic.links.explorer_evidence) || ""),
        },
        reason: "fallback",
      },
      reason: "fallback",
    };
  }

  function computeFirstAnswerPlan(input) {
    const i = input || {};
    const concerns = Array.isArray(i.concerns) ? i.concerns : [];
    const topicsRaw = Array.isArray(i.topics) ? i.topics : [];
    const positions = Array.isArray(i.positions) ? i.positions : [];
    const parties = deriveParties(i.parties, positions);

    const topics = topicsRaw
      .map((t) => {
        const tid = asInt(t && t.topic_id, 0);
        if (tid <= 0) return null;
        return {
          topic_id: tid,
          label: String((t && t.label) || `topic_id=${tid}`),
          stakes_rank: t && t.stakes_rank != null ? asNum(t.stakes_rank, 0) : null,
          is_high_stakes: Boolean(t && t.is_high_stakes),
          concern_ids: uniqIds(Array.isArray(t && t.concern_ids) ? t.concern_ids : []),
          links: (t && t.links && typeof t.links === "object" ? t.links : {}) || {},
        };
      })
      .filter((t) => t);

    const posByKey = new Map();
    for (const row of positions) {
      const tid = asInt(row && row.topic_id, 0);
      const pid = asInt(row && row.party_id, 0);
      if (tid <= 0 || pid <= 0) continue;
      const key = `${tid}:${pid}`;
      if (posByKey.has(key)) continue;
      posByKey.set(key, {
        stance: normToken(row && row.stance ? row.stance : "no_signal"),
        confidence: clamp01(asNum(row && row.confidence, 0)),
      });
    }

    const concernRank = [];
    for (const c of concerns) {
      const cid = String((c && c.id) || "").trim();
      if (!cid) continue;
      const label = String((c && (c.label || c.id)) || cid);
      const topicCandidates = topics.filter((t) => (t.concern_ids || []).includes(cid));
      if (!topicCandidates.length) continue;

      const scored = topicCandidates
        .map((t) => {
          const stats = buildTopicStats(t, parties, posByKey);
          return {
            topic: t,
            stats,
          };
        })
        .sort((a, b) => {
          const as = asNum(a && a.stats && a.stats.score, 0);
          const bs = asNum(b && b.stats && b.stats.score, 0);
          if (bs !== as) return bs - as;
          return compareTopicOrder(a.topic, b.topic);
        });

      if (!scored.length) continue;
      const best = scored[0];
      const avgClear = scored.reduce((acc, x) => acc + asNum(x.stats.clear_pct, 0), 0) / scored.length;
      const avgAnySignal = scored.reduce((acc, x) => acc + asNum(x.stats.any_signal_pct, 0), 0) / scored.length;
      let concernScore =
        asNum(best.stats.score, 0) * 0.7 +
        clamp01(avgClear) * 0.2 +
        clamp01(avgAnySignal) * 0.1 +
        Math.min(0.03, scored.length * 0.005);
      concernScore = round6(clamp01(concernScore));

      concernRank.push({
        concern_id: cid,
        concern_label: label,
        score: concernScore,
        topics_total: scored.length,
        clear_pct_avg: round6(clamp01(avgClear)),
        any_signal_pct_avg: round6(clamp01(avgAnySignal)),
        top_topic: {
          topic_id: asInt(best.topic.topic_id, 0),
          topic_label: String(best.topic.label || `topic_id=${asInt(best.topic.topic_id, 0)}`),
          score: round6(asNum(best.stats.score, 0)),
          clear_pct: round6(asNum(best.stats.clear_pct, 0)),
          any_signal_pct: round6(asNum(best.stats.any_signal_pct, 0)),
          unknown_pct: round6(asNum(best.stats.unknown_pct, 0)),
          confidence_avg_signal: round6(asNum(best.stats.confidence_avg_signal, 0)),
          is_high_stakes: Boolean(best.topic.is_high_stakes),
          stakes_rank: best.topic.stakes_rank,
          links: {
            explorer_temas: String((best.topic.links && best.topic.links.explorer_temas) || ""),
            explorer_positions: String((best.topic.links && best.topic.links.explorer_positions) || ""),
            explorer_evidence: String((best.topic.links && best.topic.links.explorer_evidence) || ""),
          },
        },
      });
    }

    concernRank.sort((a, b) => {
      const as = asNum(a && a.score, 0);
      const bs = asNum(b && b.score, 0);
      if (bs !== as) return bs - as;
      const at = asNum(a && a.top_topic && a.top_topic.score, 0);
      const bt = asNum(b && b.top_topic && b.top_topic.score, 0);
      if (bt !== at) return bt - at;
      const an = asInt(a && a.topics_total, 0);
      const bn = asInt(b && b.topics_total, 0);
      if (bn !== an) return bn - an;
      const byLabel = String(a && (a.concern_label || a.concern_id) || "").localeCompare(
        String(b && (b.concern_label || b.concern_id) || "")
      );
      if (byLabel !== 0) return byLabel;
      return String((a && a.concern_id) || "").localeCompare(String((b && b.concern_id) || ""));
    });

    let recommended = null;
    let fallbackUsed = false;
    let reason = "ranked";

    if (concernRank.length) {
      const top = concernRank[0];
      recommended = {
        concern_id: String(top.concern_id || ""),
        concern_label: String(top.concern_label || top.concern_id || ""),
        topic_id: asInt(top.top_topic && top.top_topic.topic_id, 0),
        topic_label: String((top.top_topic && top.top_topic.topic_label) || ""),
        score: round6(asNum(top.score, 0)),
        links: {
          explorer_temas: String((top.top_topic && top.top_topic.links && top.top_topic.links.explorer_temas) || ""),
          explorer_positions: String((top.top_topic && top.top_topic.links && top.top_topic.links.explorer_positions) || ""),
          explorer_evidence: String((top.top_topic && top.top_topic.links && top.top_topic.links.explorer_evidence) || ""),
        },
        reason: "ranked",
      };
    } else {
      const fallback = pickFallbackRecommendation(concerns, topics);
      recommended = fallback.recommended;
      fallbackUsed = true;
      reason = fallback.reason || "fallback";
    }

    return {
      accelerator_version: "first_answer_v1",
      concerns_total: concerns.length,
      topics_total: topics.length,
      parties_total: parties.length,
      positions_total: positions.length,
      concern_rank: concernRank,
      recommended,
      fallback_used: Boolean(fallbackUsed),
      reason: String(reason || "ranked"),
    };
  }

  return {
    computeFirstAnswerPlan,
  };
});
