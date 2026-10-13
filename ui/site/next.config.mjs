import { execFileSync } from "node:child_process";
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

// Content-derived build id: rebuilding unchanged site sources yields identical files, so the R2
// sync uploads nothing. Next's random default rewrote ~14.5k HTML/RSC files on every publish,
// enough to threaten the R2 free tier of 1M writes/month. Falls back to Next's default without git.
function contentBuildId() {
  try {
    const git = (...args) => execFileSync("git", args, { encoding: "utf8", maxBuffer: 1 << 30 });
    const hash = createHash("sha256");
    hash.update(git("rev-parse", "HEAD:./"));
    hash.update(git("diff", "HEAD", "--binary", "--", "."));
    hash.update(git("ls-files", "--others", "--exclude-standard", "--", "."));
    hash.update(basePath);
    return `site-${hash.digest("hex").slice(0, 20)}`;
  } catch {
    return null;
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  generateBuildId: contentBuildId,
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
