const RAW_ORIGIN = "https://raw.githubusercontent.com/gsusI/vota-con-la-chola/gh-pages";
const ORIGIN_PREFIX = "/vota-con-la-chola";

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

export default {
  async fetch(request) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const requestUrl = new URL(request.url);
    const normalizedPath = canonicalizeTrailingSlash(normalizePathname(requestUrl.pathname));
    if (requestUrl.pathname !== normalizedPath) {
      return Response.redirect(`${requestUrl.origin}${normalizedPath}${requestUrl.search}`, 308);
    }

    const isDirectoryPath = normalizedPath.endsWith("/");
    const upstreamPath = isDirectoryPath ? `${normalizedPath}index.html` : normalizedPath;
    const upstreamUrl = new URL(`${RAW_ORIGIN}${upstreamPath}`);

    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      redirect: "follow",
    });

    const headers = new Headers(upstreamResponse.headers);
    headers.set("cache-control", "public, max-age=300");
    headers.set("x-vclc-origin", upstreamUrl.toString());
    headers.delete("content-security-policy");
    headers.delete("content-security-policy-report-only");
    headers.delete("x-frame-options");

    const contentType = resolveContentType(upstreamUrl.pathname, upstreamResponse.headers.get("content-type"));
    if (contentType) {
      headers.set("content-type", contentType);
    }

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers,
    });
  },
};

function resolveContentType(pathname, fallback) {
  const lower = String(pathname || "").toLowerCase();
  if (lower.endsWith(".html")) return "text/html; charset=utf-8";
  if (lower.endsWith(".css")) return "text/css; charset=utf-8";
  if (lower.endsWith(".js")) return "application/javascript; charset=utf-8";
  if (lower.endsWith(".json")) return "application/json; charset=utf-8";
  if (lower.endsWith(".svg")) return "image/svg+xml";
  if (lower.endsWith(".xml")) return "application/xml; charset=utf-8";
  if (lower.endsWith(".txt")) return "text/plain; charset=utf-8";
  if (lower.endsWith(".ico")) return "image/x-icon";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".woff2")) return "font/woff2";
  if (lower.endsWith(".woff")) return "font/woff";
  return fallback || "application/octet-stream";
}
