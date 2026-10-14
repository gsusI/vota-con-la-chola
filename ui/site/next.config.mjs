import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { availableParallelism } from "node:os";

function normalizeBasePath(value) {
  const raw = String(value ?? "").trim();
  if (!raw || raw === "/") {
    return "";
  }
  const prefixed = raw.startsWith("/") ? raw : `/${raw}`;
  return prefixed.replace(/\/+$/u, "");
}

const basePath = normalizeBasePath(process.env.NEXT_PUBLIC_BASE_PATH ?? "");
// Page rendering scales with workers (1.5k pages: ~29 s on 2, ~9 s on 8); CI pins NEXT_BUILD_CPUS.
const defaultBuildCpus = Math.min(8, Math.max(2, availableParallelism() - 2));
const buildCpus = Number.parseInt(process.env.NEXT_BUILD_CPUS ?? String(defaultBuildCpus), 10);
const safeBuildCpus = Number.isFinite(buildCpus) && buildCpus > 0 ? buildCpus : 2;

// The build id is embedded in ~15k of the ~16k published files, so it must not change with app code:
// a source-derived id made every one-line edit re-upload ~15k files (~4 min of wrangler upload).
// It changes only with the framework (the lockfile), where client/server skew matters;
// app edits change just the HTML that references the new webpack runtime (~1.7k files).
function frameworkBuildId() {
  const hash = createHash("sha256");
  hash.update(readFileSync(new URL("package-lock.json", import.meta.url)));
  hash.update(basePath);
  return `site-${hash.digest("hex").slice(0, 20)}`;
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  generateBuildId: frameworkBuildId,
  trailingSlash: true,
  basePath,
  assetPrefix: basePath || undefined,
  images: {
    unoptimized: true,
  },
  experimental: {
    // CSS ships inside each page's HTML: no render-blocking stylesheet requests, so the first paint lands before
    // the JS chunks finish (Lighthouse counts every request done before LCP as blocking it: LCP 5 s on mobile).
    inlineCss: true,
    cpus: safeBuildCpus,
    staticGenerationMaxConcurrency: safeBuildCpus,
  },
};

export default nextConfig;
