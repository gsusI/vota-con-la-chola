// Origin: the published site lives in the R2 bucket bound as SITE under SITE_PREFIX.
// Workers Static Assets (shell + hashed _next assets) are matched before this script runs.
const SITE_PREFIX = "site/";
const ORIGIN_PREFIX = "/vota-con-la-chola";
// Mutable paths: browsers show the cached copy instantly and revalidate by ETag in the background.
const SHORT_CACHE = "public, max-age=300, stale-while-revalidate=86400";
const IMMUTABLE_CACHE = "public, max-age=31536000, immutable";
// Content-addressed release directories (sha256 path segment) never change once published.
const IMMUTABLE_SEGMENT = /\/[0-9a-f]{64}\//;
const SECURITY_HEADERS = {
  "x-content-type-options": "nosniff",
  "referrer-policy": "strict-origin-when-cross-origin",
};

function normalizePathname(pathname) {
  if (pathname === ORIGIN_PREFIX) {
    return "/";
  }
  if (pathname.startsWith(`${ORIGIN_PREFIX}/`)) {
    return pathname.slice(ORIGIN_PREFIX.length) || "/";
  }
  return pathname || "/";
}

function canonicalizeTrailingSlash(pathname) {
  if (!pathname || pathname === "/" || pathname.endsWith("/")) {
    return pathname || "/";
  }
  const lastSegment = pathname.split("/").pop() || "";
  if (lastSegment.includes(".")) {
    return pathname;
  }
  return `${pathname}/`;
}

export function objectKeyForPath(pathname) {
  const sitePath = pathname.endsWith("/") ? `${pathname}index.html` : pathname;
  const decoded = decodeURIComponent(sitePath).replace(/^\/+/, "");
  if (decoded.split("/").some((segment) => segment === ".." || segment === ".")) {
    throw new URIError("dot segment");
  }
  return `${SITE_PREFIX}${decoded}`;
}

function cacheControlFor(pathname) {
  return IMMUTABLE_SEGMENT.test(pathname) ? IMMUTABLE_CACHE : SHORT_CACHE;
}

function baseHeaders() {
  return new Headers(SECURITY_HEADERS);
}

function plainResponse(status, body, extra = {}) {
  const headers = baseHeaders();
  headers.set("content-type", "text/plain; charset=utf-8");
  headers.set("cache-control", "no-store");
  for (const [name, value] of Object.entries(extra)) headers.set(name, value);
  return new Response(body, { status, headers });
}

function contentRange(range, size) {
  if (!range) return null;
  // R2 may include unset keys (e.g. suffix: undefined), so check types, not key presence.
  if (typeof range.suffix === "number") {
    const start = Math.max(size - range.suffix, 0);
    return { start, end: size - 1 };
  }
  const start = typeof range.offset === "number" ? range.offset : 0;
  const length = typeof range.length === "number" ? range.length : size - start;
  return { start, end: Math.min(start + length, size) - 1 };
}

async function notFound(env, method) {
  const page = await env.SITE.get(`${SITE_PREFIX}404.html`);
  if (!page) {
    return plainResponse(404, method === "HEAD" ? null : "404: Not Found");
  }
  const headers = baseHeaders();
  headers.set("content-type", "text/html; charset=utf-8");
  headers.set("cache-control", "no-store");
  return new Response(method === "HEAD" ? null : page.body, { status: 404, headers });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return plainResponse(405, "Method Not Allowed", { allow: "GET, HEAD" });
    }

    const requestUrl = new URL(request.url);
    const normalizedPath = canonicalizeTrailingSlash(normalizePathname(requestUrl.pathname));
    if (requestUrl.pathname !== normalizedPath) {
      return Response.redirect(`${requestUrl.origin}${normalizedPath}${requestUrl.search}`, 308);
    }

    if (!env || !env.SITE) {
      return plainResponse(503, "Site origin unavailable");
    }

    let key;
    try {
      key = objectKeyForPath(normalizedPath);
    } catch {
      return plainResponse(400, "Bad Request");
    }

    const hasRange = request.headers.has("range");
    const edgeCache = typeof caches !== "undefined" ? caches.default : null;
    const cacheable = request.method === "GET" && !hasRange && edgeCache;
    const cacheKey = new Request(`${requestUrl.origin}${normalizedPath}`, { method: "GET" });
    if (cacheable) {
      const cached = await edgeCache.match(cacheKey);
      if (cached) return cached;
    }

    const object =
      request.method === "HEAD"
        ? await env.SITE.head(key)
        : await env.SITE.get(key, { range: request.headers, onlyIf: request.headers });
    if (!object) {
      return notFound(env, request.method);
    }

    const headers = baseHeaders();
    object.writeHttpMetadata(headers);
    headers.set("content-type", resolveContentType(key, headers.get("content-type")));
    headers.set("cache-control", cacheControlFor(normalizedPath));
    headers.set("etag", object.httpEtag);
    headers.set("accept-ranges", "bytes");
    headers.set("x-vclc-origin", "r2");

    if (request.method === "HEAD") {
      headers.set("content-length", String(object.size));
      return new Response(null, { status: 200, headers });
    }

    // R2 returns metadata without a body when an onlyIf precondition fails.
    if (!("body" in object)) {
      const conditional = request.headers.has("if-none-match") || request.headers.has("if-modified-since");
      return new Response(null, { status: conditional ? 304 : 412, headers });
    }

    if (hasRange && object.range) {
      const { start, end } = contentRange(object.range, object.size);
      headers.set("content-range", `bytes ${start}-${end}/${object.size}`);
      return new Response(object.body, { status: 206, headers });
    }

    const response = new Response(object.body, { status: 200, headers });
    if (cacheable && ctx && typeof ctx.waitUntil === "function") {
      // Edge copies never serve stale: a publish is visible everywhere within max-age.
      const edgeCopy = response.clone();
      const edgeHeaders = new Headers(edgeCopy.headers);
      edgeHeaders.set("cache-control", edgeHeaders.get("cache-control").replace(/, stale-while-revalidate=\d+/, ""));
      ctx.waitUntil(edgeCache.put(cacheKey, new Response(edgeCopy.body, { status: 200, headers: edgeHeaders })));
    }
    return response;
  },
};

export function resolveContentType(pathname, fallback) {
  const lower = String(pathname || "").toLowerCase();
  if (lower.endsWith(".html")) return "text/html; charset=utf-8";
  if (lower.endsWith(".css")) return "text/css; charset=utf-8";
  if (lower.endsWith(".js") || lower.endsWith(".mjs")) return "application/javascript; charset=utf-8";
  if (lower.endsWith(".json")) return "application/json; charset=utf-8";
  if (lower.endsWith(".svg")) return "image/svg+xml";
  if (lower.endsWith(".xml")) return "application/xml; charset=utf-8";
  if (lower.endsWith(".txt")) return "text/plain; charset=utf-8";
  if (lower.endsWith(".csv")) return "text/csv; charset=utf-8";
  if (lower.endsWith(".ico")) return "image/x-icon";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".woff2")) return "font/woff2";
  if (lower.endsWith(".woff")) return "font/woff";
  if (lower.endsWith(".wasm")) return "application/wasm";
  return fallback || "application/octet-stream";
}
