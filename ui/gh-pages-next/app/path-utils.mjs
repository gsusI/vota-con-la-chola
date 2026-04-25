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
