// Public origin of the live site (served from R2). Override with NEXT_PUBLIC_SITE_ORIGIN for previews.
export const SITE_ORIGIN = (process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://votaconlachola.org").replace(/\/+$/u, "");

export function normalizeBasePath(value) {
  const raw = String(value ?? "").trim();
  if (!raw || raw === "/") {
    return "";
  }
  const prefixed = raw.startsWith("/") ? raw : `/${raw}`;
  return prefixed.replace(/\/+$/u, "");
}

export function resolveBasePath() {
  return normalizeBasePath(process.env.NEXT_PUBLIC_BASE_PATH ?? "");
}

export function stripBasePath(pathname, basePath = resolveBasePath()) {
  const path = String(pathname || "") || "/";
  const normalizedBasePath = normalizeBasePath(basePath);
  if (!normalizedBasePath) {
    return path;
  }
  if (path === normalizedBasePath) {
    return "/";
  }
  if (path.startsWith(`${normalizedBasePath}/`)) {
    return path.slice(normalizedBasePath.length) || "/";
  }
  return path;
}

export function withBasePath(pathname, basePath = resolveBasePath()) {
  if (!pathname) {
    return "";
  }
  const path = String(pathname);
  if (/^[a-z][a-z\d+.-]*:/iu.test(path) || path.startsWith("#")) {
    return path;
  }
  const normalizedBasePath = normalizeBasePath(basePath);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!normalizedBasePath) {
    return normalizedPath;
  }
  if (
    normalizedPath === normalizedBasePath ||
    normalizedPath.startsWith(`${normalizedBasePath}/`) ||
    normalizedPath.startsWith(`${normalizedBasePath}?`) ||
    normalizedPath.startsWith(`${normalizedBasePath}#`)
  ) {
    return normalizedPath;
  }
  return `${normalizedBasePath}${normalizedPath}`;
}

// Absolute public URL for a site path (canonical/og:url/og:image need absolute URLs).
export function absoluteSiteUrl(pathname, basePath = resolveBasePath()) {
  return `${SITE_ORIGIN}${withBasePath(pathname, basePath)}`;
}

// Generic 1200x630 PNG share card rendered by app/og/[file]/route.js; SVG favicons are not rendered by WhatsApp/X/Telegram.
export const SITE_CARD_IMAGE = { width: 1200, height: 630, alt: "Vota Con La Chola" };

export function siteCardImage(basePath = resolveBasePath()) {
  return { url: absoluteSiteUrl("/og/site.png", basePath), ...SITE_CARD_IMAGE };
}
