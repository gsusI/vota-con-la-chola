// Citizen preset codec utilities (v1), shared by UI and tests.
(function bootstrapPresetCodec(root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
    return;
  }
  root.CitizenPresetCodec = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function presetCodecFactory() {
  function resultOk(preset) {
    return { preset, error: "", error_code: "" };
  }

  function resultError(errorCode, message) {
    return {
      preset: null,
      error: String(message || ""),
      error_code: String(errorCode || ""),
    };
  }

  function uniqKeepOrder(ids) {
    const out = [];
    const seen = new Set();
    for (const x of ids || []) {
      const k = String(x || "").trim();
      if (!k || seen.has(k)) continue;
      seen.add(k);
      out.push(k);
    }
    return out;
  }

  function parseCsvIds(s) {
    const txt = String(s || "").trim();
    if (!txt) return [];
    return uniqKeepOrder(
      txt
        .split(",")
        .map((x) => String(x || "").trim())
        .filter((x) => x)
    );
  }

  function normalizeConcernPackId(v) {
    return String(v || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function readKnownConcernIds(opts) {
    if (!opts || !Array.isArray(opts.knownConcernIds)) return [];
    return uniqKeepOrder(opts.knownConcernIds).map((x) => String(x || "").trim()).filter((x) => x);
  }

  function readMaxConcerns(opts) {
    const raw = Number(opts && opts.maxConcerns);
    if (!Number.isFinite(raw) || raw <= 0) return 6;
    return Math.floor(raw);
  }

  function normalizeSelectedConcernIds(ids, opts) {
    const raw = uniqKeepOrder(ids || []).slice(0, readMaxConcerns(opts));
    const known = new Set(readKnownConcernIds(opts));
    if (!known.size) return raw;
    return raw.filter((cid) => known.has(String(cid)));
  }

  function encodePresetPayload(opts, cfg) {
    const o = opts || {};
    const p = new URLSearchParams();
    p.set("view", "alignment");
    const method = String(o.method || "").trim();
    if (method === "votes" || method === "declared" || method === "combined") p.set("method", method);
    const pack = normalizeConcernPackId(o.pack_id || "");
    if (pack) p.set("pack", pack);
    const concerns = normalizeSelectedConcernIds(Array.isArray(o.concerns_ids) ? o.concerns_ids : [], cfg);
    if (concerns.length) p.set("concerns", concerns.join(","));
    const concern = String(o.concern_id || "").trim();
    if (concern) p.set("concern", concern);
    return p.toString();
  }

  function decodePresetPayload(payload, cfg) {
    const txt = String(payload || "").trim();
    if (!txt) return null;
    const p = new URLSearchParams(txt);
    const out = {};
    const view = String(p.get("view") || "").trim();
    if (view === "alignment" || view === "dashboard" || view === "detail" || view === "coherence") out.view = view;
    const method = String(p.get("method") || "").trim();
    if (method === "combined" || method === "votes" || method === "declared") out.method = method;
    const pack = normalizeConcernPackId(p.get("pack") || "");
    if (pack) out.concern_pack = pack;
    const concerns = normalizeSelectedConcernIds(parseCsvIds(String(p.get("concerns") || "")), cfg);
    if (concerns.length) out.concerns_ids = concerns;
    const concern = String(p.get("concern") || "").trim();
    if (concern) out.concern = concern;
    return out;
  }

  function decodePayloadWithRecovery(raw) {
    let cur = String(raw || "");
    for (let i = 0; i < 3; i += 1) {
      let next = "";
      try {
        next = decodeURIComponent(cur);
      } catch (err) {
        if (i === 0) throw err;
        break;
      }
      if (next === cur) break;
      cur = next;
    }
    return cur;
  }

  function parseVersionAndPayload(decoded) {
    const txt = String(decoded || "").trim();
    if (!txt) return { version: "", payload: "", recovery: "" };

    const m = txt.match(/^v([0-9]+)\s*:([\s\S]*)$/i);
    if (m) {
      return {
        version: `v${String(m[1] || "").trim()}`,
        payload: String(m[2] || ""),
        recovery: "",
      };
    }

    // Legacy recovery: hash with payload but without explicit version prefix.
    if (/^(view|method|pack|concerns|concern)\s*=/i.test(txt)) {
      return { version: "v1", payload: txt, recovery: "legacy_no_version" };
    }
    return { version: "", payload: "", recovery: "" };
  }

  function readPresetFromHash(hash, cfg) {
    const h = String(hash || "");
    if (!h || h.length < 2) return resultOk(null);
    if (!/^#preset=/i.test(h)) return resultOk(null);

    const raw = h.slice(h.indexOf("=") + 1);
    let decoded = "";
    try {
      decoded = decodePayloadWithRecovery(raw);
    } catch (err) {
      return resultError("decode_error", String((err && err.message) || err || "preset hash invalido"));
    }

    const parsed = parseVersionAndPayload(decoded);
    if (!parsed.version) return resultError("unsupported_version", "preset hash version no soportada");
    if (parsed.version !== "v1") return resultError("unsupported_version", "preset hash version no soportada");
    if (!String(parsed.payload || "").trim()) return resultError("empty_payload", "preset hash vacio");

    const preset = decodePresetPayload(parsed.payload, cfg);
    if (!preset) return resultError("empty_payload", "preset hash vacio");

    if (typeof preset !== "object" || Array.isArray(preset) || !Object.keys(preset).length) {
      return resultError("no_supported_fields", "preset hash sin campos validos");
    }
    const cp = new URLSearchParams();
    const canonicalView = String(preset.view || "").trim();
    if (canonicalView === "alignment" || canonicalView === "dashboard" || canonicalView === "detail" || canonicalView === "coherence") {
      cp.set("view", canonicalView);
    } else {
      cp.set("view", "alignment");
    }
    const canonicalMethod = String(preset.method || "").trim();
    if (canonicalMethod === "votes" || canonicalMethod === "declared" || canonicalMethod === "combined") cp.set("method", canonicalMethod);
    const canonicalPack = normalizeConcernPackId(preset.concern_pack || "");
    if (canonicalPack) cp.set("pack", canonicalPack);
    const canonicalConcerns = normalizeSelectedConcernIds(Array.isArray(preset.concerns_ids) ? preset.concerns_ids : [], cfg);
    if (canonicalConcerns.length) cp.set("concerns", canonicalConcerns.join(","));
    const canonicalConcern = String(preset.concern || "").trim();
    if (canonicalConcern) cp.set("concern", canonicalConcern);
    const canonicalPayload = cp.toString();
    const canonicalHash = `#preset=${encodeURIComponent(`v1:${canonicalPayload}`)}`;
    const out = resultOk(preset);
    out.canonical_hash = canonicalHash;
    out.recovered_from = String(parsed.recovery || "");
    return out;
  }

  function buildAlignmentPresetShareUrl(opts, href, origin, cfg) {
    const base = new URL(String(href || ""), String(origin || undefined));
    base.search = "";
    const payload = encodePresetPayload(opts, cfg);
    base.hash = `#preset=${encodeURIComponent(`v1:${payload}`)}`;
    return base.toString();
  }

  return {
    parseCsvIds,
    normalizeConcernPackId,
    normalizeSelectedConcernIds,
    encodePresetPayload,
    decodePresetPayload,
    readPresetFromHash,
    buildAlignmentPresetShareUrl,
  };
});
