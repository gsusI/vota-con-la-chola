import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

function normalizeBasePath(value) {
  const raw = String(value ?? "").trim();
  if (!raw || raw === "/") {
    return "";
  }
  const prefixed = raw.startsWith("/") ? raw : `/${raw}`;
  return prefixed.replace(/\/+$/u, "");
}

const basePath = normalizeBasePath(process.env.NEXT_PUBLIC_BASE_PATH ?? "");
const buildCpus = Number.parseInt(process.env.NEXT_BUILD_CPUS ?? "2", 10);
const safeBuildCpus = Number.isFinite(buildCpus) && buildCpus > 0 ? buildCpus : 2;

// The build id is embedded in ~15k of the ~16k published files, so it must not change with app code:
// a source-derived id made every one-line edit re-upload ~15k files (~4 min of wrangler upload).
// It changes only with the framework (lockfile, this config), where client/server skew matters;
// app edits change just the HTML that references the new webpack runtime (~1.7k files).
function frameworkBuildId() {
  const hash = createHash("sha256");
  for (const file of ["package-lock.json", "next.config.mjs"]) {
    hash.update(readFileSync(new URL(file, import.meta.url)));
  }
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
    cpus: safeBuildCpus,
    staticGenerationMaxConcurrency: safeBuildCpus,
  },
};

export default nextConfig;
