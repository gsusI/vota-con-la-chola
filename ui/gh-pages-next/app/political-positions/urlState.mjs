function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function normalizePoliticalPositionsSearchMode(value) {
  const normalized = String(value || "auto").trim().toLowerCase();
  if (normalized === "topic" || normalized === "person") {
    return normalized;
  }
  return "auto";
}

export function defaultPoliticalPositionsState() {
  return {
    mode: "person",
    q: "",
    pack: "",
    concern: "",
    originPack: "",
    originConcern: "",
    originTopicId: 0,
    searchMode: "auto",
    person: "",
    method: "all",
    stance: "all",
    topic: "",
    topicId: 0,
    party: "",
    sort: "person",
    limit: 180,
  };
}

export function readPoliticalPositionsUrlState(search = "") {
  const base = defaultPoliticalPositionsState();
  const params = new URLSearchParams(String(search || ""));
  const limit = Number(params.get("limit") || base.limit);

  return {
    mode: String(params.get("mode") || base.mode),
    q: String(params.get("q") || base.q),
    pack: String(params.get("pack") || base.pack),
    concern: String(params.get("concern") || base.concern),
    originPack: String(params.get("origin_pack") || base.originPack),
    originConcern: String(params.get("origin_concern") || base.originConcern),
    originTopicId: toInt(params.get("origin_topic_id") || 0),
    searchMode: normalizePoliticalPositionsSearchMode(params.get("search_mode") || base.searchMode),
    person: String(params.get("person") || base.person),
    method: String(params.get("method") || base.method),
    stance: String(params.get("stance") || base.stance),
    topic: String(params.get("topic") || base.topic),
    topicId: toInt(params.get("topic_id") || 0),
    party: String(params.get("party") || base.party),
    sort: String(params.get("sort") || base.sort),
    limit: Number.isFinite(limit) ? limit : base.limit,
  };
}

export function buildPoliticalPositionsUrlSearch(state) {
  const params = new URLSearchParams();
  if (state?.mode && state.mode !== "person") params.set("mode", state.mode);
  if (state?.q) params.set("q", state.q);
  if (state?.pack) params.set("pack", state.pack);
  if (state?.concern) params.set("concern", state.concern);
  if (state?.originPack) params.set("origin_pack", state.originPack);
  if (state?.originConcern) params.set("origin_concern", state.originConcern);
  if (toInt(state?.originTopicId || 0) > 0) params.set("origin_topic_id", String(toInt(state.originTopicId)));
  if (normalizePoliticalPositionsSearchMode(state?.searchMode) !== "auto") {
    params.set("search_mode", normalizePoliticalPositionsSearchMode(state?.searchMode));
  }
  if (state?.person) params.set("person", state.person);
  if (state?.method && state.method !== "all") params.set("method", state.method);
  if (state?.stance && state.stance !== "all") params.set("stance", state.stance);
  if (state?.topic) params.set("topic", state.topic);
  if (toInt(state?.topicId || 0) > 0) params.set("topic_id", String(toInt(state.topicId)));
  if (state?.party) params.set("party", state.party);
  if (state?.sort && state.sort !== "person") params.set("sort", state.sort);
  if (toInt(state?.limit || 0) > 0 && toInt(state.limit) !== 180) params.set("limit", String(toInt(state.limit)));
  return params.toString();
}

export function restorePoliticalPositionsDiscoveryState(state) {
  const next = {
    ...defaultPoliticalPositionsState(),
    ...(state || {}),
  };
  const originPack = String(next.originPack || "").trim();
  const originConcern = String(next.originConcern || "").trim();
  if (!originPack && !originConcern) {
    return next;
  }

  next.mode = "person";
  next.q = "";
  next.searchMode = "auto";
  next.pack = originPack;
  next.concern = originConcern;
  next.topic = "";
  next.topicId = 0;
  next.originPack = "";
  next.originConcern = "";
  return next;
}
